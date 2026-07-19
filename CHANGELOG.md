# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0]

Aligns the audit with current search and AI-search guidance, and adds the checks that carry the most
weight for AI citation.

### Breaking

`findings.json` is a machine-readable contract. Anything consuming it should review these:

- New severity level `info`, used for findings that are worth reporting but carry no score penalty.
  Consumers that switch on severity need a branch for it.
- `aeo.faqpage_schema.missing` is now `info` (was `high`); impact 2 (was 8).
- `aeo.llms_txt.missing` is now `info` (was `medium`); impact 1 (was 5).
- `aeo.content_freshness.stale` is now `medium` (was `low`) and triggers at 180 days (was 365).
- `aeo.direct_answer.missing` triggers above 60 words (was 80).
- `HowTo` is no longer a required type for the `tool` template, and is replaced by `QAPage` in the
  schema coverage matrix. The matrix column set has changed.
- `PageData.howto_schema` is replaced by `PageData.deprecated_schema` (a list) in `pages.json`.

### Added

- `aeo.ssr.missing` (**critical**) — detects client-rendered pages by comparing body word count
  before and after JavaScript runs. AI crawlers do not execute JavaScript, so a client-rendered page
  reads as an empty shell to every answer engine. This is the highest-priority AEO check in the tool.
- `aeo.ssr.unverified` (info) — emitted when rendering was skipped (`--no-render`, or Playwright
  unavailable), since client rendering cannot be established without a render to compare against.
- `aeo.passage.citability` — scores section length against the 134-167 word band that AI engines
  cite best, and flags answers buried past the first 30% of a page.
- `aeo.schema.deprecated` (info) — reports schema types Google has retired rich results for: HowTo,
  SpecialAnnouncement, ClaimReview, CourseInfo, EstimatedSalary, LearningVideo, VehicleListing.
- `aeo.ai_crawlers.training_blocked` (info) — reports blocked training-only crawlers separately from
  search crawlers, since blocking them is a licensing decision rather than a visibility loss.
- Real Core Web Vitals measurement: `seo.performance.lcp` and `seo.performance.cls`, captured via
  PerformanceObserver during the Playwright pass.
- `seo.heading_hierarchy.jump`, `seo.open_graph.image_dimensions`, `seo.performance.page_weight`,
  `seo.images.legacy_format`, `seo.hreflang.non_reciprocal`.
- `--list-checks` prints all 37 finding ids the analyzer can emit, with severity and category, from
  a single source of truth. `references/checks-catalog.md` is kept in sync with it.
- `references/aeo-evidence.md` records the sources behind each severity decision, including the
  signals this tool deliberately does not weight.

### Changed

- **AI crawler list updated and split into two tiers.** Search/citation crawlers (GPTBot,
  OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-User, PerplexityBot, Perplexity-User,
  Google-Extended, Applebot-Extended, DuckAssistBot, MistralAI-User, YouBot) score separately from
  training crawlers (CCBot, anthropic-ai, cohere-ai, Bytespider, Amazonbot, Meta-ExternalAgent,
  Google-CloudVertexBot, Diffbot, PetalBot, Omgili, Timpibot). Adds Meta-ExternalAgent,
  MistralAI-User, Google-CloudVertexBot, Claude-User, Omgili and Timpibot.
- **robots.txt parsing follows RFC 9309.** Consecutive `User-agent` lines form one group sharing the
  rules that follow; unrecognised directives leave the group open; agent names match
  case-insensitively; a `Disallow: /` paired with a re-allowing `Allow:` is not treated as a full
  block. Crawlers without their own group correctly inherit the wildcard group. Parsing is extracted
  to `parse_robots_txt()` so it can be tested without network access.
- **FAQPage guidance updated.** Rich results are retired for FAQPage across all sites; the markup
  still feeds AI answer extraction. The tool now reports it as optional, never recommends removing
  existing markup, and points genuine question-and-answer pages at `QAPage`.
- **llms.txt guidance updated** to reflect that no major AI search system is known to consume it.
  Presence is reported; no citation weight is assigned. Framework snippets for generating one remain
  for users who want it for AI coding agents.
- **Schema recommendations follow current Google guidance** — HowTo removed throughout.
- Per-template schema coverage now checks every sampled page in the template rather than the first.
- `SpeakableSpecification` detection uses a structural check instead of a string scan.
- Core Web Vitals documentation states which metrics this tool reports. LCP and CLS come from a
  single synthetic load; **INP is out of scope** because it requires real user interaction and only
  exists in field data (CrUX).
- AI search figures updated to current data (AI Overviews at 2.5B+ monthly users, Google I/O 2026).
- User-agent string now identifies the tool and links to this repository, so site owners can
  recognise it in access logs.
- README documents the scope boundary: what the tool covers, and what needs a paid index,
  credentials, or a full crawl.
- Framework snippets use `YYYY-MM-DD` placeholders instead of concrete dates.

### Removed

- `extruct` and `w3lib` dependencies. `extruct` was imported behind a try/except and its
  availability flag was never read; `w3lib` was only its transitive dependency.
- Orphan pages, broken internal links, internal link depth, RSS autodiscovery, image sitemaps and OG
  image status are now listed under "out of scope" — each needs a full site crawl, which this tool
  does not perform. Fields that are parsed for the report but carry no score are listed under
  "collected but not scored", so the boundary is explicit in both directions.

### Fixed

- Date-only `dateModified` values are parsed, widening freshness coverage to the most common date
  format.
- `--focus strategic` returns a meaningful result set.
