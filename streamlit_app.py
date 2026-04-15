import streamlit as st
import requests
from bs4 import BeautifulSoup
import urllib.parse
from xml.etree import ElementTree as ET
import json
import time
from urllib.robotparser import RobotFileParser

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ComplyKrawl",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
}
.stApp {
    background: #0a0d14;
    color: #e8eaf0;
}
.main-header {
    background: linear-gradient(135deg, #0d1117 0%, #111827 100%);
    border: 1px solid #1e2d40;
    border-radius: 16px;
    padding: 32px 40px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
}
.main-header::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 200px; height: 200px;
    background: radial-gradient(circle, rgba(56,189,248,0.12) 0%, transparent 70%);
}
.main-header h1 {
    font-size: 2.4rem;
    font-weight: 800;
    color: #f0f4ff;
    letter-spacing: -0.02em;
    margin: 0;
}
.main-header .tagline {
    font-family: 'DM Mono', monospace;
    font-size: 0.78rem;
    color: #38bdf8;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 6px;
}
.score-card {
    background: #111827;
    border: 1px solid #1e2d40;
    border-radius: 14px;
    padding: 22px 26px;
    text-align: center;
    transition: border-color 0.2s;
}
.score-card:hover { border-color: #38bdf8; }
.score-number {
    font-size: 3rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    line-height: 1;
}
.score-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 6px;
}
.risk-badge {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 99px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.risk-low    { background: #064e3b; color: #6ee7b7; border: 1px solid #065f46; }
.risk-medium { background: #451a03; color: #fbbf24; border: 1px solid #78350f; }
.risk-high   { background: #450a0a; color: #f87171; border: 1px solid #7f1d1d; }
.risk-critical { background: #3b0764; color: #d946ef; border: 1px solid #581c87; }
.finding-item {
    background: #0f172a;
    border-left: 3px solid #38bdf8;
    padding: 10px 16px;
    margin: 6px 0;
    border-radius: 0 8px 8px 0;
    font-size: 0.88rem;
    color: #cbd5e1;
}
.gap-item {
    background: #0f172a;
    border-left: 3px solid #f59e0b;
    padding: 10px 16px;
    margin: 6px 0;
    border-radius: 0 8px 8px 0;
    font-size: 0.88rem;
    color: #cbd5e1;
}
.rec-item {
    background: #0f172a;
    border-left: 3px solid #22c55e;
    padding: 10px 16px;
    margin: 6px 0;
    border-radius: 0 8px 8px 0;
    font-size: 0.88rem;
    color: #cbd5e1;
}
.url-chip {
    display: inline-block;
    background: #111827;
    border: 1px solid #1e2d40;
    border-radius: 6px;
    padding: 3px 10px;
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    color: #94a3b8;
    margin: 3px;
    word-break: break-all;
}
.section-header {
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    color: #38bdf8;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin: 20px 0 10px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-header::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #1e2d40;
}
.circular-card {
    background: #0f172a;
    border: 1px solid #1e2d40;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 8px 0;
    font-size: 0.85rem;
}
.circular-card .circ-title { color: #e2e8f0; font-weight: 600; }
.circular-card .circ-meta  { 
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem; 
    color: #64748b; 
    margin-top: 4px;
}
.stProgress > div > div { background: #38bdf8; }
div[data-testid="stMetricValue"] { font-family: 'Syne', sans-serif; font-weight: 700; }
.stButton > button {
    background: linear-gradient(135deg, #0ea5e9, #2563eb);
    color: white;
    border: none;
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    letter-spacing: 0.04em;
    border-radius: 10px;
    padding: 12px 28px;
    transition: all 0.2s;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #38bdf8, #3b82f6);
    transform: translateY(-1px);
    box-shadow: 0 8px 25px rgba(14,165,233,0.3);
}
</style>
""", unsafe_allow_html=True)

# ─── Constants ─────────────────────────────────────────────────────────────────
REGULATORS = {
    "SEBI": {
        "name": "Securities and Exchange Board of India",
        "source": "sebi",
        "country": "🇮🇳 India",
        "color": "#f59e0b",
    },
    "RBI": {
        "name": "Reserve Bank of India",
        "source": "rbi",
        "country": "🇮🇳 India",
        "color": "#22c55e",
    },
    "FCA": {
        "name": "Financial Conduct Authority",
        "source": "fca",
        "country": "🇬🇧 UK",
        "color": "#60a5fa",
    },
}

LENS_API_BASE = "https://lbtoopahmulfgffzjumy.supabase.co/functions/v1/lens-api"
PDF_EXTRACT_API = "http://72.61.251.247:3000/extract-pdf-url"

# ─── Secrets ───────────────────────────────────────────────────────────────────
def get_secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return default

CF_ACCOUNT_ID    = get_secret("CLOUDFLARE_ACCOUNT_ID")
CF_AUTH_TOKEN    = get_secret("CLOUDFLARE_AUTH_TOKEN")
LENS_API_KEY     = get_secret("LENS_API_KEY")
CF_AI_URL        = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/@cf/google/gemma-4-26b-a4b-it"

# ─── Crawler Helpers ───────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (ComplyKrawl/1.0; compliance-crawler)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def normalise_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    return url.rstrip("/")


def fetch_sitemap(base_url: str) -> list[str] | None:
    candidates = [
        f"{base_url}/sitemap.xml",
        f"{base_url}/sitemap_index.xml",
        f"{base_url}/sitemap/sitemap.xml",
        f"{base_url}/sitemap/index.xml",
    ]
    # Check robots.txt for Sitemap hint
    try:
        robots_r = requests.get(f"{base_url}/robots.txt", headers=HEADERS, timeout=8)
        if robots_r.status_code == 200:
            for line in robots_r.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    candidates.insert(0, sitemap_url)
    except Exception:
        pass

    for url in candidates:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            ct = r.headers.get("Content-Type", "")
            if r.status_code == 200 and ("xml" in ct or r.text.strip().startswith("<")):
                urls = _parse_sitemap_xml(r.text, base_url)
                if urls:
                    return urls
        except Exception:
            pass
    return None


def _parse_sitemap_xml(xml_text: str, base_url: str, depth: int = 0) -> list[str]:
    if depth > 3:
        return []
    urls = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # Sitemap index
        for child in root.findall("sm:sitemap", ns):
            loc = child.find("sm:loc", ns)
            if loc is not None and loc.text:
                try:
                    r = requests.get(loc.text.strip(), headers=HEADERS, timeout=10)
                    if r.status_code == 200:
                        urls.extend(_parse_sitemap_xml(r.text, base_url, depth + 1))
                except Exception:
                    pass

        # Regular entries
        for url_el in root.findall("sm:url", ns):
            loc = url_el.find("sm:loc", ns)
            if loc is not None and loc.text:
                urls.append(loc.text.strip())
    except Exception:
        pass
    return urls


def crawl_website(base_url: str, max_pages: int = 50) -> list[str]:
    visited: set[str] = set()
    queue: list[str] = [base_url]
    found: list[str] = []
    parsed_base = urllib.parse.urlparse(base_url)
    base_domain = parsed_base.netloc

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            found.append(url)
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup.find_all(["a", "link"], href=True):
                href = tag["href"]
                full = urllib.parse.urljoin(url, href)
                parsed = urllib.parse.urlparse(full)
                clean = parsed._replace(fragment="").geturl()
                if parsed.netloc == base_domain and clean not in visited:
                    queue.append(clean)
        except Exception:
            pass
    return found


def build_custom_urls(base_url: str, paths_text: str) -> list[str]:
    urls = []
    for line in paths_text.strip().splitlines():
        path = line.strip()
        if path:
            urls.append(urllib.parse.urljoin(base_url + "/", path.lstrip("/")))
    return urls


DOC_EXTS = {".pdf", ".doc", ".docx", ".xlsx", ".xls", ".ppt", ".pptx", ".txt", ".csv"}

def filter_documents(urls: list[str]) -> list[str]:
    result = []
    for u in urls:
        path = urllib.parse.urlparse(u).path.lower()
        if any(path.endswith(ext) for ext in DOC_EXTS):
            result.append(u)
    return result


# ─── API Helpers ───────────────────────────────────────────────────────────────
def fetch_circulars(source: str, limit: int = 10) -> dict | None:
    try:
        r = requests.get(
            f"{LENS_API_BASE}/circulars",
            params={"source": source, "limit": limit},
            headers={"x-api-key": LENS_API_KEY},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def extract_pdf(pdf_url: str) -> str | None:
    try:
        r = requests.post(
            PDF_EXTRACT_API,
            json={"url": pdf_url},
            timeout=45,
        )
        if r.status_code == 200:
            data = r.json()
            text = (
                data.get("text")
                or data.get("content")
                or data.get("extracted_text")
                or json.dumps(data)
            )
            return str(text)
    except Exception:
        pass
    return None


def fetch_page_text(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return None


def call_cloudflare_ai(system_prompt: str, user_prompt: str) -> str:
    try:
        r = requests.post(
            CF_AI_URL,
            headers={
                "Authorization": f"Bearer {CF_AUTH_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ]
            },
            timeout=90,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("result", {}).get("response", "")
    except Exception as e:
        return f"__ERROR__: {e}"
    return ""


# ─── Compliance Analysis ───────────────────────────────────────────────────────
def build_circular_context(circulars_data) -> str:
    if not circulars_data:
        return "No regulatory circulars available."
    items = circulars_data if isinstance(circulars_data, list) else (
        circulars_data.get("data") or circulars_data.get("circulars") or
        circulars_data.get("results") or []
    )
    lines = []
    for c in items[:8]:
        if isinstance(c, dict):
            title = c.get("title", c.get("subject", "Untitled"))
            date  = c.get("date", c.get("published_date", c.get("issued_date", "")))
            ref   = c.get("circular_number", c.get("ref", ""))
            lines.append(f"• [{ref}] {title} ({date})")
    return "\n".join(lines) if lines else "Circulars fetched but no structured entries found."


def analyse_document(content: str | None, circulars_data, regulator: str, doc_url: str) -> dict:
    reg_info   = REGULATORS[regulator]
    reg_name   = reg_info["name"]
    circ_ctx   = build_circular_context(circulars_data)
    content_snippet = (content or "")[:3500]

    system_prompt = f"""You are a senior regulatory compliance analyst specialising in {reg_name} ({regulator}) regulations.
Analyse documents for compliance with {regulator} rules, guidelines, and recent circulars.
Respond ONLY with a valid JSON object — no markdown fences, no preamble — with these exact keys:
  compliance_score  : integer 0–100 (100 = fully compliant)
  risk_level        : one of "Low" | "Medium" | "High" | "Critical"
  summary           : 2–3 sentence plain-English overview
  key_findings      : array of 3–5 strings (specific observations)
  gaps              : array of identified compliance gaps (may be empty)
  recommendations   : array of 2–4 actionable strings
  applicable_rules  : array of relevant {regulator} regulations/sections referenced"""

    user_prompt = f"""Assess this document for {regulator} compliance.

Document URL: {doc_url}

Extracted Content:
{content_snippet if content_snippet else "[Content could not be extracted — infer from URL and context]"}

Recent {regulator} Circulars / Regulatory Context:
{circ_ctx}

Return the JSON compliance analysis now."""

    raw = call_cloudflare_ai(system_prompt, user_prompt)

    if raw.startswith("__ERROR__"):
        return _fallback_result(raw)

    try:
        clean = raw.strip()
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        return json.loads(clean.strip())
    except Exception:
        return {
            "compliance_score": 50,
            "risk_level": "Medium",
            "summary": raw[:600] if raw else "Analysis could not be structured.",
            "key_findings": [],
            "gaps": [],
            "recommendations": [],
            "applicable_rules": [],
        }


def _fallback_result(msg: str) -> dict:
    return {
        "compliance_score": 0,
        "risk_level": "High",
        "summary": f"Analysis failed: {msg}",
        "key_findings": [],
        "gaps": [],
        "recommendations": ["Check API credentials in Streamlit secrets."],
        "applicable_rules": [],
    }


# ─── Score Colour Helpers ──────────────────────────────────────────────────────
def score_colour(s: int) -> str:
    if s >= 80: return "#22c55e"
    if s >= 60: return "#f59e0b"
    if s >= 40: return "#f97316"
    return "#ef4444"

def risk_class(r: str) -> str:
    return {"Low": "risk-low", "Medium": "risk-medium", "High": "risk-high", "Critical": "risk-critical"}.get(r, "risk-medium")

# ─── UI ────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <div class="tagline">⚖️ &nbsp; Regulatory Compliance Intelligence</div>
  <h1>ComplyKrawl</h1>
  <div style="margin-top:10px;color:#64748b;font-size:0.9rem;">
    Crawl any website · Extract documents · Analyse against live regulatory circulars
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")

    regulator = st.selectbox(
        "Regulatory Body",
        list(REGULATORS.keys()),
        format_func=lambda x: f"{x}  —  {REGULATORS[x]['country']}",
    )
    reg_info = REGULATORS[regulator]
    st.caption(reg_info["name"])

    st.divider()

    crawl_mode = st.radio(
        "Crawl Strategy",
        ["🗺️ Auto (Sitemap → Crawl)", "🗺️ Sitemap Only", "🤖 Full Crawl", "📁 Custom Paths"],
        index=0,
    )

    max_pages = st.slider("Max pages (crawl mode)", 10, 150, 40)
    max_docs  = st.slider("Max documents to analyse", 1, 20, 5)
    circ_limit = st.slider("Circulars to load", 5, 50, 15)

    st.divider()
    docs_only = st.checkbox("📄 Documents only (PDF/DOCX/etc.)", value=True)

    st.divider()
    st.markdown("""
    <div style="font-size:0.72rem;color:#475569;font-family:'DM Mono',monospace;">
    Keys loaded from<br><code>st.secrets</code>:<br>
    CLOUDFLARE_ACCOUNT_ID<br>
    CLOUDFLARE_AUTH_TOKEN<br>
    LENS_API_KEY
    </div>
    """, unsafe_allow_html=True)

# ─── Main Input ────────────────────────────────────────────────────────────────
c1, c2 = st.columns([5, 1])
with c1:
    website_url = st.text_input(
        "🌐 Target Website URL",
        placeholder="https://www.sebi.gov.in",
        label_visibility="collapsed",
    )
with c2:
    run_btn = st.button("🚀 Analyse", use_container_width=True, type="primary")

custom_paths_text = ""
if "Custom" in crawl_mode:
    custom_paths_text = st.text_area(
        "Custom document paths (one per line)",
        placeholder="/documents/\n/circulars/annual-report.pdf\n/compliance/",
        height=100,
    )

st.divider()

# ─── Main Logic ────────────────────────────────────────────────────────────────
if run_btn:
    if not website_url:
        st.warning("Please enter a website URL.")
        st.stop()

    website_url = normalise_url(website_url)

    # ── Phase 1: Crawl ──────────────────────────────────────────────────────
    st.markdown('<div class="section-header">01 · URL Discovery</div>', unsafe_allow_html=True)

    all_urls: list[str] = []
    sitemap_used = False

    with st.status("Crawling website…", expanded=True) as crawl_status:
        if "Custom" in crawl_mode:
            st.write("📁 Building URLs from custom paths…")
            all_urls = build_custom_urls(website_url, custom_paths_text)
            st.write(f"✅ {len(all_urls)} custom URLs built")
        else:
            if "Auto" in crawl_mode or "Sitemap" in crawl_mode:
                st.write("🗺️ Searching for sitemap…")
                sitemap_urls = fetch_sitemap(website_url)
                if sitemap_urls:
                    all_urls = sitemap_urls
                    sitemap_used = True
                    st.write(f"✅ Sitemap found — {len(sitemap_urls)} URLs indexed")
                else:
                    st.write("⚠️ No sitemap found")

            if not sitemap_used and "Sitemap Only" not in crawl_mode:
                st.write(f"🤖 Starting link crawler (max {max_pages} pages)…")
                all_urls = crawl_website(website_url, max_pages)
                st.write(f"✅ Crawl complete — {len(all_urls)} pages discovered")

        analysis_targets = all_urls
        if docs_only:
            doc_urls = filter_documents(all_urls)
            st.write(f"📄 {len(doc_urls)} document URLs filtered from {len(all_urls)} total")
            analysis_targets = doc_urls if doc_urls else all_urls[:max_docs]
        else:
            analysis_targets = all_urls[:max_docs * 4]

        analysis_targets = analysis_targets[:max_docs]
        crawl_status.update(label=f"✅ Discovery done — {len(all_urls)} URLs | {len(analysis_targets)} queued for analysis", state="complete")

    # Display discovered URLs
    with st.expander(f"📋 All discovered URLs ({len(all_urls)})", expanded=False):
        cols = st.columns(2)
        for i, u in enumerate(all_urls[:200]):
            cols[i % 2].markdown(f'<div class="url-chip">{u}</div>', unsafe_allow_html=True)

    # ── Phase 2: Regulatory Context ─────────────────────────────────────────
    st.markdown(f'<div class="section-header">02 · {regulator} Regulatory Context</div>', unsafe_allow_html=True)

    circulars_data = None
    with st.status(f"Fetching {regulator} circulars…", expanded=False) as reg_status:
        circulars_data = fetch_circulars(reg_info["source"], circ_limit)
        if circulars_data:
            reg_status.update(label=f"✅ {regulator} circulars loaded", state="complete")
        else:
            reg_status.update(label=f"⚠️ Could not load {regulator} circulars (check LENS_API_KEY)", state="error")

    if circulars_data:
        items = circulars_data if isinstance(circulars_data, list) else (
            circulars_data.get("data") or circulars_data.get("circulars") or
            circulars_data.get("results") or []
        )
        with st.expander(f"📜 {regulator} Circulars ({len(items)} loaded)", expanded=False):
            for c in items[:10]:
                if isinstance(c, dict):
                    title = c.get("title", c.get("subject", "Untitled"))
                    date  = c.get("date", c.get("published_date", "—"))
                    ref   = c.get("circular_number", c.get("ref", ""))
                    st.markdown(f"""
                    <div class="circular-card">
                        <div class="circ-title">{title}</div>
                        <div class="circ-meta">{ref} &nbsp;·&nbsp; {date}</div>
                    </div>""", unsafe_allow_html=True)

    # ── Phase 3: Extract + Analyse ──────────────────────────────────────────
    if not analysis_targets:
        st.warning("No documents to analyse. Try unchecking 'Documents only' or adding custom paths.")
        st.stop()

    st.markdown('<div class="section-header">03 · AI Compliance Analysis</div>', unsafe_allow_html=True)

    all_results = []

    for idx, doc_url in enumerate(analysis_targets):
        doc_name = doc_url.split("/")[-1] or doc_url
        is_pdf   = doc_url.lower().endswith(".pdf")

        with st.expander(f"{'📕' if is_pdf else '🌐'} {doc_name}", expanded=(idx == 0)):
            pcol, acol = st.columns([1, 2])

            with pcol:
                st.markdown(f"**URL**")
                st.code(doc_url, language=None)
                st.caption(f"Type: {'PDF Document' if is_pdf else 'Web Page'}")

            with acol:
                prog = st.empty()
                prog.info("⏳ Extracting content…")
                content = None

                if is_pdf:
                    content = extract_pdf(doc_url)
                    if not content:
                        prog.warning("⚠️ PDF extraction failed — analysing from URL context.")
                    else:
                        prog.success(f"✅ Extracted {len(content):,} chars from PDF")
                else:
                    content = fetch_page_text(doc_url)
                    if content:
                        prog.success(f"✅ Extracted {len(content):,} chars from page")
                    else:
                        prog.warning("⚠️ Page extraction failed")

            ai_prog = st.empty()
            ai_prog.info(f"🤖 Running {regulator} compliance analysis via Cloudflare AI…")
            analysis = analyse_document(content, circulars_data, regulator, doc_url)
            ai_prog.empty()

            all_results.append({"url": doc_url, "name": doc_name, "analysis": analysis})

            score     = analysis.get("compliance_score", 0)
            risk      = analysis.get("risk_level", "Medium")
            summary   = analysis.get("summary", "")
            findings  = analysis.get("key_findings", [])
            gaps      = analysis.get("gaps", [])
            recs      = analysis.get("recommendations", [])
            rules     = analysis.get("applicable_rules", [])

            sc = score_colour(score)
            rc = risk_class(risk)

            # Score row
            m1, m2, m3 = st.columns(3)
            m1.markdown(f"""
            <div class="score-card">
                <div class="score-number" style="color:{sc}">{score}</div>
                <div class="score-label">Compliance Score / 100</div>
            </div>""", unsafe_allow_html=True)

            m2.markdown(f"""
            <div class="score-card">
                <div style="margin-top:8px;"><span class="risk-badge {rc}">{risk}</span></div>
                <div class="score-label" style="margin-top:10px;">Risk Level</div>
            </div>""", unsafe_allow_html=True)

            m3.markdown(f"""
            <div class="score-card">
                <div class="score-number" style="color:#60a5fa">{len(gaps)}</div>
                <div class="score-label">Compliance Gaps</div>
            </div>""", unsafe_allow_html=True)

            st.progress(score / 100)

            if summary:
                st.markdown(f"> {summary}")

            r1, r2 = st.columns(2)
            with r1:
                if findings:
                    st.markdown("**🔍 Key Findings**")
                    for f in findings:
                        st.markdown(f'<div class="finding-item">• {f}</div>', unsafe_allow_html=True)
                if rules:
                    st.markdown("**📖 Applicable Rules**")
                    for rule in rules:
                        st.markdown(f'<div class="finding-item" style="border-left-color:#818cf8">• {rule}</div>', unsafe_allow_html=True)

            with r2:
                if gaps:
                    st.markdown("**⚠️ Compliance Gaps**")
                    for g in gaps:
                        st.markdown(f'<div class="gap-item">⚠ {g}</div>', unsafe_allow_html=True)
                if recs:
                    st.markdown("**✅ Recommendations**")
                    for rec in recs:
                        st.markdown(f'<div class="rec-item">→ {rec}</div>', unsafe_allow_html=True)

    # ── Phase 4: Summary Dashboard ──────────────────────────────────────────
    if len(all_results) > 1:
        st.markdown('<div class="section-header">04 · Portfolio Summary</div>', unsafe_allow_html=True)

        scores  = [r["analysis"].get("compliance_score", 0) for r in all_results]
        avg     = sum(scores) / len(scores)
        hi_risk = sum(1 for r in all_results if r["analysis"].get("risk_level") in ("High", "Critical"))
        total_gaps = sum(len(r["analysis"].get("gaps", [])) for r in all_results)

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("📊 Avg Score", f"{avg:.0f}/100")
        d2.metric("📄 Docs Analysed", len(all_results))
        d3.metric("🔴 High/Critical Risk", hi_risk)
        d4.metric("⚠️ Total Gaps", total_gaps)

        st.progress(avg / 100)

        # Score breakdown table
        st.markdown("**Score Breakdown**")
        rows = []
        for r in all_results:
            a = r["analysis"]
            s = a.get("compliance_score", 0)
            sc = score_colour(s)
            rows.append(
                f"<tr>"
                f"<td style='padding:8px 12px;color:#94a3b8;font-size:0.8rem;font-family:DM Mono,monospace;word-break:break-all'>{r['url'][:80]}</td>"
                f"<td style='padding:8px 12px;text-align:center'><span style='font-weight:700;color:{sc}'>{s}</span></td>"
                f"<td style='padding:8px 12px;text-align:center'><span class='risk-badge {risk_class(a.get('risk_level','Medium'))}'>{a.get('risk_level','—')}</span></td>"
                f"<td style='padding:8px 12px;text-align:center;color:#94a3b8'>{len(a.get('gaps',[]))}</td>"
                f"</tr>"
            )
        table_html = f"""
        <style>
        .summary-table {{ width:100%;border-collapse:collapse;background:#0f172a;border-radius:12px;overflow:hidden; }}
        .summary-table th {{ padding:10px 12px;text-align:left;font-family:'DM Mono',monospace;font-size:0.7rem;
                             color:#38bdf8;text-transform:uppercase;letter-spacing:0.1em;background:#111827; }}
        .summary-table tr:hover td {{ background:#1e293b; }}
        </style>
        <table class="summary-table">
          <thead><tr>
            <th>Document</th><th style="text-align:center">Score</th>
            <th style="text-align:center">Risk</th><th style="text-align:center">Gaps</th>
          </tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>"""
        st.markdown(table_html, unsafe_allow_html=True)

elif not run_btn:
    # Landing placeholder
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;color:#334155;">
        <div style="font-size:3.5rem;margin-bottom:16px;">⚖️</div>
        <div style="font-size:1.1rem;font-weight:600;color:#64748b;">
            Enter a website URL and select a regulator to begin
        </div>
        <div style="font-size:0.85rem;margin-top:10px;color:#475569;">
            ComplyKrawl will crawl the site, extract documents, fetch live regulatory circulars,<br>
            and run AI-powered compliance analysis — all in one click.
        </div>
    </div>
    """, unsafe_allow_html=True)
