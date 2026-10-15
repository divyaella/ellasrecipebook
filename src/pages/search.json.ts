import type { APIRoute } from 'astro';
import { loadRecipes, meta, fmtCost, tone } from '../data/site';

/** Compact index for client-side search on /recipes. One line per published recipe. */
export const GET: APIRoute = async () => {
  const all = await loadRecipes();
  const index = all
    .map((r) => ({
      s: r.slug,
      t: r.title,
      m: [meta(r), fmtCost(r)].filter(Boolean).join(' · '),
      g: r.series ?? '',
      k: [r.title, r.series ?? '', ...r.keywords, ...r.tags, ...r.ingredients.flatMap((x) => x.items)].join(' ').toLowerCase(),
      tg: r.tags,
      tm: r.time_minutes ?? null,
      c: r.cost_for_two ?? null,
      p: r.macros.protein ?? null,
      kc: r.macros.kcal ?? null,
      l: r.likes,
      d: r.posted,
      o: tone(r),
      i: r.image ?? null,
    }));
  return new Response(JSON.stringify(index), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
};
