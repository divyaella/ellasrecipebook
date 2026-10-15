"""Parse Instagram captions into structured recipe records.

Input:  content/raw/instagram-rows-enriched.json  (432 reels, from the profile scrape)
Output: content/recipes/<slug>.json                 (one file per recipe-like reel)
        content/raw/parse-report.json               (what parsed, what needs review)

Heuristic parser: it gets the shape right for the 2023–2026 caption format and
flags anything it is unsure about with needs_review, so each recipe can be
checked by hand when its page is built.
"""
import json, re, unicodedata, collections
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
rows = json.load(open(ROOT / "content/raw/instagram-rows-enriched.json"))
OUT = ROOT / "content/recipes"
OUT.mkdir(parents=True, exist_ok=True)

EMOJI = re.compile(r"[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍ ]+")
SERIES = [
    ("Feeding Adi", r"feeding\s*adi"),
    ("The Salad Edit", r"salad\s*edit"),
    ("Fake Fried", r"fake\s*fried"),
    ("Lazy Girl Breakfast", r"lazy[\s-]*girl"),
    ("Between the Slices", r"between the slices"),
    ("Home Food 101", r"home food 101"),
    ("Breakfast Diaries", r"breakfast diaries"),
    ("Weekday Lunch Diaries", r"lunch diaries"),
]
SECTION_HEAD = re.compile(
    r"^\s*(ingredients?|method|instructions?|directions?|steps|pro\s*tips?|tips?|notes?|nutrition|macros|veg alternatives?|storage|substitutions?)\b"
    r"\s*(?:\([^)]{0,40}\))?\s*(?:[:\-–—]\s*)?(?:\([^)]{0,40}\))?\s*$",
    re.I,
)
TIME_RE = re.compile(
    r"(?:\b(?:ready|done|dinner|lunch|breakfast|meal|recipe|together)\b[^.\n]{0,25}?\b(?:in|under|about|takes?)\s*~?(\d{1,2})\s*(?:min|minute)s?\b)"
    r"|(?:\b(\d{1,2})[- ]?(?:min|minute)s?\s*(?:meals?|recipes?|breakfasts?|dinners?|lunch(?:es)?|prep)\b)"
    r"|(?:\btakes?\s*(?:about|around|under)?\s*(\d{1,2})\s*(?:min|minute)s?\b)",
    re.I,
)


def clean(s):
    s = EMOJI.sub("", s)
    s = s.replace(" ", " ").replace("\xa0", " ").replace("�", "")
    return re.sub(r"[ \t]+", " ", s).strip()


VERB_START = re.compile(
    r"^(?:then\s+|now\s+|next\s+|first\s+|finally\s+|once\s+|while\s+|when\s+|after\s+|meanwhile\s+)?"
    r"(add|mix|cook|heat|whisk|pour|stir|top|bake|fry|blend|season|serve|toast|saut[eé]|boil|simmer|chop|slice|combine|fold|press|roll|spread|layer|grill|roast|air[- ]?fry|preheat|marinate|rest|let|allow|remove|drain|rinse|soak|pressure[- ]?cook|temper|garnish|finish|assemble|crack|beat|melt|reduce|bring|cover|flip|transfer|plate|scoop|shape|form|knead|dip|coat|sprinkle|drizzle|squeeze|grate|mash|crush|blitz|pulse|microwave|steam|wrap|fill|stuff|freeze|chill|refrigerate|store|enjoy|dig|eat|keep|use|start|take|put|place|throw|toss|turn|lower|raise|switch|set)\b",
    re.I,
)


def looks_like_instruction(t):
    if ING_LINE.match(t):
        return False
    words = len(t.split())
    return bool(VERB_START.match(t)) or (words >= 12 and not re.match(r"^[•\-\*]", t))


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:70]


