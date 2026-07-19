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
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# Identify the tool honestly so site owners can recognise (and rate-limit, or allow)
# it in their access logs. A spoofed browser UA is both dishonest and more likely to
# be blocked by WAFs that fingerprint mismatched header sets.
__version__ = "2.0.0"

USER_AGENT = (
    f"Mozilla/5.0 (compatible; seo-aeo-audit/{__version__}; "
    "+https://github.com/openairlabs/seo-aeo-audit)"
)

# Used only for the mobile screenshot pass, where a real mobile UA is needed to get
# the mobile variant of the page. Kept current — a stale OS version is itself a
# fingerprint some CDNs treat as a bot signal.
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1"
)

# AI crawlers split by what blocking them actually costs you.
#
# SEARCH_AI_CRAWLERS fetch pages to answer a user's live query and cite the source.
# Blocking these removes you from AI-mediated discovery — a real visibility loss.
#
# TRAINING_AI_CRAWLERS collect corpora for model training. Blocking them is a
# legitimate content-licensing decision with no direct search cost, so the audit
# reports it without treating it as a problem.
SEARCH_AI_CRAWLERS = [
    "GPTBot", "OAI-SearchBot", "ChatGPT-User",
    "ClaudeBot", "Claude-User",
    "PerplexityBot", "Perplexity-User",
    "Google-Extended",
    "Applebot-Extended",
    "DuckAssistBot",
    "MistralAI-User",
    "YouBot",
]

TRAINING_AI_CRAWLERS = [
    "CCBot",
    "anthropic-ai",
    "cohere-ai",
    "Bytespider",
    "Amazonbot",
    "Meta-ExternalAgent",
    "Google-CloudVertexBot",
    "Diffbot",
    "PetalBot",
    "Omgili",
    "Timpibot",
]

# Schema types Google has retired rich-result support for. Shipping these is not an
# error — the markup is still valid Schema.org — but it earns nothing in search and
# should not be recommended. Date = Google's deprecation announcement.
DEPRECATED_SCHEMA_TYPES: dict[str, str] = {
    "HowTo": "rich results removed September 2023",
    "SpecialAnnouncement": "deprecated July 2025",
    "ClaimReview": "deprecated June 2025",
    "CourseInfo": "deprecated June 2025",
    "EstimatedSalary": "deprecated June 2025",
    "LearningVideo": "deprecated June 2025",
    "VehicleListing": "deprecated June 2025",
}

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
    # Content words present in the raw server HTML, before any JavaScript ran.
    # Compared against word_count to prove (not guess at) client-side rendering.
    raw_word_count: int = 0
    image_count: int = 0
    image_missing_alt: int = 0
    image_formats: dict[str, int] = field(default_factory=dict)
    # Words between one H2/H3 and the next, in document order. Used for passage
    # citability — AI engines cite self-contained chunks, not whole pages.
    section_word_counts: list[int] = field(default_factory=list)
    internal_links: int = 0
    external_links: int = 0
    nofollow_links: int = 0

    # AEO
    jsonld_raw: list[dict[str, Any]] = field(default_factory=list)
    schema_types: list[str] = field(default_factory=list)
    organization_depth: dict[str, bool] = field(default_factory=dict)
    faq_detected_in_content: bool = False
    faqpage_schema: bool = False
    deprecated_schema: list[str] = field(default_factory=list)
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
    # Loose heuristic. Its ONLY job is deciding whether to spend a Playwright
    # render — over-eager on purpose. Never use it to emit a finding.
    was_spa_shell: bool = False
    # Evidence-based: proven client-rendered via a raw-vs-rendered comparison.
    client_rendered: bool = False
    # True when no render happened, so the client-render check could not run.
    csr_check_skipped: bool = False

    # Playwright metrics.
    #
    # These are synthetic lab measurements from a single headless load on one
    # network path. They indicate where a problem is likely; they do not prove
    # what real users experience.
    #
    # INP is deliberately absent. INP measures latency of real user interactions
    # and cannot be produced by a synthetic page load — there is no interaction to
    # measure. Getting it requires field data (CrUX / a RUM script), which is out
    # of scope for this tool. Do not synthesise a value for it.
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


def parse_robots_txt(text: str) -> dict[str, Any]:
    """Parse robots.txt into sitemap URLs and per-user-agent rule groups.

    Consecutive User-agent lines form one group sharing the rules that follow, so
    agents accumulate until the first rule line is seen; only then does the next
    User-agent line start a fresh group. Unrecognised directives (Crawl-delay,
    Sitemap, vendor extensions) must not end a group.

    Agent names are matched case-insensitively per RFC 9309, so keys are stored
    lowercased. Look them up via ai_policy_for() rather than indexing directly.
    """
    sitemap_urls: list[str] = []
    policies: dict[str, dict[str, list[str]]] = {}
    current_agents: list[str] = []
    group_open = False  # True once this group has consumed at least one rule

    for line in text.splitlines():
        ls = line.split("#", 1)[0].strip()
        if not ls or ":" not in ls:
            continue
        field, _, value = ls.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "sitemap":
            if value:
                sitemap_urls.append(value)
        elif field == "user-agent":
            if group_open:
                current_agents = []
                group_open = False
            if value:
                current_agents.append(value.lower())
        elif field in ("disallow", "allow"):
            group_open = True
            for a in current_agents:
                policy = policies.setdefault(a, {"disallow": [], "allow": []})
                policy[field].append(value)

    return {"sitemap_urls": sitemap_urls, "ai_crawler_policy": policies}


async def fetch_robots(client: httpx.AsyncClient, base: str) -> dict[str, Any]:
    robots_url = urljoin(base, "/robots.txt")
    text = await fetch_text(client, robots_url)
    parsed = parse_robots_txt(text or "")
    result = {
        "url": robots_url,
        "present": text is not None,
        "text": text or "",
        "sitemap_urls": parsed["sitemap_urls"],
        "ai_crawler_policy": parsed["ai_crawler_policy"],
        "has_llms_txt": False,
    }
    # llms.txt
    llms_text = await fetch_text(client, urljoin(base, "/llms.txt"))
    result["has_llms_txt"] = llms_text is not None
    return result


def ai_policy_for(robots: dict[str, Any], agent: str) -> dict[str, list[str]]:
    """Look up a user-agent's parsed rules. Names are case-insensitive (RFC 9309)."""
    return robots.get("ai_crawler_policy", {}).get(agent.lower(), {"disallow": [], "allow": []})


def blocks_everything(policy: dict[str, list[str]]) -> bool:
    """True if the group disallows the whole site with no re-allowing rule."""
    return "/" in policy.get("disallow", []) and not policy.get("allow")


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


def content_word_count(html: str) -> int:
    """Word count of meaningful body content, matching how parse_page counts words.

    Chrome/nav/footer and script/style are stripped so the number reflects what a
    non-executing crawler would actually have to work with.
    """
    if not html:
        return 0
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    return len(soup.get_text(" ", strip=True).split())


