import type { ImageMetadata } from 'astro';

/** Reel cover images, one per recipe slug, in src/images/recipes/<slug>.jpg (720×1280 from Instagram). */
const mods = import.meta.glob<{ default: ImageMetadata }>('../images/recipes/*.jpg', { eager: true });

const bySlug: Record<string, ImageMetadata> = {};
for (const [path, mod] of Object.entries(mods)) {
  const slug = path.split('/').pop()!.replace(/\.jpg$/, '');
  bySlug[slug] = mod.default;
}

export const photoFor = (slug: string): ImageMetadata | undefined => bySlug[slug];
export const photoCount = Object.keys(bySlug).length;
