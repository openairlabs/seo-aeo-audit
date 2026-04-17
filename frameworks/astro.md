# Astro — SEO/AEO fix library

Gold-standard patterns for production Astro sites. When Astro is detected, prefer these patterns verbatim. For the deeper pattern library (Organization schema depth, Speakable, combined `@graph`, AI bot tracking), see `references/astro-gold-standard-patterns.md`.

## robots.missing

Create `public/robots.txt`:

```txt
User-agent: *
Allow: /

Sitemap: https://www.example.com/sitemap-index.xml
```

## sitemap.missing

Install `@astrojs/sitemap` and add to `astro.config.mjs`:

```js
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://www.example.com',
  integrations: [sitemap({
    changefreq: 'weekly',
    priority: 0.7,
    filter: (page) => !page.includes('/drafts/'),
  })],
});
```

## ai_crawlers.blocked

Edit `public/robots.txt` to explicitly allow AI crawlers:

```txt
User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: CCBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: Applebot-Extended
Allow: /
```

## llms_txt.missing

Create `public/llms.txt` listing primary content for LLMs:

```txt
# Example Inc
> One-line description of what you do.

## Primary Pages
- [Home](https://www.example.com/): Value proposition
- [Pricing](https://www.example.com/pricing): Plans + pricing
- [Docs](https://www.example.com/docs): Product documentation
- [Blog](https://www.example.com/blog): Articles + research

## Key Products
- [Product X](https://www.example.com/product/x): One-line description
```

## title.missing / title.length

In your page layout (e.g., `src/layouts/BaseLayout.astro`):

```astro
---
interface Props {
  title?: string;
  description?: string;
}
const { title = 'Default Title — Brand', description = 'Default desc' } = Astro.props;
---
<title>{title}</title>
<meta name="title" content={title} />
<meta name="description" content={description} />
```

Each page passes `title` + `description`:

```astro
<BaseLayout title="Your Page — 50-60 char keyword-forward title" description="120-160 char description with keyword in first 50 and a CTA.">
```

## canonical.missing

In `BaseLayout.astro` head:

```astro
---
const canonicalURL = canonical || new URL(Astro.url.pathname, Astro.site).href.replace(/\/$/, '');
const is404 = Astro.url.pathname === '/404';
---
{!is404 && <link rel="canonical" href={canonicalURL} />}
```

## open_graph.incomplete

```astro
<meta property="og:type" content="website" />
<meta property="og:site_name" content="Example" />
<meta property="og:url" content={canonicalURL} />
<meta property="og:title" content={title} />
<meta property="og:description" content={description} />
<meta property="og:image" content={new URL(image, Astro.site).href} />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content={title} />
<meta name="twitter:description" content={description} />
<meta name="twitter:image" content={new URL(image, Astro.site).href} />
<meta name="twitter:creator" content="@example" />
```

## schema.home — WebSite + Organization JSON-LD

Use a `utils/structured-data.ts` helper and inject in the base layout. Centralized pattern:

```ts
// src/utils/structured-data.ts
export function generateWebSiteSchema(siteUrl: string, siteName: string) {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    '@id': `${siteUrl}#website`,
    url: siteUrl,
    name: siteName,
  };
}
```

```astro
<!-- In BaseLayout.astro head -->
<script type="application/ld+json" is:inline set:html={JSON.stringify(
  generateWebSiteSchema('https://www.example.com', 'Example')
)} />

<script type="application/ld+json" is:inline>
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "https://www.example.com/#organization",
  "name": "Example Inc",
  "legalName": "Example Inc Pty Ltd",
  "url": "https://www.example.com",
  "logo": { "@type": "ImageObject", "url": "https://www.example.com/logo.webp" },
  "foundingDate": "2024-01-01",
  "founder": [
    { "@type": "Person", "name": "Founder Name", "jobTitle": "CEO" }
  ],
  "knowsAbout": ["Primary topic", "Secondary topic"],
  "slogan": "Your one-line slogan",
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "Customer Service",
    "email": "team@example.com"
  },
  "sameAs": [
    "https://www.wikidata.org/wiki/Qxxxxxx",
    "https://x.com/example",
    "https://www.linkedin.com/company/example",
    "https://www.crunchbase.com/organization/example"
  ]
}
</script>
```

## schema.blog_post — BlogPosting + Breadcrumb + Speakable

In `src/layouts/BlogLayout.astro`:

```astro
---
import { combineSchemas, generateArticleSchema, generateBreadcrumbSchema, generateSpeakableSchema } from '@/utils/structured-data';

