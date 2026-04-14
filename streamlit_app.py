import streamlit as st
import requests
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Set
import json
from datetime import datetime

# Page config
st.set_page_config(
    page_title="ComplyScore - Compliance Analysis Engine",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(120deg, #2E3192 0%, #1BFFFF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .score-card {
        padding: 1.5rem;
        border-radius: 10px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        text-align: center;
        margin: 1rem 0;
    }
    .score-number {
        font-size: 3rem;
        font-weight: 700;
    }
    .regulator-badge {
        display: inline-block;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        background: #f0f2f6;
        margin: 0.25rem;
    }
    .finding-card {
        padding: 1rem;
        border-left: 4px solid #667eea;
        background: #f8f9fa;
        margin: 0.5rem 0;
        border-radius: 4px;
    }
    .critical { border-left-color: #dc3545; }
    .warning { border-left-color: #ffc107; }
    .info { border-left-color: #17a2b8; }
    .success { border-left-color: #28a745; }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None

class ComplianceCrawler:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.visited_urls = set()
        self.pdf_urls = set()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
    def extract_pdf_links_from_page(self, url: str) -> Set[str]:
        """Extract all PDF links from a single page - IMPROVED VERSION"""
        pdf_links = set()
        
        try:
            response = requests.get(url, headers=self.headers, timeout=15, allow_redirects=True)
            if response.status_code != 200:
                return pdf_links
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Method 1: Find all <a> tags with href
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                # Convert relative URLs to absolute
                full_url = urljoin(url, href)
                
                # Check if it's a PDF (multiple patterns)
                if (full_url.lower().endswith('.pdf') or 
                    '.pdf?' in full_url.lower() or
                    'pdf' in full_url.lower() and '.' in full_url.split('/')[-1]):
                    pdf_links.add(full_url)
            
            # Method 2: Find iframe sources (PDFs embedded)
            for iframe in soup.find_all('iframe', src=True):
                src = urljoin(url, iframe['src'])
                if '.pdf' in src.lower():
                    pdf_links.add(src)
            
            # Method 3: Find object/embed tags
            for obj in soup.find_all(['object', 'embed'], {'data': True}):
                data = urljoin(url, obj['data'])
                if '.pdf' in data.lower():
                    pdf_links.add(data)
            
            for obj in soup.find_all(['object', 'embed'], {'src': True}):
                src = urljoin(url, obj['src'])
                if '.pdf' in src.lower():
                    pdf_links.add(src)
            
            # Method 4: Look for download buttons/links with data attributes
            for elem in soup.find_all(attrs={'data-href': True}):
                data_href = urljoin(url, elem['data-href'])
                if '.pdf' in data_href.lower():
                    pdf_links.add(data_href)
            
            for elem in soup.find_all(attrs={'data-url': True}):
                data_url = urljoin(url, elem['data-url'])
                if '.pdf' in data_url.lower():
                    pdf_links.add(data_url)
            
            # Method 5: Regex search in page content for PDF URLs
            pdf_pattern = r'https?://[^\s<>"\']+\.pdf(?:\?[^\s<>"\']*)?'
            pdf_matches = re.findall(pdf_pattern, response.text, re.IGNORECASE)
            for match in pdf_matches:
                pdf_links.add(match)
            
            # Method 6: Look in onclick attributes
            for elem in soup.find_all(attrs={'onclick': True}):
                onclick = elem['onclick']
                # Extract URLs from onclick
                url_matches = re.findall(r'["\']([^"\']+\.pdf[^"\']*)["\']', onclick, re.IGNORECASE)
                for match in url_matches:
                    full_url = urljoin(url, match)
                    pdf_links.add(full_url)
                    
        except Exception as e:
            st.warning(f"Error crawling {url}: {str(e)}")
        
        return pdf_links
    
    def fetch_sitemap(self) -> List[str]:
        """Try to fetch sitemap.xml"""
        sitemap_urls = [
            urljoin(self.base_url, '/sitemap.xml'),
            urljoin(self.base_url, '/sitemap_index.xml'),
            urljoin(self.base_url, '/robots.txt')
        ]
        
        urls = []
        for sitemap_url in sitemap_urls:
            try:
                response = requests.get(sitemap_url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    if 'sitemap.xml' in sitemap_url or 'sitemap_index.xml' in sitemap_url:
                        root = ET.fromstring(response.content)
                        # Handle both regular sitemap and sitemap index
                        for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                            urls.append(url_elem.text)
                    elif 'robots.txt' in sitemap_url:
                        # Parse robots.txt for sitemap references
                        for line in response.text.split('\n'):
                            if line.lower().startswith('sitemap:'):
                                sitemap = line.split(':', 1)[1].strip()
                                urls.extend(self.fetch_sitemap_from_url(sitemap))
                    if urls:
                        return urls
            except Exception as e:
                continue
        return urls
    
    def fetch_sitemap_from_url(self, url: str) -> List[str]:
        """Fetch URLs from a specific sitemap URL"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                return [elem.text for elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        except:
            pass
        return []
    
    def discover_common_paths(self) -> List[str]:
        """Check common paths where PDFs might be stored"""
        common_paths = [
            '/downloads',
            '/documents',
            '/forms',
            '/pdfs',
            '/resources',
            '/download-forms',
            '/customer-service',
            '/compliance',
            '/regulatory',
            '/download',
            '/files',
            '/media',
            '/assets/pdf',
            '/assets/documents'
        ]
        
        urls = [self.base_url]
        
        for path in common_paths:
            test_url = urljoin(self.base_url, path)
            urls.append(test_url)
            
            # Also try with common extensions
            urls.append(test_url + '.html')
            urls.append(test_url + '/index.html')
        
        return urls
    
    def crawl_for_pdfs(self, custom_path: str = None, max_pages: int = 50) -> List[str]:
        """IMPROVED: Crawl website for PDF documents with better detection"""
        urls_to_visit = []
        
        # Strategy 1: Try sitemap
        sitemap_urls = self.fetch_sitemap()
        if sitemap_urls:
            urls_to_visit.extend(sitemap_urls[:max_pages])
        
        # Strategy 2: Add custom path if provided
        if custom_path:
            custom_url = urljoin(self.base_url, custom_path)
            urls_to_visit.insert(0, custom_url)
        
        # Strategy 3: Add common paths
        urls_to_visit.extend(self.discover_common_paths())
        
        # Strategy 4: Always include base URL
        if self.base_url not in urls_to_visit:
            urls_to_visit.insert(0, self.base_url)
        
        # Remove duplicates while preserving order
        seen = set()
        urls_to_visit = [x for x in urls_to_visit if not (x in seen or seen.add(x))]
        
        st.info(f"🔍 Scanning {min(len(urls_to_visit), max_pages)} pages for PDFs...")
        
        progress_container = st.empty()
        
        # Crawl pages
        for idx, url in enumerate(urls_to_visit[:max_pages]):
            if url in self.visited_urls:
                continue
            
            progress_container.text(f"Scanning page {idx + 1}/{min(len(urls_to_visit), max_pages)}: {url[:60]}...")
            
            self.visited_urls.add(url)
            
            # If URL itself is a PDF
            if url.lower().endswith('.pdf'):
                self.pdf_urls.add(url)
                continue
            
            # Extract PDF links from this page
            page_pdfs = self.extract_pdf_links_from_page(url)
            self.pdf_urls.update(page_pdfs)
            
            # If we found PDFs, also crawl linked pages (breadth-first)
            if page_pdfs and len(self.visited_urls) < max_pages:
                try:
                    response = requests.get(url, headers=self.headers, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Find pages that might have more PDFs
                        for link in soup.find_all('a', href=True):
                            href = link['href']
                            full_url = urljoin(url, href)
                            
                            # Only follow same-domain links
                            if (urlparse(full_url).netloc == self.domain and 
                                full_url not in self.visited_urls and
                                len(urls_to_visit) < max_pages * 2):
                                
                                # Prioritize links with keywords
                                link_text = link.get_text().lower()
                                keywords = ['download', 'form', 'document', 'pdf', 'file', 'compliance', 'regulatory']
                                
                                if any(kw in full_url.lower() or kw in link_text for kw in keywords):
                                    urls_to_visit.append(full_url)
                except:
                    pass
        
        progress_container.empty()
        
        # Filter out invalid URLs
        valid_pdfs = []
        for pdf_url in self.pdf_urls:
            # Basic validation
            if pdf_url.startswith('http') and len(pdf_url) > 10:
                valid_pdfs.append(pdf_url)
        
        return valid_pdfs

class ComplianceAnalyzer:
    def __init__(self, cloudflare_account_id: str, cloudflare_auth_token: str, 
                 supabase_api_key: str, pdf_extractor_url: str):
        self.cloudflare_account_id = cloudflare_account_id
        self.cloudflare_auth_token = cloudflare_auth_token
        self.supabase_api_key = supabase_api_key
        self.pdf_extractor_url = pdf_extractor_url
        
    def get_regulatory_context(self, source: str, limit: int = 20) -> List[Dict]:
        """Fetch recent circulars from regulatory body"""
        url = f"https://lbtoopahmulfgffzjumy.supabase.co/functions/v1/lens-api/circulars?source={source.lower()}&limit={limit}"
        headers = {"x-api-key": self.supabase_api_key}
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            st.error(f"Error fetching regulatory context: {str(e)}")
        return []
    
    def extract_pdf_content(self, pdf_url: str) -> str:
        """Extract text from PDF URL"""
        try:
            response = requests.post(
                self.pdf_extractor_url,
                json={"url": pdf_url},
                timeout=60
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('text', '')
        except Exception as e:
            st.warning(f"Could not extract PDF {pdf_url}: {str(e)}")
        return ""
    
    def analyze_with_ai(self, document_content: str, regulatory_context: List[Dict], 
                       regulator: str) -> Dict:
        """Analyze document against regulatory requirements using AI"""
        # Prepare regulatory context summary
        context_summary = "\n".join([
            f"- {circ.get('title', 'N/A')} (Date: {circ.get('date', 'N/A')})"
            for circ in regulatory_context[:10]
        ])
        
        system_prompt = f"""You are a compliance analyst expert specializing in {regulator} regulations.

Recent {regulator} Circulars and Guidelines:
{context_summary}

Analyze the provided document for compliance with {regulator} regulations. Provide:
1. Overall Compliance Score (0-100)
2. Key Findings (Critical, Warning, Info levels)
3. Specific regulatory gaps or violations
4. Recommendations for improvement

Format your response as JSON with this structure:
{{
    "score": <number 0-100>,
    "summary": "<brief summary>",
    "findings": [
        {{"level": "critical|warning|info|success", "title": "<title>", "description": "<description>", "regulation": "<relevant regulation>"}}
    ],
    "recommendations": ["<recommendation 1>", "<recommendation 2>"]
}}"""

        user_prompt = f"Analyze this compliance document:\n\n{document_content[:8000]}"
        
        url = f"https://api.cloudflare.com/client/v4/accounts/{self.cloudflare_account_id}/ai/run/@cf/google/gemma-4-26b-a4b-it"
        headers = {
            "Authorization": f"Bearer {self.cloudflare_auth_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get('result', {}).get('response', '')
                
                # Try to parse JSON from response
                try:
                    # Extract JSON if wrapped in markdown
                    json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                except:
                    pass
                
                # Fallback to text response
                return {
                    "score": 70,
                    "summary": ai_response[:500],
                    "findings": [],
                    "recommendations": []
                }
        except Exception as e:
            st.error(f"AI analysis error: {str(e)}")
        
        return {
            "score": 0,
            "summary": "Analysis failed",
            "findings": [],
            "recommendations": []
        }

# Main App
st.markdown('<h1 class="main-header">🔍 ComplyScore</h1>', unsafe_allow_html=True)
st.markdown("**Automated Compliance Analysis Engine**")

# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    website_url = st.text_input(
        "Website URL",
        placeholder="https://example.com",
        help="Enter the website to analyze"
    )
    
    st.subheader("📁 Document Discovery")
    use_custom_path = st.checkbox("Use custom document path")
    custom_path = ""
    if use_custom_path:
        custom_path = st.text_input(
            "Custom Path",
            placeholder="/compliance/documents",
            help="Specific path where compliance documents are stored"
        )
    
    max_pages = st.slider("Max pages to crawl", 10, 200, 100)
    
    st.subheader("🏛️ Regulatory Body")
    regulator = st.selectbox(
        "Select Regulator",
        ["SEBI", "RBI", "FCA"],
        help="Choose the regulatory body for compliance analysis"
    )
    
    # Map regulator to source code
    regulator_map = {
        "SEBI": "sebi",
        "RBI": "rbi",
        "FCA": "fca"
    }
    
    st.divider()
    
    analyze_button = st.button("🚀 Start Analysis", type="primary", use_container_width=True)

# Main Content Area
if not analyze_button and not st.session_state.analysis_complete:
    # Welcome screen
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("**1. Enter Website**\nProvide the URL to analyze")
    
    with col2:
        st.info("**2. Select Regulator**\nChoose applicable regulatory body")
    
    with col3:
        st.info("**3. Get Insights**\nReceive compliance score and recommendations")
    
    st.divider()
    
    st.subheader("Supported Regulators")
    cols = st.columns(3)
    regulators_info = [
        ("SEBI", "Securities and Exchange Board of India", "India"),
        ("RBI", "Reserve Bank of India", "India"),
        ("FCA", "Financial Conduct Authority", "UK")
    ]
    
    for col, (code, name, country) in zip(cols, regulators_info):
        with col:
            st.markdown(f"""
            <div class="regulator-badge">
                <strong>{code}</strong><br>
                <small>{name}</small><br>
                <small>📍 {country}</small>
            </div>
            """, unsafe_allow_html=True)

elif analyze_button:
    if not website_url:
        st.error("Please enter a website URL")
    else:
        # Get secrets
        try:
            cloudflare_account_id = st.secrets["CLOUDFLARE_ACCOUNT_ID"]
            cloudflare_auth_token = st.secrets["CLOUDFLARE_AUTH_TOKEN"]
            supabase_api_key = st.secrets["SUPABASE_API_KEY"]
            pdf_extractor_url = st.secrets.get("PDF_EXTRACTOR_URL", "http://72.61.251.247:3000/extract-pdf-url")
        except Exception as e:
            st.error(f"Missing required secrets: {str(e)}")
            st.stop()
        
        # Start analysis
        with st.spinner("🔍 Crawling website for compliance documents..."):
            crawler = ComplianceCrawler(website_url)
            pdf_urls = crawler.crawl_for_pdfs(custom_path, max_pages)
        
        st.success(f"✅ Found {len(pdf_urls)} PDF documents")
        
        if pdf_urls:
            # Show found documents
            with st.expander(f"📄 Found Documents ({len(pdf_urls)})"):
                for i, url in enumerate(pdf_urls[:50], 1):
                    st.text(f"{i}. {url}")
                if len(pdf_urls) > 50:
                    st.info(f"... and {len(pdf_urls) - 50} more")
            
            # Fetch regulatory context
            with st.spinner(f"📋 Fetching {regulator} regulatory context..."):
                analyzer = ComplianceAnalyzer(
                    cloudflare_account_id,
                    cloudflare_auth_token,
                    supabase_api_key,
                    pdf_extractor_url
                )
                regulatory_context = analyzer.get_regulatory_context(
                    regulator_map[regulator]
                )
            
            st.success(f"✅ Retrieved {len(regulatory_context)} recent {regulator} circulars")
            
            # Analyze documents
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            all_analyses = []
            
            for i, pdf_url in enumerate(pdf_urls[:5]):  # Analyze first 5 PDFs
                status_text.text(f"Analyzing document {i+1}/{min(5, len(pdf_urls))}...")
                progress_bar.progress((i + 1) / min(5, len(pdf_urls)))
                
                # Extract PDF content
                content = analyzer.extract_pdf_content(pdf_url)
                
                if content:
                    # Analyze with AI
                    analysis = analyzer.analyze_with_ai(
                        content,
                        regulatory_context,
                        regulator
                    )
                    analysis['url'] = pdf_url
                    all_analyses.append(analysis)
            
            progress_bar.empty()
            status_text.empty()
            
            # Calculate overall score
            if all_analyses:
                avg_score = sum(a.get('score', 0) for a in all_analyses) / len(all_analyses)
                
                st.session_state.analysis_results = {
                    'score': avg_score,
                    'regulator': regulator,
                    'analyses': all_analyses,
                    'pdf_count': len(pdf_urls),
                    'website': website_url
                }
                st.session_state.analysis_complete = True
                st.rerun()
        else:
            st.warning("No PDF documents found on the website. Try adjusting the custom path or crawl depth.")

# Display Results
if st.session_state.analysis_complete and st.session_state.analysis_results:
    results = st.session_state.analysis_results
    
    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"Analysis Results for {results['website']}")
        st.caption(f"Regulator: {results['regulator']} | Documents Analyzed: {len(results['analyses'])}/{results['pdf_count']}")
    
    with col2:
        if st.button("🔄 New Analysis"):
            st.session_state.analysis_complete = False
            st.session_state.analysis_results = None
            st.rerun()
    
    # Overall Score
    score = results['score']
    score_color = "#28a745" if score >= 80 else "#ffc107" if score >= 60 else "#dc3545"
    
    st.markdown(f"""
    <div class="score-card" style="background: linear-gradient(135deg, {score_color}dd 0%, {score_color}99 100%);">
        <div>Overall Compliance Score</div>
        <div class="score-number">{score:.0f}/100</div>
        <div>{'Excellent' if score >= 80 else 'Needs Improvement' if score >= 60 else 'Critical Issues'}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Document-wise Analysis
    st.subheader("📊 Detailed Analysis")
    
    for idx, analysis in enumerate(results['analyses'], 1):
        with st.expander(f"Document {idx} - Score: {analysis.get('score', 0)}/100"):
            st.caption(f"🔗 {analysis.get('url', 'N/A')}")
            
            st.markdown(f"**Summary:** {analysis.get('summary', 'No summary available')}")
            
            # Findings
            findings = analysis.get('findings', [])
            if findings:
                st.markdown("**Findings:**")
                for finding in findings:
                    level = finding.get('level', 'info')
                    st.markdown(f"""
                    <div class="finding-card {level}">
                        <strong>{finding.get('title', 'N/A')}</strong><br>
                        {finding.get('description', 'N/A')}<br>
                        <small><em>Regulation: {finding.get('regulation', 'N/A')}</em></small>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Recommendations
            recommendations = analysis.get('recommendations', [])
            if recommendations:
                st.markdown("**Recommendations:**")
                for rec in recommendations:
                    st.markdown(f"- {rec}")
    
    # Export option
    st.divider()
    if st.button("📥 Export Report (JSON)"):
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "website": results['website'],
            "regulator": results['regulator'],
            "overall_score": results['score'],
            "documents_analyzed": len(results['analyses']),
            "total_documents": results['pdf_count'],
            "analyses": results['analyses']
        }
        
        st.download_button(
            label="Download Report",
            data=json.dumps(report_data, indent=2),
            file_name=f"compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
