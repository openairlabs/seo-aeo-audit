# Astro — Gold-Standard SEO/AEO Patterns

When auditing an Astro site, these patterns represent the current bar for SEO/AEO done right. Reference them when comparing the audited site and when generating the framework-specific code section of the report.

## 1. BaseLayout meta stack (complete)

A base layout component that covers every meta category:

- Title / meta title / meta description
- Hreflang (even single-language: `en-US` + `x-default`)
- Favicon (.svg + .ico) + apple-touch-icon + manifest
- theme-color (dynamic from class observer, e.g., dark/light mode sync)
- Open Graph: type, site_name, url, title, description, image (with explicit 1200×630 dimensions)
- Twitter: card type, title, description, image, creator
- Robots meta (+ googlebot-specific) with `max-image-preview:large, max-video-preview:-1, max-snippet:-1`
- Sitemap discovery: `<link rel="sitemap" href="/sitemap-index.xml">`
- RSS autodiscovery (separate feeds for `/updates/rss.xml` and `/blog/rss.xml`)
- Canonical URL (conditional — skip on `/404`)
- Search engine verification tags (Bing, Google) loaded from env vars

## 2. Organization schema depth

The bar for Organization JSON-LD — every field filled, not just the required ones:

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "https://www.example.com/#organization",
  "name": "Example Inc",
  "legalName": "EXAMPLE INC PTY LTD",
  "alternateName": ["Example Co", "Example Platform"],
  "url": "https://www.example.com",
  "logo": { "@type": "ImageObject", "url": "https://www.example.com/logo.webp" },
  "description": "One-sentence description of what the company does.",
  "foundingDate": "2024-01-01",
  "foundingLocation": { "@type": "Place", "name": "City, Country" },
  "founder": [
    { "@type": "Person", "name": "Founder Name", "jobTitle": "Founder & CEO" },
    { "@type": "Person", "name": "Co-founder Name", "jobTitle": "Co-founder & CTO" }
  ],
  "knowsAbout": [
    "Primary topic area",
    "Secondary topic area",
    "Third topic area",
    "Industry the company operates in",
    "Related fields of expertise"
  ],
  "slogan": "One-line slogan that captures the positioning.",
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "Customer Service",
    "email": "team@example.com"
  },
  "sameAs": [
    "https://www.wikidata.org/wiki/Qxxxxxx",
    "https://x.com/example",
    "https://www.linkedin.com/company/example",
    "https://www.crunchbase.com/organization/example",
    "https://github.com/example"
  ],
  "hasOfferCatalog": { "@type": "OfferCatalog", "name": "Plans", "itemListElement": [] }
}
```

**Why it's the bar**: legalName + alternateName + `knowsAbout` (5+ items) + `sameAs` with a Wikidata URL + OfferCatalog. This is entity-level recognition, not just meta tags.

## 3. BlogLayout schema composition

A blog post layout that combines three schemas into one `@graph` block:

```ts
const breadcrumbSchema = generateBreadcrumbSchema([
  { name: 'Home', url: 'https://www.example.com' },
  { name: 'Blog', url: 'https://www.example.com/blog' },
  { name: title, url: pageUrl },
]);

const speakableSchema = generateSpeakableSchema(
  ['.prose > p:first-of-type', '.prose h2 + p', '.blog-description'],
  { combineWithWebPage: true, pageUrl, pageName: title }
);

const articleSchema = generateArticleSchema({
  headline: title,
  description,
  url: pageUrl,
  datePublished: date.toISOString(),
  dateModified: updatedAt ? updatedAt.toISOString() : undefined,
  author: { name: author },
  image: ogImage,
});

