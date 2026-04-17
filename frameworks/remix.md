# Remix — SEO/AEO fix library

Remix uses `meta` and `links` exports per route + `<script type="application/ld+json">` in the component body.

## robots.missing / ai_crawlers.blocked

Create `app/routes/[robots.txt].ts`:

```ts
export const loader = () => {
  const body = `User-agent: *
Allow: /

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

Sitemap: https://www.example.com/sitemap.xml`;
  return new Response(body, { headers: { 'Content-Type': 'text/plain' } });
};
```

## sitemap.missing

Create `app/routes/[sitemap.xml].ts` returning dynamic `<urlset>`.

## llms_txt.missing

Create `app/routes/[llms.txt].ts`.

## title / meta_description / canonical / open_graph

```tsx
// app/routes/_index.tsx or any route
import type { MetaFunction, LinksFunction } from '@remix-run/node';

export const meta: MetaFunction = () => [
  { title: 'Page title — Example' },
  { name: 'description', content: '...' },
  { property: 'og:type', content: 'website' },
  { property: 'og:title', content: 'Page title' },
  { property: 'og:description', content: '...' },
  { property: 'og:image', content: 'https://www.example.com/og.png' },
  { name: 'twitter:card', content: 'summary_large_image' },
];

export const links: LinksFunction = () => [
  { rel: 'canonical', href: 'https://www.example.com/page' },
];
```

## schema.home / organization_schema.shallow / schema.blog_post

Inject JSON-LD in the component — Remix renders it into the head/body HTML:

```tsx
export default function Index() {
  const orgSchema = { /* ... */ };
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{
        __html: JSON.stringify(orgSchema)
      }} />
      {/* rest of page */}
    </>
  );
}
```

## faqpage_schema.missing / speakable_schema.missing

Same pattern.

## viewport.missing / html_lang.missing

In `app/root.tsx`:

```tsx
<html lang="en">
  <head>
    <meta charSet="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <Meta />
    <Links />
  </head>
  <body>
    <Outlet />
  </body>
</html>
```

## images.missing_alt

Always provide `alt`.