def find_title(lines):
    """Prefer an ALL-CAPS dish line; else a Title Case line early on; else the first line."""
    skip = re.compile(r"^(ingredients?|method|macros|nutrition|serves|makes|episode|ep\.?|for the|for |home food 101|the salad edit|fake fried|lazy girl|feeding adi|between the slices)\b", re.I)
    prefix = re.compile(r"^(?:feeding adi|the salad edit|fake fried|lazy girl breakfast|between the slices|home food 101)\s*(?:[—:\-|]|ep(?:isode)?\.?\s*\d+)?\s*(?:[—:\-|]\s*)?", re.I)
    cands = []
    for ln in lines[:12]:
        t = clean(ln).strip(" :-–—|")
        t2 = prefix.sub("", t).strip(" :-–—|")
        if t2 != t and len(t2) >= 4:
            t = t2
        cands.append(t)
    for t in cands:
        if len(t) < 4 or skip.search(t):
            continue
        letters = re.sub(r"[^A-Za-z]", "", t)
        if len(letters) >= 6 and letters.upper() == letters and "KCAL" not in letters and "PROTEIN" not in letters:
            return t.title().replace("'S", "'s")
    for t in cands[:6]:
        if 4 <= len(t) <= 70 and not skip.search(t) and not t.endswith("?") and not re.search(r"\b(kcal|calories|protein)\b", t, re.I):
            # a title-ish line: most words capitalised, or a short noun phrase
            words = [w for w in re.split(r"\s+", t) if w]
            caps = sum(1 for w in words if w[:1].isupper())
            if caps >= max(2, len(words) * 0.6):
                return t
    t = cands[0] if cands else ""
    return t[:80]


ING_LINE = re.compile(r"^(?:[•\-\*▪◦·]\s*)?(?:~?\d+[\d/½¼¾.\-–]*\s*(?:g|gm|gms|grams?|kg|ml|l|tbsp|tsp|cups?|cloves?|large|small|medium|slices?|pieces?|pcs|eggs?|handful|pinch|bunch|whole|x)\b|[•\-\*▪◦·]\s*\S)", re.I)
SUBHEAD = re.compile(r"^(?:for the\b.*|[A-Z][A-Z &'()\-]{3,40})$")


def fallback_ingredients(lines, method_lines):
    """Captions that list ingredients under 'FOR THE X' / 'PANEER TIKKA' headings with no 'Ingredients' line."""
    out, cur, hits = [], {"name": None, "items": []}, 0
    stop_at = set(method_lines)
    for ln in lines:
        t = clean(ln)
        if not t or t in stop_at:
            continue
        if SECTION_HEAD.match(t) and re.match(r"method|instruction|direction|steps", t, re.I):
            break
        if SUBHEAD.match(t) and not ING_LINE.match(t) and len(t) < 45 and not re.search(r"\b(kcal|protein|serves|makes|save|episode)\b", t, re.I):
            if cur["items"]:
                out.append(cur)
            cur = {"name": t.rstrip(":").title() if t.isupper() else t.rstrip(":"), "items": []}
            continue
        if ING_LINE.match(t) and len(t) < 90:
            cur["items"].append(re.sub(r"^[•\-\*▪◦·]\s*", "", t)); hits += 1
    if cur["items"]:
        out.append(cur)
    return out if hits >= 3 else []