const combined = combineSchemas(breadcrumbSchema, speakableSchema, articleSchema);
```

**Key takeaways**:
- Every blog post emits **three** schemas (Article + Breadcrumb + Speakable)
- Speakable targets three CSS selectors covering opening + first paragraph after each H2
- All combined into a single JSON-LD block via a `combineSchemas` utility

## 4. Structured-data utility module

A single `src/utils/structured-data.ts` module exports reusable generators:

- `generateFAQSchema(faqs)` — strips HTML from answers (schema.org requires plain text)
- `generateHowToSchema(data)` — with totalTime, estimatedCost, steps
- `generateProductSchema(data)` — includes aggregateRating, priceValidUntil auto-calculated
- `generateSoftwareApplicationSchema(data)` — with provider reference to Organization `@id`
- `generateWebSiteSchema(siteUrl, siteName, hasSearch)`
- `generateArticleSchema(data)`
- `generateBreadcrumbSchema(items)`
- `generateSpeakableSchema(cssSelectors, opts)`
- `combineSchemas(...schemas)` — merges into a single `@graph`

**Why it matters**: centralization. Every page uses the same generator, so schema shape is consistent and updates happen in one place.

## 5. Content collection schema with SEO subobject

A `src/content.config.ts` with a reusable `seoSchema`:

```ts
const seoSchema = z.object({
  title: z.string().optional(),
  description: z.string().optional(),
  canonical: z.url().optional(),
  noindex: z.boolean().default(false),
  nofollow: z.boolean().default(false),
  ogTitle: z.string().optional(),
  ogDescription: z.string().optional(),
  ogImage: z.union([z.string(), z.object({ src, alt, width, height })]).optional(),
  twitterCard: z.enum(['summary', 'summary_large_image', 'app', 'player']).default('summary_large_image'),
  focusKeyword: z.string().optional(),
  schemaType: z.enum(['Article', 'BlogPosting', 'TechArticle', 'HowTo', 'FAQPage', 'SoftwareApplication', 'Product']).optional(),
}).optional();
```

**Key takeaway**: schema is enforced at the content layer, not left to editorial discretion. `focusKeyword` and `schemaType` are first-class metadata.

## 6. AI bot detection + tracking

A production-only inline script in the base layout that detects AI crawlers (GPTBot / Claude / Perplexity / Gemini / Copilot / ExaBot / etc.) and logs their visits to a backend endpoint. This closes the loop — the team measures **AEO visibility in near real-time** instead of only measuring Google rankings.

Outline:

```html
<script is:inline>
  (function() {
    if (typeof window === 'undefined' || window.__botTrackingLoaded) return;
    window.__botTrackingLoaded = true;
    const ua = navigator.userAgent || '';
    const exclude = /Lighthouse|PageSpeed|GTmetrix|Pingdom|WebPageTest/i;
    if (exclude.test(ua)) return;
    const botPatterns = /GPT|ChatGPT|OpenAI|Claude|Anthropic|Perplexity|Bard|Gemini|Copilot|ExaBot|Googlebot|bingbot/i;
    if (botPatterns.test(ua)) {
      fetch('/api/track-bot', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          url: location.href,
          userAgent: ua,
          referrer: document.referrer || '',
          timestamp: Date.now()
        })
      }).catch(() => {});
    }
  })();
</script>
```

**This is rare.** Most sites optimize for AI crawlers but don't measure AI crawler visits. The track-bot pattern closes the loop.

## 7. Robots meta with full rendering directives

```html
<meta name="robots" content="index, follow, max-image-preview:large, max-video-preview:-1, max-snippet:-1">
<meta name="googlebot" content="index, follow, max-image-preview:large, max-video-preview:-1, max-snippet:-1">
```

`max-snippet:-1` + `max-image-preview:large` + `max-video-preview:-1` unlocks maximum snippet size in search results.

## 8. Resource hints + performance

- Preconnect to critical CDNs:
  ```html
  <link rel="preconnect" href="https://stream.mux.com" crossorigin />
  ```
- Preload hero-above-fold assets with `fetchpriority="high"`:
  ```html
  <link rel="preload" href="/hero-poster.webp" as="image" type="image/webp" fetchpriority="high" />
  ```
- Preload critical fonts with `font-display: swap`:
  ```html
  <link rel="preload" href="/fonts/Body-Regular.woff2" as="font" type="font/woff2" crossorigin />
  ```

This is the LCP-optimization pattern — preconnect + preload + swap.

## 9. Accessibility + multiple layouts

- Skip-to-content link:
  ```html
  <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 bg-primary text-primary-foreground px-4 py-2 rounded z-[9999]">Skip to content</a>
  ```
- Single SVG sprite component for all icons (reduces requests)
- Per-page-type layouts: `BaseLayout`, `BlogLayout`, `PageLayout`, `ToolLayout`, etc. — each with its own schema composition

## Applying this to an audit

When the detected framework is Astro, the report should:

1. Compare the audited site's Organization schema against the full-depth bar above (founder, `sameAs` w/ Wikidata, `knowsAbout`, slogan, foundingDate, hasOfferCatalog)
2. Check for a central `structured-data.ts` utility vs. inline schema repeated per page
3. Check for Speakable schema on blog posts (most Astro sites miss this)
4. Check the content collection schema for `focusKeyword` + `schemaType` enforcement
5. Flag if AI bot detection/tracking isn't in place

Reference these patterns in the framework-specific code section of the report — they're the concrete implementation of what "gold standard Astro SEO/AEO" looks like.
