#!/usr/bin/env python3
"""
audit.py — SEO/AEO site auditor.

Crawls a site via sitemap (or homepage fallback), samples one representative URL
per template, fetches with httpx with a Playwright fallback for SPA shells,
parses meta/schema/headings/content, detects the framework, scores SEO and AEO,
and emits findings.json + screenshots/ for a Claude skill to synthesize into a
report.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import click
import httpx
import tldextract
from bs4 import BeautifulSoup

try:
    import extruct
    EXTRUCT_AVAILABLE = True
except ImportError:
    EXTRUCT_AVAILABLE = False

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


USER_AGENT = "Mozilla/5.0 (compatible; SEOAuditBot/1.0)"

AI_CRAWLERS = [
    "GPTBot", "ChatGPT-User", "OAI-SearchBot",
    "ClaudeBot", "Claude-Web", "anthropic-ai",
    "PerplexityBot", "Perplexity-User",
    "CCBot",
    "Google-Extended",
    "Applebot-Extended",
    "Bytespider",
    "Amazonbot",
    "cohere-ai",
    "Diffbot",
    "DuckAssistBot",
    "PetalBot",
    "YouBot",
]

TEMPLATE_PATTERNS: list[tuple[str, str]] = [
    ("home", r"^/?$"),
    ("blog_index", r"^/(blog|articles|posts|insights|learn)/?$"),
    ("blog_post", r"^/(blog|articles|posts|insights|learn)/[^/]+/?$"),
    ("category", r"^/(categor(y|ies)|tags?|topics?)/[^/]+/?$"),
    ("pricing", r"^/pricing/?$"),
    ("platform", r"^/platform/[^/]+/?$"),
    ("product", r"^/(products?|features)(/[^/]+)?/?$"),
    ("tool", r"^/tools?/[^/]+/?$"),
    ("integration", r"^/integrations?/[^/]+/?$"),
    ("use_case", r"^/(for|solutions|use-cases)/[^/]+/?$"),
    ("about", r"^/about(/[^/]+)?/?$"),
    ("contact", r"^/contact(-us)?/?$"),
    ("careers", r"^/(careers?|jobs)/?$"),
    ("docs", r"^/(docs?|documentation|guides?)/.+"),
    ("resources", r"^/(resources?|help|support)(/.+)?/?$"),
    ("legal", r"^/(privacy|terms|legal|cookies?|security)/?$"),
    ("updates", r"^/(updates?|changelog|releases|news)(/.+)?/?$"),
]

FRAMEWORK_SIGNATURES: list[tuple[str, list[str]]] = [
    ("nextjs", [r"/_next/static/", r"__NEXT_DATA__"]),
    ("astro", [r"astro-island", r"astro-slot", r'data-astro-']),
    ("nuxt", [r"__NUXT__", r"/_nuxt/"]),
    ("sveltekit", [r"__sveltekit", r"/_app/immutable/"]),
    ("gatsby", [r"___gatsby", r"/page-data/"]),
    ("remix", [r"window\.__remixContext", r'data-remix-']),
    ("wordpress", [r"/wp-content/", r"/wp-includes/", r'name="generator"\s+content="WordPress']),
    ("shopify", [r"cdn\.shopify\.com", r"shopify-features"]),
    ("hubspot", [r"hs-scripts\.com", r"cdn2\.hubspot\.net"]),
    ("webflow", [r"webflow\.com/js", r"w-webflow"]),
    ("squarespace", [r"squarespace\.com", r"squarespace-cdn"]),
    ("wix", [r"wix\.com", r"wixstatic\.com"]),
]

QUESTION_STARTERS = re.compile(
    r"^\s*(what|how|why|when|where|who|which|can|do|does|is|are|should|will)\b",
    re.IGNORECASE,
)


# ---------- Data classes ----------


@dataclass
class PageData:
    url: str
    template: str = "unknown"
    status: int = 0
    rendered: bool = False
    fetch_error: Optional[str] = None
    html_size: int = 0
    final_url: Optional[str] = None
    redirect_count: int = 0

    # Head
    title: Optional[str] = None
    meta_description: Optional[str] = None
    canonical: Optional[str] = None
    lang: Optional[str] = None
    robots: Optional[str] = None
    viewport: Optional[str] = None
    charset: Optional[str] = None
    favicon: bool = False
    manifest: bool = False
    theme_color: Optional[str] = None
    hreflang: list[dict[str, str]] = field(default_factory=list)

    # Social
    og: dict[str, str] = field(default_factory=dict)
    twitter: dict[str, str] = field(default_factory=dict)

    # Content
    h1_count: int = 0
    h1_text: list[str] = field(default_factory=list)
    heading_tree: list[tuple[int, str]] = field(default_factory=list)
    word_count: int = 0
    image_count: int = 0
    image_missing_alt: int = 0
    internal_links: int = 0
    external_links: int = 0
    nofollow_links: int = 0

    # AEO
    jsonld_raw: list[dict[str, Any]] = field(default_factory=list)
    schema_types: list[str] = field(default_factory=list)
    organization_depth: dict[str, bool] = field(default_factory=dict)
    faq_detected_in_content: bool = False
    faqpage_schema: bool = False
    howto_schema: bool = False
    speakable_schema: bool = False
    breadcrumb_schema: bool = False
    author_schema: bool = False
    direct_answer_words: int = 0
    toc_detected: bool = False
    question_headings: int = 0
    wikidata_referenced: bool = False
    date_modified: Optional[str] = None
    date_published: Optional[str] = None

    # Framework
    framework: Optional[str] = None
    was_spa_shell: bool = False

    # Playwright metrics
    screenshot_desktop: Optional[str] = None
    screenshot_mobile: Optional[str] = None
    lcp_ms: Optional[float] = None
    fcp_ms: Optional[float] = None
    cls: Optional[float] = None
    page_weight_kb: Optional[float] = None
    resource_count: Optional[int] = None


@dataclass
class Finding:
    id: str
    severity: str
    category: str
    template: Optional[str]
    affected_urls: list[str]
    evidence: str
    why: str
    recommendation: str
    framework_fix_key: Optional[str] = None
    impact_score: int = 5


# ---------- URL discovery ----------


def norm_url(u: str, base: str) -> str:
    """Normalize URL: absolute, strip fragment, strip trailing slash (except root)."""
    if not u:
        return ""
    absolute = urljoin(base, u.strip())
    parsed = urlparse(absolute)
    if not parsed.scheme.startswith("http"):
        return ""
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def classify_template(url: str) -> str:
    path = urlparse(url).path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    for name, pattern in TEMPLATE_PATTERNS:
        if re.match(pattern, path):
            return name
    depth = path.count("/")
    if depth <= 1:
        return "top_level"
    return "other"


async def fetch_text(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        r = await client.get(url, follow_redirects=True)
        if r.status_code == 200:
            return r.text
    except Exception:
        return None
    return None


async def fetch_robots(client: httpx.AsyncClient, base: str) -> dict[str, Any]:
    robots_url = urljoin(base, "/robots.txt")
    text = await fetch_text(client, robots_url)
    result = {
        "url": robots_url,
        "present": text is not None,
        "text": text or "",
        "sitemap_urls": [],
        "ai_crawler_policy": {},
        "has_llms_txt": False,
    }
    if text:
        for line in text.splitlines():
            line = line.strip()
            if line.lower().startswith("sitemap:"):
                sm = line.split(":", 1)[1].strip()
                result["sitemap_urls"].append(sm)
        # Parse per-agent directives (simplified)
        current_agents: list[str] = []
        for line in text.splitlines():
            ls = line.strip()
            if not ls or ls.startswith("#"):
                continue
            if ls.lower().startswith("user-agent:"):
                agent = ls.split(":", 1)[1].strip()
                if agent == "*":
                    current_agents = ["*"]
                else:
                    current_agents.append(agent)
            elif ls.lower().startswith("disallow:"):
                path = ls.split(":", 1)[1].strip()
                for a in current_agents:
                    result["ai_crawler_policy"].setdefault(a, {"disallow": [], "allow": []})
                    result["ai_crawler_policy"][a]["disallow"].append(path)
            elif ls.lower().startswith("allow:"):
                path = ls.split(":", 1)[1].strip()
                for a in current_agents:
                    result["ai_crawler_policy"].setdefault(a, {"disallow": [], "allow": []})
                    result["ai_crawler_policy"][a]["allow"].append(path)
            else:
                current_agents = []
    # llms.txt
    llms_text = await fetch_text(client, urljoin(base, "/llms.txt"))
    result["has_llms_txt"] = llms_text is not None
    return result


async def fetch_sitemap(client: httpx.AsyncClient, sitemap_url: str, seen: set[str]) -> list[str]:
    if sitemap_url in seen:
        return []
    seen.add(sitemap_url)
    text = await fetch_text(client, sitemap_url)
    if not text:
        return []
    urls: list[str] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    # Sitemap index
    for sm in root.findall(".//sm:sitemap/sm:loc", ns):
        if sm.text:
            urls.extend(await fetch_sitemap(client, sm.text.strip(), seen))
    # URL set
    for loc in root.findall(".//sm:url/sm:loc", ns):
        if loc.text:
            urls.append(loc.text.strip())
    return urls


async def discover_urls(client: httpx.AsyncClient, base_url: str, robots: dict[str, Any]) -> list[str]:
    """Discover candidate URLs from sitemap first, then homepage fallback."""
    urls: list[str] = []
    for sm_url in robots.get("sitemap_urls", []):
        urls.extend(await fetch_sitemap(client, sm_url, set()))
    if not urls:
        # Try common sitemap paths
        for candidate in ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"]:
            urls.extend(await fetch_sitemap(client, urljoin(base_url, candidate), set()))
    if not urls:
        # Homepage BFS fallback — scrape homepage anchors
        html = await fetch_text(client, base_url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            base_host = urlparse(base_url).netloc
            for a in soup.find_all("a", href=True):
                candidate = norm_url(a["href"], base_url)
                if candidate and urlparse(candidate).netloc == base_host:
                    urls.append(candidate)
    # Filter to same hostname + dedupe
    base_host = urlparse(base_url).netloc
    seen: set[str] = set()
    clean: list[str] = []
    for u in urls:
        nu = norm_url(u, base_url)
        if not nu:
            continue
        if urlparse(nu).netloc != base_host:
            continue
        if nu in seen:
            continue
        seen.add(nu)
        clean.append(nu)
    return clean


def sample_by_template(urls: list[str], base_url: str, max_pages: int) -> dict[str, str]:
    """Return {template: representative_url}. Always include home."""
    by_template: dict[str, list[str]] = {}
    for u in urls:
        t = classify_template(u)
        by_template.setdefault(t, []).append(u)
    # Force home in
    home = norm_url("/", base_url)
    by_template.setdefault("home", []).insert(0, home)
    # Pick one per template (shortest URL — usually the canonical example)
    sample: dict[str, str] = {}
    for t, candidates in by_template.items():
        candidates_sorted = sorted(set(candidates), key=lambda x: (len(x), x))
        sample[t] = candidates_sorted[0]
    # Priority order — keep the most SEO-important templates first
    priority = [
        "home", "pricing", "product", "platform", "blog_index", "blog_post",
        "tool", "integration", "use_case", "about", "docs", "category",
        "resources", "top_level", "contact", "updates", "other", "legal", "careers",
    ]
    ordered: dict[str, str] = {}
    for p in priority:
        if p in sample:
            ordered[p] = sample[p]
    for t, u in sample.items():
        if t not in ordered:
            ordered[t] = u
    # Truncate
    truncated = dict(list(ordered.items())[:max_pages])
    return truncated


# ---------- Fetch + render ----------


def is_spa_shell(html: str) -> bool:
    if not html or len(html) < 1000:
        return True
    soup = BeautifulSoup(html, "html.parser")
    # Empty main containers
    for div_id in ("root", "app", "__next", "__nuxt", "svelte"):
        el = soup.find(id=div_id)
        if el is not None and len(el.get_text(strip=True)) < 50:
            return True
    # Very low body word count
    body_text = soup.body.get_text(" ", strip=True) if soup.body else ""
    if len(body_text.split()) < 100:
        return True
    return False


async def fetch_and_maybe_render(
    url: str,
    client: httpx.AsyncClient,
    render_enabled: bool,
    screenshot_dir: Path,
    template: str,
    browser_name: str = "chromium",
) -> tuple[str, dict[str, Any]]:
    """Returns (html, meta). meta has: rendered, status, lcp_ms, screenshot paths, etc."""
    meta: dict[str, Any] = {
        "rendered": False, "status": 0, "fetch_error": None,
        "screenshot_desktop": None, "screenshot_mobile": None,
        "lcp_ms": None, "fcp_ms": None, "cls": None,
        "page_weight_kb": None, "resource_count": None,
        "final_url": url, "redirect_count": 0,
    }
    html = ""
    try:
        r = await client.get(url, follow_redirects=True)
        meta["status"] = r.status_code
        meta["final_url"] = str(r.url)
        meta["redirect_count"] = len(r.history)
        html = r.text
    except Exception as e:
        meta["fetch_error"] = str(e)[:200]
    if not render_enabled or not PLAYWRIGHT_AVAILABLE:
        return html, meta
    if not is_spa_shell(html) and meta["status"] == 200:
        # Still take a screenshot for the key templates so Claude can judge design
        if template in ("home", "pricing", "blog_post", "product", "platform"):
            try:
                html, shot_meta = await render_with_playwright(url, screenshot_dir, template, browser_name)
                meta.update(shot_meta)
                meta["rendered"] = True
            except Exception as e:
                meta["fetch_error"] = (meta.get("fetch_error") or "") + f" | render: {e}"[:200]
        return html, meta
    # SPA shell — render required
    try:
        rendered_html, shot_meta = await render_with_playwright(url, screenshot_dir, template, browser_name)
        html = rendered_html
        meta.update(shot_meta)
        meta["rendered"] = True
    except Exception as e:
        meta["fetch_error"] = (meta.get("fetch_error") or "") + f" | render: {e}"[:200]
    return html, meta


async def pick_browser(preferred: str) -> Optional[str]:
    """Probe installed Playwright browsers. preferred='auto' tries chromium→firefox→webkit.
    Returns the browser name that works, or None if none are installed.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    order: list[str]
    if preferred == "auto":
        order = ["chromium", "firefox", "webkit"]
    else:
        order = [preferred]
    async with async_playwright() as pw:
        for name in order:
            try:
                bt = getattr(pw, name)
                b = await bt.launch(headless=True)
                await b.close()
                return name
            except Exception:
                continue
    return None