def parse_macros(text):
    m = {}
    t = text.replace("|", " | ")
    kc = (re.search(r"calories?\s*[:\-]?\s*(~?\d{2,4})\b", t, re.I)
          or re.search(r"(~?\d{2,4})[ \t]*(?:kcal|cal(?:ories)?)\b", t, re.I))
    if kc:
        m["kcal"] = int(kc.group(1).lstrip("~"))
    for key, pat in (("protein", r"(\d{1,3})[ \t]*g?[ \t]*(?:of[ \t]*)?protein|protein[ \t]*[:\-]?[ \t]*(\d{1,3})[ \t]*g|\bP[ \t]*[:=][ \t]*(\d{1,3})|(\d{1,3})[ \t]*g[ \t]*P\b"),
                     ("carbs", r"(\d{1,3})[ \t]*g?[ \t]*carbs?|carbs?[ \t]*[:\-]?[ \t]*(\d{1,3})[ \t]*g|\bC[ \t]*[:=][ \t]*(\d{1,3})|(\d{1,3})[ \t]*g[ \t]*C\b"),
                     ("fat", r"(\d{1,3})[ \t]*g?[ \t]*fat|fat[ \t]*[:\-]?[ \t]*(\d{1,3})[ \t]*g|\bF[ \t]*[:=][ \t]*(\d{1,3})|(\d{1,3})[ \t]*g[ \t]*F\b")):
        r = re.search(pat, t, re.I)
        if r:
            val = next(g for g in r.groups() if g)
            m[key] = int(val)
    if m.get("kcal") and m.get("kcal") < 60:
        m.pop("kcal")  # a stray macro number, not calories
    return m


def parse_serves(text):
    r = re.search(r"\b(?:serves|servings?|makes)\s*[:\-]?\s*~?(\d{1,2})", text, re.I)
    if r:
        return int(r.group(1))
    r = re.search(r"\((\d{1,2})\s*(?:sandwiches|servings|portions|jars|bowls)\)", text, re.I)
    return int(r.group(1)) if r else None


def split_sections(lines):
    """Walk the caption; bucket lines under ingredients / method / tips / other."""
    buckets = collections.OrderedDict(intro=[], ingredients=[], method=[], tips=[], other=[])
    cur = "intro"
    for ln in lines:
        t = clean(ln)
        if not t:
            continue
        if re.match(r"^(ingredients?\s*(?:\+|&|and)\s*method|recipe|here'?s what you need|what you need|how to make it|methods?|instructions?)\s*[:\-–—]?\s*$", t, re.I):
            cur = "method" if re.match(r"^(how to|methods?|instructions?)", t, re.I) else "ingredients"
            continue
        head = SECTION_HEAD.match(t)
        if head:
            h = head.group(1).lower()
            cur = ("ingredients" if h.startswith("ingredient") else
                   "method" if h in ("method", "instructions", "instruction", "directions", "direction", "steps") else
                   "tips" if ("tip" in h or "note" in h or "alternative" in h or "storage" in h or "substitution" in h) else "other")
            continue
        if re.match(r"^(macros?|nutrition|calories)\b", t, re.I) and cur == "intro":
            continue
        if re.match(r"^(pro\s*tips?|tips?)\s*[:\-–—]", t, re.I):
            cur = "tips"; t = re.sub(r"^(pro\s*tips?|tips?)\s*[:\-–—]\s*", "", t, flags=re.I)
        if re.match(r"^(save this|save for|share (it|this)|comment\b|follow\b)", t, re.I):
            cur = "other"
        if re.match(r"^[\(\[]", t) and len(t) > 40 and t.rstrip().endswith((")", "]")):
            cur = "other"  # keyword list
        # inline "Ingredients:" or "Method:" at line start with content after
        im = re.match(r"^(ingredients?|method)\s*[:\-–—]\s*(.+)$", t, re.I)
        if im:
            cur = "ingredients" if im.group(1).lower().startswith("ingredient") else "method"
            t = im.group(2)
        buckets[cur].append(t)
    return buckets


def parse_ingredients(lines):
    groups, cur = [], {"name": None, "items": []}
    for t in lines:
        is_head = (t.endswith(":") and len(t) < 50) or re.match(r"^(for the|for )", t, re.I) and len(t) < 50 and not re.search(r"\d", t)
        if is_head or (len(t) < 32 and not re.search(r"\d", t) and t.istitle() and not re.match(r"^[•\-\*]", t) and cur["items"]):
            if cur["items"] or cur["name"]:
                groups.append(cur)
            cur = {"name": t.rstrip(":"), "items": []}
            continue
        item = re.sub(r"^[•\-\*▪◦·]\s*", "", t).strip()
        if item:
            cur["items"].append(item)
    if cur["items"] or cur["name"]:
        groups.append(cur)
    return groups


