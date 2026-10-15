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
  seoTitle: string;      // <title> for the collection page, ≤ 60 chars
  seoDescription: string;
  intro: string;         // a paragraph of real copy on the page
  filter: (r: Recipe) => boolean;
  sort?: (a: Recipe, b: Recipe) => number;
}[] = [
  {
    id: 'popular',
    name: 'Popular on Instagram',
    short: 'From the Reels',
    blurb: 'Recipes you’ll already recognise from the Reels.',
    seoTitle: 'Popular Indian Recipes from Instagram Reels',
    seoDescription: "Ella's most-watched recipes from @ellasrecipebook_, written out in full — ingredients, method, macros — so you can cook them instead of rewinding the reel.",
    intro: 'These are the recipes people keep coming back to on Instagram — the ones that got saved, shared and cooked the most. Every one is written out here in full, with the ingredient list, the method step by step and the macros per serving, so you never have to pause a reel at the wrong moment again.',
    filter: (r) => true,
    sort: (a, b) => b.likes - a.likes,
  },
  {
    id: 'ready-in-20',
    name: 'Ready in 20 minutes',
    short: 'Under 20 min',
    blurb: 'Quick recipes for everyday cooking — the clock starts when you open the fridge.',
    seoTitle: 'Quick Indian Recipes Ready in 20 Minutes',
    seoDescription: 'Healthy recipes that go from fridge to table in 20 minutes or less — eggs, paneer, chicken, one-pan dinners — with macros per serving.',
    intro: 'Twenty minutes is the honest limit on a weeknight. Everything here clears it: quick egg dishes, paneer and chicken stir-fries, bowls and toasts that come together while the kettle boils. The time on each card is the whole thing — chopping included — not just the cooking.',
    filter: (r) => r.tags.includes('under-20-min'),
    sort: (a, b) => (a.time_minutes ?? 99) - (b.time_minutes ?? 99) || b.likes - a.likes,
  },
  {
    id: 'under-500',
    name: 'Feed 2 for under ₹500',
    short: 'Under ₹500 for two',
    blurb: 'Budget-conscious meals, with the cost of feeding two made clear — no hidden “pantry staples”.',
    seoTitle: 'Dinner for Two Under ₹500 — Budget Indian Recipes',
    seoDescription: 'Full meals that feed two for under ₹500, costed ingredient by ingredient at Gurgaon prices. Big flavour, small bill.',
    intro: "Every recipe here is costed ingredient by ingredient — what the vegetables, protein and dairy cost at Gurgaon grocery prices — and comes in under ₹500 for two people. Pantry staples like oil, salt and spices are counted too, so the number on the card is close to what you'll actually spend.",
    filter: (r) => (r.cost_for_two ?? Infinity) <= 500,
    sort: (a, b) => (a.cost_for_two ?? 0) - (b.cost_for_two ?? 0),
  },
  {
    id: 'high-protein',
    name: 'High protein',
    short: 'High protein',
    blurb: 'Filling, flavourful meals with the protein per serving on the card.',
    seoTitle: 'High-Protein Indian Recipes (25g+ per serving)',
    seoDescription: 'Filling Indian meals with 25g or more protein per serving — chicken, eggs, paneer, prawns, dal — with full macros and a method that actually works.',
    intro: "Protein that doesn't taste like a chore. Every recipe here delivers 25 grams or more per serving — chicken, eggs, paneer, prawns, dal — with the full macros on the card so you can fit it into whatever you're tracking. Most are everyday Indian dishes, lightened up rather than reinvented.",
    filter: (r) => r.tags.includes('high-protein'),
    sort: (a, b) => (b.macros.protein ?? 0) - (a.macros.protein ?? 0),
  },
  {
    id: 'under-500-kcal',
    name: 'Under 500 calories',
    short: 'Under 500 kcal',
    blurb: 'Lighter plates that still feel like dinner.',
    seoTitle: 'Under 500 Calorie Indian Meals That Still Feel Like Dinner',
    seoDescription: 'Lighter Indian meals under 500 calories per serving, with full macros. Proper plates — curries, bowls, eggs, stir-fries — not snacks dressed up as meals.',
    intro: 'Under 500 calories, but a proper plate: curries, rice bowls, eggs, stir-fries and pasta that feel like dinner. Sides and chutneys are kept out of this list on purpose — everything here is a meal on its own, with the calories and macros per serving on the card.',
    // proper meals only — sides and chutneys sit under 150 kcal and aren't what this collection promises
    filter: (r) => r.tags.includes('under-500-kcal') && (r.macros.kcal ?? 0) >= 150,
    sort: (a, b) => b.likes - a.likes,
  },
  {
    id: 'meal-prep',
    name: 'Meal prep',
    short: 'Meal prep',
    blurb: 'Recipes that make planning and preparing the week easier — big-batch bases and things that keep.',
    seoTitle: 'Meal Prep Recipes for the Week — Indian & Easy',
    seoDescription: 'Big-batch Indian recipes that keep well and reheat better — dals, curries, mince, overnight oats — plus a sample week to copy.',
    intro: 'Recipes that make Sunday cooking pay off all week: dals and curries that deepen overnight, a chicken mince that becomes three different dinners, overnight oats and chia puddings for grab-and-go breakfasts. Each one keeps for at least three days in the fridge.',
    filter: (r) => r.tags.includes('meal-prep'),
    sort: (a, b) => b.likes - a.likes,
  },
];

