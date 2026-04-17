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
| **tool** | `HowTo`, `SoftwareApplication` | `VideoObject` (if demo), `FAQPage` | `SpeakableSpecification` |
| **integration** | `Product` or `Service`, `Offer` | Related `Brand` (the integration partner) | — |
| **use_case** | `WebPage`, `BreadcrumbList` | `FAQPage`, `HowTo` (if step-by-step) | — |
| **about** | `AboutPage`, `Organization` (reference only) | `Person` for each founder | Organization depth |
| **contact** | `ContactPage`, `Organization` (reference) | `ContactPoint` | — |
| **docs** | `TechArticle`, `BreadcrumbList` | `FAQPage`, `HowTo` | `SpeakableSpecification` |
| **resources** | `WebPage` / `Article` / `CreativeWork` | `BreadcrumbList` | — |
| **legal** | — (none needed) | `PrivacyPolicy` / `TermsOfService` (WebPage subtypes) | — |
| **updates** | `BlogPosting` or `Article`, `BreadcrumbList` | — | — |
| **careers** | `JobPosting` (per role) | `Organization` reference | — |

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