async def render_with_playwright(
    url: str, screenshot_dir: Path, template: str, browser_name: str = "chromium"
) -> tuple[str, dict[str, Any]]:
    meta: dict[str, Any] = {}
    async with async_playwright() as pw:
        browser_type = getattr(pw, browser_name)
        browser = await browser_type.launch(headless=True)
        try:
            # Desktop pass (also captures HTML + metrics)
            ctx = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=USER_AGENT,
            )
            page = await ctx.new_page()
            resources: list[dict[str, Any]] = []
            page.on("response", lambda r: resources.append({
                "url": r.url,
                "size": int(r.headers.get("content-length", 0) or 0),
            }))
            try:
                await page.goto(url, wait_until="networkidle", timeout=15000)
            except Exception:
                # Fall back to load instead of networkidle
                await page.goto(url, wait_until="load", timeout=15000)
            html = await page.content()
            # Perf metrics
            try:
                perf = await page.evaluate("""() => {
                    const pe = performance.getEntriesByType('paint');
                    const fcp = pe.find(e => e.name === 'first-contentful-paint');
                    return {
                        fcp_ms: fcp ? fcp.startTime : null,
                        nav: (() => {
                            const nav = performance.getEntriesByType('navigation')[0];
                            return nav ? {loadEventEnd: nav.loadEventEnd, domContentLoaded: nav.domContentLoadedEventEnd} : null;
                        })(),
                    };
                }""")
                meta["fcp_ms"] = perf.get("fcp_ms")
            except Exception:
                pass
            total_bytes = sum(r["size"] for r in resources if r["size"])
            meta["page_weight_kb"] = round(total_bytes / 1024, 1) if total_bytes else None
            meta["resource_count"] = len(resources) or None
            # Screenshot (full-page desktop)
            safe = re.sub(r"[^a-zA-Z0-9._-]", "-", template)[:40]
            shot_d = screenshot_dir / f"{safe}-desktop.png"
            try:
                await page.screenshot(path=str(shot_d), full_page=False)
                meta["screenshot_desktop"] = str(shot_d.relative_to(screenshot_dir.parent))
            except Exception:
                pass
            await ctx.close()
            # Mobile pass (screenshot only)
            ctx_m = await browser.new_context(
                viewport={"width": 390, "height": 844},
                user_agent=(
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
                ),
                device_scale_factor=3,
                is_mobile=True,
                has_touch=True,
            )
            page_m = await ctx_m.new_page()
            try:
                await page_m.goto(url, wait_until="load", timeout=12000)
                shot_m = screenshot_dir / f"{safe}-mobile.png"
                await page_m.screenshot(path=str(shot_m), full_page=False)
                meta["screenshot_mobile"] = str(shot_m.relative_to(screenshot_dir.parent))
            except Exception:
                pass
            await ctx_m.close()
        finally:
            await browser.close()
    return html, meta