def has_empty_mount_point(html: str) -> bool:
    """True when raw HTML contains a known empty SPA mount point AND a JS bundle.

    Corroborating evidence only — never sufficient on its own, because a
    server-rendered app can legitimately ship an empty container.
    """
    if not html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    mount_found = False
    for div_id in ("root", "app", "__next", "__nuxt", "svelte"):
        el = soup.find(id=div_id)
        if el is not None and len(el.get_text(strip=True)) < 50:
            mount_found = True
            break
    if not mount_found:
        return False
    return any(s.get("src") for s in soup.find_all("script"))


# Thresholds for the evidence-based client-render determination. Deliberately
# strict: a false `critical` finding discredits the whole report.
CSR_RAW_WORD_CEILING = 40      # raw HTML must be near-empty of prose
CSR_RENDER_MULTIPLE = 5.0      # rendered content must dwarf it
# ...and amount to real content. Kept low because canvas/app-shell SPAs
# (excalidraw.com renders ~84 words of UI chrome) are exactly the case this
# check exists to catch. The multiple above is what does the real work; this
# floor only suppresses noise like 1 word -> 8 words.
CSR_RENDERED_WORD_FLOOR = 30


def detect_client_rendered(raw_word_count: int, final_word_count: int, rendered: bool,
                           empty_mount: bool) -> bool:
    """Prove client-side rendering from a before/after comparison.

    Requires an actual Playwright render — without one there is no "after", so
    nothing can be proven and this returns False. A tiny server-rendered page
    (example.com) has raw == final, so the multiple test fails and it is cleared.
    """
    if not rendered:
        return False
    if final_word_count < CSR_RENDERED_WORD_FLOOR:
        return False
    ceiling = CSR_RAW_WORD_CEILING * 2 if empty_mount else CSR_RAW_WORD_CEILING
    if raw_word_count > ceiling:
        return False
    return final_word_count >= max(raw_word_count, 1) * CSR_RENDER_MULTIPLE


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
        "raw_word_count": 0, "raw_html_size": 0, "raw_empty_mount": False,
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
    # Measure the pre-JavaScript HTML now, before any render can overwrite `html`.
    # This is exactly what a non-executing AI crawler receives.
    meta["raw_word_count"] = content_word_count(html)
    meta["raw_html_size"] = len(html or "")
    meta["raw_empty_mount"] = has_empty_mount_point(html)
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


# Injected before navigation. Records the latest largest-contentful-paint entry and
# the cumulative sum of layout-shift values that were not caused by user input.
# clsSupported distinguishes "no shifts happened" (0.0) from "this browser cannot
# report shifts" (null), which matters because reporting a confident 0 on a browser
# that never measured anything would be a fabricated number.
CWV_INIT_SCRIPT = """
(() => {
  const s = { lcp: null, cls: 0, clsSupported: false };
  window.__seoAuditCWV = s;
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) { s.lcp = e.startTime; }
    }).observe({ type: 'largest-contentful-paint', buffered: true });
  } catch (e) { /* entry type unsupported in this browser */ }
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        if (!e.hadRecentInput) { s.cls += e.value; }
      }
    }).observe({ type: 'layout-shift', buffered: true });
    s.clsSupported = true;
  } catch (e) { /* entry type unsupported in this browser */ }
})();
"""


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
            # Install the CWV observers before any navigation so they are live for
            # the first paint. buffered:true also replays entries that landed
            # before the observer attached. Chromium supports both entry types;
            # firefox/webkit do not, hence the per-observer try — a browser
            # without support leaves the metric null rather than reporting zero.
            await ctx.add_init_script(CWV_INIT_SCRIPT)
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
            # Give late-arriving LCP candidates and layout shifts a moment to land
            # before reading the observers. Cheap, and without it a hero image that
            # decodes just after load is missed.
            try:
                await page.wait_for_timeout(1200)
            except Exception:
                pass
            # Perf metrics. FCP from the paint timeline; LCP and CLS from the
            # PerformanceObservers installed above. No INP — see PageData.
            try:
                perf = await page.evaluate("""() => {
                    const pe = performance.getEntriesByType('paint');
                    const fcp = pe.find(e => e.name === 'first-contentful-paint');
                    const cwv = window.__seoAuditCWV || {};
                    return {
                        fcp_ms: fcp ? fcp.startTime : null,
                        lcp_ms: (typeof cwv.lcp === 'number') ? cwv.lcp : null,
                        cls: cwv.clsSupported ? cwv.cls : null,
                        nav: (() => {
                            const nav = performance.getEntriesByType('navigation')[0];
                            return nav ? {loadEventEnd: nav.loadEventEnd, domContentLoaded: nav.domContentLoadedEventEnd} : null;
                        })(),
                    };
                }""")
                meta["fcp_ms"] = perf.get("fcp_ms")
                meta["lcp_ms"] = perf.get("lcp_ms")
                meta["cls"] = perf.get("cls")
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
                user_agent=MOBILE_USER_AGENT,
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
    p.raw_word_count = meta.get("raw_word_count", 0)
    # Without a render there is no "after" to compare against, so client-side
    # rendering cannot be proven either way.
    p.csr_check_skipped = not p.rendered

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
    p.deprecated_schema = sorted(t for t in types if t in DEPRECATED_SCHEMA_TYPES)
    p.speakable_schema = has_speakable(p.jsonld_raw)
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

    # Before/after comparison: proof of client-side rendering, not a word-count guess.
    p.client_rendered = detect_client_rendered(
        raw_word_count=p.raw_word_count,
        final_word_count=p.word_count,
        rendered=p.rendered,
        empty_mount=bool(meta.get("raw_empty_mount")),
    )

    # Direct-answer proxy: first <p> inside <article> or <main> or first visible <p>
    container = soup.find("article") or soup.find("main") or soup.body
    if container:
        first_p = container.find("p")
        if first_p:
            p.direct_answer_words = len(first_p.get_text(" ", strip=True).split())

        # Section lengths: words from each H2/H3 up to the next heading at the same
        # nesting level. Deterministic and cheap; it under-counts pages that wrap
        # every section in its own <section>, which is why the citability check
        # only fires when there are enough sections to be confident.
        for h in container.find_all(["h2", "h3"]):
            words = 0
            for sib in h.next_siblings:
                if getattr(sib, "name", None) in ("h2", "h3"):
                    break
                text = sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else str(sib).strip()
                words += len(text.split())
            p.section_word_counts.append(words)

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
    for i in imgs:
        ext = best_image_format(i)
        if ext:
            p.image_formats[ext] = p.image_formats.get(ext, 0) + 1

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


MODERN_IMAGE_FORMATS = ("webp", "avif")
LEGACY_IMAGE_FORMATS = ("jpg", "jpeg", "png", "gif", "bmp")
IMAGE_EXT_RE = re.compile(r"\.([a-z0-9]{2,4})(?:[?#]|$)", re.IGNORECASE)


