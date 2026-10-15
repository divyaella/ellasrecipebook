# ellasrecipebook.com

Static recipe site for [@ellasrecipebook_](https://www.instagram.com/ellasrecipebook_/), built with Astro.

## How it fits together

- `content/recipes/*.json` — one file per recipe. This is the source of truth the site builds from.
- `content/raw/` — the Instagram export the recipes were parsed from (captions, likes, dates).
- `content/overrides.json` — hand fixes keyed by Instagram post id (titles, intros). Survive re-parsing.
- `scripts/parse_captions.py` — turns captions into recipe JSON. `scripts/clean_recipes.py` tidies the result,
  marks reposts as duplicates and re-derives slugs. `npm run parse` runs both.
- `src/data/site.ts` — site constants, the discovery collections (filters + sort), the categories, formatting helpers.
- `src/pages/` — `index` (home), `recipes/[slug]` (recipe, with Recipe JSON-LD), `recipes/index` (browse all + search),
  `collections/[id]`, `categories/[id]`, `about`, `404`, `search.json` (client-side search index).
- `src/styles/global.css` — design tokens (Blueberry & Butter palette, Lora + Caveat) and shared components.

A recipe is published when it has ingredients **and** method and is not marked `duplicate_of` another post.
Everything else stays in `content/recipes/` unpublished until it is completed by hand.

## Commands

```
npm install
npm run dev       # local preview at http://localhost:4321
npm run build     # static site into dist/
npm run parse     # rebuild content/recipes from content/raw (keeps overrides.json)
```

## Adding or fixing a recipe

Edit the JSON in `content/recipes/<slug>.json` (or add a new one with the same fields) and commit.
For a fix that should survive `npm run parse`, put it in `content/overrides.json` under the post id instead.
Photos: set `"image": "/images/<slug>.jpg"` and drop the file in `public/images/`.

## Hosting

Vercel, static output. `astro.config.mjs` sets the canonical site URL (`https://www.ellasrecipebook.com`);
the sitemap and robots.txt are generated from it. DNS at GoDaddy → Vercel.