# ---------- Parse ----------


def parse_page(url: str, html: str, template: str, meta: dict[str, Any]) -> PageData:
    p = PageData(url=url, template=template)
    p.status = meta.get("status", 0)
    p.rendered = meta.get("rendered", False)
    p.fetch_error = meta.get("fetch_error")
    p.html_size = len(html or "")
    p.final_url = meta.get("final_url") or url
    p.redirect_count = meta.get("redirect_count", 0)
    p.screenshot_desktop = meta.get("screenshot_desktop")
    p.screenshot_mobile = meta.get("screenshot_mobile")
    p.lcp_ms = meta.get("lcp_ms")
    p.fcp_ms = meta.get("fcp_ms")
    p.cls = meta.get("cls")
    p.page_weight_kb = meta.get("page_weight_kb")
    p.resource_count = meta.get("resource_count")

    if not html:
        return p

    p.was_spa_shell = is_spa_shell(html)
    soup = BeautifulSoup(html, "html.parser")

    # <html lang>, charset, viewport, title
    html_tag = soup.find("html")
    if html_tag:
        p.lang = html_tag.get("lang")
    title_tag = soup.find("title")
    if title_tag and title_tag.text:
        p.title = title_tag.text.strip()
    meta_charset = soup.find("meta", attrs={"charset": True})
    if meta_charset:
        p.charset = meta_charset.get("charset")
    meta_viewport = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
    if meta_viewport:
        p.viewport = meta_viewport.get("content")
    meta_desc = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if meta_desc:
        p.meta_description = meta_desc.get("content")
    meta_robots = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    if meta_robots:
        p.robots = meta_robots.get("content")
    meta_theme = soup.find("meta", attrs={"name": re.compile("^theme-color$", re.I)})
    if meta_theme:
        p.theme_color = meta_theme.get("content")

    # Canonical
    canon = soup.find("link", rel=lambda v: v and "canonical" in v)
    if canon:
        p.canonical = (canon.get("href") or "").strip() or None

    # Hreflang
    for alt in soup.find_all("link", rel=lambda v: v and "alternate" in v):
        hl = alt.get("hreflang")
        href = alt.get("href")
        if hl and href:
            p.hreflang.append({"hreflang": hl, "href": href})

    # Favicon + manifest
    p.favicon = bool(soup.find("link", rel=lambda v: v and "icon" in v))
    p.manifest = bool(soup.find("link", rel=lambda v: v and "manifest" in v))

    # Open Graph + Twitter
    for m in soup.find_all("meta"):
        prop = m.get("property", "")
        name = m.get("name", "")
        content = m.get("content", "")
        if not content:
            continue
        if prop.startswith("og:"):
            p.og[prop[3:]] = content
        elif name.startswith("twitter:"):
            p.twitter[name[8:]] = content

    # Headings
    h1s = soup.find_all("h1")
    p.h1_count = len(h1s)
    p.h1_text = [h.get_text(" ", strip=True) for h in h1s][:5]
    for lvl in range(1, 5):
        for h in soup.find_all(f"h{lvl}"):
            txt = h.get_text(" ", strip=True)
            if txt:
                p.heading_tree.append((lvl, txt[:200]))

    # Question-format headings (good for AEO / FAQ auto-extraction)
    p.question_headings = sum(
        1 for (_, t) in p.heading_tree
        if t.rstrip().endswith("?") or QUESTION_STARTERS.match(t)
    )

    # FAQ detected in content = 3+ question-headings in document body
    p.faq_detected_in_content = p.question_headings >= 3

    # JSON-LD extraction MUST happen before the decompose below, which strips all
    # <script> tags from the soup for word-count hygiene — including ld+json.
    ld_blocks = soup.find_all("script", type=lambda v: v and "ld+json" in v)
    for s in ld_blocks:
        try:
            raw = s.string or s.text or ""
            if not raw.strip():
                continue
            data = json.loads(raw)
            if isinstance(data, list):
                for d in data:
                    p.jsonld_raw.append(d)
            else:
                p.jsonld_raw.append(data)
        except Exception:
            continue

    # Walk JSON-LD for schema types + key fields
    def walk(obj: Any, found_types: set[str]) -> None:
        if isinstance(obj, dict):
            t = obj.get("@type")
            if isinstance(t, str):
                found_types.add(t)
            elif isinstance(t, list):
                for x in t:
                    if isinstance(x, str):
                        found_types.add(x)
            for v in obj.values():
                walk(v, found_types)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, found_types)

    types: set[str] = set()
    walk(p.jsonld_raw, types)
    p.schema_types = sorted(types)
    p.faqpage_schema = "FAQPage" in types
    p.howto_schema = "HowTo" in types
    p.speakable_schema = "SpeakableSpecification" in types or any(
        "speakable" in str(k).lower() for k in json.dumps(p.jsonld_raw).split()
    )
    p.breadcrumb_schema = "BreadcrumbList" in types
    p.author_schema = "Person" in types and any(
        self_has_author(d) for d in p.jsonld_raw
    )

    # Organization depth
    org = find_schema_node(p.jsonld_raw, "Organization")
    if org:
        p.organization_depth = {
            "founder": bool(org.get("founder")),
            "sameAs": bool(org.get("sameAs")),
            "knowsAbout": bool(org.get("knowsAbout")),
            "slogan": bool(org.get("slogan")),
            "foundingDate": bool(org.get("foundingDate")),
            "contactPoint": bool(org.get("contactPoint")),
            "hasOfferCatalog": bool(org.get("hasOfferCatalog")),
            "logo": bool(org.get("logo")),
        }
        sames = org.get("sameAs") or []
        if isinstance(sames, list):
            p.wikidata_referenced = any("wikidata.org" in str(s) for s in sames)

    # dateModified / datePublished
    article = find_schema_node(p.jsonld_raw, "BlogPosting") or find_schema_node(p.jsonld_raw, "Article")
    if article:
        p.date_published = article.get("datePublished")
        p.date_modified = article.get("dateModified")

    # Content text + word count (exclude nav/footer/script/style)
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    body_text = soup.get_text(" ", strip=True)
    p.word_count = len(body_text.split())

    # Direct-answer proxy: first <p> inside <article> or <main> or first visible <p>
    container = soup.find("article") or soup.find("main") or soup.body
    if container:
        first_p = container.find("p")
        if first_p:
            p.direct_answer_words = len(first_p.get_text(" ", strip=True).split())

    # TOC detection: look for nav/list of internal anchors near top
    for nav in soup.find_all(["nav", "ul", "ol"], limit=10):
        anchors = nav.find_all("a", href=lambda h: h and h.startswith("#"))
        if len(anchors) >= 3:
            p.toc_detected = True
            break

    # Images
    imgs = soup.find_all("img")
    p.image_count = len(imgs)
    p.image_missing_alt = sum(1 for i in imgs if not i.get("alt") and i.get("alt") != "")

    # Links
    base_host = urlparse(url).netloc
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if h.startswith("#") or h.startswith("mailto:") or h.startswith("tel:"):
            continue
        full = urljoin(url, h)
        host = urlparse(full).netloc
        if host == base_host:
            p.internal_links += 1
        else:
            p.external_links += 1
        rel = " ".join(a.get("rel") or [])
        if "nofollow" in rel:
            p.nofollow_links += 1

    # Framework signature detection (single-page hint; aggregated later)
    for fw_name, sigs in FRAMEWORK_SIGNATURES:
        if any(re.search(sig, html) for sig in sigs):
            p.framework = fw_name
            break

    return p


