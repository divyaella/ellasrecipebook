import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const recipes = defineCollection({
  loader: glob({ pattern: '*.json', base: './content/recipes' }),
  schema: z.object({
    id: z.string(),
    slug: z.string(),
    title: z.string(),
    source_url: z.string().url(),
    posted: z.string(),
    likes: z.number(),
    comments: z.number(),
    series: z.string().nullable(),
    episode: z.number().nullable(),
    intro: z.string(),
    macros: z.object({
      kcal: z.number().optional(),
      protein: z.number().optional(),
      carbs: z.number().optional(),
      fat: z.number().optional(),
    }),
    serves: z.number().nullable(),
    time_minutes: z.number().nullable(),
    cost_for_two: z.number().nullable().optional(),
    ingredients: z.array(z.object({ name: z.string().nullable(), items: z.array(z.string()) })),
    method: z.array(z.string()),
    tips: z.array(z.string()),
    keywords: z.array(z.string()),
    hashtags: z.array(z.string()),
    tags: z.array(z.string()),
    needs_review: z.array(z.string()),
    caption: z.string(),
    image: z.string().optional(),
    duplicate_of: z.string().optional(),
  }),
});

export const collections = { recipes };