const pageUrl = `https://www.example.com/blog/${slug}`;
const breadcrumbSchema = generateBreadcrumbSchema([
  { name: 'Home', url: 'https://www.example.com' },
  { name: 'Blog', url: 'https://www.example.com/blog' },
  { name: title, url: pageUrl },
]);

const speakableSchema = generateSpeakableSchema(
  ['.prose > p:first-of-type', '.prose h2 + p'],
  { combineWithWebPage: true, pageUrl, pageName: title }
);

const articleSchema = generateArticleSchema({
  headline: title,
  description,
  url: pageUrl,
  datePublished: new Date(date).toISOString(),
  dateModified: updatedAt ? new Date(updatedAt).toISOString() : undefined,
  author: { name: author },
  image,
});

const combined = combineSchemas(breadcrumbSchema, speakableSchema, articleSchema);
---
<script type="application/ld+json" is:inline set:html={JSON.stringify(combined)} />
```

## faqpage_schema.missing

Auto-generate from question-format headings in content. Add to your content collection schema:

```ts
// src/content.config.ts
const blogSchema = z.object({
  // ...
  faq: z.array(z.object({
    question: z.string(),
    answer: z.string(),
  })).optional(),
});
```

Then in `BlogLayout.astro`:

```astro
---
import { generateFAQSchema } from '@/utils/structured-data';
const faqSchema = entry.data.faq ? generateFAQSchema(entry.data.faq) : null;
---
{faqSchema && (
  <script type="application/ld+json" is:inline set:html={JSON.stringify(faqSchema)} />
)}
```

## speakable_schema.missing

```ts
// src/utils/structured-data.ts
export function generateSpeakableSchema(
  cssSelectors: string[],
  opts: { combineWithWebPage: boolean; pageUrl: string; pageName: string }
) {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    '@id': opts.pageUrl,
    name: opts.pageName,
    speakable: {
      '@type': 'SpeakableSpecification',
      cssSelector: cssSelectors,
    },
  };
}
```

## wikidata.unreferenced

1. Create a Wikidata item at https://www.wikidata.org/wiki/Special:NewItem
2. Add basic claims: instance of (Q4830453 = business), country, founding date, website
3. Copy the URL (e.g., `https://www.wikidata.org/wiki/Q137601537`)
4. Add to Organization schema `sameAs` array (first entry)

## organization_schema.shallow

Expand the Organization JSON-LD — see schema.home above. Required fields for depth:
- `founder[]` with full Person objects
- `sameAs[]` including Wikidata, X, LinkedIn, Crunchbase, GitHub, Facebook
- `knowsAbout[]` — your topical authority areas
- `slogan`, `foundingDate`, `foundingLocation`
- `contactPoint`
- `hasOfferCatalog` if you have pricing tiers

## viewport.missing

```astro
<meta name="viewport" content="width=device-width, initial-scale=1" />
```

## html_lang.missing

```astro
<html lang="en">
```

## images.missing_alt

Always provide `alt` on images. Astro's `<Image>` component:

```astro
import { Image } from 'astro:assets';
import hero from '@/assets/images/hero.png';

<Image src={hero} alt="Descriptive alt with keyword context" width={1200} height={630} />
```

## direct_answer.missing

Convention in MDX content: first paragraph is ≤50 words and answers the implied query.

```mdx
---
title: What is X?
---

**X is [one-sentence definition] that [outcome].** This article covers [scope].

## Full context...
```

## toc.missing

Use `@astrojs/mdx` with the `rehype-toc` plugin or generate manually. Minimal inline component:

```astro
---
const toc = headings.filter(h => h.depth === 2);
---
{toc.length > 2 && (
  <nav aria-label="Table of contents" class="toc">
    <ol>
      {toc.map(h => <li><a href={`#${h.slug}`}>{h.text}</a></li>)}
    </ol>
  </nav>
)}
```

## content.thin

Enforce minimum word count in your content collection validator:

```ts
const blogSchema = z.object({
  // ...
  body: z.string().refine(s => s.split(/\s+/).length >= 800, {
    message: 'Blog posts must be at least 800 words',
  }),
});
```

## redirects.chain

Update internal links to point to the final URL. A central `@/lib/links` registry (a TS module exporting canonical paths) prevents ad-hoc string literals from drifting.

## fetch.errors

Audit the broken URLs. Add 301 redirects via `astro.config.mjs` redirects config or edge/middleware:

```js
export default defineConfig({
  redirects: {
    '/old-path': '/new-path',
  },
});
```
