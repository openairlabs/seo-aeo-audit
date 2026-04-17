# WordPress — SEO/AEO fix library

Most fixes here assume Yoast SEO or Rank Math are installed (one is present on 80%+ of WP sites). If neither is installed, recommend installing **Rank Math** as step 0 — it handles most meta/schema automatically.

## robots.missing / ai_crawlers.blocked

In **Rank Math**: Dashboard → Rank Math → General Settings → Edit robots.txt. Add:

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

Sitemap: https://www.example.com/sitemap_index.xml
```

In **Yoast**: SEO → Tools → File Editor → robots.txt.

## sitemap.missing

**Rank Math:** Dashboard → Sitemap Settings → enable → visit `/sitemap_index.xml`.
**Yoast:** SEO → General → Features → XML sitemaps → On. Visit `/sitemap_index.xml`.

## llms_txt.missing

Add a file plugin (e.g., "File Manager") to write `/llms.txt`, or add via `functions.php`:

```php
add_action('init', function() {
  add_rewrite_rule('^llms\.txt$', 'index.php?llms_txt=1', 'top');
});

add_action('template_redirect', function() {
  if (get_query_var('llms_txt')) {
    header('Content-Type: text/plain');
    echo "# Example Inc\n> Description.\n\n## Primary Pages\n- " . home_url('/') . ": Home\n";
    exit;
  }
});
```

## title.missing / title.length / meta_description.missing

**Rank Math:** Post edit → Rank Math SEO sidebar → Snippet Editor → set Title + Description.
**Yoast:** Post edit → Yoast SEO meta box → set SEO title + meta description.

Set global template in Dashboard → Rank Math → Titles & Meta.

## canonical.missing

Rank Math and Yoast add canonical automatically. Check for plugin conflicts if missing:
- Disable any other SEO plugins
- In Rank Math: Post edit → Advanced tab → Canonical URL (only override if needed)

## open_graph.incomplete

Rank Math / Yoast generate OG/Twitter automatically. If missing, check:
- Rank Math: Titles & Meta → enable OG/Twitter
- Yoast: Social → Facebook/Twitter → enable

## schema.home / organization_schema.shallow

**Rank Math:** Dashboard → Titles & Meta → Local SEO → set Organization name, logo, address, social profiles (these become `sameAs`). Add Wikidata URL under "Additional Info" → Social Profiles → add custom.

**Yoast:** General → Site representation → Organization. Schema is generated automatically.

For depth beyond plugin defaults (founder, knowsAbout, slogan, founding date):

```php
// In a code snippet plugin or functions.php
add_filter('rank_math/json_ld', function($data, $jsonld) {
  if (isset($data['Organization'])) {
    $data['Organization']['founder'] = [
      ['@type' => 'Person', 'name' => 'Founder Name', 'jobTitle' => 'CEO']
    ];
    $data['Organization']['knowsAbout'] = ['Topic 1', 'Topic 2'];
    $data['Organization']['slogan'] = 'One-line slogan';
    $data['Organization']['foundingDate'] = '2024-01-01';
    if (!isset($data['Organization']['sameAs'])) $data['Organization']['sameAs'] = [];
    $data['Organization']['sameAs'][] = 'https://www.wikidata.org/wiki/Qxxxxxx';
  }
  return $data;
}, 99, 2);
```

## schema.blog_post

Both plugins add BlogPosting automatically. For Speakable (AEO):

```php
add_filter('rank_math/json_ld', function($data, $jsonld) {
  if (is_single()) {
    $data['Speakable'] = [
      '@context' => 'https://schema.org',
      '@type' => 'WebPage',
      '@id' => get_permalink(),
      'speakable' => [
        '@type' => 'SpeakableSpecification',
        'cssSelector' => ['.entry-content > p:first-of-type', '.entry-content h2 + p'],
      ],
    ];
  }
  return $data;
}, 99, 2);
```

## faqpage_schema.missing

**Rank Math:** In Gutenberg, add a "Rank Math FAQ" block — auto-generates FAQPage schema.
**Yoast:** FAQ block in Yoast's Gutenberg block library does the same.

## viewport.missing

Rare on WP. If missing, edit theme `header.php` or `functions.php`:

```php
add_action('wp_head', function() {
  echo '<meta name="viewport" content="width=device-width, initial-scale=1">';
}, 1);
```

## html_lang.missing

Should be auto-set by `<?php language_attributes(); ?>` in `header.php`. If missing, add it.

## images.missing_alt

Run a plugin like "Enable Media Replace" or "Image SEO" to audit alt gaps. Or in PHP:

```sql
SELECT ID, post_title FROM wp_posts WHERE post_type = 'attachment'
  AND ID NOT IN (SELECT post_id FROM wp_postmeta WHERE meta_key = '_wp_attachment_image_alt');
```

Then batch-update via CLI or admin.

## redirects.chain

Use the **Redirection** plugin → Tools → Import → scan for chains. Fix by pointing the first redirect directly at the final URL.

## fetch.errors

Use **Broken Link Checker** or **Redirection** plugin. Fix each 404 with 301.
