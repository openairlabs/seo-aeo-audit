---
name: seo-aeo-audit
description: Audit any website (any framework) for SEO and AEO (Answer-Engine Optimization) quality, producing a prioritized improvement report with framework-specific code fixes. Holistic whole-site audit, not just blog posts. Use when the user says "audit X.com", "SEO audit on...", "AEO audit", "check SEO/AEO gaps on...", or asks for an improvement/architectural report on a live website. Works on Next.js, Astro, Nuxt, SvelteKit, Gatsby, Remix, WordPress, Shopify, or generic HTML.
---

# SEO + AEO Audit Skill

You are running a holistic SEO & AEO audit of a live website. This skill combines a deterministic Python analyzer with your own judgment to produce a prioritized, strategic improvement report with framework-specific code fixes.

## When to invoke

Trigger when the user asks to:
- "audit [domain]" / "run an SEO audit" / "AEO audit" / "check SEO gaps"
- "analyze [URL] for search optimization"
- "generate an improvement report for [site]"
- produce "architectural improvements" or "gaps" for search/AI visibility

## Process (follow in order)

### Step 1 — Verify environment

**CRITICAL: This skill installs its Python deps into a venv at `~/.claude/skills/seo-aeo-audit/venv/`. Always use the venv's Python — NEVER plain `python3` or `python`.** Plain `python3` is the system Python and won't have the skill's deps, so it will always report missing modules and send you down a false install path.

The single Python binary to use everywhere in this skill is:

```
~/.claude/skills/seo-aeo-audit/venv/bin/python
```

**First, check if the venv is installed:**

```bash
ls ~/.claude/skills/seo-aeo-audit/venv/bin/python 2>/dev/null && echo "venv present" || echo "venv missing"
```