def best_image_format(img: Any) -> Optional[str]:
    """Classify one <img> by the best format it can actually serve.

    A <picture> offering AVIF with a JPEG fallback is already doing the right
    thing, so the modern source wins over the fallback. Extensionless CDN URLs
    (Cloudinary, Next.js /_next/image, imgix) return None rather than being
    guessed at — counting them as legacy would produce false positives on sites
    that already negotiate format by Accept header.
    """
    candidates: list[str] = []
    for attr in ("src", "data-src", "data-lazy-src"):
        v = img.get(attr)
        if v:
            candidates.append(v)
    for attr in ("srcset", "data-srcset"):
        v = img.get(attr)
        if v:
            candidates.extend(part.strip().split(" ")[0] for part in v.split(","))
    parent = img.parent
    if parent is not None and getattr(parent, "name", None) == "picture":
        for src_tag in parent.find_all("source"):
            type_attr = (src_tag.get("type") or "").lower()
            if type_attr.startswith("image/"):
                candidates.append("x." + type_attr.split("/", 1)[1])
            v = src_tag.get("srcset") or ""
            candidates.extend(part.strip().split(" ")[0] for part in v.split(",") if part.strip())

    found: list[str] = []
    for c in candidates:
        m = IMAGE_EXT_RE.search(c)
        if not m:
            continue
        ext = m.group(1).lower()
        if ext == "jpeg":
            ext = "jpg"
        if ext in MODERN_IMAGE_FORMATS or ext in LEGACY_IMAGE_FORMATS or ext == "svg":
            found.append(ext)
    for modern in MODERN_IMAGE_FORMATS:
        if modern in found:
            return modern
    return found[0] if found else None


def has_speakable(obj: Any) -> bool:
    """True if the JSON-LD contains a real speakable declaration.

    Either a node typed SpeakableSpecification, or a `speakable` property on any
    node. Scanning the serialised JSON for the substring instead matches URLs,
    body copy, and unrelated field values, which is why that approach was wrong.
    """
    if isinstance(obj, dict):
        t = obj.get("@type")
        if t == "SpeakableSpecification" or (isinstance(t, list) and "SpeakableSpecification" in t):
            return True
        for k, v in obj.items():
            # Keys may be namespaced, e.g. "schema:speakable".
            if str(k).split(":")[-1] == "speakable" and v:
                return True
            if has_speakable(v):
                return True
    elif isinstance(obj, list):
        return any(has_speakable(x) for x in obj)
    return False


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

# The catalog is the single source of truth for every finding the analyzer can
# emit. build_findings() never states a severity or category inline — it names a
# check and emit() reads both from here, so `--list-checks` cannot drift from what
# the code actually produces. Adding a finding means adding a catalog entry first;
# emit() raises on an unknown id.
#
# A tuple of severities means the check picks one at emission time based on which
# band the measured value lands in. The first entry is the default, and emit()
# rejects anything outside the declared set.
#
# CHECK_ID_TEMPLATE_TOKEN marks ids that are parameterised per page template.
CHECK_ID_TEMPLATE_TOKEN = "<template>"

CHECKS: dict[str, dict[str, Any]] = {
    "seo.robots.missing": {"severity": "high", "category": "seo"},
    "seo.sitemap.missing": {"severity": "high", "category": "seo"},
    "aeo.ai_crawlers.blocked": {"severity": "high", "category": "aeo"},
    "aeo.ai_crawlers.training_blocked": {"severity": "info", "category": "aeo"},
    "aeo.llms_txt.missing": {"severity": "info", "category": "aeo"},
    "aeo.ssr.missing": {"severity": "critical", "category": "aeo"},
    "aeo.ssr.unverified": {"severity": "info", "category": "aeo"},
    "seo.title.missing": {"severity": "critical", "category": "seo"},
    "seo.title.length": {"severity": "medium", "category": "seo"},
    "seo.meta_description.missing": {"severity": "high", "category": "seo"},
    "seo.meta_description.length": {"severity": "low", "category": "seo"},
    "seo.canonical.missing": {"severity": "high", "category": "seo"},
    "seo.h1.count": {"severity": "medium", "category": "seo"},
    "seo.heading_hierarchy.jump": {"severity": "low", "category": "seo"},
    "seo.open_graph.incomplete": {"severity": "medium", "category": "seo"},
    "seo.open_graph.image_dimensions": {"severity": "low", "category": "seo"},
    "seo.images.missing_alt": {"severity": "medium", "category": "seo"},
    "seo.images.legacy_format": {"severity": "low", "category": "seo"},
    "seo.hreflang.non_reciprocal": {"severity": "medium", "category": "seo"},
    f"aeo.schema.{CHECK_ID_TEMPLATE_TOKEN}.missing_types": {"severity": "high", "category": "aeo"},
    "aeo.schema.deprecated": {"severity": "info", "category": "aeo"},
    "aeo.organization_schema.shallow": {"severity": "medium", "category": "aeo"},
    "aeo.wikidata.unreferenced": {"severity": "high", "category": "aeo"},
    "aeo.faqpage_schema.missing": {"severity": "info", "category": "aeo"},
    "aeo.speakable_schema.missing": {"severity": "medium", "category": "aeo"},
    "aeo.content_freshness.stale": {"severity": "medium", "category": "aeo"},
    "seo.content.thin": {"severity": "medium", "category": "seo"},
    "aeo.direct_answer.missing": {"severity": "medium", "category": "aeo"},
    "aeo.passage.citability": {"severity": "medium", "category": "aeo"},
    "aeo.toc.missing": {"severity": "low", "category": "aeo"},
    "seo.viewport.missing": {"severity": "high", "category": "seo"},
    "seo.html_lang.missing": {"severity": "medium", "category": "seo"},
    "seo.performance.lcp": {"severity": ("medium", "high"), "category": "seo"},
    "seo.performance.cls": {"severity": ("low", "medium"), "category": "seo"},
    "seo.performance.page_weight": {"severity": ("low", "medium"), "category": "seo"},
    "seo.redirects.chain": {"severity": ("low", "medium"), "category": "seo"},
    "seo.fetch.errors": {"severity": "high", "category": "seo"},
}

CATEGORIES = sorted({spec["category"] for spec in CHECKS.values()})


def check_severities(check_id: str) -> tuple[str, ...]:
    spec = CHECKS[check_id]["severity"]
    return (spec,) if isinstance(spec, str) else tuple(spec)


def emit(
    check_id: str,
    *,
    evidence: str,
    why: str,
    recommendation: str,
    affected_urls: list[str],
    template: Optional[str] = None,
    severity: Optional[str] = None,
    framework_fix_key: Optional[str] = None,
    impact_score: int = 5,
    catalog_key: Optional[str] = None,
) -> Finding:
    """Build a Finding, taking severity and category from CHECKS."""
    key = catalog_key or check_id
    if key not in CHECKS:
        raise KeyError(f"{key!r} is not registered in CHECKS — add it there first.")
    allowed = check_severities(key)
    sev = severity or allowed[0]
    if sev not in allowed:
        raise ValueError(f"severity {sev!r} not declared for check {key!r} (allowed: {allowed})")
    return Finding(
        id=check_id,
        severity=sev,
        category=CHECKS[key]["category"],
        template=template,
        affected_urls=affected_urls,
        evidence=evidence,
        why=why,
        recommendation=recommendation,
        framework_fix_key=framework_fix_key,
        impact_score=impact_score,
    )


def list_checks() -> list[tuple[str, str, str]]:
    """(id, severity, category) for every check, in catalog order."""
    return [
        (cid, "|".join(check_severities(cid)), spec["category"])
        for cid, spec in CHECKS.items()
    ]