/** Categories — the header line and /categories/<id> pages. */
export const CATEGORIES: { id: string; name: string; seoTitle: string; intro: string; filter: (r: Recipe) => boolean }[] = [
  { id: 'breakfast', name: 'Breakfast', seoTitle: 'Healthy Indian Breakfast Recipes', intro: "Breakfasts worth getting up for: eggs every which way, parathas, overnight oats and chia puddings, dosa and idli with proper chutney. Most take under 15 minutes, and the ones that don't are worth the wait.", filter: (r) => r.tags.includes('breakfast') },
  { id: 'mains', name: 'Mains', seoTitle: 'Indian Dinner & Lunch Recipes — Mains', intro: 'The main event: curries, dals, rice dishes, pasta, noodles, stir-fries and one-pot dinners. Everyday home food, with macros per serving and the method written so it works the first time.', filter: (r) => !r.tags.includes('breakfast') && !r.tags.includes('dessert') && !r.tags.includes('salad') },
  { id: 'desserts', name: 'Desserts', seoTitle: 'Dessert & Baking Recipes', intro: 'Brownies, cookies, cakes, chia puddings and a few sugar-free experiments — Ella started as a dessert person, and it shows.', filter: (r) => r.tags.includes('dessert') },
  { id: 'salads', name: 'Salads', seoTitle: 'Salad Recipes That Are Actually Filling', intro: 'Salads built like meals — paneer tikka, chicken caesar, quinoa and chickpea — with enough protein to count as lunch.', filter: (r) => r.tags.includes('salad') },
  { id: 'vegetarian', name: 'Vegetarian', seoTitle: 'Vegetarian Indian Recipes', intro: "Vegetarian dishes with real substance: paneer, dal, subzis, khichdi and the occasional pasta. Marked vegetarian only when there's no egg either.", filter: (r) => r.tags.includes('vegetarian') },
  { id: 'eggs', name: 'Eggs', seoTitle: 'Egg Recipes — Indian & Beyond', intro: 'Eggs for breakfast, lunch or dinner: bhurji, omelettes, fried eggs with chilli oil, curries, frittatas. Cheap protein, done well.', filter: (r) => r.tags.includes('eggs') },
  { id: 'chicken', name: 'Chicken', seoTitle: 'Healthy Chicken Recipes', intro: "Chicken the way it gets cooked at home in India: curries, roasts, kebabs, mince, air-fried 'fakeaways' — high in protein, light on oil.", filter: (r) => r.tags.includes('chicken') },
  { id: 'prawns', name: 'Prawns', seoTitle: 'Prawn Recipes', intro: 'Kerala-style curries, pulao and quick stir-fries — prawns cook in minutes, so these are some of the fastest dinners on the site.', filter: (r) => r.tags.includes('prawns') },
  { id: 'pasta', name: 'Pasta', seoTitle: 'Pasta Recipes with Macros', intro: 'Pasta with the macros worked out: bolognese, creamy mushroom, cherry tomato, mac and cheese — comfort food that still fits the week.', filter: (r) => r.tags.includes('pasta') },
  { id: 'noodles', name: 'Noodles', seoTitle: 'Noodle Recipes — Ramen, Stir-Fries & More', intro: 'Dan dan, chilli oil, Korean rice noodles, upgraded instant ramen and Maggi — fast, hot and mostly under 30 minutes.', filter: (r) => r.tags.includes('noodles') },
  { id: 'paneer', name: 'Paneer', seoTitle: 'Paneer Recipes — High Protein & Easy', intro: 'Paneer tikka, bhurji, matar paneer, palak paneer, stir-fries and salads — the vegetarian protein that does everything.', filter: (r) => r.tags.includes('paneer') },
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
