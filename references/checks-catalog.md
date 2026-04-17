# Checks Catalog

Every check run by the analyzer, what it measures, and why it matters. Claude uses this when the user asks "why does X matter?" or "what does the [finding] mean?".

## SEO (deterministic)

### Head & crawl directives
- **Title tag present, 30-70 chars** — largest on-page ranking signal + SERP CTR driver
- **Meta description present, 120-160 chars** — CTR driver; Google auto-generates ugly fallbacks
- **Canonical tag present, self-referential, absolute** — prevents duplicate content dilution
- **Hreflang pairs** — required for multilingual; wrong/missing hreflang confuses index
- **Robots meta (+ X-Robots + robots.txt) consistent** — contradictions cause accidental de-indexing
- **`<html lang>` set** — signals content language; affects Google Translate + accessibility
- **Viewport meta** — mobile usability ranking factor
- **Charset, theme-color, favicon, manifest** — small signals but ubiquitous; missing → careless site impression

### Distribution & discovery
- **robots.txt served** — crawl-directive discoverability
- **sitemap.xml present, referenced in robots.txt** — accelerates indexation, signals canonical set
- **llms.txt present** — emerging convention for AI crawlers
- **RSS autodiscovery** — for content sites
- **Image sitemap** — boosts image search
- **Status codes / redirect chains** — each hop = wasted crawl budget + latency
- **Orphan pages** — in sitemap but no inbound internal links → crawlers skip

### Content structure
- **Exactly 1 H1** — clarifies primary topic
- **Heading hierarchy** — no H1→H3 jumps (accessibility + crawl)
- **Word count per template** — thin content loses to comprehensive competitors
- **Image alt coverage >80%** — accessibility + image search + AI image understanding
- **Internal link count / depth** — helps distribute PageRank, provides navigation signals
- **Broken internal links** — waste crawl budget, harm UX

### Social / share
- **OG tags: type, url, title, description, image (1200×630), site_name** — social CTR
- **Twitter card tags** — direct social CTR
- **OG image returns 200** — broken OG → empty previews

### Performance signals
- **LCP (Largest Contentful Paint)** — Core Web Vital (ranking factor); <2.5s good
- **FCP (First Contentful Paint)** — user-perceived speed; <1.8s good
- **CLS (Cumulative Layout Shift)** — Core Web Vital; <0.1 good
- **Page weight** — correlates with LCP and mobile speed
- **Resource count** — too many → parallelism ceiling hit
- **Modern image formats (webp/avif)** — 30-50% smaller than jpg/png

## AEO (deterministic)

### Schema.org coverage per template
- **Home: WebSite + Organization + BreadcrumbList** — required for Knowledge Graph
- **Blog post: BlogPosting + Breadcrumb + (FAQPage if FAQ) + Author** — rich results, AI citation
- **Pricing: Product + Offer** — price rich results
- **Product/platform: SoftwareApplication + Offer + AggregateRating** — software listings
- **Tool page: HowTo + SoftwareApplication** — step-by-step rich results
- **About: AboutPage + Organization.founder** — entity depth
- **Legal: no schema required**

### Organization schema depth (single biggest AEO signal)
- `founder[]` — E-E-A-T signal
- `sameAs[]` with **Wikidata URL** — cross-reference for Knowledge Graph + AI
- `knowsAbout[]` — topical authority
- `slogan` — brand entity completeness
- `foundingDate`, `foundingLocation`, `legalName`
- `contactPoint` — trust + local SEO
- `hasOfferCatalog` — product visibility

### Answer-engine readability
- **Direct-answer paragraph ≤50 words** — AI engines cite verbatim; long intros bury the answer
- **Question-format H2/H3 count** — triggers PAA surfacing + FAQPage auto-extraction
- **FAQ in content + FAQPage schema** — missing schema on detected FAQ = wasted signal
- **SpeakableSpecification** — voice search + Google Assistant direct answers
- **Table of contents with anchors** — AI chunks content; TOC helps surface jump-to links
- **Citations to authoritative sources** — helps AI verify claims + increases your citation rate

### AI crawler & emerging signals
- **robots.txt allows GPTBot, ClaudeBot, PerplexityBot, CCBot, Google-Extended, Applebot-Extended** — blocked crawlers = invisible to AI answer engines
- **llms.txt** — emerging AEO maturity signal
- **Author schema + E-E-A-T fields** (`jobTitle`, `sameAs`, `alumniOf`) — expert attribution
- **Entity density / Wikidata references** — transforms "string" into "entity"
- **dateModified freshness** — recent = preferred for AI queries

## Strategic & Design (Claude judgment)

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
- **CTA consistency** — same verb, same color across templates
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