def build_findings(
    base_url: str,
    pages: list[PageData],
    robots: dict[str, Any],
) -> list[Finding]:
    findings: list[Finding] = []

    # --- Sitemap + robots ---
    if not robots.get("present"):
        findings.append(emit(
            "seo.robots.missing",
            affected_urls=[base_url],
            evidence="No /robots.txt served.",
            why="robots.txt is how crawlers discover allowed paths and the sitemap. Missing it forces heuristics and slows indexing.",
            recommendation="Serve /robots.txt with Sitemap: directive and explicit User-agent rules.",
            framework_fix_key="robots.missing", impact_score=7,
        ))
    if not robots.get("sitemap_urls"):
        findings.append(emit(
            "seo.sitemap.missing",
            affected_urls=[base_url],
            evidence="No sitemap referenced in robots.txt and none found at common paths.",
            why="Sitemaps accelerate indexation and signal canonical URL set.",
            recommendation="Publish /sitemap.xml (or /sitemap-index.xml) and add Sitemap: line to robots.txt.",
            framework_fix_key="sitemap.missing", impact_score=7,
        ))

    # --- AI crawler policy ---
    star_blocks_all = blocks_everything(ai_policy_for(robots, "*"))

    def blocked(bots: list[str]) -> list[str]:
        out = []
        for bot in bots:
            policy = ai_policy_for(robots, bot)
            has_own_group = bool(policy.get("disallow") or policy.get("allow"))
            # A bot with no group of its own falls through to the wildcard group.
            if blocks_everything(policy) or (not has_own_group and star_blocks_all):
                out.append(bot)
        return out

    blocked_search = blocked(SEARCH_AI_CRAWLERS)
    blocked_training = blocked(TRAINING_AI_CRAWLERS)

    if blocked_search:
        via = " (via the wildcard User-agent: * group)" if star_blocks_all else ""
        findings.append(emit(
            "aeo.ai_crawlers.blocked",
            affected_urls=[base_url],
            evidence=f"robots.txt disallows{via}: {', '.join(blocked_search)}",
            why=(
                "These crawlers fetch pages to answer a user's live query and cite the source. "
                "Blocking them removes the site from AI-mediated discovery in ChatGPT, Claude, Perplexity and AI Overviews. "
                "Two distinctions worth knowing: blocking Google-Extended stops Gemini training but does NOT remove you "
                "from AI Overviews, which crawl as Googlebot; and blocking GPTBot does not stop ChatGPT citing you, "
                "because live browsing fetches as ChatGPT-User."
            ),
            recommendation=f"Allow {', '.join(SEARCH_AI_CRAWLERS[:6])} unless the content is genuinely proprietary. Block by path, not by blanket Disallow: /.",
            framework_fix_key="ai_crawlers.blocked", impact_score=9,
        ))

    if blocked_training:
        findings.append(emit(
            "aeo.ai_crawlers.training_blocked",
            affected_urls=[base_url],
            evidence=f"robots.txt disallows training crawlers: {', '.join(blocked_training)}",
            why="These crawlers collect training corpora rather than answering live queries, so blocking them carries no direct search or citation cost. Recorded so the policy is visible, not because it is a problem.",
            recommendation="No action needed. This is a content-licensing decision, and blocking training crawlers while allowing search crawlers is a coherent position.",
            framework_fix_key=None, impact_score=1,
        ))
    if not robots.get("has_llms_txt"):
        findings.append(emit(
            "aeo.llms_txt.missing",
            affected_urls=[base_url],
            evidence="No /llms.txt served.",
            why="No major AI search system is known to consume llms.txt, and server-log studies show it draws a negligible share of AI-bot traffic. It carries no citation weight today. See references/aeo-evidence.md.",
            recommendation="Not required for AI search visibility — do not prioritise it over SSR, schema depth, or crawler access. It is worth publishing only if you want AI coding agents to navigate your developer docs.",
            framework_fix_key="llms_txt.missing", impact_score=1,
        ))

    # --- Server-side rendering ---
    # Fires only on proof: raw (pre-JavaScript) HTML near-empty of prose AND the
    # rendered HTML containing many times more content. A small but genuinely
    # server-rendered page has raw == rendered and is never reported here.
    # was_spa_shell is NOT used — it is a deliberately over-eager render trigger.
    spa_pages = [p for p in pages if p.client_rendered]
    if spa_pages:
        detail = "; ".join(
            f"{p.template} ({p.raw_word_count} words before JavaScript, {p.word_count} after)"
            for p in spa_pages
        )
        findings.append(emit(
            "aeo.ssr.missing",
            affected_urls=[p.url for p in spa_pages],
            evidence=(
                f"{len(spa_pages)} of {len(pages)} sampled page(s) served almost no content until "
                f"JavaScript ran: {detail}. The first number is what a non-executing AI crawler gets."
            ),
            why=(
                "AI crawlers do not execute JavaScript. GPTBot, ClaudeBot, PerplexityBot and the "
                "rest read the HTML the server returns and nothing more, so a client-rendered page "
                "reaches them as an empty div. This outranks every other AEO consideration on this "
                "report: there is no point tuning schema, headings, or answer formatting on a page "
                "an AI crawler sees as an empty shell. Fix rendering first, then everything else "
                "starts to count. Googlebot does render JavaScript, so classic search may look "
                "fine while AI visibility is zero — the two failures do not show up together."
            ),
            recommendation=(
                "Server-render or statically generate these routes so the meaningful content is in "
                "the initial HTML response. Verify with `curl -s <url> | grep '<your headline>'` — "
                "if the text is not in that output, no AI crawler can read it."
            ),
            framework_fix_key="ssr.missing", impact_score=10,
        ))

    # No render means no before/after comparison, so client-side rendering can be
    # neither proven nor ruled out. Say so; do not guess with a critical finding.
    unverified = [p for p in pages if p.csr_check_skipped and not p.client_rendered]
    if unverified and not spa_pages:
        findings.append(emit(
            "aeo.ssr.unverified",
            affected_urls=[p.url for p in unverified],
            evidence=(
                f"{len(unverified)} of {len(pages)} sampled page(s) were not rendered in a browser "
                "(--no-render, or Playwright unavailable), so raw HTML could not be compared "
                "against post-JavaScript HTML."
            ),
            why=(
                "Whether a page is server-rendered can only be established by comparing the HTML "
                "the server returns against the HTML after JavaScript runs. Without a render there "
                "is no comparison, so this report makes no claim either way. It is not evidence "
                "that rendering is fine, nor that it is broken."
            ),
            recommendation=(
                "Re-run without --no-render (and with Playwright installed) to check rendering. "
                "For a quick manual check: `curl -s <url> | grep '<your headline>'` — if your main "
                "content is absent from that output, AI crawlers cannot read it."
            ),
            framework_fix_key="ssr.missing", impact_score=1,
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
        findings.append(emit(
            "seo.title.missing",
            affected_urls=title_issues["missing"],
            evidence=f"{len(title_issues['missing'])} page(s) have no <title>.",
            why="Title tag is the single largest on-page ranking signal and the SERP click driver.",
            recommendation="Every page must have a unique 30-70 char title with the primary keyword near the front.",
            framework_fix_key="title.missing", impact_score=10,
        ))
    if title_issues["short"] or title_issues["long"]:
        urls = title_issues["short"] + title_issues["long"]
        findings.append(emit(
            "seo.title.length",
            affected_urls=urls,
            evidence=f"{len(urls)} title(s) outside 30-70 char window.",
            why="Titles under 30 chars under-sell; over 70 truncate in SERPs.",
            recommendation="Rewrite to 50-60 chars with primary keyword + value promise.",
            framework_fix_key="title.length", impact_score=5,
        ))
    if meta_issues["missing"]:
        findings.append(emit(
            "seo.meta_description.missing",
            affected_urls=meta_issues["missing"],
            evidence=f"{len(meta_issues['missing'])} page(s) have no meta description.",
            why="Without a meta description Google auto-generates one — usually lower CTR than a written version.",
            recommendation="120-160 char meta description with primary keyword in first 50 chars and a CTA.",
            framework_fix_key="meta_description.missing", impact_score=7,
        ))
    if meta_issues["short"] or meta_issues["long"]:
        urls = meta_issues["short"] + meta_issues["long"]
        findings.append(emit(
            "seo.meta_description.length",
            affected_urls=urls,
            evidence=f"{len(urls)} meta description(s) outside 120-160 window.",
            why="Short descriptions under-sell; long ones truncate in SERPs.",
            recommendation="Rewrite to 140-155 chars.",
            framework_fix_key="meta_description.length", impact_score=3,
        ))

    # Canonical
    canon_missing = [p.url for p in pages if not p.canonical]
    if canon_missing:
        findings.append(emit(
            "seo.canonical.missing",
            affected_urls=canon_missing,
            evidence=f"{len(canon_missing)} page(s) missing <link rel=canonical>.",
            why="Without canonicals, duplicate content via filters, UTMs, or pagination dilutes ranking signals.",
            recommendation="Add self-referential absolute canonical URL in <head> of every indexable page.",
            framework_fix_key="canonical.missing", impact_score=8,
        ))

    # H1
    h1_issues = [p.url for p in pages if p.h1_count != 1]
    if h1_issues:
        findings.append(emit(
            "seo.h1.count",
            affected_urls=h1_issues,
            evidence=f"{len(h1_issues)} page(s) with 0 or >1 H1.",
            why="Exactly one H1 per page clarifies the primary topic for crawlers and assistive tech.",
            recommendation="Use exactly one H1 that contains the primary keyword.",
            framework_fix_key="h1.count", impact_score=5,
        ))

    # Heading hierarchy — a level skipped on the way down (H1 → H3, H2 → H4)
    jump_pages: list[str] = []
    jump_examples: list[str] = []
    for p in pages:
        prev = 0
        for lvl, txt in p.heading_tree:
            if prev and lvl > prev + 1:
                jump_pages.append(p.url)
                jump_examples.append(f"H{prev} → H{lvl} at \"{txt[:60]}\"")
                break
            prev = lvl
    if jump_pages:
        findings.append(emit(
            "seo.heading_hierarchy.jump",
            affected_urls=jump_pages,
            evidence=f"{len(jump_pages)} page(s) skip a heading level, e.g. {jump_examples[0]}.",
            why=(
                "Heading levels are the document outline, and both screen readers and the chunkers "
                "AI engines use to split pages read nesting from them. A skipped level makes a "
                "sibling section look like a child of the wrong parent, so extracted passages come "
                "away attached to the wrong topic. Sizing is a CSS decision, not a reason to skip."
            ),
            recommendation=(
                "Step heading levels one at a time going down. If an H3 was chosen for its size, "
                "use an H2 and style it."
            ),
            framework_fix_key="heading_hierarchy.jump", impact_score=3,
        ))

    # Open Graph completeness (home + primary templates)
    og_gaps = []
    for p in pages:
        required = {"title", "description", "image", "url", "type"}
        missing = required - set(p.og.keys())
        if missing:
            og_gaps.append((p.url, missing))
    if og_gaps:
        findings.append(emit(
            "seo.open_graph.incomplete",
            affected_urls=[u for u, _ in og_gaps],
            evidence=f"{len(og_gaps)} page(s) missing OG fields (e.g., {list(og_gaps[0][1])[:3]}).",
            why="Incomplete OG tags produce ugly or truncated previews when shared — direct CTR cost.",
            recommendation="Every page: og:title, og:description, og:image (1200x630), og:url, og:type, og:site_name.",
            framework_fix_key="open_graph.incomplete", impact_score=5,
        ))

    # og:image dimensions — 1200x630 is the size every major platform crops to
    OG_IMAGE_W, OG_IMAGE_H = "1200", "630"
    og_dim_wrong: list[str] = []
    og_dim_absent: list[str] = []
    for p in pages:
        if "image" not in p.og:
            continue  # already covered by seo.open_graph.incomplete
        w = (p.og.get("image:width") or "").strip()
        h = (p.og.get("image:height") or "").strip()
        if w and h:
            if (w, h) != (OG_IMAGE_W, OG_IMAGE_H):
                og_dim_wrong.append(f"{p.url} ({w}x{h})")
        else:
            og_dim_absent.append(p.url)
    if og_dim_wrong or og_dim_absent:
        parts = []
        if og_dim_wrong:
            parts.append(f"{len(og_dim_wrong)} page(s) declare non-standard dimensions: {og_dim_wrong[0]}")
        if og_dim_absent:
            parts.append(f"{len(og_dim_absent)} page(s) declare og:image with no width/height")
        findings.append(emit(
            "seo.open_graph.image_dimensions",
            affected_urls=[u.split(" ")[0] for u in og_dim_wrong] + og_dim_absent,
            evidence="; ".join(parts) + ".",
            why=(
                "1200x630 is the 1.91:1 box LinkedIn, Facebook, Slack and X all crop previews to. "
                "Ship another ratio and the crop lands wherever it lands — commonly through the "
                "headline or the logo. Declaring og:image:width and og:image:height also lets a "
                "platform reserve the right space before the image downloads, so the first scrape "
                "renders the large card instead of falling back to a thumbnail."
            ),
            recommendation=(
                "Render social images at exactly 1200x630 and declare og:image:width and "
                "og:image:height alongside og:image. Use an absolute URL — relative paths fail on "
                "several scrapers."
            ),
            framework_fix_key="open_graph.image_dimensions", impact_score=3,
        ))

    # Image alt
    alt_gaps =[p for p in pages if p.image_count > 0 and p.image_missing_alt / max(1, p.image_count) > 0.2]
    if alt_gaps:
        findings.append(emit(
            "seo.images.missing_alt",
            affected_urls=[p.url for p in alt_gaps],
            evidence=f"{len(alt_gaps)} page(s) with >20% images missing alt.",
            why="Missing alt hurts accessibility and image search ranking. AI crawlers also use alt as image semantic context.",
            recommendation="Every content image needs alt. Decorative images use alt=\"\" (empty, not missing).",
            framework_fix_key="images.missing_alt", impact_score=4,
        ))

    # Legacy image formats. Only URLs with a real extension are counted — sites on a
    # format-negotiating CDN serve extensionless URLs and are already fine.
    legacy_pages: list[str] = []
    legacy_detail = ""
    for p in pages:
        legacy = sum(p.image_formats.get(f, 0) for f in ("jpg", "png", "gif", "bmp"))
        modern = sum(p.image_formats.get(f, 0) for f in MODERN_IMAGE_FORMATS)
        if legacy >= 5 and modern == 0:
            legacy_pages.append(p.url)
            if not legacy_detail:
                legacy_detail = f"{p.url}: {legacy} legacy image(s), no WebP or AVIF"
    if legacy_pages:
        findings.append(emit(
            "seo.images.legacy_format",
            affected_urls=legacy_pages,
            evidence=f"{len(legacy_pages)} page(s) serve only JPEG/PNG/GIF. Example: {legacy_detail}.",
            why=(
                "WebP is typically 25-35% smaller than JPEG at matching quality and AVIF more than "
                "that, and both are supported by every browser in current use. On image-led pages "
                "the hero is usually the LCP element, so the format choice moves LCP directly. "
                "Nothing else on the page has to change to collect the saving."
            ),
            recommendation=(
                "Serve WebP or AVIF with a JPEG/PNG fallback in <picture>, or move to an image CDN "
                "that negotiates format from the Accept header. Keep PNG only where lossless or "
                "transparency genuinely matters."
            ),
            framework_fix_key="images.legacy_format", impact_score=4,
        ))

    # hreflang reciprocity — self-reference is the half sites forget
    hreflang_gaps: list[str] = []
    for p in pages:
        if not p.hreflang:
            continue
        self_url = norm_url(p.canonical or p.final_url or p.url, p.url)
        declared = {norm_url(a["href"], p.url) for a in p.hreflang}
        if self_url and self_url not in declared:
            hreflang_gaps.append(p.url)
    if hreflang_gaps:
        findings.append(emit(
            "seo.hreflang.non_reciprocal",
            affected_urls=hreflang_gaps,
            evidence=(
                f"{len(hreflang_gaps)} page(s) declare hreflang alternates but list no entry "
                f"pointing at themselves."
            ),
            why=(
                "An hreflang cluster is only valid if every member lists every member including "
                "itself. Google treats a set without the self-reference as unconfirmed and drops "
                "the whole annotation, so the localised pages compete with each other instead of "
                "being swapped per market — and the effort spent translating them earns nothing."
            ),
            recommendation=(
                "Add a self-referential <link rel=\"alternate\" hreflang=\"...\" href=\"...\"> to "
                "each page with its own language code and absolute URL, and confirm every alternate "
                "points back. Add x-default for the fallback locale."
            ),
            framework_fix_key="hreflang.non_reciprocal", impact_score=5,
        ))

    # --- Schema coverage matrix findings ---
    schema_requirements = {
        "home": ["WebSite", "Organization"],
        "blog_post": ["BlogPosting", "BreadcrumbList"],
        "blog_index": ["Blog", "BreadcrumbList"],
        "pricing": ["Product", "Offer"],
        "product": ["Product"],
        "platform": ["SoftwareApplication"],
        "tool": ["SoftwareApplication"],
        "about": ["AboutPage", "Organization"],
        "docs": ["TechArticle"],
    }
    for tpl, page_list in by_tpl.items():
        required = schema_requirements.get(tpl)
        if not required:
            continue
        # Check every sampled page in the template, not just the first — the report
        # presents this as template-wide coverage, so it has to be measured that way.
        offenders: list[PageData] = []
        missing_union: set[str] = set()
        found_union: set[str] = set()
        for pg in page_list:
            found_union.update(pg.schema_types)
            gaps = [t for t in required if t not in pg.schema_types]
            if gaps:
                offenders.append(pg)
                missing_union.update(gaps)
        if offenders:
            missing = sorted(missing_union)
            findings.append(emit(
                f"aeo.schema.{tpl}.missing_types",
                catalog_key=f"aeo.schema.{CHECK_ID_TEMPLATE_TOKEN}.missing_types",
                template=tpl, affected_urls=[pg.url for pg in offenders],
                evidence=(
                    f"{len(offenders)} of {len(page_list)} sampled '{tpl}' page(s) missing required "
                    f"schema types: {missing}. Types seen across the template: "
                    f"{sorted(found_union) or 'none'}."
                ),
                why="Schema.org markup is how Google, Bing, and AI assistants understand page semantics. Missing types cost rich-result eligibility and AEO visibility.",
                recommendation=f"Add JSON-LD for: {', '.join(missing)} on all {tpl} pages.",
                framework_fix_key=f"schema.{tpl}",
                impact_score=8 if tpl in ("home", "blog_post", "pricing") else 6,
            ))

    # Deprecated schema types still shipping
    deprecated_pages = [p for p in pages if p.deprecated_schema]
    if deprecated_pages:
        seen_types = sorted({t for p in deprecated_pages for t in p.deprecated_schema})
        detail = ", ".join(f"{t} ({DEPRECATED_SCHEMA_TYPES[t]})" for t in seen_types)
        findings.append(emit(
            "aeo.schema.deprecated",
            affected_urls=[p.url for p in deprecated_pages],
            evidence=f"{len(deprecated_pages)} page(s) ship deprecated schema: {detail}.",
            why="Google no longer generates rich results from these types. The markup is valid but earns nothing in search — it is maintenance cost without return.",
            recommendation="Remove on the next content pass, or leave it if you rely on it elsewhere. Do not add more. For genuine Q&A content use QAPage.",
            framework_fix_key=None, impact_score=1,
        ))

    # Organization depth (homepage)
    home_pages = [p for p in pages if p.template == "home"]
    if home_pages:
        h = home_pages[0]
        if "Organization" in h.schema_types:
            depth = h.organization_depth
            weak = [k for k, v in depth.items() if not v]
            if weak:
                findings.append(emit(
                    "aeo.organization_schema.shallow",
                    template="home", affected_urls=[h.url],
                    evidence=f"Organization schema missing fields: {weak}",
                    why="Deep Organization schema (founder, sameAs w/ Wikidata, knowsAbout, slogan, foundingDate) is the single strongest entity-recognition signal for AI assistants and Google's Knowledge Graph.",
                    recommendation="Fill every field. Priority: sameAs with Wikidata URL, founder[], knowsAbout[], slogan, foundingDate, contactPoint.",
                    framework_fix_key="organization_schema.shallow", impact_score=9,
                ))
            if not h.wikidata_referenced:
                findings.append(emit(
                    "aeo.wikidata.unreferenced",
                    template="home", affected_urls=[h.url],
                    evidence="Organization.sameAs does not include a wikidata.org URL.",
                    why="A Wikidata entity ID is the highest-confidence cross-reference for AI answer engines. Without it, your brand is a string, not an entity.",
                    recommendation="Create a Wikidata item for your company, then list its URL (https://www.wikidata.org/wiki/Qxxxxxx) in Organization.sameAs.",
                    framework_fix_key="wikidata.unreferenced", impact_score=9,
                ))

    # FAQ detected in content but no FAQPage schema
    faq_missing = [p.url for p in pages if p.faq_detected_in_content and not p.faqpage_schema]
    if faq_missing:
        findings.append(emit(
            "aeo.faqpage_schema.missing",
            affected_urls=faq_missing,
            evidence=f"{len(faq_missing)} page(s) have question-format headings but no FAQPage JSON-LD.",
            why="Google retired FAQPage rich results for all sites, so there is no SERP gain here. AI answer engines still parse the markup for question-answer extraction, which is the only remaining reason to add it.",
            recommendation="Optional. If the questions are genuine and already well-structured in the HTML, generating FAQPage JSON-LD costs little and may help AI answer extraction. Do not add it expecting rich results, and never remove existing FAQPage markup. For single-question pages with community answers, use QAPage instead.",
            framework_fix_key="faqpage_schema.missing", impact_score=2,
        ))

    # Speakable schema for blog
    blog_pages = [p for p in pages if p.template == "blog_post"]
    if blog_pages and not any(p.speakable_schema for p in blog_pages):
        findings.append(emit(
            "aeo.speakable_schema.missing",
            template="blog_post",
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
            # Date-only values ("2025-09-04") parse as naive, and subtracting a
            # naive datetime from an aware one raises — which silently swallowed
            # every date-only dateModified into the except below. Assume UTC.
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_days = (today - dt).days
            if age_days > 180:
                stale.append((p.url, age_days))
        except Exception:
            pass
    if stale:
        oldest = max(age for _, age in stale)
        findings.append(emit(
            "aeo.content_freshness.stale",
            template="blog_post",
            affected_urls=[u for u, _ in stale],
            evidence=(
                f"{len(stale)} blog post(s) not updated in over 180 days "
                f"(oldest: {oldest} days)."
            ),
            why=(
                "Citation eligibility decays with age. Content updated within roughly the last "
                "three months is substantially more likely to be cited by AI answer engines, and "
                "the drop-off becomes pronounced past about six months — which is why 180 days is "
                "the line here. The previous 365-day threshold only caught posts that were already "
                "a year stale, by which point the ranking loss had long since happened; it was too "
                "lenient to act on."
            ),
            recommendation=(
                "Put these on a refresh cycle: re-check facts, figures and screenshots, then update "
                "dateModified when the edit is genuine. Do not touch dateModified without changing "
                "the content — engines compare the claimed date against the actual diff."
            ),
            framework_fix_key="content_freshness.stale", impact_score=4,
        ))

    # Thin content
    thin = [p.url for p in pages if p.template in ("blog_post", "product", "pricing") and p.word_count < 300]
    if thin:
        findings.append(emit(
            "seo.content.thin",
            affected_urls=thin,
            evidence=f"{len(thin)} key template page(s) under 300 words.",
            why="Thin content loses to competitors who cover the topic fully, and gives AI engines too little to cite.",
            recommendation="Expand to 800+ words (blog 1500+) with real substance, not filler.",
            framework_fix_key="content.thin", impact_score=6,
        ))

    # Direct-answer paragraph (AEO)
    long_intros = [p.url for p in pages if p.template == "blog_post" and p.direct_answer_words > 60]
    if long_intros:
        findings.append(emit(
            "aeo.direct_answer.missing",
            template="blog_post", affected_urls=long_intros,
            evidence=f"{len(long_intros)} blog post(s) open with a paragraph over 60 words.",
            why=(
                "An answer engine quoting your page lifts a short, self-contained span. An opening "
                "paragraph over 60 words rarely survives that extraction intact — the model either "
                "truncates it mid-thought or skips to a competitor who answered in one sentence. "
                "The threshold is 60 rather than 80 because the extractable window is narrower "
                "than it looks: 40-60 words is where openings both answer the question and fit."
            ),
            recommendation=(
                "Open every post with a 40-60 word paragraph that answers the implied query "
                "outright, stated so it reads correctly with no surrounding context. Background, "
                "caveats and narrative go after it."
            ),
            framework_fix_key="direct_answer.missing", impact_score=6,
        ))

    # Passage citability (AEO)
    # Sections are measured between consecutive H2/H3s. Sections under 20 words are
    # treated as unmeasured rather than as failures — they are usually a heading
    # wrapping nested markup the sibling walk cannot see, and counting them would
    # flag well-structured pages. A page needs 3+ measurable sections to be judged.
    CITABLE_MIN, CITABLE_MAX = 134, 167
    BAND_LOW, BAND_HIGH = 100, 250  # the 134-167 core plus working tolerance
    poor_citability: list[tuple[str, int, int]] = []
    for p in pages:
        if p.template != "blog_post":
            continue
        measurable = [w for w in p.section_word_counts if w >= 20]
        if len(measurable) < 3:
            continue
        in_band = sum(1 for w in measurable if BAND_LOW <= w <= BAND_HIGH)
        if in_band / len(measurable) < 0.34:
            poor_citability.append((p.url, in_band, len(measurable)))
    if poor_citability:
        worst = min(poor_citability, key=lambda x: x[1] / x[2])
        findings.append(emit(
            "aeo.passage.citability",
            template="blog_post",
            affected_urls=[u for u, _, _ in poor_citability],
            evidence=(
                f"{len(poor_citability)} blog post(s) where under a third of sections fall in the "
                f"{BAND_LOW}-{BAND_HIGH} word range. Worst: {worst[0]} with {worst[1]} of "
                f"{worst[2]} sections in range."
            ),
            why=(
                f"Answer engines cite passages, not pages. Passages that get cited cluster at "
                f"{CITABLE_MIN}-{CITABLE_MAX} words — long enough to stand alone once lifted out of "
                f"the page, short enough to quote whole. Sections far below that are fragments a "
                f"model cannot use without stitching; far above it and the model has to summarise, "
                f"which is where attribution gets dropped. The check allows {BAND_LOW}-{BAND_HIGH} "
                f"rather than the bare band so ordinary variation does not register as a problem — "
                f"it fires only when most sections miss by a wide margin. Position matters too: "
                f"roughly 44% of AI citations come from the first 30% of a page, so the sections "
                f"nearest the top are the ones worth fixing first."
            ),
            recommendation=(
                f"Restructure so each H2/H3 section answers one question in roughly "
                f"{CITABLE_MIN}-{CITABLE_MAX} words. Split sections that sprawl; merge or cut "
                f"one-line sections. Start with the sections in the top third of the page, where "
                f"most citations are drawn from."
            ),
            framework_fix_key="passage.citability", impact_score=6,
        ))

    # TOC (long posts)
    long_no_toc = [p.url for p in pages if p.template == "blog_post" and p.word_count > 1500 and not p.toc_detected]
    if long_no_toc:
        findings.append(emit(
            "aeo.toc.missing",
            template="blog_post", affected_urls=long_no_toc,
            evidence=f"{len(long_no_toc)} long blog post(s) without a TOC.",
            why="TOC with jump anchors helps AI engines chunk content and surface jump-to-section links in SERPs.",
            recommendation="Auto-generate TOC from H2s with anchor links for posts over 1500 words.",
            framework_fix_key="toc.missing", impact_score=3,
        ))

    # viewport
    no_viewport = [p.url for p in pages if not p.viewport]
    if no_viewport:
        findings.append(emit(
            "seo.viewport.missing",
            affected_urls=no_viewport,
            evidence=f"{len(no_viewport)} page(s) missing viewport meta.",
            why="Without viewport meta, mobile rendering breaks. Mobile usability is a ranking factor.",
            recommendation='Add <meta name="viewport" content="width=device-width, initial-scale=1">.',
            framework_fix_key="viewport.missing", impact_score=7,
        ))

    # html lang
    no_lang = [p.url for p in pages if not p.lang]
    if no_lang:
        findings.append(emit(
            "seo.html_lang.missing",
            affected_urls=no_lang,
            evidence=f"{len(no_lang)} page(s) missing <html lang>.",
            why="lang attribute signals content language to Google and assistive tech.",
            recommendation='Add <html lang="en"> (or the correct BCP 47 code).',
            framework_fix_key="html_lang.missing", impact_score=3,
        ))

    # --- Core Web Vitals (synthetic) ---
    # Lab numbers from one headless load on this machine's network. They locate a
    # problem; they do not measure what real users get. INP is absent by design: it
    # requires real user interaction and can only come from field data (CrUX/RUM).
    LAB_CAVEAT = (
        "This is a synthetic lab measurement from a single headless page load, not field data. "
        "It indicates a problem rather than proving one — confirm against CrUX or your own RUM "
        "before sizing the work. (INP cannot be measured this way at all: it needs real user "
        "interactions, so it only comes from field data and is out of scope here.)"
    )

    lcp_pages = [p for p in pages if p.lcp_ms is not None]
    lcp_bad = [p for p in lcp_pages if p.lcp_ms > 2500]
    if lcp_bad:
        worst_lcp = max(p.lcp_ms for p in lcp_bad)
        findings.append(emit(
            "seo.performance.lcp",
            severity="high" if worst_lcp > 4000 else "medium",
            affected_urls=[p.url for p in lcp_bad],
            evidence=(
                f"{len(lcp_bad)} of {len(lcp_pages)} measured page(s) over the 2.5s LCP threshold; "
                f"worst {worst_lcp / 1000:.1f}s (good ≤2.5s, poor >4.0s)."
            ),
            why=(
                "LCP is when the largest element in the viewport finishes rendering — in practice "
                "the moment the page looks usable. It is a Core Web Vital, so it feeds ranking "
                "directly, and past about 4s abandonment climbs sharply regardless of ranking. "
                + LAB_CAVEAT
            ),
            recommendation=(
                "Identify the LCP element in DevTools, then: serve it from the initial HTML rather "
                "than after a client fetch, preload it, size it correctly in a modern format, and "
                "clear render-blocking CSS/fonts ahead of it. Re-check against CrUX afterwards."
            ),
            framework_fix_key="performance.lcp",
            impact_score=8 if worst_lcp > 4000 else 6,
        ))

    cls_pages = [p for p in pages if p.cls is not None]
    cls_bad = [p for p in cls_pages if p.cls > 0.1]
    if cls_bad:
        worst_cls = max(p.cls for p in cls_bad)
        findings.append(emit(
            "seo.performance.cls",
            severity="medium" if worst_cls > 0.25 else "low",
            affected_urls=[p.url for p in cls_bad],
            evidence=(
                f"{len(cls_bad)} of {len(cls_pages)} measured page(s) over the 0.1 CLS threshold; "
                f"worst {worst_cls:.3f} (good ≤0.1, poor >0.25)."
            ),
            why=(
                "CLS totals how far visible content jumps after it first paints. It is a Core Web "
                "Vital, and the user-facing cost is mis-clicks — a button that moves under the "
                "cursor. Typical causes are images and ads without reserved space, and webfonts "
                "swapping in at a different metric. " + LAB_CAVEAT
            ),
            recommendation=(
                "Set width and height (or aspect-ratio) on every image, iframe and ad slot; use "
                "font-display: optional or a metric-matched fallback; and never insert banners "
                "above content already on screen."
            ),
            framework_fix_key="performance.cls",
            impact_score=5 if worst_cls > 0.25 else 3,
        ))

    # Page weight. Summed from Content-Length response headers, so chunked or
    # header-less responses are undercounted — the real figure is never smaller.
    WEIGHT_HEAVY, WEIGHT_VERY_HEAVY = 2000, 4000
    heavy = [p for p in pages if p.page_weight_kb and p.page_weight_kb > WEIGHT_HEAVY]
    if heavy:
        worst_w = max(p.page_weight_kb for p in heavy)
        findings.append(emit(
            "seo.performance.page_weight",
            severity="medium" if worst_w > WEIGHT_VERY_HEAVY else "low",
            affected_urls=[p.url for p in heavy],
            evidence=(
                f"{len(heavy)} page(s) transfer over {WEIGHT_HEAVY / 1000:.0f}MB; "
                f"heaviest {worst_w / 1024:.1f}MB across "
                f"{max((p.resource_count or 0) for p in heavy)} requests. Measured from "
                f"Content-Length headers, so the true figure is this or larger."
            ),
            why=(
                "Every kilobyte is time on the connection the visitor actually has, and mobile "
                "users on cellular pay for it twice — in latency and in data. Weight at this level "
                "sets a floor under LCP that no amount of render-path tuning gets below."
            ),
            recommendation=(
                "Look at the largest responses first: uncompressed images, un-subset fonts, and "
                "JS bundles pulling in libraries used on one route. Compress and modernise images, "
                "code-split by route, defer third-party tags, and confirm Brotli or gzip is on."
            ),
            framework_fix_key="performance.page_weight",
            impact_score=5 if worst_w > WEIGHT_VERY_HEAVY else 3,
        ))

    # Redirects
    redirects = [p for p in pages if p.redirect_count > 0]
    if redirects:
        findings.append(emit(
            "seo.redirects.chain",
            severity="low" if all(p.redirect_count <= 1 for p in redirects) else "medium",
            affected_urls=[p.url for p in redirects],
            evidence=f"{len(redirects)} URL(s) redirect before resolving.",
            why="Redirect chains waste crawl budget and add latency. Each hop = ~100ms added LCP.",
            recommendation="Point links directly to final URL. Limit to 1 redirect max.",
            framework_fix_key="redirects.chain", impact_score=3,
        ))

    # Fetch errors
    errs = [p for p in pages if p.fetch_error or (p.status and p.status >= 400)]
    if errs:
        findings.append(emit(
            "seo.fetch.errors",
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
        "BlogPosting", "Article", "FAQPage", "QAPage",
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


def _print_checks(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    """Eager --list-checks callback: print the catalog and exit before URL is needed."""
    if not value or ctx.resilient_parsing:
        return
    width = max(len(cid) for cid, _, _ in list_checks())
    for cid, severity, category in list_checks():
        click.echo(f"{cid.ljust(width)}  {severity.ljust(13)}  {category}")
    ctx.exit()


@click.command()
@click.argument("url")
@click.option(
    "--list-checks", is_flag=True, callback=_print_checks, expose_value=False, is_eager=True,
    help="Print every finding id the analyzer can emit, with severity and category, then exit.",
)
@click.option("--out", "out_dir", default="./audits", help="Output directory (default ./audits)")
@click.option("--max-pages", default=15, type=int, help="Max templates to sample (default 15)")
@click.option("--no-render", is_flag=True, help="Disable Playwright fallback (httpx-only)")
@click.option(
    "--focus",
    # "strategic" used to be offered here but no rule emits that category, so the
    # option silently produced an empty findings list. Strategic analysis is the
    # skill's job, downstream of this file, not a filter over these findings.
    type=click.Choice([*CATEGORIES, "all"]),
    default="all",
    help="Restrict findings to one category (default: all).",
)
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
