# seo-aeo-audit

A framework-agnostic SEO + AEO (Answer-Engine Optimization) audit skill for Claude Code. Point it at any live website on any framework and it produces a prioritized improvement report with stack-specific code fixes — plus a plain-English summary for non-technical stakeholders.

Works as a Claude Code skill (install once, invoke from any repo) or as a standalone CLI tool.

---

## What it does

Given a URL, the tool:

1. **Discovers your site structure** via sitemap + homepage crawl
2. **Classifies pages into templates** (home, product, pricing, blog, docs, etc.) and samples one representative per template (~10-15 pages)
3. **Fetches each page** — httpx for static HTML, Playwright fallback for SPAs
4. **Parses** meta tags, OG/Twitter, canonical, hreflang, robots, headings, word count, image alt coverage, internal link graph, and every JSON-LD block
5. **Detects the framework** (Next.js, Astro, Nuxt, SvelteKit, Gatsby, Remix, WordPress, Shopify, etc.)
6. **Scores** SEO and AEO on a 0-100 scale
7. **Synthesizes two reports:**
   - **Technical report** (`report.md` + `report.docx`) — for the web/content team. Full finding list with framework-specific code fixes.
   - **Layman summary** (`summary.md` + `summary.docx`) — for stakeholders. Plain-English traffic-light health check, top 5 priorities with effort estimates, and a strategic ideas & guidance section.

**80% of the report is technical checks the Python analyzer runs deterministically.** The other 20% is strategic/design reasoning Claude does by looking at the captured screenshots — above-the-fold clarity, positioning, information architecture, visual hierarchy, brand voice distinctiveness, topical authority gaps.

---

## Why AEO matters

Most audits cover SEO. This one equally weights AEO — Answer-Engine Optimization — the signals that make AI assistants (ChatGPT, Perplexity, Google AI Overview, Claude) cite your site. In 2026, more than half of all searches go through an AI interface before ever hitting a Google blue link. If your Organization schema doesn't reference Wikidata, your FAQ sections don't emit `FAQPage` JSON-LD, your blog posts don't have Speakable schema, and your robots.txt silently blocks `GPTBot` / `ClaudeBot` / `PerplexityBot` — you're invisible to half of all searches.

The report treats these with the same severity as missing title tags.

---

## Install

Python 3.10+ required.

```bash
git clone https://github.com/YOUR-ORG/seo-aeo-audit ~/.claude/skills/seo-aeo-audit
cd ~/.claude/skills/seo-aeo-audit

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install at least one browser. Chromium is smallest/fastest.
python -m playwright install chromium
# or Firefox: python -m playwright install firefox
# or WebKit:  python -m playwright install webkit
```

For use as a Claude Code skill, the directory needs to be at `~/.claude/skills/seo-aeo-audit/` — clone or symlink accordingly.

---

## Use as a Claude Code skill

Once installed at `~/.claude/skills/seo-aeo-audit/`, Claude Code auto-loads the skill. From any project, just say:

```
"Audit example.com"
"Run SEO/AEO audit on https://your-site.com"
"Check SEO gaps on competitor.com"
```

Claude reads `SKILL.md`, runs the Python analyzer, reads the findings JSON + screenshots, then writes the markdown reports and converts them to `.docx`.

---

## Use as a standalone CLI

```bash
python audit.py https://example.com --out ./audits/
```

Flags:

| Flag | Default | Description |
|---|---|---|
| `--out DIR` | `./audits` | Output directory |
| `--max-pages N` | `15` | Max templates to sample |
| `--no-render` | off | Skip Playwright fallback (httpx only, faster, misses SPAs) |
| `--focus {seo,aeo,strategic,all}` | `all` | Narrow analyzer output |
| `--browser {auto,chromium,firefox,webkit}` | `auto` | Playwright browser. `auto` tries chromium → firefox → webkit |

Then convert the markdown reports to Word format:

```bash
python render_docx.py report.md  report.docx
python render_docx.py summary.md summary.docx
```

---

## Output

```
./audits/<domain>/<YYYY-MM-DD>/
├── report.md         ← Technical audit (for web/content team)
├── report.docx       ← Same, as Word doc
├── summary.md        ← Layman summary (for stakeholders)
├── summary.docx      ← Same, as Word doc
├── findings.json     ← Structured findings (for tooling)
├── pages.json        ← Raw per-page parsed data
└── screenshots/
    ├── home-desktop.png
    ├── home-mobile.png
    └── ...
```

---

## What gets checked

### SEO (deterministic, Python)
- Meta title (30-70 chars, keyword placement), meta description (120-160 chars, CTA)
- Canonical, hreflang, robots directives, viewport, `<html lang>`, charset
- Open Graph (type, url, title, description, image 1200×630) + Twitter Card
- Sitemap.xml + robots.txt consistency, llms.txt presence
- Heading hierarchy (exactly one H1; no H1→H3 jumps)
- Word count per template (thin-content flags)
- Image alt coverage, internal link graph, broken links (sampled)
- Redirect chains, status codes
- Core Web Vitals proxies (FCP, LCP element, page weight, resource count) via Playwright

### AEO (deterministic, Python)
- Schema.org coverage matrix per template (WebSite + Organization + BlogPosting + FAQPage + HowTo + Product + SoftwareApplication + BreadcrumbList + Speakable)
- Organization schema depth (founder[], sameAs[] **with Wikidata URL**, knowsAbout[], slogan, foundingDate, contactPoint, hasOfferCatalog)
- FAQ content detection vs. FAQPage schema presence
- Direct-answer paragraph (≤50 words opening)
- Question-format headings count
- Table of contents on long posts
- Author schema + E-E-A-T fields
- `dateModified` freshness
- AI crawler robots.txt policy (GPTBot, ClaudeBot, PerplexityBot, CCBot, Google-Extended, Applebot-Extended, Bytespider, Amazonbot, cohere-ai, Diffbot, DuckAssistBot, PetalBot, YouBot, etc.)
- Wikidata cross-reference detection

### Strategic & design (Claude, from screenshots)
- Above-the-fold 3-second test — what does the site do, who's it for?
- Hero headline sharpness vs. template SaaS generics
- Primary CTA visibility & singularity
- Social proof presence in first viewport
- Navigation clarity (jobs-to-be-done vs. org chart)
- Conversion path depth
- Brand voice distinctiveness
- Topical authority gaps
- Mobile-first impression
- Visual hierarchy

---

## Framework support

Auto-detects and produces stack-specific code examples for:

- **Astro** (incl. app-router layouts + structured-data utility pattern)
- **Next.js** (App Router + Pages Router)
- **Nuxt** (3+)
- **SvelteKit**
- **Gatsby** (Head API)
- **Remix**
- **WordPress** (with Rank Math / Yoast)
- **Shopify** (Liquid themes)
- **Generic HTML** (fallback for anything else)

Each framework has a dedicated fix library under `frameworks/` keyed by finding ID.

---

## Performance

- **Full run (render enabled):** 30-90 seconds for 10-15 templates
- **httpx-only (`--no-render`):** 10-20 seconds
- **Cost:** zero API fees (all deterministic Python + Claude's existing context)

---

## What this is not

- Not a full Lighthouse replacement — we capture key performance signals, not a complete perf budget
- Not a Screaming Frog replacement — template-sampling is intentional for signal extraction, not full crawl
- Not a rank tracker
- Not a content-writing tool

---

## Contributing

Pull requests welcome. Particularly useful:
- New framework fix libraries under `frameworks/`
- Additional check classes in `audit.py`
- Better detection heuristics for edge-case SPAs

---

## License

MIT — see `LICENSE`.