def parse_method(lines):
    steps = []
    for t in lines:
        t = re.sub(r"^\(?\d{1,2}[\.\)]\s*", "", t).strip()
        if t:
            steps.append(t)
    # one long paragraph with sentences → split on '. '
    if len(steps) == 1 and len(steps[0]) > 220:
        steps = [s.strip() for s in re.split(r"(?<=[.!])\s+(?=[A-Z])", steps[0]) if s.strip()]
    return steps


def keywords(caption):
    m = re.findall(r"[\(\[]([^()\[\]]{40,})[\)\]]", caption)
    if not m:
        return []
    kw = [k.strip(" .") for k in re.split(r",", m[-1])]
    return [k for k in kw if 2 < len(k) < 60]


def tags(rec, caption):
    c = caption.lower(); t = set()
    ing = " ".join(i for g in rec["ingredients"] for i in g["items"]).lower() or c
    if re.search(r"\b(prawn|shrimp)", ing): t.add("prawns")
    if re.search(r"\b(chicken|keema|kheema|mince)\b", ing): t.add("chicken")
    if re.search(r"\b(eggs?|omelet|frittata|bhurji)\b", ing + " " + rec["title"].lower()): t.add("eggs")
    if re.search(r"\bpaneer\b", ing + " " + rec["title"].lower()): t.add("paneer")
    if re.search(r"\b(pasta|spaghetti|penne|farfalle|cannelloni|lasagn|macaroni|fusilli)\b", ing + " " + rec["title"].lower()): t.add("pasta")
    if re.search(r"\b(noodle|ramen|udon|maggi)\b", ing + " " + rec["title"].lower()): t.add("noodles")
    if re.search(r"\b(fish|salmon|tuna)\b", ing): t.add("fish")
    if not (t & {"prawns", "chicken", "fish"}) and not re.search(r"\b(mutton|lamb|beef|pork|bacon|sausage|frankfurter)\b", ing):
        t.add("vegetarian" if "eggs" not in t else "eggetarian")
    if re.search(r"\b(oats|chia|yogurt|yoghurt|smoothie|pancake|toast|breakfast|bhurji|omelet|frittata|granola|muffin)\b", c) or re.search(r"\b(eggs?)\b", rec["title"].lower()):
        t.add("breakfast")
    if re.search(r"\b(dessert|cookie|brownie|blondie|cake|cheesecake|truffle|tiramisu|biscoff|mousse|pudding|fudge)\b", rec["title"].lower()): t.add("dessert")
    if re.search(r"\b(salad)\b", rec["title"].lower()): t.add("salad")
    if re.search(r"\b(meal prep|batch|overnight|freez)", c): t.add("meal-prep")
    if re.search(r"\b(no oil|zero oil|zero-oil|no-oil|oil free|oil-free)\b", c): t.add("zero-oil")
    m = rec["macros"]
    if m.get("protein", 0) >= 25: t.add("high-protein")
    if 0 < m.get("kcal", 0) <= 500: t.add("under-500-kcal")
    tm = TIME_RE.search(caption)
    if tm:
        mins = int(next(g for g in tm.groups() if g))
        if 3 <= mins <= 90:
            rec["time_minutes"] = mins
            if mins <= 20: t.add("under-20-min")
    return sorted(t)