def self_has_author(d: Any) -> bool:
    if isinstance(d, dict):
        if "author" in d:
            return True
        for v in d.values():
            if self_has_author(v):
                return True
    elif isinstance(d, list):
        return any(self_has_author(x) for x in d)
    return False


def find_schema_node(jsonld: list[Any], schema_type: str) -> Optional[dict[str, Any]]:
    """Return the first dict in jsonld with @type == schema_type (recursive)."""
    def rec(obj: Any) -> Optional[dict[str, Any]]:
        if isinstance(obj, dict):
            t = obj.get("@type")
            if t == schema_type or (isinstance(t, list) and schema_type in t):
                return obj
            for v in obj.values():
                found = rec(v)
                if found:
                    return found
        elif isinstance(obj, list):
            for v in obj:
                found = rec(v)
                if found:
                    return found
        return None
    return rec(jsonld)


# ---------- Framework aggregation ----------


def aggregate_framework(pages: list[PageData]) -> str:
    counts: dict[str, int] = {}
    for p in pages:
        if p.framework:
            counts[p.framework] = counts.get(p.framework, 0) + 1
    if not counts:
        return "unknown"
    return max(counts.items(), key=lambda kv: kv[1])[0]


# ---------- Findings ----------


def build_findings(
    base_url: str,
    pages: list[PageData],
    robots: dict[str, Any],
) -> list[Finding]:
    findings: list[Finding] = []
    all_urls = [p.url for p in pages]

    # --- Sitemap + robots ---
    if not robots.get("present"):
        findings.append(Finding(
            id="seo.robots.missing",
            severity="high", category="seo", template=None, affected_urls=[base_url],
            evidence="No /robots.txt served.",
            why="robots.txt is how crawlers discover allowed paths and the sitemap. Missing it forces heuristics and slows indexing.",
            recommendation="Serve /robots.txt with Sitemap: directive and explicit User-agent rules.",
            framework_fix_key="robots.missing", impact_score=7,
        ))
    if not robots.get("sitemap_urls"):
        findings.append(Finding(
            id="seo.sitemap.missing",
            severity="high", category="seo", template=None, affected_urls=[base_url],
            evidence="No sitemap referenced in robots.txt and none found at common paths.",
            why="Sitemaps accelerate indexation and signal canonical URL set.",
            recommendation="Publish /sitemap.xml (or /sitemap-index.xml) and add Sitemap: line to robots.txt.",
            framework_fix_key="sitemap.missing", impact_score=7,
        ))

    # --- AI crawler policy ---
    star_policy = robots.get("ai_crawler_policy", {}).get("*", {"disallow": []})
    star_disallows = star_policy.get("disallow", [])
    global_blocks_all = "/" in star_disallows
    blocked_ai = []
    for bot in AI_CRAWLERS:
        policy = robots.get("ai_crawler_policy", {}).get(bot)
        if policy and "/" in policy.get("disallow", []):
            blocked_ai.append(bot)
    if blocked_ai:
        findings.append(Finding(
            id="aeo.ai_crawlers.blocked",
            severity="high", category="aeo", template=None, affected_urls=[base_url],
            evidence=f"robots.txt explicitly disallows: {', '.join(blocked_ai)}",
            why="Blocked AI crawlers cannot index your content for answer-engine surfaces (ChatGPT, Perplexity, Claude, Google AI Overview). You vanish from AI-mediated discovery.",
            recommendation=f"Review robots.txt: intentionally block only what you must. Allow {', '.join(AI_CRAWLERS[:6])} unless content is proprietary.",
            framework_fix_key="ai_crawlers.blocked", impact_score=9,
        ))
    if not robots.get("has_llms_txt"):
        findings.append(Finding(
            id="aeo.llms_txt.missing",
            severity="medium", category="aeo", template=None, affected_urls=[base_url],
            evidence="No /llms.txt served.",
            why="llms.txt is an emerging convention for AI crawlers — a curated index of your most important content for LLM consumption. Early signal of AEO maturity.",
            recommendation="Publish /llms.txt listing primary pages (home, pricing, docs, product) for AI-specific discovery.",
            framework_fix_key="llms_txt.missing", impact_score=5,
        ))

    # --- Per-page + per-template aggregates ---
    by_tpl: dict[str, list[PageData]] = {}
    for p in pages:
        by_tpl.setdefault(p.template, []).append(p)

    # Title + meta description rules
    title_issues: dict[str, list[str]] = {"missing": [], "short": [], "long": []}
    meta_issues: dict[str, list[str]] = {"missing": [], "short": [], "long": []}
    for p in pages:
        if not p.title:
            title_issues["missing"].append(p.url)
        else:
            tl = len(p.title)
            if tl < 30:
                title_issues["short"].append(p.url)
            elif tl > 70:
                title_issues["long"].append(p.url)
        if not p.meta_description:
            meta_issues["missing"].append(p.url)
        else:
            ml = len(p.meta_description)
            if ml < 120:
                meta_issues["short"].append(p.url)
            elif ml > 160:
                meta_issues["long"].append(p.url)

    if title_issues["missing"]:
        findings.append(Finding(
            id="seo.title.missing",
            severity="critical", category="seo", template=None, affected_urls=title_issues["missing"],
            evidence=f"{len(title_issues['missing'])} page(s) have no <title>.",
            why="Title tag is the single largest on-page ranking signal and the SERP click driver.",
            recommendation="Every page must have a unique 30-70 char title with the primary keyword near the front.",
            framework_fix_key="title.missing", impact_score=10,
        ))
    if title_issues["short"] or title_issues["long"]:
        urls = title_issues["short"] + title_issues["long"]
        findings.append(Finding(
            id="seo.title.length",
            severity="medium", category="seo", template=None, affected_urls=urls,
            evidence=f"{len(urls)} title(s) outside 30-70 char window.",
            why="Titles under 30 chars under-sell; over 70 truncate in SERPs.",
            recommendation="Rewrite to 50-60 chars with primary keyword + value promise.",
            framework_fix_key="title.length", impact_score=5,
        ))
    if meta_issues["missing"]:
        findings.append(Finding(
            id="seo.meta_description.missing",
            severity="high", category="seo", template=None, affected_urls=meta_issues["missing"],
            evidence=f"{len(meta_issues['missing'])} page(s) have no meta description.",
            why="Without a meta description Google auto-generates one — usually lower CTR than a written version.",
            recommendation="120-160 char meta description with primary keyword in first 50 chars and a CTA.",
            framework_fix_key="meta_description.missing", impact_score=7,
        ))
    if meta_issues["short"] or meta_issues["long"]:
        urls = meta_issues["short"] + meta_issues["long"]
        findings.append(Finding(
            id="seo.meta_description.length",
            severity="low", category="seo", template=None, affected_urls=urls,
            evidence=f"{len(urls)} meta description(s) outside 120-160 window.",
            why="Short descriptions under-sell; long ones truncate in SERPs.",
            recommendation="Rewrite to 140-155 chars.",
            framework_fix_key="meta_description.length", impact_score=3,
        ))

    # Canonical
    canon_missing = [p.url for p in pages if not p.canonical]
    if canon_missing:
        findings.append(Finding(
            id="seo.canonical.missing",
            severity="high", category="seo", template=None, affected_urls=canon_missing,
            evidence=f"{len(canon_missing)} page(s) missing <link rel=canonical>.",
            why="Without canonicals, duplicate content via filters, UTMs, or pagination dilutes ranking signals.",
            recommendation="Add self-referential absolute canonical URL in <head> of every indexable page.",
            framework_fix_key="canonical.missing", impact_score=8,
        ))

    # H1
    h1_issues = [p.url for p in pages if p.h1_count != 1]
    if h1_issues:
        findings.append(Finding(
            id="seo.h1.count",
            severity="medium", category="seo", template=None, affected_urls=h1_issues,
            evidence=f"{len(h1_issues)} page(s) with 0 or >1 H1.",
            why="Exactly one H1 per page clarifies the primary topic for crawlers and assistive tech.",
            recommendation="Use exactly one H1 that contains the primary keyword.",
            framework_fix_key="h1.count", impact_score=5,
        ))

    # Open Graph completeness (home + primary templates)
    og_gaps = []
    for p in pages:
        required = {"title", "description", "image", "url", "type"}
        missing = required - set(p.og.keys())
        if missing:
            og_gaps.append((p.url, missing))
    if og_gaps:
        findings.append(Finding(
            id="seo.open_graph.incomplete",
            severity="medium", category="seo", template=None,
            affected_urls=[u for u, _ in og_gaps],
            evidence=f"{len(og_gaps)} page(s) missing OG fields (e.g., {list(og_gaps[0][1])[:3]}).",
            why="Incomplete OG tags produce ugly or truncated previews when shared — direct CTR cost.",
            recommendation="Every page: og:title, og:description, og:image (1200x630), og:url, og:type, og:site_name.",
            framework_fix_key="open_graph.incomplete", impact_score=5,
        ))

    # Image alt
    alt_gaps = [p for p in pages if p.image_count > 0 and p.image_missing_alt / max(1, p.image_count) > 0.2]
    if alt_gaps:
        findings.append(Finding(
            id="seo.images.missing_alt",
            severity="medium", category="seo", template=None,
            affected_urls=[p.url for p in alt_gaps],
            evidence=f"{len(alt_gaps)} page(s) with >20% images missing alt.",
            why="Missing alt hurts accessibility and image search ranking. AI crawlers also use alt as image semantic context.",
            recommendation="Every content image needs alt. Decorative images use alt=\"\" (empty, not missing).",
            framework_fix_key="images.missing_alt", impact_score=4,
        ))

    # --- Schema coverage matrix findings ---
    schema_requirements = {
        "home": ["WebSite", "Organization"],
        "blog_post": ["BlogPosting", "BreadcrumbList"],
        "blog_index": ["Blog", "BreadcrumbList"],
        "pricing": ["Product", "Offer"],
        "product": ["Product"],
        "platform": ["SoftwareApplication"],
        "tool": ["HowTo", "SoftwareApplication"],
        "about": ["AboutPage", "Organization"],
        "docs": ["TechArticle"],
    }
    for tpl, page_list in by_tpl.items():
        required = schema_requirements.get(tpl)
        if not required:
            continue
        # Check all sampled pages in this template
        p0 = page_list[0]
        missing = [t for t in required if t not in p0.schema_types]
        if missing:
            findings.append(Finding(
                id=f"aeo.schema.{tpl}.missing_types",
                severity="high", category="aeo", template=tpl, affected_urls=[p0.url],
                evidence=f"Template '{tpl}' sample missing schema types: {missing}. Found: {p0.schema_types or 'none'}.",
                why="Schema.org markup is how Google, Bing, and AI assistants understand page semantics. Missing types cost rich-result eligibility and AEO visibility.",
                recommendation=f"Add JSON-LD for: {', '.join(missing)} on all {tpl} pages.",
                framework_fix_key=f"schema.{tpl}",
                impact_score=8 if tpl in ("home", "blog_post", "pricing") else 6,
            ))

    # Organization depth (homepage)
    home_pages = [p for p in pages if p.template == "home"]
    if home_pages:
        h = home_pages[0]
        if "Organization" in h.schema_types:
            depth = h.organization_depth
            weak = [k for k, v in depth.items() if not v]
            if weak:
                findings.append(Finding(
                    id="aeo.organization_schema.shallow",
                    severity="medium", category="aeo", template="home", affected_urls=[h.url],
                    evidence=f"Organization schema missing fields: {weak}",
                    why="Deep Organization schema (founder, sameAs w/ Wikidata, knowsAbout, slogan, foundingDate) is the single strongest entity-recognition signal for AI assistants and Google's Knowledge Graph.",
                    recommendation="Fill every field. Priority: sameAs with Wikidata URL, founder[], knowsAbout[], slogan, foundingDate, contactPoint.",
                    framework_fix_key="organization_schema.shallow", impact_score=9,
                ))
            if not h.wikidata_referenced:
                findings.append(Finding(
                    id="aeo.wikidata.unreferenced",
                    severity="high", category="aeo", template="home", affected_urls=[h.url],
                    evidence="Organization.sameAs does not include a wikidata.org URL.",
                    why="A Wikidata entity ID is the highest-confidence cross-reference for AI answer engines. Without it, your brand is a string, not an entity.",
                    recommendation="Create a Wikidata item for your company, then list its URL (https://www.wikidata.org/wiki/Qxxxxxx) in Organization.sameAs.",
                    framework_fix_key="wikidata.unreferenced", impact_score=9,
                ))

    # FAQ detected in content but no FAQPage schema
    faq_missing = [p.url for p in pages if p.faq_detected_in_content and not p.faqpage_schema]
    if faq_missing:
        findings.append(Finding(
            id="aeo.faqpage_schema.missing",
            severity="high", category="aeo", template=None, affected_urls=faq_missing,
            evidence=f"{len(faq_missing)} page(s) have question-format headings but no FAQPage JSON-LD.",
            why="FAQPage schema unlocks rich results in Google, voice answers, and direct citations in AI answer engines.",
            recommendation="Auto-generate FAQPage JSON-LD from question-format H2/H3 headings and their following paragraph.",
            framework_fix_key="faqpage_schema.missing", impact_score=8,
        ))

    # Speakable schema for blog
    blog_pages = [p for p in pages if p.template == "blog_post"]
    if blog_pages and not any(p.speakable_schema for p in blog_pages):
        findings.append(Finding(
            id="aeo.speakable_schema.missing",
            severity="medium", category="aeo", template="blog_post",
            affected_urls=[p.url for p in blog_pages],
            evidence="No SpeakableSpecification on sampled blog posts.",
            why="Speakable schema tells Google Assistant/voice search which excerpts to read aloud. Direct AEO/voice signal.",
            recommendation="Add SpeakableSpecification targeting opening paragraph and first paragraph after H2.",
            framework_fix_key="speakable_schema.missing", impact_score=5,
        ))

    # dateModified freshness
    stale = []
    today = datetime.now(timezone.utc)
    for p in blog_pages:
        dm = p.date_modified or p.date_published
        if not dm:
            continue
        try:
            dt = datetime.fromisoformat(dm.replace("Z", "+00:00"))
            age_days = (today - dt).days
            if age_days > 365:
                stale.append((p.url, age_days))
        except Exception:
            pass
    if stale:
        findings.append(Finding(
            id="aeo.content_freshness.stale",
            severity="low", category="aeo", template="blog_post",
            affected_urls=[u for u, _ in stale],
            evidence=f"{len(stale)} blog post(s) with dateModified >365 days old.",
            why="AI answer engines and Google prefer recent content for query-responsive ranking. Refresh keeps rankings.",
            recommendation="Audit for content refresh. Update dateModified when meaningful edits ship.",
            framework_fix_key="content_freshness.stale", impact_score=4,
        ))

    # Thin content
    thin = [p.url for p in pages if p.template in ("blog_post", "product", "pricing") and p.word_count < 300]
    if thin:
        findings.append(Finding(
            id="seo.content.thin",
            severity="medium", category="seo", template=None, affected_urls=thin,
            evidence=f"{len(thin)} key template page(s) under 300 words.",
            why="Thin content loses to comprehensive competitors and gives AI engines too little to cite.",
            recommendation="Expand to 800+ words (blog 1500+) with real substance, not filler.",
            framework_fix_key="content.thin", impact_score=6,
        ))

    # Direct-answer paragraph (AEO)
    long_intros = [p.url for p in pages if p.template == "blog_post" and p.direct_answer_words > 80]
    if long_intros:
        findings.append(Finding(
            id="aeo.direct_answer.missing",
            severity="medium", category="aeo", template="blog_post", affected_urls=long_intros,
            evidence=f"{len(long_intros)} blog post(s) open with >80-word paragraphs.",
            why="AI answer engines prefer concise direct-answer openings (≤50 words) they can cite verbatim. Long intros bury the answer.",
            recommendation="Lead every post with a ≤50-word direct answer to the implied query. Details after.",
            framework_fix_key="direct_answer.missing", impact_score=6,
        ))

    # TOC (long posts)
    long_no_toc = [p.url for p in pages if p.template == "blog_post" and p.word_count > 1500 and not p.toc_detected]
    if long_no_toc:
        findings.append(Finding(
            id="aeo.toc.missing",
            severity="low", category="aeo", template="blog_post", affected_urls=long_no_toc,
            evidence=f"{len(long_no_toc)} long blog post(s) without a TOC.",
            why="TOC with jump anchors helps AI engines chunk content and surface jump-to-section links in SERPs.",
            recommendation="Auto-generate TOC from H2s with anchor links for posts over 1500 words.",
            framework_fix_key="toc.missing", impact_score=3,
        ))

    # viewport
    no_viewport = [p.url for p in pages if not p.viewport]
    if no_viewport:
        findings.append(Finding(
            id="seo.viewport.missing",
            severity="high", category="seo", template=None, affected_urls=no_viewport,
            evidence=f"{len(no_viewport)} page(s) missing viewport meta.",
            why="Without viewport meta, mobile rendering breaks. Mobile usability is a ranking factor.",
            recommendation='Add <meta name="viewport" content="width=device-width, initial-scale=1">.',
            framework_fix_key="viewport.missing", impact_score=7,
        ))

    # html lang
    no_lang = [p.url for p in pages if not p.lang]
    if no_lang:
        findings.append(Finding(
            id="seo.html_lang.missing",
            severity="medium", category="seo", template=None, affected_urls=no_lang,
            evidence=f"{len(no_lang)} page(s) missing <html lang>.",
            why="lang attribute signals content language to Google and assistive tech.",
            recommendation='Add <html lang="en"> (or the correct BCP 47 code).',
            framework_fix_key="html_lang.missing", impact_score=3,
        ))

    # Redirects
    redirects = [p for p in pages if p.redirect_count > 0]
    if redirects:
        findings.append(Finding(
            id="seo.redirects.chain",
            severity="low" if all(p.redirect_count <= 1 for p in redirects) else "medium",
            category="seo", template=None,
            affected_urls=[p.url for p in redirects],
            evidence=f"{len(redirects)} URL(s) redirect before resolving.",
            why="Redirect chains waste crawl budget and add latency. Each hop = ~100ms added LCP.",
            recommendation="Point links directly to final URL. Limit to 1 redirect max.",
            framework_fix_key="redirects.chain", impact_score=3,
        ))

    # Fetch errors
    errs = [p for p in pages if p.fetch_error or (p.status and p.status >= 400)]
    if errs:
        findings.append(Finding(
            id="seo.fetch.errors",
            severity="high", category="seo", template=None,
            affected_urls=[p.url for p in errs],
            evidence=f"{len(errs)} URL(s) failed to fetch or returned 4xx/5xx.",
            why="Broken pages lose ranking and drop from index.",
            recommendation="Investigate: restore content, 301 to equivalent, or de-list from sitemap.",
            framework_fix_key="fetch.errors", impact_score=9,
        ))

    # Sort by impact desc
    findings.sort(key=lambda f: (-f.impact_score, f.severity))
    return findings


