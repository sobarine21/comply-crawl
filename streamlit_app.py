import streamlit as st
import requests
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Set
import json
from datetime import datetime
import time

# Page config
st.set_page_config(
    page_title="ComplyScore - Compliance Analysis Engine",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS (same as before)
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
    .debug-section {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 4px;
        font-family: monospace;
        font-size: 0.85rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'show_debug' not in st.session_state:
    st.session_state.show_debug = False

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
                full_url = urljoin(url, href)
                
                if (full_url.lower().endswith('.pdf') or 
                    '.pdf?' in full_url.lower() or
                    'pdf' in full_url.lower() and '.' in full_url.split('/')[-1]):
                    pdf_links.add(full_url)
            
            # Method 2: Find iframe sources
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
            
            # Method 4: Data attributes
            for elem in soup.find_all(attrs={'data-href': True}):
                data_href = urljoin(url, elem['data-href'])
                if '.pdf' in data_href.lower():
                    pdf_links.add(data_href)
            
            for elem in soup.find_all(attrs={'data-url': True}):
                data_url = urljoin(url, elem['data-url'])
                if '.pdf' in data_url.lower():
                    pdf_links.add(data_url)
            
            # Method 5: Regex in content
            pdf_pattern = r'https?://[^\s<>"\']+\.pdf(?:\?[^\s<>"\']*)?'
            pdf_matches = re.findall(pdf_pattern, response.text, re.IGNORECASE)
            for match in pdf_matches:
                pdf_links.add(match)
            
            # Method 6: onclick attributes
            for elem in soup.find_all(attrs={'onclick': True}):
                onclick = elem['onclick']
                url_matches = re.findall(r'["\']([^"\']+\.pdf[^"\']*)["\']', onclick, re.IGNORECASE)
                for match in url_matches:
                    full_url = urljoin(url, match)
                    pdf_links.add(full_url)
                    
        except Exception as e:
            pass
        
        return pdf_links
    
    def fetch_sitemap(self) -> List[str]:
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
                        for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                            urls.append(url_elem.text)
                    elif 'robots.txt' in sitemap_url:
                        for line in response.text.split('\n'):
                            if line.lower().startswith('sitemap:'):
                                sitemap = line.split(':', 1)[1].strip()
                                urls.extend(self.fetch_sitemap_from_url(sitemap))
                    if urls:
                        return urls
            except:
                continue
        return urls
    
    def fetch_sitemap_from_url(self, url: str) -> List[str]:
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                return [elem.text for elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        except:
            pass
        return []
    
    def discover_common_paths(self) -> List[str]:
        common_paths = [
            '/downloads', '/documents', '/forms', '/pdfs', '/resources',
            '/download-forms', '/customer-service', '/compliance', '/regulatory',
            '/download', '/files', '/media', '/assets/pdf', '/assets/documents'
        ]
        
        urls = [self.base_url]
        for path in common_paths:
            test_url = urljoin(self.base_url, path)
            urls.append(test_url)
            urls.append(test_url + '.html')
            urls.append(test_url + '/index.html')
        
        return urls
    
    def crawl_for_pdfs(self, custom_path: str = None, max_pages: int = 50) -> List[str]:
        urls_to_visit = []
        
        sitemap_urls = self.fetch_sitemap()
        if sitemap_urls:
            urls_to_visit.extend(sitemap_urls[:max_pages])
        
        if custom_path:
            custom_url = urljoin(self.base_url, custom_path)
            urls_to_visit.insert(0, custom_url)
        
        urls_to_visit.extend(self.discover_common_paths())
        
        if self.base_url not in urls_to_visit:
            urls_to_visit.insert(0, self.base_url)
        
        seen = set()
        urls_to_visit = [x for x in urls_to_visit if not (x in seen or seen.add(x))]
        
        st.info(f"🔍 Scanning {min(len(urls_to_visit), max_pages)} pages for PDFs...")
        
        progress_container = st.empty()
        
        for idx, url in enumerate(urls_to_visit[:max_pages]):
            if url in self.visited_urls:
                continue
            
            progress_container.text(f"Scanning page {idx + 1}/{min(len(urls_to_visit), max_pages)}: {url[:60]}...")
            
            self.visited_urls.add(url)
            
            if url.lower().endswith('.pdf'):
                self.pdf_urls.add(url)
                continue
            
            page_pdfs = self.extract_pdf_links_from_page(url)
            self.pdf_urls.update(page_pdfs)
            
            if page_pdfs and len(self.visited_urls) < max_pages:
                try:
                    response = requests.get(url, headers=self.headers, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        for link in soup.find_all('a', href=True):
                            href = link['href']
                            full_url = urljoin(url, href)
                            
                            if (urlparse(full_url).netloc == self.domain and 
                                full_url not in self.visited_urls and
                                len(urls_to_visit) < max_pages * 2):
                                
                                link_text = link.get_text().lower()
                                keywords = ['download', 'form', 'document', 'pdf', 'file', 'compliance', 'regulatory']
                                
                                if any(kw in full_url.lower() or kw in link_text for kw in keywords):
                                    urls_to_visit.append(full_url)
                except:
                    pass
        
        progress_container.empty()
        
        valid_pdfs = []
        for pdf_url in self.pdf_urls:
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
        self.debug_info = []
        
    def get_regulatory_context(self, source: str, limit: int = 20) -> List[Dict]:
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
        try:
            response = requests.post(
                self.pdf_extractor_url,
                json={"url": pdf_url},
                timeout=60
            )
            if response.status_code == 200:
                data = response.json()
                text = data.get('text', '')
                self.debug_info.append(f"✅ PDF extracted: {len(text)} characters")
                return text
            else:
                self.debug_info.append(f"❌ PDF extraction failed: HTTP {response.status_code}")
        except Exception as e:
            self.debug_info.append(f"❌ PDF extraction error: {str(e)}")
        return ""
    
    def analyze_with_ai(self, document_content: str, regulatory_context: List[Dict], 
                       regulator: str, pdf_url: str) -> Dict:
        """FIXED: Real AI analysis with proper error handling"""
        
        if not document_content or len(document_content) < 100:
            return {
                "score": 0,
                "summary": f"ERROR: Document content too short or empty ({len(document_content)} chars)",
                "findings": [{
                    "level": "critical",
                    "title": "No Document Content",
                    "description": "PDF extraction failed or returned empty content",
                    "regulation": "N/A"
                }],
                "recommendations": ["Verify PDF URL is accessible", "Check PDF extraction service"],
                "raw_response": "No content to analyze",
                "ai_error": True
            }
        
        # Prepare regulatory context
        context_summary = "\n".join([
            f"- {circ.get('title', 'N/A')[:100]} (Date: {circ.get('date', 'N/A')})"
            for circ in regulatory_context[:10]
        ])
        
        system_prompt = f"""You are a compliance analyst expert for {regulator} regulations.

Recent {regulator} Circulars:
{context_summary}

CRITICAL: You MUST respond with ONLY valid JSON. No markdown, no explanations, ONLY JSON.

Analyze the document and return this EXACT structure:
{{
    "score": 75,
    "summary": "Brief 2-3 sentence summary of compliance status",
    "findings": [
        {{
            "level": "critical",
            "title": "Finding title",
            "description": "Detailed description",
            "regulation": "Relevant {regulator} regulation reference"
        }}
    ],
    "recommendations": [
        "Specific recommendation 1",
        "Specific recommendation 2"
    ]
}}

Score guidelines:
- 0-40: Critical violations, major gaps
- 41-60: Significant issues, partial compliance
- 61-80: Minor issues, mostly compliant
- 81-100: Excellent compliance

Finding levels: critical, warning, info, success"""

        user_prompt = f"""Document URL: {pdf_url}

Document Content (first 8000 chars):
{document_content[:8000]}

Analyze this document for {regulator} compliance. Return ONLY JSON, no other text."""
        
        url = f"https://api.cloudflare.com/client/v4/accounts/{self.cloudflare_account_id}/ai/run/@cf/google/gemma-4-26b-a4b-it"
        headers = {
            "Authorization": f"Bearer {self.cloudflare_auth_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 2048,
            "temperature": 0.3
        }
        
        self.debug_info.append(f"🤖 Sending to Cloudflare AI...")
        self.debug_info.append(f"📊 Document length: {len(document_content)} chars")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            
            self.debug_info.append(f"🔄 AI Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"Cloudflare AI API error: {response.status_code}"
                self.debug_info.append(f"❌ {error_msg}")
                self.debug_info.append(f"Response: {response.text[:500]}")
                
                return {
                    "score": 0,
                    "summary": f"AI API Error: {response.status_code}",
                    "findings": [{
                        "level": "critical",
                        "title": "AI Analysis Failed",
                        "description": f"Could not connect to AI service. Status: {response.status_code}",
                        "regulation": "N/A"
                    }],
                    "recommendations": ["Check Cloudflare API credentials", "Verify API quota"],
                    "raw_response": response.text[:500],
                    "ai_error": True
                }
            
            result = response.json()
            ai_response = result.get('result', {}).get('response', '')
            
            self.debug_info.append(f"📝 Raw AI response length: {len(ai_response)} chars")
            self.debug_info.append(f"First 200 chars: {ai_response[:200]}")
            
            # Try multiple JSON extraction methods
            parsed_json = None
            
            # Method 1: Direct JSON parse
            try:
                parsed_json = json.loads(ai_response)
                self.debug_info.append("✅ Method 1: Direct JSON parse succeeded")
            except:
                pass
            
            # Method 2: Extract JSON from markdown code blocks
            if not parsed_json:
                try:
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', ai_response, re.DOTALL)
                    if json_match:
                        parsed_json = json.loads(json_match.group(1))
                        self.debug_info.append("✅ Method 2: Markdown extraction succeeded")
                except:
                    pass
            
            # Method 3: Extract any JSON object
            if not parsed_json:
                try:
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', ai_response, re.DOTALL)
                    if json_match:
                        parsed_json = json.loads(json_match.group())
                        self.debug_info.append("✅ Method 3: Regex extraction succeeded")
                except:
                    pass
            
            if parsed_json and isinstance(parsed_json, dict):
                # Validate required fields
                if 'score' in parsed_json and 'summary' in parsed_json:
                    # Ensure findings and recommendations exist
                    if 'findings' not in parsed_json:
                        parsed_json['findings'] = []
                    if 'recommendations' not in parsed_json:
                        parsed_json['recommendations'] = []
                    
                    parsed_json['raw_response'] = ai_response[:500]
                    parsed_json['ai_error'] = False
                    self.debug_info.append(f"✅ Valid analysis returned: Score {parsed_json['score']}")
                    return parsed_json
            
            # If all parsing failed
            self.debug_info.append("❌ All JSON parsing methods failed")
            self.debug_info.append(f"Full AI response: {ai_response}")
            
            return {
                "score": 0,
                "summary": "AI returned invalid format",
                "findings": [{
                    "level": "warning",
                    "title": "Analysis Format Error",
                    "description": f"AI response could not be parsed as JSON. Response: {ai_response[:200]}",
                    "regulation": "N/A"
                }],
                "recommendations": ["Check AI prompt format", "Review AI response structure"],
                "raw_response": ai_response,
                "ai_error": True
            }
            
        except Exception as e:
            error_msg = f"AI analysis exception: {str(e)}"
            self.debug_info.append(f"❌ {error_msg}")
            
            return {
                "score": 0,
                "summary": f"Analysis failed: {str(e)}",
                "findings": [{
                    "level": "critical",
                    "title": "AI Analysis Exception",
                    "description": str(e),
                    "regulation": "N/A"
                }],
                "recommendations": ["Check network connection", "Verify AI service availability"],
                "raw_response": str(e),
                "ai_error": True
            }

# Main App (sidebar and UI same as before, just the analysis part changes)
st.markdown('<h1 class="main-header">🔍 ComplyScore</h1>', unsafe_allow_html=True)
st.markdown("**Automated Compliance Analysis Engine - V3 with Real AI Analysis**")

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
    
    regulator_map = {
        "SEBI": "sebi",
        "RBI": "rbi",
        "FCA": "fca"
    }
    
    st.divider()
    
    # Debug mode toggle
    st.session_state.show_debug = st.checkbox("🐛 Show Debug Info", value=False)
    
    analyze_button = st.button("🚀 Start Analysis", type="primary", use_container_width=True)

# Main content
if not analyze_button and not st.session_state.analysis_complete:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("**1. Enter Website**\nProvide the URL to analyze")
    
    with col2:
        st.info("**2. Select Regulator**\nChoose applicable regulatory body")
    
    with col3:
        st.info("**3. Get Real AI Analysis**\nNo mock scores - actual compliance evaluation")
    
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
        try:
            cloudflare_account_id = st.secrets["CLOUDFLARE_ACCOUNT_ID"]
            cloudflare_auth_token = st.secrets["CLOUDFLARE_AUTH_TOKEN"]
            supabase_api_key = st.secrets["SUPABASE_API_KEY"]
            pdf_extractor_url = st.secrets.get("PDF_EXTRACTOR_URL", "http://72.61.251.247:3000/extract-pdf-url")
        except Exception as e:
            st.error(f"Missing required secrets: {str(e)}")
            st.stop()
        
        with st.spinner("🔍 Crawling website for compliance documents..."):
            crawler = ComplianceCrawler(website_url)
            pdf_urls = crawler.crawl_for_pdfs(custom_path, max_pages)
        
        st.success(f"✅ Found {len(pdf_urls)} PDF documents")
        
        if pdf_urls:
            with st.expander(f"📄 Found Documents ({len(pdf_urls)})"):
                for i, url in enumerate(pdf_urls[:50], 1):
                    st.text(f"{i}. {url}")
                if len(pdf_urls) > 50:
                    st.info(f"... and {len(pdf_urls) - 50} more")
            
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
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            all_analyses = []
            all_debug_info = []
            
            for i, pdf_url in enumerate(pdf_urls[:5]):
                status_text.text(f"🔍 Analyzing document {i+1}/{min(5, len(pdf_urls))}...")
                progress_bar.progress((i + 1) / min(5, len(pdf_urls)))
                
                analyzer.debug_info = []  # Reset debug info
                
                # Extract PDF
                content = analyzer.extract_pdf_content(pdf_url)
                
                # Always analyze, even if extraction failed (to show error)
                analysis = analyzer.analyze_with_ai(
                    content,
                    regulatory_context,
                    regulator,
                    pdf_url
                )
                analysis['url'] = pdf_url
                analysis['content_length'] = len(content)
                all_analyses.append(analysis)
                all_debug_info.extend(analyzer.debug_info)
                
                # Small delay to avoid rate limiting
                time.sleep(1)
            
            progress_bar.empty()
            status_text.empty()
            
            # Calculate overall score (exclude failed analyses)
            valid_analyses = [a for a in all_analyses if not a.get('ai_error', False)]
            
            if valid_analyses:
                avg_score = sum(a.get('score', 0) for a in valid_analyses) / len(valid_analyses)
            else:
                avg_score = 0
                st.error("⚠️ All AI analyses failed. Check debug info below.")
            
            st.session_state.analysis_results = {
                'score': avg_score,
                'regulator': regulator,
                'analyses': all_analyses,
                'pdf_count': len(pdf_urls),
                'website': website_url,
                'debug_info': all_debug_info,
                'failed_count': len([a for a in all_analyses if a.get('ai_error', False)])
            }
            st.session_state.analysis_complete = True
            st.rerun()
        else:
            st.warning("No PDF documents found on the website.")

# Display Results
if st.session_state.analysis_complete and st.session_state.analysis_results:
    results = st.session_state.analysis_results
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"Analysis Results for {results['website']}")
        st.caption(f"Regulator: {results['regulator']} | Documents Analyzed: {len(results['analyses'])}/{results['pdf_count']}")
        if results.get('failed_count', 0) > 0:
            st.warning(f"⚠️ {results['failed_count']} analysis failed - see details below")
    
    with col2:
        if st.button("🔄 New Analysis"):
            st.session_state.analysis_complete = False
            st.session_state.analysis_results = None
            st.rerun()
    
    # Debug info
    if st.session_state.show_debug and results.get('debug_info'):
        with st.expander("🐛 Debug Information", expanded=True):
            st.markdown('<div class="debug-section">', unsafe_allow_html=True)
            for info in results['debug_info']:
                st.text(info)
            st.markdown('</div>', unsafe_allow_html=True)
    
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
    
    # Document Analysis
    st.subheader("📊 Detailed Analysis")
    
    for idx, analysis in enumerate(results['analyses'], 1):
        is_error = analysis.get('ai_error', False)
        score_display = analysis.get('score', 0)
        
        title = f"Document {idx} - "
        if is_error:
            title += "❌ ANALYSIS FAILED"
        else:
            title += f"Score: {score_display}/100"
        
        with st.expander(title, expanded=is_error):
            st.caption(f"🔗 {analysis.get('url', 'N/A')}")
            st.caption(f"📄 Content: {analysis.get('content_length', 0)} characters extracted")
            
            # Show raw AI response in debug mode
            if st.session_state.show_debug and 'raw_response' in analysis:
                st.markdown("**Raw AI Response:**")
                st.code(analysis['raw_response'], language='text')
            
            st.markdown(f"**Summary:** {analysis.get('summary', 'No summary available')}")
            
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
            
            recommendations = analysis.get('recommendations', [])
            if recommendations:
                st.markdown("**Recommendations:**")
                for rec in recommendations:
                    st.markdown(f"- {rec}")
    
    # Export
    st.divider()
    if st.button("📥 Export Report (JSON)"):
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "website": results['website'],
            "regulator": results['regulator'],
            "overall_score": results['score'],
            "documents_analyzed": len(results['analyses']),
            "total_documents": results['pdf_count'],
            "failed_analyses": results.get('failed_count', 0),
            "analyses": results['analyses']
        }
        
        st.download_button(
            label="Download Report",
            data=json.dumps(report_data, indent=2),
            file_name=f"compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
