# Shopify — SEO/AEO fix library

Shopify provides some SEO automatically (sitemap, canonical). Most fixes involve theme `*.liquid` edits or apps.

## robots.missing / ai_crawlers.blocked

Shopify serves `/robots.txt` automatically but you can customize via `robots.txt.liquid` template in `templates/`:

```liquid
{% for group in robots.default_groups %}
  {{- group.user_agent }}
  {% for rule in group.rules %}
    {{- rule }}
  {% endfor %}
  {%- if group.sitemap != blank %}
    {{- group.sitemap }}
  {% endif %}
{% endfor %}

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

## sitemap.missing

Shopify generates `/sitemap.xml` automatically at the domain root — should not be missing. If missing, check that the store isn't on a password-protected preview.

## llms_txt.missing

Shopify doesn't support arbitrary file serving in the store root. Workarounds:
1. Use an app like "SEO Manager" that adds arbitrary routes
2. Add a page at `/pages/llms` with structured content (sub-optimal but works)

## title / meta_description / open_graph

Edit `snippets/meta-tags.liquid` or `layout/theme.liquid`:

```liquid
<title>{{ page_title }}{% if current_tags %} — tagged "{{ current_tags | join: ', ' }}"{% endif %}{% if current_page != 1 %} — Page {{ current_page }}{% endif %}{% unless page_title contains shop.name %} — {{ shop.name }}{% endunless %}</title>
{% if page_description %}<meta name="description" content="{{ page_description | escape }}">{% endif %}

<meta property="og:type" content="{% if template contains 'product' %}product{% elsif template contains 'article' %}article{% else %}website{% endif %}">
<meta property="og:title" content="{{ page_title | escape }}">
<meta property="og:description" content="{{ page_description | escape }}">
<meta property="og:url" content="{{ canonical_url }}">
<meta property="og:image" content="{% if template contains 'product' %}{{ product.featured_image | image_url: width: 1200 }}{% else %}{{ 'og-image.png' | asset_url }}{% endif %}">
<meta property="og:site_name" content="{{ shop.name }}">
<meta name="twitter:card" content="summary_large_image">
```

## canonical.missing

Shopify auto-emits `{{ canonical_url }}`. In theme:

```liquid
<link rel="canonical" href="{{ canonical_url }}">
```

## schema.home / organization_schema.shallow

Add JSON-LD to `layout/theme.liquid` before `</head>`:

```liquid
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "{{ shop.url }}/#organization",
  "name": "{{ shop.name }}",
  "url": "{{ shop.url }}",
  "logo": "{{ 'logo.png' | asset_url }}",
  "sameAs": [
    "https://www.wikidata.org/wiki/Qxxxxxx",
    "https://x.com/example",
    "https://www.instagram.com/example"
  ]
}
</script>
```

## schema.product

Add Product JSON-LD to `sections/product.liquid`:

```liquid
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "{{ product.title | escape }}",
  "description": "{{ product.description | strip_html | escape }}",
  "image": "{{ product.featured_image | image_url: width: 1200 }}",
  "brand": { "@type": "Brand", "name": "{{ product.vendor | escape }}" },
  "sku": "{{ product.selected_or_first_available_variant.sku }}",
  "offers": {
    "@type": "Offer",
    "price": "{{ product.price | money_without_currency }}",
    "priceCurrency": "{{ cart.currency.iso_code }}",
    "availability": "{% if product.available %}https://schema.org/InStock{% else %}https://schema.org/OutOfStock{% endif %}"
  }
}
</script>
```

## schema.blog_post

Edit `templates/article.liquid`:

```liquid
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "{{ article.title | escape }}",
  "image": "{{ article.image | image_url: width: 1200 }}",
  "datePublished": "{{ article.published_at | date: '%Y-%m-%dT%H:%M:%SZ' }}",
  "dateModified": "{{ article.updated_at | date: '%Y-%m-%dT%H:%M:%SZ' }}",
  "author": { "@type": "Person", "name": "{{ article.author | escape }}" }
}
</script>
```

## faqpage_schema.missing

Use a metaobject for FAQ entries or a page template. Emit FAQPage JSON-LD from the template.

## viewport.missing / html_lang.missing

In `layout/theme.liquid`:

```liquid
<html lang="{{ request.locale.iso_code }}">
  <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
```

## images.missing_alt

Shopify's image tags accept alt. Default Liquid pattern:

```liquid
<img src="{{ product.featured_image | image_url: width: 800 }}"
     alt="{{ product.featured_image.alt | default: product.title | escape }}">
```

Admin: Products → edit product image → set Alt text.