**If the venv is present, verify deps (using the venv's Python):**

```bash
~/.claude/skills/seo-aeo-audit/venv/bin/python -c "import playwright, httpx, bs4, tldextract, click, docx" 2>&1
```

(`extruct` is optional. `docx` means `python-docx` — required for the `.docx` output step.)

**Only if the venv is missing or the import check fails,** run the install ladder:

```bash
# 1. If pip is missing (Ubuntu/WSL often lacks it):
sudo apt-get install -y python3-pip python3-venv

# 2. Create the skill's venv:
python3 -m venv ~/.claude/skills/seo-aeo-audit/venv

# 3. Install Python deps (use the venv's pip, NOT system pip):
~/.claude/skills/seo-aeo-audit/venv/bin/pip install -r ~/.claude/skills/seo-aeo-audit/requirements.txt

# 4. Install at least one Playwright browser (uses the venv's python):
~/.claude/skills/seo-aeo-audit/venv/bin/python -m playwright install chromium
# or firefox: ~/.claude/skills/seo-aeo-audit/venv/bin/python -m playwright install firefox
# or webkit:  ~/.claude/skills/seo-aeo-audit/venv/bin/python -m playwright install webkit
```

Offer to run the install for the user if needed. Do not proceed with the analyzer until the venv's Python can import the modules.

### Step 2 — Run the analyzer

Always invoke via the venv's Python:

```bash
~/.claude/skills/seo-aeo-audit/venv/bin/python ~/.claude/skills/seo-aeo-audit/audit.py <URL> --out ./audits/
```

Common flags:
- `--max-pages N` — cap sampled templates (default 15)
- `--no-render` — skip Playwright fallback (faster, misses SPAs)
- `--focus {seo,aeo,strategic,all}` — narrow the analyzer output
- `--browser {auto,chromium,firefox,webkit}` — Playwright browser. `auto` probes in order chromium → firefox → webkit and uses the first available. Default: `auto`.
- `--compare URL` — produce a delta vs. reference site (use with caution, doubles runtime)

Expect 30-90 seconds. The analyzer writes to `./audits/<domain>/<YYYY-MM-DD>/`:
- `findings.json` — structured findings (this is your source of truth)
- `screenshots/` — desktop + mobile PNGs per sampled URL
- `pages.json` — raw parsed data per page (useful for citations)

### Step 3 — Read findings.json and screenshots

```bash
# Structure:
# findings.json
#   - run: { url, date, pages_sampled, framework_detected, scores }
#   - findings: [ { id, severity, category, template, affected_urls, evidence, why, recommendation, framework_fix, impact_score } ]
#   - templates: { template_name: [sample_urls] }
#   - schema_matrix: { template: { BlogPosting: bool, FAQPage: bool, ... } }
```

Then look at 3-5 key screenshots (home, primary product/pricing, blog post, key conversion page). The strategic/design 20% layer of the report comes from YOUR read of these screenshots — the analyzer cannot judge visual hierarchy or positioning.

### Step 4 — Synthesize the technical report

Write the report to `./audits/<domain>/<YYYY-MM-DD>/report.md` using `templates/report-template.md` as scaffold. The report MUST contain these sections in this order:

1. **Executive Summary** — scores (SEO, AEO, Strategic 0-100), 3 biggest wins, 3 biggest gaps, recommended focus
2. **Critical Issues** — blockers that lose traffic/ranking today. Filter `severity: critical` from findings.
3. **High-Impact Improvements** — 30-day list, ordered by `impact_score`
4. **Per-Template Findings** — one section per sampled template
5. **Schema Coverage Matrix** — render the matrix as a markdown table (✓/✗)
6. **AEO Readiness** — answer-engine posture: schema depth, AI crawler access, entity linking (Wikidata etc.), direct-answer structure, Speakable schema
7. **Strategic & Design Layer (the 20%)** — YOUR judgment from screenshots. Cover: above-the-fold 3-second test, positioning sharpness, primary CTA visibility, social proof, IA clarity, conversion path, visual hierarchy, brand voice distinctiveness, topical authority gaps, mobile impression
8. **30/60/90 Roadmap** — prioritized action plan
9. **Framework-Specific Code** — for each critical/high finding, show the fix in the detected framework. Load `frameworks/<detected>.md` for patterns.
10. **Methodology** — one paragraph + link to raw findings.json

### Step 5 — Apply framework-specific fixes

The analyzer populates `run.framework_detected` (one of: `astro`, `nextjs`, `nuxt`, `sveltekit`, `gatsby`, `remix`, `wordpress`, `shopify`, `unknown`).

For the Framework-Specific Code section:
1. Read `frameworks/<detected>.md` — contains canonical code snippets per issue class
2. For each critical + high finding, cross-reference its `id` against the framework file
3. If the framework is `astro`, reference `references/astro-gold-standard-patterns.md` for the full-depth pattern library (Organization schema depth, Speakable schema, combined `@graph` utility, AI bot detection, etc.)
4. Fall back to `frameworks/generic-html.md` when framework is unknown

### Step 6 — Write the technical report

Keep the report actionable. For every finding, include:
- **What** — one-line statement of the issue
- **Why it matters** — SEO/AEO impact in plain language
- **Fix** — HTML-level description
- **Code** — framework-specific snippet
- **Evidence** — sampled URL(s) + what was observed

### Step 7 — Write the layman summary (for non-technical stakeholders)

Every audit also produces a plain-English summary aimed at founders, marketing leads, and non-technical stakeholders who don't read code. Write to `./audits/<domain>/<YYYY-MM-DD>/summary.md` using `templates/summary-template.md` as scaffold.

Rules for the summary:
- **No jargon without definition.** Any technical term gets expanded in the glossary.
- **Business impact, not technical detail.** Frame every gap as lost traffic, fewer AI citations, lower conversion, worse first impression.
- **Traffic-light health section.** Green (what's working), yellow (could be better), red (broken / costing visibility).
- **Top 5 things to do first** — each with title, what, why, effort (day/week/month), who to assign.
- **Ideas & guidance section** — this is the "so what" for a strategic reader. Go beyond just fixing what's broken:
  - Content areas/topical authority the site should own
  - Positioning / hero-headline tightening (suggest actual rewrites when you can)
  - Trust signals to add (logos, case studies, counts, testimonials)
  - Pages to create (comparisons, tools/calculators, guides) that capture commercial-intent traffic
  - Distribution plays (llms.txt, newsletter, Wikipedia/Wikidata presence, community, podcast outreach)
- **Glossary** — define every acronym and technical term used.
- **Tone:** confident, specific, kind. Not condescending. Assume the reader is smart but not a web developer.

Keep `summary.md` to roughly 800-1500 words.

### Step 8 — Render .docx versions of both

Run the bundled converter to produce Word-compatible docx files (again, always via the venv's Python):

```bash
~/.claude/skills/seo-aeo-audit/venv/bin/python \
  ~/.claude/skills/seo-aeo-audit/render_docx.py \
  ./audits/<domain>/<date>/report.md \
  ./audits/<domain>/<date>/report.docx

~/.claude/skills/seo-aeo-audit/venv/bin/python \
  ~/.claude/skills/seo-aeo-audit/render_docx.py \
  ./audits/<domain>/<date>/summary.md \
  ./audits/<domain>/<date>/summary.docx
```

This gives stakeholders shareable `.docx` files alongside the markdown source.

### Step 9 — Final message to the user

End with two lines to the user:
1. `Report: ./audits/<domain>/<date>/report.md (+ .docx)` — for the web/content team
2. `Summary: ./audits/<domain>/<date>/summary.md (+ .docx)` — for stakeholders
Plus scores and the single top gap: `Scores: SEO X/100, AEO Y/100, Strategic Z/100. Top gap: <gap>.`

## The Strategic 20% — how to read screenshots

Don't just list what you see. For each screenshot, answer:

- **Above the fold**: In 3 seconds, what does this site do? Who's it for?
- **Hero**: Is the headline sharp and specific, or template SaaS? ("The ad spend OS for scaling lead gen" is sharp; "The best platform for your business" is not)
- **Visual hierarchy**: Does the design lead the eye to the primary CTA? Is there ONE primary CTA or competing ones?
- **Social proof**: Are trust signals (logos, counts, testimonials) visible in the first viewport?
- **IA signals**: Nav clarity — jobs-to-be-done or internal org chart? How many top-level items?
- **Copy voice**: Does it sound distinctive (brand-owned) or generic (AI-written template)?
- **Mobile**: How does the mobile screenshot change the experience? Is content re-ordered well?

## AEO is the differentiator — don't skimp on it

Most audits are SEO-only. AEO (how AI answer engines like ChatGPT, Perplexity, Google AI Overview, Claude represent the site) is where sites win or lose in 2026. Heavily emphasize:

- **Schema depth** — Organization schema with `sameAs` including Wikidata URL is a 10x entity-recognition signal
- **FAQPage + HowTo + Speakable schemas** — direct AEO surfaces
- **AI crawler policy** — robots.txt must allow GPTBot, ClaudeBot, PerplexityBot, CCBot, Google-Extended, Applebot-Extended (flag any disallows as gaps unless the user has a reason)
- **llms.txt** — emerging standard, flag if missing
- **Direct-answer structure** — first ≤50 words of each page should answer the implied question
- **Entity density** — how many Wikipedia/Wikidata-linkable entities appear as `sameAs`?

Reference: `references/playbook-distilled.md` for the full set of AEO principles applied during synthesis.

## Tone & calibration

- Be direct. This is a technical audit, not marketing copy.
- Quantify findings when possible ("73% of sampled blog posts missing canonical").
- Never say "comprehensive", "holistic", "leverage", "world-class" in the report — they're hollow filler.
- Lead with the biggest gap. If the home page has no Organization schema, that's worth more than 50 meta description tweaks.
- Be specific about framework-specific fixes — vague "add schema markup" is a failure mode.

## Output

Final deliverable the user sees:
```
./audits/<domain>/<YYYY-MM-DD>/
├── report.md          ← Technical audit (for web/content team)
├── report.docx        ← Same, as Word doc
├── summary.md         ← Layman summary (for stakeholders)
├── summary.docx       ← Same, as Word doc
├── findings.json      ← Raw analyzer output (structured, for tooling)
├── pages.json         ← Raw per-page parsed data
└── screenshots/
    ├── home-desktop.png
    ├── home-mobile.png
    ├── blog-desktop.png
    └── ...
```
