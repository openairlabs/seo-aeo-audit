# Playbook Distilled — AEO/SEO Principles

The principles that drive modern "gold-standard" content and site architecture. Apply them as evaluation lenses when synthesizing the audit report.

## The core shift (2024 → 2026)

- **60% of searches now happen through AI interfaces** (ChatGPT, Perplexity, Google AI Overview, Claude).
- **40% still go through Google blue links.**
- Every site needs to be optimized for **both**. AEO is not SEO-lite — it's a parallel discipline.

## AEO ≠ SEO — where they diverge

| SEO | AEO |
|---|---|
| Rank in SERP | Get cited verbatim by AI engines |
| Keyword-targeted meta | Entity-recognized content |
| Backlinks as authority | Schema + entity density as authority |
| CTR from the blue link | Attribution in AI answer |
| Content length (2000+) | Direct-answer opening (≤50 words) |
| Sitemap discovery | llms.txt + schema + Wikidata |

**The synthesis**: write for both. A sharp direct-answer opening satisfies AEO; the 2000-word explanation satisfies SEO.

## The six AEO multipliers

When auditing, look for these specifically. Sites that nail 5/6 outperform on AI surfaces:

1. **Wikidata-referenced Organization schema** — the strongest entity signal. Without it, your brand is a string, not a citable entity.
2. **FAQPage + HowTo + Speakable schemas** — direct answer-engine surfaces.
3. **Direct-answer openings** — ≤50 words. AI cites verbatim.
4. **Question-format headings** — auto-expands AEO surface area.
5. **Open robots.txt policy for AI crawlers** — GPTBot, ClaudeBot, PerplexityBot, CCBot, Google-Extended, Applebot-Extended. Blocked = invisible.
6. **llms.txt** — emerging standard; maturity signal.

## The content quality stack (research → generation → refinement → polish)

When judging blog content strategically:

- **Research depth**: Does the post reference real data, real user questions (PAA, Reddit/Quora), or is it generic reformatting of other articles?
- **Brand voice**: Does it sound distinctive or like template SaaS ("leverage", "seamlessly", "best-in-class")?
- **Human-in-the-loop signals**: Author bylines with photos/credentials? Updated dates? Real examples vs. fabricated?
- **Structure for AEO**: Direct-answer open, question-format H2/H3, FAQ block with schema, TOC for long posts, citations.

## Common failure patterns

1. **"One model/framework for everything"** — optimizing only for Google or only for AI. Both.
2. **"AI writes, then publish"** — no human review = generic, template copy. Dead-on-arrival for AEO.
3. **Technical-only audits** — ignoring brand voice, IA, positioning leaves 20% of the value on the table.
4. **No brand voice config** — the site reads like every other AI-written competitor.
5. **No caching / no reuse** — every page rebuilds the same org/website schema inline instead of sharing a source.
6. **Deploying before hardening** — launching without FAQPage/Speakable/Breadcrumb/Author schemas means years of AI-surface underperformance.
7. **No analytics on AEO** — tracking Google rankings but not AI-engine citation rate.

## Report tone guide

- **Be direct.** Quantify findings. "73% of sampled blog posts missing canonical" > "Some pages could use canonicals".
- **Lead with biggest gap.** Home page missing Organization schema > 50 meta description tweaks.
- **Don't hedge.** "Add Wikidata URL to Organization.sameAs" is better than "Consider adding entity references where appropriate."
- **Cut the cliché vocabulary.** Never use "comprehensive", "holistic", "leverage", "world-class", "seamlessly", "cutting-edge" in the report body — they signal template thinking.
- **Strategic ≠ vague.** The 20% strategic layer should be as specific as the 80% technical. "Hero headline is generic — 'The best CRM for teams' reads identical to 40 competitors. Sharper: pick one job ('Closing deals', 'Renewals') and own that frame."
