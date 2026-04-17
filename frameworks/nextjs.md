# Next.js — SEO/AEO fix library

Covers both App Router (13+) and Pages Router. Prefer App Router patterns where both exist.

## robots.missing

**App Router:** `app/robots.ts`

```ts
import type { MetadataRoute } from 'next';
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: '*', allow: '/' }],
    sitemap: 'https://www.example.com/sitemap.xml',
  };
}
```

## sitemap.missing

**App Router:** `app/sitemap.ts`

```ts
import type { MetadataRoute } from 'next';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const posts = await getAllPosts();
  return [
    { url: 'https://www.example.com', lastModified: new Date(), priority: 1 },
    ...posts.map(p => ({
      url: `https://www.example.com/blog/${p.slug}`,
      lastModified: new Date(p.updatedAt),
      changeFrequency: 'monthly' as const,
    })),
  ];
}
```

## ai_crawlers.blocked

**App Router:** update `app/robots.ts`:

```ts
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: '*', allow: '/' },
      { userAgent: 'GPTBot', allow: '/' },
      { userAgent: 'ClaudeBot', allow: '/' },
      { userAgent: 'PerplexityBot', allow: '/' },
      { userAgent: 'CCBot', allow: '/' },
      { userAgent: 'Google-Extended', allow: '/' },
      { userAgent: 'Applebot-Extended', allow: '/' },
    ],
    sitemap: 'https://www.example.com/sitemap.xml',
  };
}
```

## llms_txt.missing

Create `public/llms.txt` — served as-is from `/llms.txt`.

## title.missing / title.length / meta_description.missing

**App Router:** export `metadata` from `layout.tsx` or `page.tsx`:

```tsx
// app/layout.tsx or app/blog/[slug]/page.tsx
export const metadata = {
  title: {
    default: 'Example — Fast, reliable X',
    template: '%s | Example',
  },
  description: 'One-line 120-160 char description with keyword in first 50 and a CTA.',
};
```

Dynamic per-post:

```tsx
export async function generateMetadata({ params }): Promise<Metadata> {
  const post = await getPost(params.slug);
  return {
    title: `${post.title} — Example Blog`,
    description: post.excerpt,
  };
}
```

## canonical.missing

```tsx
export const metadata = {
  alternates: { canonical: 'https://www.example.com/page' },
};
```

Dynamic:

```tsx
export async function generateMetadata({ params }) {
  return {
    alternates: { canonical: `https://www.example.com/blog/${params.slug}` },
  };
}
```

## open_graph.incomplete

```tsx
export const metadata = {
  openGraph: {
    title: 'Page title',
    description: 'Description',
    url: 'https://www.example.com/page',
    siteName: 'Example',
    images: [{ url: 'https://www.example.com/og.png', width: 1200, height: 630 }],
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Page title',
    description: 'Description',
    images: ['https://www.example.com/og.png'],
    creator: '@example',
  },
};
```

## schema.home / schema.blog_post / organization_schema.shallow

Render JSON-LD in a server component:

```tsx
// app/layout.tsx
const orgSchema = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  '@id': 'https://www.example.com/#organization',
  name: 'Example Inc',
  url: 'https://www.example.com',
  logo: 'https://www.example.com/logo.png',
  founder: [{ '@type': 'Person', name: 'Founder', jobTitle: 'CEO' }],
  knowsAbout: ['Primary topic', 'Secondary topic'],
  sameAs: [
    'https://www.wikidata.org/wiki/Qxxxxxx',
    'https://x.com/example',
    'https://www.linkedin.com/company/example',
  ],
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(orgSchema) }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
```

## schema.blog_post

```tsx
// app/blog/[slug]/page.tsx
export default async function Post({ params }) {
  const post = await getPost(params.slug);
  const articleSchema = {
    '@context': 'https://schema.org',
    '@type': 'BlogPosting',
    headline: post.title,
    description: post.excerpt,
    datePublished: post.publishedAt,
    dateModified: post.updatedAt,
    author: { '@type': 'Person', name: post.author },
    image: post.image,
    url: `https://www.example.com/blog/${post.slug}`,
  };
  const breadcrumbSchema = { /* ... */ };
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{
        __html: JSON.stringify([articleSchema, breadcrumbSchema])
      }} />
      <article>{/* ... */}</article>
    </>
  );
}
```

## faqpage_schema.missing

```tsx
const faqSchema = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: post.faqs.map(faq => ({
    '@type': 'Question',
    name: faq.question,
    acceptedAnswer: { '@type': 'Answer', text: faq.answer },
  })),
};
```

## speakable_schema.missing

Merge into BlogPosting or add as separate WebPage node:

```tsx
{
  '@type': 'WebPage',
  '@id': url,
  speakable: {
    '@type': 'SpeakableSpecification',
    cssSelector: ['.prose > p:first-of-type', '.prose h2 + p'],
  },
}
```

## viewport.missing

```tsx
// app/layout.tsx
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};
```

## html_lang.missing

```tsx
<html lang="en">
```

## images.missing_alt

Use `next/image` with explicit `alt`:

```tsx
import Image from 'next/image';
<Image src="/hero.png" alt="Descriptive alt text" width={1200} height={630} />
```

## redirects.chain

`next.config.js`:

```js
module.exports = {
  async redirects() {
    return [
      { source: '/old', destination: '/new', permanent: true },
    ];
  },
};
```

## wikidata.unreferenced

See `astro.md` — same process. Add `https://www.wikidata.org/wiki/Qxxxxxx` as first entry in `Organization.sameAs`.
