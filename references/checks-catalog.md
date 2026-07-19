# Checks Catalog

Every check the analyzer runs, what it measures, and why it matters. Claude uses this when the user
asks "why does X matter?" or "what does this finding mean?".

**This file is a contract with `audit.py`.** Every id below is emitted by the analyzer, and every id
the analyzer emits is listed below. Verify with:

```bash
~/.claude/skills/seo-aeo-audit/venv/bin/python audit.py --list-checks
```

If that output and this file disagree, one of them is a bug.

---

## SEO (deterministic)

### Head & crawl directives

| Finding id | Severity | What & why |
|---|---|---|
| `seo.title.missing` | critical | No `<title>`. The largest on-page ranking signal and the SERP click driver. |
| `seo.title.length` | medium | Outside 30-70 chars. Short under-sells; long truncates in the SERP. |
| `seo.meta_description.missing` | high | Google auto-generates a fallback, usually with worse CTR than a written one. |
| `seo.meta_description.length` | low | Outside 120-160 chars. Truncates or under-sells. |
| `seo.canonical.missing` | high | Without a canonical, URL variants from filters, UTMs and pagination compete with each other. |
| `seo.html_lang.missing` | medium | Signals content language to search engines and assistive tech. |
| `seo.viewport.missing` | high | Mobile rendering breaks without it. Mobile usability is a ranking factor. |
| `seo.hreflang.non_reciprocal` | medium | A page declaring hreflang alternates must include a self-referential entry, or the cluster is ignored. |

### Distribution & discovery

| Finding id | Severity | What & why |
|---|---|---|
| `seo.robots.missing` | high | robots.txt is how crawlers discover allowed paths and the sitemap. |
| `seo.sitemap.missing` | high | Sitemaps accelerate indexation and signal the canonical URL set. |
| `seo.redirects.chain` | low / medium | Each hop wastes crawl budget and adds latency. Medium when more than one hop. |
| `seo.fetch.errors` | high | Pages returning 4xx/5xx lose ranking and drop out of the index. |

### Content structure

| Finding id | Severity | What & why |
|---|---|---|
| `seo.h1.count` | medium | Exactly one H1 clarifies the primary topic for crawlers and screen readers. |
| `seo.heading_hierarchy.jump` | low | Skipping a level (H1 straight to H3) breaks the document outline. |
| `seo.content.thin` | medium | Thin pages lose to deeper competitors and give AI engines too little to cite. |
| `seo.images.missing_alt` | medium | Alt text drives accessibility, image search, and AI image understanding. |

### Social

| Finding id | Severity | What & why |
|---|---|---|
| `seo.open_graph.incomplete` | medium | Missing OG fields produce broken or ugly link previews — a direct CTR cost. |
| `seo.open_graph.image_dimensions` | low | og:image should be 1200×630. Wrong ratios get cropped badly by each platform. |

### Performance

Measured in a single synthetic page load, not from real visitors. Treat as indicative.

LCP and CLS require Chromium — under `--browser firefox` or `--browser webkit` they stay null and
neither finding fires. `page_weight` is derived from Content-Length, so chunked responses contribute
nothing and the figure is a lower bound.

| Finding id | Severity | What & why |
|---|---|---|
| `seo.performance.lcp` | medium / high | Largest Contentful Paint. Good ≤2.5s, poor >4.0s. |
| `seo.performance.cls` | low / medium | Cumulative Layout Shift. Good ≤0.1, poor >0.25. |
| `seo.performance.page_weight` | low / medium | Correlates with LCP and mobile speed. Derived from Content-Length, so it is a lower bound. |
| `seo.images.legacy_format` | low | WebP/AVIF are typically 30-50% smaller than the equivalent JPEG/PNG. |

