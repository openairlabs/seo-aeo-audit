# SvelteKit — SEO/AEO fix library

Meta handled via `<svelte:head>`. JSON-LD via `@html` in `<svelte:head>`.

## robots.missing / ai_crawlers.blocked

Place `static/robots.txt`:

```txt
User-agent: *
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

User-agent: Applebot-Extended
Allow: /

Sitemap: https://www.example.com/sitemap.xml
```

## sitemap.missing

Create `src/routes/sitemap.xml/+server.ts`:

```ts
export async function GET() {
  const urls = await getAllUrls();
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map(u => `<url><loc>${u.loc}</loc><lastmod>${u.lastmod}</lastmod></url>`).join('\n')}
</urlset>`;
  return new Response(body, { headers: { 'Content-Type': 'application/xml' } });
}
```

## llms_txt.missing

Place `static/llms.txt`.

## title / meta_description / canonical / open_graph

```svelte
<script>
  export let data;
  const canonical = `https://www.example.com${$page.url.pathname}`;
</script>

<svelte:head>
  <title>{data.title} — Example</title>
  <meta name="description" content={data.description} />
  <link rel="canonical" href={canonical} />

  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonical} />
  <meta property="og:title" content={data.title} />
  <meta property="og:description" content={data.description} />
  <meta property="og:image" content="https://www.example.com/og.png" />

  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={data.title} />
  <meta name="twitter:description" content={data.description} />
</svelte:head>
```

## schema.home / organization_schema.shallow

In `src/routes/+layout.svelte`:

```svelte
<script>
  const orgSchema = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    '@id': 'https://www.example.com/#organization',
    name: 'Example Inc',
    url: 'https://www.example.com',
    logo: 'https://www.example.com/logo.png',
    founder: [{ '@type': 'Person', name: 'Founder', jobTitle: 'CEO' }],
    knowsAbout: ['Topic 1', 'Topic 2'],
    sameAs: [
      'https://www.wikidata.org/wiki/Qxxxxxx',
      'https://x.com/example',
      'https://www.linkedin.com/company/example',
    ],
  };
</script>

<svelte:head>
  {@html `<script type="application/ld+json">${JSON.stringify(orgSchema)}</script>`}
</svelte:head>
```

## schema.blog_post / faqpage_schema.missing / speakable_schema.missing

Same pattern — emit JSON-LD via `{@html}` in `<svelte:head>`.

## viewport.missing / html_lang.missing / images.missing_alt

- `src/app.html`: `<html lang="%sveltekit.lang%">` and `<meta name="viewport" content="width=device-width, initial-scale=1">`
- Always use `<img alt="...">`
