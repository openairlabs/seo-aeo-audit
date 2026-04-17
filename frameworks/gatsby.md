# Gatsby — SEO/AEO fix library

Modern Gatsby (5+) uses the Head API. Older sites use `react-helmet`. Patterns below use the Head API.

## robots.missing / ai_crawlers.blocked

Create `static/robots.txt` (copied as-is to public). Include AI crawler allow rules and Sitemap: line.

## sitemap.missing

```js
// gatsby-config.js
module.exports = {
  siteMetadata: { siteUrl: 'https://www.example.com' },
  plugins: ['gatsby-plugin-sitemap'],
};
```

## llms_txt.missing

Place at `static/llms.txt`.

## title / meta_description / canonical / open_graph

Gatsby Head API:

```tsx
// src/pages/my-page.tsx or src/templates/blog-post.tsx
import type { HeadFC } from 'gatsby';

export const Head: HeadFC = () => (
  <>
    <title>Page title — Example</title>
    <meta name="description" content="..." />
    <link rel="canonical" href="https://www.example.com/page" />
    <meta property="og:type" content="website" />
    <meta property="og:title" content="Page title" />
    <meta property="og:description" content="..." />
    <meta property="og:image" content="https://www.example.com/og.png" />
    <meta name="twitter:card" content="summary_large_image" />
  </>
);
```

## schema.home / organization_schema.shallow / schema.blog_post

```tsx
export const Head: HeadFC = () => {
  const orgSchema = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'Example Inc',
    url: 'https://www.example.com',
    founder: [{ '@type': 'Person', name: 'Founder', jobTitle: 'CEO' }],
    knowsAbout: ['Topic 1', 'Topic 2'],
    sameAs: [
      'https://www.wikidata.org/wiki/Qxxxxxx',
      'https://x.com/example',
    ],
  };
  return (
    <script type="application/ld+json">
      {JSON.stringify(orgSchema)}
    </script>
  );
};
```

## faqpage_schema.missing / speakable_schema.missing

Same pattern — inject JSON-LD via the Head API.

## viewport.missing / html_lang.missing / images.missing_alt

- HTML attrs via `gatsby-ssr.js` → `onRenderBody` → `setHtmlAttributes({ lang: 'en' })`
- Use `<StaticImage alt="...">` or `<GatsbyImage alt="...">` from `gatsby-plugin-image`
