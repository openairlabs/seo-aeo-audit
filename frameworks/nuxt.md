# Nuxt — SEO/AEO fix library

Nuxt 3 uses `useHead()` / `useSeoMeta()` composables. Patterns below assume Nuxt 3.

## robots.missing / ai_crawlers.blocked

Install `@nuxtjs/robots`:

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  modules: ['@nuxtjs/robots'],
  robots: {
    sitemap: 'https://www.example.com/sitemap.xml',
    groups: [
      { userAgent: '*', allow: '/' },
      { userAgent: 'GPTBot', allow: '/' },
      { userAgent: 'ClaudeBot', allow: '/' },
      { userAgent: 'PerplexityBot', allow: '/' },
      { userAgent: 'CCBot', allow: '/' },
      { userAgent: 'Google-Extended', allow: '/' },
      { userAgent: 'Applebot-Extended', allow: '/' },
    ],
  },
});
```

## sitemap.missing

Install `@nuxtjs/sitemap`:

```ts
// nuxt.config.ts
modules: ['@nuxtjs/sitemap'],
sitemap: { hostname: 'https://www.example.com' },
```

## llms_txt.missing

Place at `public/llms.txt` — served as-is.

## title.missing / title.length / meta_description.missing / canonical.missing / open_graph.incomplete

```vue
<script setup lang="ts">
useSeoMeta({
  title: 'Page title — 50-60 chars',
  description: '120-160 char description with keyword in first 50 and a CTA.',
  ogTitle: 'Page title',
  ogDescription: 'Description',
  ogImage: 'https://www.example.com/og.png',
  ogUrl: 'https://www.example.com/page',
  ogType: 'website',
  twitterCard: 'summary_large_image',
  twitterCreator: '@example',
});

useHead({
  link: [{ rel: 'canonical', href: 'https://www.example.com/page' }],
  htmlAttrs: { lang: 'en' },
});
</script>
```

## schema.home / organization_schema.shallow / schema.blog_post

Use `nuxt-schema-org` (`@nuxtjs/seo`):

```ts
// nuxt.config.ts
modules: ['@nuxtjs/seo'],
site: {
  url: 'https://www.example.com',
  name: 'Example',
},
```

```vue
<script setup>
defineOrganization({
  name: 'Example Inc',
  logo: '/logo.png',
  founder: [{ type: 'Person', name: 'Founder', jobTitle: 'CEO' }],
  knowsAbout: ['Topic 1', 'Topic 2'],
  sameAs: [
    'https://www.wikidata.org/wiki/Qxxxxxx',
    'https://x.com/example',
    'https://www.linkedin.com/company/example',
  ],
});

// Blog post:
defineArticle({
  headline: title,
  datePublished: new Date(publishedAt),
  dateModified: new Date(updatedAt),
  author: [{ name: author }],
});
```

## faqpage_schema.missing

```vue
<script setup>
useSchemaOrg([
  defineQuestion({ name: 'What is X?', acceptedAnswer: 'X is...' }),
  defineQuestion({ name: 'How does Y work?', acceptedAnswer: 'Y works by...' }),
]);
</script>
```

## speakable_schema.missing

`@nuxtjs/seo` doesn't have a speakable helper — inject raw:

```vue
<script setup>
useHead({
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      '@id': canonical,
      speakable: {
        '@type': 'SpeakableSpecification',
        cssSelector: ['.prose > p:first-of-type', '.prose h2 + p'],
      },
    }),
  }],
});
</script>
```

## viewport.missing / html_lang.missing / images.missing_alt

```ts
// nuxt.config.ts
app: {
  head: {
    htmlAttrs: { lang: 'en' },
    meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
  },
},
```

Use `<NuxtImg alt="...">` or `<img alt="...">` — always provide alt.
