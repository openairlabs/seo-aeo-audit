# AEO Evidence Notes

Why this audit weights certain AEO signals the way it does. Every claim that changes a finding's
severity should be traceable to a primary source recorded here — the point is that a user can argue
with the evidence rather than with the tool.

Recorded so that future maintainers know *why* a severity was set, and can revisit when the
underlying evidence changes.

---

## llms.txt — reported, but zero weight

**Finding:** `aeo.llms_txt.missing` — severity `info`, impact 1.

llms.txt is widely recommended in SEO commentary as an AI-visibility signal. The available primary
evidence does not support that:

- **Google (John Mueller, 2025)** — stated no AI system currently uses llms.txt, and drew the
  comparison to the meta keywords tag: a file authors control, describing themselves, which search
  systems therefore have little reason to trust.
- **Google (Gary Illyes, July 2025)** — no plans to support it.
- **SE Ranking (Nov 2025)** — study across ~300,000 domains. Of the 50 most-cited domains in AI
  answers, one served an llms.txt file.
- **OtterlyAI server-log analysis** — llms.txt accounted for 84 of 62,100 AI-bot requests observed
  (~0.1%).

**Where it does have value:** AI *coding* agents (Cursor, Cline, Claude Code) and documentation
platforms that generate it for developer docs. That is a developer-experience feature, not a search
one.

**Policy:** report presence or absence; assign no citation-ranking weight; never rank it above SSR,
schema depth, or crawler access in a roadmap.

---

## FAQPage — keep it, don't chase it

**Finding:** `aeo.faqpage_schema.missing` — severity `info`, impact 2.

Google retired FAQPage rich results for all sites. Rich Results Test support and Search Console
reporting are being wound down on the same trajectory. So:

- There is **no SERP benefit** to adding FAQPage today.
- AI answer engines still parse the markup for question-answer pairs, so it retains some extraction
  value.
- Existing FAQPage markup should **never** be flagged for removal — it is valid Schema.org, it costs
  nothing to serve, and it may be feeding AI extraction.

For pages that are genuinely one question with community answers, `QAPage` is the correct type and
is not deprecated.

---

## Deprecated schema types

**Finding:** `aeo.schema.deprecated` — severity `info`, impact 1.

Google has retired rich results for `HowTo` (September 2023), `ClaimReview`, `CourseInfo`,
`EstimatedSalary`, `LearningVideo`, `VehicleListing` (June 2025) and `SpecialAnnouncement`
(July 2025). Detecting these is worth an informational note — it is maintenance cost with no return
— but it is not an error, and the audit does not penalise the score for it.

---

## Server-side rendering — the signal that actually matters

**Finding:** `aeo.ssr.missing` — severity `critical`, impact 10.

AI crawlers do not execute JavaScript. A page whose content only exists after client-side hydration
is empty to every AI answer engine, regardless of how good its schema or content is. This outranks
every other AEO consideration in the audit: there is no point tuning passage length on a page an AI
crawler sees as an empty shell.

This is also why the analyzer's `was_spa_shell` detection is worth scoring rather than merely
collecting.

---

## Passage-level citability

**Finding:** `aeo.passage.citability` — severity `medium`.

Two observations drive the thresholds:

- Citable passages cluster around **134–167 words** — long enough to stand alone as an answer, short
  enough to quote whole.
- Roughly **44% of AI citations come from the first 30% of a page** (SE Ranking). Burying the
  substantive answer below the fold of the document costs citation eligibility.

The direct-answer rule follows from the same place: lead with a **40–60 word** answer to the implied
question, then expand.

---

## Content freshness

**Finding:** `aeo.content_freshness.stale` — `medium` at 180 days.

Recency correlates strongly with citation. Content under three months old is substantially more
likely to be cited, and citation eligibility drops off past roughly six months. The previous
365-day threshold was too lenient to be actionable — it only fired once a page was already well
past the point where refreshing would have helped.

---

## What this audit deliberately does not measure

Brand-mention correlation, backlink profiles, and rank tracking all matter for AI visibility —
brand mentions across YouTube, Reddit and Wikipedia correlate with AI citation more strongly than
domain authority does. They are excluded here because they need paid APIs or a full crawl, and this
tool is designed to run standalone against a live URL with no credentials. See README for the full
scope boundary.