# ---------- Scoring ----------


SEVERITY_WEIGHTS = {"critical": 20, "high": 10, "medium": 5, "low": 2}


def score_category(findings: list[Finding], category: str) -> int:
    penalty = sum(SEVERITY_WEIGHTS.get(f.severity, 0) for f in findings if f.category == category)
    return max(0, 100 - penalty)


# ---------- Schema matrix ----------


def build_schema_matrix(pages: list[PageData]) -> dict[str, dict[str, bool]]:
    target_types = [
        "WebSite", "Organization", "BreadcrumbList",
        "BlogPosting", "Article", "FAQPage", "HowTo",
        "Product", "Offer", "SoftwareApplication",
        "SpeakableSpecification", "Person",
    ]
    matrix: dict[str, dict[str, bool]] = {}
    by_tpl: dict[str, list[PageData]] = {}
    for p in pages:
        by_tpl.setdefault(p.template, []).append(p)
    for tpl, page_list in by_tpl.items():
        combined_types: set[str] = set()
        for p in page_list:
            combined_types.update(p.schema_types)
        matrix[tpl] = {t: t in combined_types for t in target_types}
    return matrix


# ---------- Main orchestration ----------


async def run_audit(
    base_url: str,
    out_dir: Path,
    max_pages: int,
    render_enabled: bool,
    focus: str,
    browser_pref: str = "auto",
) -> None:
    started = datetime.now(timezone.utc)
    parsed = urlparse(base_url)
    if not parsed.scheme:
        base_url = "https://" + base_url
        parsed = urlparse(base_url)

    ext = tldextract.extract(base_url)
    domain = ".".join([p for p in [ext.subdomain, ext.domain, ext.suffix] if p])
    date_str = started.strftime("%Y-%m-%d")

    run_dir = out_dir / domain / date_str
    screenshot_dir = run_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    browser_name: Optional[str] = None
    if render_enabled and PLAYWRIGHT_AVAILABLE:
        browser_name = await pick_browser(browser_pref)
        if browser_name:
            print(f"[0/5] Browser: {browser_name} (preference: {browser_pref})", file=sys.stderr)
        else:
            print(f"[0/5] No Playwright browser available (preference: {browser_pref}). "
                  f"Falling back to httpx-only.", file=sys.stderr)
            render_enabled = False

    print(f"[1/5] Discovering URLs on {base_url}", file=sys.stderr)
    timeout = httpx.Timeout(15.0, connect=10.0)
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True, http2=False) as client:
        robots = await fetch_robots(client, base_url)
        all_urls = await discover_urls(client, base_url, robots)
        print(f"      Found {len(all_urls)} URLs (sitemap + homepage crawl)", file=sys.stderr)

        samples = sample_by_template(all_urls, base_url, max_pages)
        print(f"[2/5] Sampling {len(samples)} templates: {list(samples.keys())}", file=sys.stderr)

        print(f"[3/5] Fetching (+ Playwright fallback: {render_enabled and PLAYWRIGHT_AVAILABLE})", file=sys.stderr)
        pages: list[PageData] = []
        for i, (tpl, url) in enumerate(samples.items(), 1):
            print(f"      [{i}/{len(samples)}] {tpl}: {url}", file=sys.stderr)
            html, meta = await fetch_and_maybe_render(
                url, client, render_enabled, screenshot_dir, tpl,
                browser_name or "chromium",
            )
            pg = parse_page(url, html, tpl, meta)
            pages.append(pg)

    framework = aggregate_framework(pages)
    print(f"[4/5] Framework detected: {framework}", file=sys.stderr)

    findings = build_findings(base_url, pages, robots)
    if focus != "all":
        findings = [f for f in findings if f.category == focus]

    schema_matrix = build_schema_matrix(pages)

    run_meta = {
        "url": base_url,
        "date": date_str,
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "pages_sampled": len(pages),
        "framework_detected": framework,
        "render_enabled": render_enabled and PLAYWRIGHT_AVAILABLE,
        "playwright_available": PLAYWRIGHT_AVAILABLE,
        "browser_used": browser_name,
        "focus": focus,
        "scores": {
            "seo": score_category(findings, "seo"),
            "aeo": score_category(findings, "aeo"),
            "strategic": None,  # Claude fills this
        },
        "robots": {
            "present": robots["present"],
            "sitemap_urls": robots["sitemap_urls"],
            "has_llms_txt": robots["has_llms_txt"],
            "ai_crawler_policy_sample": {
                k: v for k, v in list(robots.get("ai_crawler_policy", {}).items())[:20]
            },
        },
    }

    findings_out = {
        "run": run_meta,
        "findings": [asdict(f) for f in findings],
        "templates": {p.template: p.url for p in pages},
        "schema_matrix": schema_matrix,
    }

    pages_out = [asdict(p) for p in pages]

    (run_dir / "findings.json").write_text(json.dumps(findings_out, indent=2))
    (run_dir / "pages.json").write_text(json.dumps(pages_out, indent=2))

    print(f"[5/5] Done. Output: {run_dir}", file=sys.stderr)
    print(f"      SEO {run_meta['scores']['seo']}/100  AEO {run_meta['scores']['aeo']}/100  "
          f"Findings: {len(findings)}  Framework: {framework}", file=sys.stderr)


# ---------- CLI ----------


@click.command()
@click.argument("url")
@click.option("--out", "out_dir", default="./audits", help="Output directory (default ./audits)")
@click.option("--max-pages", default=15, type=int, help="Max templates to sample (default 15)")
@click.option("--no-render", is_flag=True, help="Disable Playwright fallback (httpx-only)")
@click.option("--focus", type=click.Choice(["seo", "aeo", "strategic", "all"]), default="all")
@click.option(
    "--browser",
    type=click.Choice(["auto", "chromium", "firefox", "webkit"]),
    default="auto",
    help="Playwright browser to use. 'auto' tries chromium → firefox → webkit (default).",
)
def main(url: str, out_dir: str, max_pages: int, no_render: bool, focus: str, browser: str) -> None:
    """Run an SEO/AEO audit on URL."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    asyncio.run(run_audit(
        base_url=url,
        out_dir=out_path,
        max_pages=max_pages,
        render_enabled=not no_render,
        focus=focus,
        browser_pref=browser,
    ))


if __name__ == "__main__":
    main()