report = {"total": len(rows), "recipes": 0, "skipped": 0, "needs_review": 0, "by_year": collections.Counter(), "skipped_titles": [], "review_reasons": collections.Counter()}
seen_slugs = collections.Counter()
for r in rows:
    cap = r["caption"]
    lines = cap.split("\n")
    recipe_like = bool(re.search(r"\b(ingredients?|method|recipe|kcal|calories|protein)\b", cap, re.I))
    if not recipe_like:
        report["skipped"] += 1; report["skipped_titles"].append(clean(lines[0])[:60]); continue
    buckets = split_sections(lines)
    rec = {
        "id": r["id"],
        "source_url": f"https://www.instagram.com/ellasrecipebook_/reel/{r['id']}/",
        "posted": datetime.fromisoformat(r["dt"]).date().isoformat(),
        "likes": r["likes"], "comments": r["comments"],
        "title": find_title(lines),
        "series": next((n for n, p in SERIES if re.search(p, cap, re.I)), None),
        "episode": (lambda m: int(m.group(1)) if m else None)(re.search(r"\b(?:ep(?:isode)?\.?)\s*0?(\d{1,2})\b", cap, re.I)),
        "intro": " ".join(l for l in buckets["intro"][1:] if not re.search(r"\b(kcal|calories|protein|serves|makes)\b", l, re.I))[:600],
        "macros": parse_macros(cap),
        "serves": parse_serves(cap),
        "time_minutes": None,
        "ingredients": parse_ingredients(buckets["ingredients"]),
        "method": parse_method(buckets["method"]),
        "tips": buckets["tips"],
        "keywords": keywords(cap),
        "hashtags": re.findall(r"#(\w+)", cap),
        "caption": cap,
    }
    # instruction-like lines that landed in the ingredient list → method (2023 captions run them together)
    if rec["ingredients"] and len(rec["method"]) < 2:
        moved = []
        for g in rec["ingredients"]:
            keep = []
            for it in g["items"]:
                (moved if looks_like_instruction(it) else keep).append(it)
            g["items"] = keep
        rec["ingredients"] = [g for g in rec["ingredients"] if g["items"]]
        if len(moved) >= 1:
            rec["method"] = parse_method(moved) + rec["method"]
    if not rec["ingredients"]:
        rec["ingredients"] = fallback_ingredients(lines, buckets["method"])
        if rec["ingredients"]:
            got = {i for g in rec["ingredients"] for i in g["items"]}
            rec["intro"] = " ".join(l for l in buckets["intro"][1:] if clean(l) not in got and not SUBHEAD.match(clean(l)) and not re.search(r"\b(kcal|calories|protein|serves|makes)\b", l, re.I))[:600]
    if not rec["method"]:
        numbered = [re.sub(r"^\d{1,2}[\.\)]\s*", "", clean(l)) for l in lines if re.match(r"^\s*\d{1,2}[\.\)]\s+\S", l)]
        if len(numbered) >= 2 and not rec["tips"]:
            rec["method"] = numbered
    rec["tags"] = tags(rec, cap)
    reasons = []
    if not rec["ingredients"]: reasons.append("no-ingredients")
    if not rec["method"]: reasons.append("no-method")
    if not rec["macros"]: reasons.append("no-macros")
    if len(rec["title"]) < 6 or rec["title"].endswith("?"): reasons.append("weak-title")
    rec["needs_review"] = reasons
    for x in reasons: report["review_reasons"][x] += 1
    if reasons: report["needs_review"] += 1
    slug = slugify(rec["title"]) or r["id"].lower()
    seen_slugs[slug] += 1
    if seen_slugs[slug] > 1:
        slug = f"{slug}-{rec['posted']}"
    rec["slug"] = slug
    json.dump(rec, open(OUT / f"{slug}.json", "w"), ensure_ascii=False, indent=2)
    report["recipes"] += 1
    report["by_year"][rec["posted"][:4]] += 1

report["by_year"] = dict(report["by_year"]); report["review_reasons"] = dict(report["review_reasons"])
json.dump(report, open(ROOT / "content/raw/parse-report.json", "w"), ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in report.items() if k != "skipped_titles"}, indent=2))
print("complete (no review flags):", report["recipes"] - report["needs_review"])
