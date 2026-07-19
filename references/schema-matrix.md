# Schema.org Coverage Matrix by Template

What each page template SHOULD have as JSON-LD. The analyzer flags missing types in findings; the report renders this as a matrix.

| Template | Required | Recommended | AEO-multiplier |
|---|---|---|---|
| **home** | `WebSite`, `Organization` | `BreadcrumbList` (if nested), `SiteNavigationElement` | Organization with full depth (founder, Wikidata sameAs, knowsAbout, slogan) |
| **blog_index** | `Blog`, `BreadcrumbList` | `ItemList` of BlogPosting | `CollectionPage` |
| **blog_post** | `BlogPosting`, `BreadcrumbList` | `Person` (author), `FAQPage` (if questions) | `SpeakableSpecification`, `TechArticle` (if technical) |
| **category** | `CollectionPage`, `ItemList`, `BreadcrumbList` | — | — |
| **pricing** | `Product` OR `SoftwareApplication`, `Offer` | `AggregateOffer`, `AggregateRating` | `FAQPage` (objection handling) |
| **product** | `Product`, `Offer` | `AggregateRating`, `Review`, `Brand` | — |
| **platform** | `SoftwareApplication`, `Offer` | `AggregateRating`, `ApplicationCategory` | — |
| **tool** | `SoftwareApplication` | `VideoObject` (if demo) | `SpeakableSpecification` |
| **integration** | `Product` or `Service`, `Offer` | Related `Brand` (the integration partner) | — |
| **use_case** | `WebPage`, `BreadcrumbList` | `QAPage` (if genuine Q&A) | — |
| **about** | `AboutPage`, `Organization` (reference only) | `Person` for each founder | Organization depth |
| **contact** | `ContactPage`, `Organization` (reference) | `ContactPoint` | — |
| **docs** | `TechArticle`, `BreadcrumbList` | `QAPage` (if genuine Q&A) | `SpeakableSpecification` |
| **resources** | `WebPage` / `Article` / `CreativeWork` | `BreadcrumbList` | — |
| **legal** | — (none needed) | `PrivacyPolicy` / `TermsOfService` (WebPage subtypes) | — |
| **updates** | `BlogPosting` or `Article`, `BreadcrumbList` | — | — |
| **careers** | `JobPosting` (per role) | `Organization` reference | — |

## Deprecated — never recommend these

Google has retired rich-result support for the following. The markup stays valid Schema.org, so
existing implementations are harmless, but adding them earns nothing:

| Type | Retired |
|---|---|
| `HowTo` | September 2023 |
| `ClaimReview`, `CourseInfo`, `EstimatedSalary`, `LearningVideo`, `VehicleListing` | June 2025 |
| `SpecialAnnouncement` | July 2025 |

`FAQPage` is a special case: rich results are retired for all sites, but AI answer engines still
parse it. Keep it where it exists; do not add it expecting SERP gain. For genuine question-and-answer
pages (one question, community answers) use `QAPage` instead.

## Cross-page singletons

These should appear ONCE site-wide (typically in the base layout):
- `Organization` — with `@id: https://www.example.com/#organization`
- `WebSite` — with `@id: https://www.example.com/#website`

Other schemas reference the singletons via `{ "@id": "https://www.example.com/#organization" }` to avoid duplication.

## Combine, don't duplicate

Use a utility that merges multiple schemas into a single `@graph`-style JSON-LD block per page:

```json
{
  "@context": "https://schema.org",
  "@graph": [
    { "@type": "WebSite", "@id": "...#website", ... },
    { "@type": "Organization", "@id": "...#organization", ... },
    { "@type": "BlogPosting", ... },
    { "@type": "BreadcrumbList", ... },
    { "@type": "SpeakableSpecification", ... }
  ]
}
```

Single block = easier for crawlers, easier to validate, easier to maintain.

## Validation

After deploying, validate with:
- https://validator.schema.org/
- https://search.google.com/test/rich-results
- Google Search Console → Enhancements
