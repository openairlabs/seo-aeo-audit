# Generic HTML — SEO/AEO fix library

Framework-agnostic fallback. Applies to any site where the framework couldn't be detected, including vanilla HTML, unknown generators, or bespoke stacks.

## robots.missing

Serve `/robots.txt` at the site root:

```txt
User-agent: *
Allow: /

Sitemap: https://www.example.com/sitemap.xml
```

## sitemap.missing

Serve `/sitemap.xml` at root. Minimal example:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.example.com/</loc>
    <lastmod>2026-04-17</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://www.example.com/pricing</loc>
    <lastmod>2026-03-10</lastmod>
    <priority>0.9</priority>
  </url>
</urlset>
```

Add `Sitemap: https://www.example.com/sitemap.xml` to `robots.txt`.

## ai_crawlers.blocked

Update `robots.txt` to allow AI crawlers:

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

Serve `/llms.txt`:

```
# Example Inc
> One-line description.

## Primary Pages
- [Home](https://www.example.com/)
- [Pricing](https://www.example.com/pricing)
- [Docs](https://www.example.com/docs)
```

## title.missing / title.length

```html
<title>50-60 char keyword-forward title — Brand</title>
```

## meta_description.missing / meta_description.length

```html
<meta name="description" content="120-160 char description with primary keyword in first 50 chars and a CTA.">
```

## canonical.missing

```html
<link rel="canonical" href="https://www.example.com/this-exact-page">
```

Must be self-referential and absolute.

## open_graph.incomplete

```html
<meta property="og:type" content="website">
<meta property="og:site_name" content="Example">
<meta property="og:url" content="https://www.example.com/page">
<meta property="og:title" content="Page title">
<meta property="og:description" content="Description">
<meta property="og:image" content="https://www.example.com/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Page title">
<meta name="twitter:description" content="Description">
<meta name="twitter:image" content="https://www.example.com/og.png">
<meta name="twitter:creator" content="@example">
```

## schema.home / organization_schema.shallow

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "https://www.example.com/#organization",
  "name": "Example Inc",
  "url": "https://www.example.com",
  "logo": { "@type": "ImageObject", "url": "https://www.example.com/logo.png" },
  "foundingDate": "2024-01-01",
  "founder": [{ "@type": "Person", "name": "Founder Name", "jobTitle": "CEO" }],
  "knowsAbout": ["Topic 1", "Topic 2"],
  "slogan": "One-line slogan",
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "Customer Service",
    "email": "team@example.com"
  },
  "sameAs": [
    "https://www.wikidata.org/wiki/Qxxxxxx",
    "https://x.com/example",
    "https://www.linkedin.com/company/example"
  ]
}
</script>

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "@id": "https://www.example.com/#website",
  "url": "https://www.example.com",
  "name": "Example"
}
</script>
```

## schema.blog_post

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "Post title",
  "description": "Post excerpt",
  "datePublished": "2026-04-17T10:00:00Z",
  "dateModified": "2026-04-17T10:00:00Z",
  "author": { "@type": "Person", "name": "Author Name" },
  "image": "https://www.example.com/post-image.png",
  "url": "https://www.example.com/blog/slug",
  "publisher": {
    "@type": "Organization",
    "name": "Example Inc",
    "logo": { "@type": "ImageObject", "url": "https://www.example.com/logo.png" }
  }
}
</script>
```

## schema.pricing

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Example",
  "description": "Product description",
  "brand": { "@type": "Brand", "name": "Example" },
  "offers": [
    { "@type": "Offer", "name": "Starter", "price": "0", "priceCurrency": "USD" },
    { "@type": "Offer", "name": "Pro", "price": "149", "priceCurrency": "USD" }
  ]
}
</script>
```

## faqpage_schema.missing

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is X?",
      "acceptedAnswer": { "@type": "Answer", "text": "X is..." }
    }
  ]
}
</script>
```

## speakable_schema.missing

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "@id": "https://www.example.com/blog/slug",
  "speakable": {
    "@type": "SpeakableSpecification",
    "cssSelector": [".prose > p:first-of-type", ".prose h2 + p"]
  }
}
</script>
```

## wikidata.unreferenced

1. Create a Wikidata item: https://www.wikidata.org/wiki/Special:NewItem
2. Add claims: instance of (business), country, founded, official website
3. Add the URL to Organization schema `sameAs` — this is the highest-confidence cross-reference for AI answer engines

## viewport.missing

```html
<meta name="viewport" content="width=device-width, initial-scale=1">
```

## html_lang.missing

```html
<html lang="en">
```

## images.missing_alt

Every `<img>` needs `alt`. Use `alt=""` for decorative images (explicitly empty, not missing).

```html
<img src="hero.png" alt="Descriptive alt text" width="1200" height="630">
<img src="decoration.svg" alt="" role="presentation">
```

## h1.count

Use exactly one `<h1>` per page. Section headings below use `<h2>` → `<h3>` → etc.

## direct_answer.missing

Lead each page with a ≤50-word paragraph that directly answers the query. Example:

```html
<article>
  <h1>What is X?</h1>
  <p><strong>X is a [one-sentence definition] that [outcome].</strong> This page covers [scope].</p>
  <!-- detail sections follow -->
</article>
```

## toc.missing

For long content (1500+ words), add a TOC:

```html
<nav aria-label="Table of contents">
  <ol>
    <li><a href="#section-1">Section 1</a></li>
    <li><a href="#section-2">Section 2</a></li>
  </ol>
</nav>
```

## content.thin

Target minimum word counts:
- Blog post: 1500+
- Product/pricing: 800+
- Category: 500+

Expand with substance, not filler.

## redirects.chain

Resolve each redirect to a single 301. Update internal links to point directly at the final URL.

## fetch.errors

Broken URLs: investigate, restore content, 301 to equivalent, or remove from sitemap.