**INP is not measured.** It is the third Core Web Vital, but it requires real user interaction and
can only come from field data (Google's CrUX dataset). No synthetic tool can produce it. Anything
claiming otherwise is measuring something else.

---

## AEO (deterministic)

### Rendering — check this first

| Finding id | Severity | What & why |
|---|---|---|
| `aeo.ssr.missing` | critical | AI crawlers do not execute JavaScript. A client-rendered page is an empty shell to every answer engine regardless of how good its schema or content is. Nothing else in this section matters until this passes. Detection compares body word count before and after JavaScript runs, so the evidence cites both numbers. |
| `aeo.ssr.unverified` | info | Rendering was skipped (`--no-render`, or Playwright unavailable), so there is no post-JavaScript document to compare against. The check could not run — this is not a pass. |

### Crawler access

| Finding id | Severity | What & why |
|---|---|---|
| `aeo.ai_crawlers.blocked` | high | Search/citation crawlers (GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-User, PerplexityBot, Perplexity-User, Google-Extended, Applebot-Extended, DuckAssistBot, MistralAI-User, YouBot) fetch pages to answer a live query and cite the source. Blocking them removes you from AI-mediated discovery. |
| `aeo.ai_crawlers.training_blocked` | info | Training crawlers (CCBot, anthropic-ai, cohere-ai, Bytespider, Amazonbot, Meta-ExternalAgent, Google-CloudVertexBot, Diffbot, PetalBot, Omgili, Timpibot) collect corpora rather than answering queries. Blocking them is a licensing decision with no search cost — recorded, not flagged. |
| `aeo.llms_txt.missing` | info | Reported for completeness only. No known AI search consumer and no citation weight — see [`aeo-evidence.md`](aeo-evidence.md). |

Two distinctions users routinely get wrong: blocking `Google-Extended` stops Gemini *training* but
does **not** remove you from AI Overviews, which crawl as `Googlebot`. And blocking `GPTBot` does not
stop ChatGPT citing you, because live browsing fetches as `ChatGPT-User`.

### Schema coverage

| Finding id | Severity | What & why |
|---|---|---|
| `aeo.schema.<template>.missing_types` | high | Per-template required types are missing. See [`schema-matrix.md`](schema-matrix.md) for the full matrix. |
| `aeo.schema.deprecated` | info | The page ships schema Google has retired rich results for. Valid markup, no return — maintenance cost only. |
| `aeo.organization_schema.shallow` | medium | Organization depth (`founder[]`, `sameAs[]`, `knowsAbout[]`, `slogan`, `foundingDate`, `contactPoint`, `hasOfferCatalog`, `logo`) is the strongest entity-recognition signal available. |
| `aeo.wikidata.unreferenced` | high | Without a Wikidata URL in `Organization.sameAs`, your brand is a string rather than an entity. |
| `aeo.faqpage_schema.missing` | info | Rich results are retired for FAQPage. The markup still feeds AI answer extraction, so it is worth having but not worth prioritising. Never remove existing FAQPage markup. |
| `aeo.speakable_schema.missing` | medium | `SpeakableSpecification` marks the excerpts voice assistants read aloud. |

### Answer-engine readability

| Finding id | Severity | What & why |
|---|---|---|
| `aeo.direct_answer.missing` | medium | Lead with a 40-60 word direct answer to the implied question. Long intros bury the quotable part. |
| `aeo.passage.citability` | medium | AI engines cite self-contained passages, not whole pages. Sections land best around 134-167 words, and roughly 44% of citations come from the first 30% of a page. |
| `aeo.toc.missing` | low | A TOC with anchors helps engines chunk long content and can surface jump-to links. |
| `aeo.content_freshness.stale` | medium | Fires past 180 days. Recent content is substantially more likely to be cited; eligibility falls off past roughly six months. |

---

## Collected but not scored

The analyzer parses these into `pages.json` for citation and manual inspection, but deliberately
emits no finding for them. They are available to Claude when writing the report; they do not affect
any score.

`charset` · `favicon` · `manifest` · `theme_color` · meta `robots` directives · Twitter Card tags ·
internal/external/nofollow link counts · `question_headings` · `breadcrumb_schema` ·
`author_schema` · FCP · `resource_count` · `heading_tree` · `was_spa_shell`

## Out of scope

Not checked, and not claimed. Each needs either a full site crawl or credentials this tool does not
ask for: orphan pages, broken internal links, internal link depth, RSS autodiscovery, image
sitemaps, OG image HTTP status, backlink profile, brand mentions, keyword rankings, field
performance data, and indexation reality. See the README for what covers each.

---

## Strategic & Design (Claude judgment, not the analyzer)

Nothing below produces a finding id. These are the lenses Claude applies to the captured
screenshots — the 20% of the report the analyzer cannot produce.

### Homepage / above-the-fold
- **3-second test** — can a visitor state what the product does?
- **Hero headline sharpness** — specific and category-defining vs. generic template SaaS
- **Primary CTA** — visible, singular, above-fold
- **Social proof** — logos, counts, testimonials in first viewport

### Information architecture
- **Nav: jobs-to-be-done vs. org chart** — "Pricing / Platform / Blog" > "Who we are / What we do / Our team"
- **Top-level nav count** — 5-7 ideal; 10+ is a signal IA is unsolved
- **Footer** — canonical path for conversions, trust/legal, sitemap completeness
- **Dead-end pages** — every page should have a next action

### Conversion architecture
- **Click depth to primary conversion** — 2 clicks is gold, 4+ is a leak
- **CTA consistency** — same verb, same colour across templates
- **Pricing clarity** — tier differentiation, anchoring, objection handling

### Brand voice & E-E-A-T
- **Distinctive copy** — no "leverage", "seamlessly", "world-class"
- **Author bylines + faces on blog** — E-E-A-T signal
- **Case studies / quotes density** — trust builder + unique content

### Topical authority gaps
- **Pillar/cluster map** — implied from blog taxonomy; obvious category holes?
- **Comparison / vs / alternatives coverage** — commercial-intent traffic capture

### Visual & accessibility impression
- **Visual hierarchy** — design leads eye to action
- **Whitespace & density**
- **Font-size minimums, contrast**
- **Mobile re-composition** — does the mobile experience read well, or is it a zoomed desktop?
