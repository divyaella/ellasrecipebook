import { getCollection, type CollectionEntry } from 'astro:content';

export type Recipe = CollectionEntry<'recipes'>['data'];

export const SITE = {
  name: "Ella's Recipe Book",
  domain: 'ellasrecipebook.com',
  url: 'https://www.ellasrecipebook.com',
  instagram: 'https://www.instagram.com/ellasrecipebook_/',
  handle: '@ellasrecipebook_',
  tagline: 'Home cooking, written down.',
  description:
    'Healthy recipes you’ll actually crave — big flavour, better macros, the cost of feeding two made clear. By Divya Ella, Gurgaon.',
  author: 'Divya Ella',
};

/** A recipe is published when it has enough to cook from and isn't a repost of another one. */
export const isPublished = (r: Recipe) => r.ingredients.length > 0 && r.method.length > 0 && !r.duplicate_of;

/** All published recipes, newest first. */
export async function loadRecipes(): Promise<Recipe[]> {
  const entries = await getCollection('recipes');
  return entries.map((e) => e.data).filter(isPublished).sort((a, b) => b.posted.localeCompare(a.posted));
}

/** Discovery collections — the homepage sections and /collections/<id> pages. */
export const COLLECTIONS: {
  id: string;
  name: string;
  short: string;
  blurb: string;
  filter: (r: Recipe) => boolean;
  sort?: (a: Recipe, b: Recipe) => number;
}[] = [
  {
    id: 'popular',
    name: 'Popular on Instagram',
    short: 'From the Reels',
    blurb: 'Recipes you’ll already recognise from the Reels.',
    filter: (r) => true,
    sort: (a, b) => b.likes - a.likes,
  },
  {
    id: 'ready-in-20',
    name: 'Ready in 20 minutes',
    short: 'Under 20 min',
    blurb: 'Quick recipes for everyday cooking — the clock starts when you open the fridge.',
    filter: (r) => r.tags.includes('under-20-min'),
    sort: (a, b) => (a.time_minutes ?? 99) - (b.time_minutes ?? 99) || b.likes - a.likes,
  },
  {
    id: 'under-500',
    name: 'Feed 2 for under ₹500',
    short: 'Under ₹500 for two',
    blurb: 'Budget-conscious meals, with the cost of feeding two made clear — no hidden “pantry staples”.',
    filter: (r) => (r.cost_for_two ?? Infinity) <= 500,
    sort: (a, b) => (a.cost_for_two ?? 0) - (b.cost_for_two ?? 0),
  },
  {
    id: 'high-protein',
    name: 'High protein',
    short: 'High protein',
    blurb: 'Filling, flavourful meals with the protein per serving on the card.',
    filter: (r) => r.tags.includes('high-protein'),
    sort: (a, b) => (b.macros.protein ?? 0) - (a.macros.protein ?? 0),
  },
  {
    id: 'under-500-kcal',
    name: 'Under 500 calories',
    short: 'Under 500 kcal',
    blurb: 'Lighter plates that still feel like dinner.',
    // proper meals only — sides and chutneys sit under 150 kcal and aren't what this collection promises
    filter: (r) => r.tags.includes('under-500-kcal') && (r.macros.kcal ?? 0) >= 150,
    sort: (a, b) => b.likes - a.likes,
  },
  {
    id: 'meal-prep',
    name: 'Meal prep',
    short: 'Meal prep',
    blurb: 'Recipes that make planning and preparing the week easier — big-batch bases and things that keep.',
    filter: (r) => r.tags.includes('meal-prep'),
    sort: (a, b) => b.likes - a.likes,
  },
];

/** Categories — the header line and /categories/<id> pages. */
export const CATEGORIES: { id: string; name: string; filter: (r: Recipe) => boolean }[] = [
  { id: 'breakfast', name: 'Breakfast', filter: (r) => r.tags.includes('breakfast') },
  { id: 'mains', name: 'Mains', filter: (r) => !r.tags.includes('breakfast') && !r.tags.includes('dessert') && !r.tags.includes('salad') },
  { id: 'desserts', name: 'Desserts', filter: (r) => r.tags.includes('dessert') },
  { id: 'salads', name: 'Salads', filter: (r) => r.tags.includes('salad') },
  { id: 'vegetarian', name: 'Vegetarian', filter: (r) => r.tags.includes('vegetarian') },
  { id: 'eggs', name: 'Eggs', filter: (r) => r.tags.includes('eggs') },
  { id: 'chicken', name: 'Chicken', filter: (r) => r.tags.includes('chicken') },
  { id: 'prawns', name: 'Prawns', filter: (r) => r.tags.includes('prawns') },
  { id: 'pasta', name: 'Pasta', filter: (r) => r.tags.includes('pasta') },
  { id: 'noodles', name: 'Noodles', filter: (r) => r.tags.includes('noodles') },
  { id: 'paneer', name: 'Paneer', filter: (r) => r.tags.includes('paneer') },
];

export const SERIES: { id: string; name: string; blurb: string }[] = [
  { id: 'feeding-adi', name: 'Feeding Adi', blurb: 'Dinners Adi asked for, made to fit the goals. Normal food, better macros.' },
  { id: 'lazy-girl-breakfast', name: 'Lazy Girl Breakfast', blurb: 'Breakfasts that take ten minutes and keep you full.' },
  { id: 'the-salad-edit', name: 'The Salad Edit', blurb: 'This is your sign to eat more salad — but make it really, really good.' },
  { id: 'fake-fried', name: 'Fake Fried', blurb: 'The fried things you crave, without the oil.' },
  { id: 'home-food-101', name: 'Home Food 101', blurb: 'Everyday Indian home food, done properly.' },
  { id: 'breakfast-diaries', name: 'Breakfast Diaries', blurb: 'What breakfast looked like, one morning at a time.' },
  { id: 'weekday-lunch-diaries', name: 'Weekday Lunch Diaries', blurb: 'Dal, rice, sabzi — the weekday plate.' },
];

export const seriesId = (name: string | null) => (name ? name.toLowerCase().replace(/[^a-z0-9]+/g, '-') : null);

/* ---------- small formatting helpers ---------- */

export const fmtTime = (r: Recipe) => (r.time_minutes ? `${r.time_minutes} min` : null);
export const fmtServes = (r: Recipe) => (r.serves ? `Serves ${r.serves}` : null);
export const fmtCost = (r: Recipe) => (r.cost_for_two ? `₹${r.cost_for_two} for two` : null);
export const fmtMacros = (r: Recipe) => {
  const m = r.macros;
  const parts = [];
  if (m.kcal) parts.push(`${m.kcal} kcal`);
  if (m.protein) parts.push(`${m.protein}g protein`);
  if (m.carbs) parts.push(`${m.carbs}g carbs`);
  if (m.fat) parts.push(`${m.fat}g fat`);
  return parts;
};
export const meta = (r: Recipe) => [fmtTime(r), fmtServes(r)].filter(Boolean).join(' · ');

/** Deterministic placeholder tone per recipe until photos exist. */
export const tone = (r: Recipe) => {
  let h = 0;
  for (const ch of r.slug) h = (h * 31 + ch.charCodeAt(0)) % 9973;
  return ['butter', 'lavender', 'honey', 'berry'][h % 4];
};
