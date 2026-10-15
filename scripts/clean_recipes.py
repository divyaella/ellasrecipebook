#!/usr/bin/env python3
"""Post-parse cleanup for content/recipes/*.json. Idempotent; run after parse_captions.py.

- titles: hand overrides (content/overrides.json by post id), CTA-line titles replaced by the
  caption's first line, ALL-CAPS words title-cased, trailing "recipe"/"my way"/"!!!" trimmed
- intro: leading "a | b | c" keyword lines moved to keywords; macro strings and anything after
  them removed; first letter capitalised
- method: hashtag-only / CTA steps dropped, trailing hashtags stripped, first letter capitalised
- ingredients: hashtags stripped, empty items dropped
- duplicates: same dish posted more than once -> the most-liked post keeps the clean slug and
  is canonical; the others get `duplicate_of` and are not published
- slugs re-derived from the final title (files renamed to match)
"""
import json, re, sys, unicodedata, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / 'content' / 'recipes'
OVR = json.loads((ROOT / 'content' / 'overrides.json').read_text())

MACRO = re.compile(r'(?:(?:paneer|chicken)\s+macros\s*:\s*|macros\s*:\s*|why i love this recipe\s*:\s*)?[CFP]\s*:\s*\d+(?:\s*\|?\s*[CFP]\s*:\s*\d+)*', re.I)
PIPELINE = re.compile(r'^\s*(?:[^|\n.!?]{2,32}\|\s*)+[^|\n.!?]{2,32}')  # "a | b | c" keyword line
CTA_INTRO = re.compile(r'(questions about the recipe|drop a comment|leave a comment|comment below|full recipe|recipe (below|in (the )?(bio|comments|my previous))|link in bio|save this|tag (us|me)|follow (me|for)|part two drops|serving size\s*:)', re.I)
QTY = re.compile(r'\b\d+(?:[./]\d+)?\s*(?:-\s*\d+\s*)?(?:cups?|grams?|g|kg|ml|tbsp|tsp|tablespoons?|teaspoons?)\b', re.I)
HASHTAG = re.compile(r'(?:^|\s)[#@][\w.]+')
CTA_TITLE = re.compile(r'\b(save this|don.?t forget|tag (us|me)|link in bio|follow for|comment|dm me|recipe (below|in)|swipe)\b', re.I)
CTA_STEP = re.compile(r'\b(save this|don.?t forget to save|tag (us|me)|link in bio|follow (me|us|for)|drop a comment|comment below|let me know|dm me|share this|recipe in (the )?(bio|comments))\b', re.I)
TRAIL = re.compile(r'[\s!.:–—-]+$')
ACRONYM = {'BBQ', 'KFC', 'PB&J', 'AP', 'NYC', 'USA', 'DIY'}
STRIP_TITLE = [
    (re.compile(r'\s*,?\s*(my way|the ella way|at home)\s*[!.]*$', re.I), ''),
    (re.compile(r'^\s*(my|the)\s+(favou?rite|best(?:\s+ever)?)\s+', re.I), ''),
    (re.compile(r'^\s*my\s+', re.I), ''),
    (re.compile(r'\s+recipes?\s*[!.]*$', re.I), ''),
    (re.compile(r'\s*\((\d+\s*(?:servings?|sandwiches?|pieces?)|makes[^)]*)\)\s*$', re.I), ''),
]
EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿⬀-⯿️‍]+')


def slugify(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return s[:70].rstrip('-')


def cap(s):
    s = s.strip()
    return s[:1].upper() + s[1:] if s else s


def fix_caps(t):
    out = []
    for w in t.split(' '):
        core = re.sub(r'[^A-Za-z&]', '', w)
        if len(core) >= 3 and core.isupper() and core not in ACRONYM:
            out.append(w[:1] + w[1:].lower())
        else:
            out.append(w)
    return ' '.join(out)


def clean_title(r):
    t = r['title']
    if CTA_TITLE.search(t) or t.strip().upper() == (r.get('series') or '').upper():
        first = EMOJI.sub('', r['caption'].strip().split('\n')[0]).strip()
        first = re.split(r'\s*[|:]\s*', first)[0]
        if 3 < len(first) < 70 and not CTA_TITLE.search(first):
            t = first
    t = EMOJI.sub('', t)
    t = t.replace('�', '')
    t = re.sub(r'\bsouffl\b', 'soufflé', t, flags=re.I)
    t = re.sub(r'\bgarlick-y\b', 'garlicky', t, flags=re.I)
    for rx, rep in STRIP_TITLE:
        t2 = rx.sub(rep, t)
        if len(t2) >= 4:
            t = t2
    t = fix_caps(t)
    t = re.sub(r'\s+', ' ', TRAIL.sub('', t)).strip(' ,')
    # consistent title case: lowercase words get capitalised, small words stay small (except first)
    small = {'and', 'of', 'the', 'with', 'in', 'for', 'a', 'an', 'on', 'to', 'ki', 'ka', 'ke', 'wale', 'wali', 'x', 'or', 'at', 'from', 'style'}
    words = t.split(' ')
    out = []
    for i, w in enumerate(words):
        core = re.sub(r'[^A-Za-z]', '', w)
        if core and core.islower() and (i == 0 or core not in small):
            w = re.sub(r'[a-z]', lambda m: m.group(0).upper(), w, count=1)
        out.append(w)
    return ' '.join(out)


def clean_intro(r):
    s = r['intro'].replace('\n', ' ').strip()
    kws = []
    m = PIPELINE.match(s)
    if m:
        head = m.group(0)
        # the last "keyword" may run into the first sentence: "lazy girl breakfast This quinoa is..."
        last = head.rsplit('|', 1)[-1]
        cut = re.search(r'\s(?=[A-Z][a-z]|(?i:this|the|a|an|i|my|we|you|it|these|here|yes|so|if|when|today|made|make|perfect)\b)', last.strip())
        if cut:
            head = head[: len(head) - len(last) + cut.start() + (len(last) - len(last.lstrip()))]
        kws = [k.strip(' .') for k in head.split('|') if k.strip(' .')]
        s = s[len(head):].strip(' |')
    m = MACRO.search(s)
    if m:
        s = s[: m.start()].strip(' |,:')
    m = QTY.search(s)
    if m and m.start() > 0:
        s = s[: m.start()].strip(' ,:-')
        r.setdefault('needs_review', []).append('intro-truncated')
    s = HASHTAG.sub('', s).strip()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'^\(([^)]*)\)\s*', r'\1 — ', s) if s.startswith('(') else s
    # drop CTA sentences ("as always, if you have any questions… leave a comment")
    sents = re.split(r'(?<=[.!?])\s+', s)
    s = ' '.join(x for x in sents if not CTA_INTRO.search(x)).strip()
    if re.match(r'^(\*|-|•|\d)', s) or len(s) < 25:
        s = ''
    if kws:
        seen = set(k.lower() for k in r['keywords'])
        r['keywords'] = r['keywords'] + [k for k in kws if k.lower() not in seen and len(k) < 40]
    return cap(s)


def clean_method(r):
    out = []
    for step in r['method']:
        s = step.strip()
        tags = len(re.findall(r'(?:^|\s)#\w+', s))
        if tags >= 2 or re.fullmatch(r'[\s#@\w.]*', s) and tags >= 1:
            continue
        if CTA_STEP.search(s) and len(s) < 140:
            continue
        s = re.sub(r'(\s*#\w+)+\s*$', '', s).strip()
        s = re.sub(r'^[-•*]\s*', '', s)
        if len(s) < 3:
            continue
        out.append(cap(s))
    return out


def clean_ingredients(r):
    groups = []
    for g in r['ingredients']:
        items = []
        for it in g['items']:
            s = re.sub(r'(\s*#\w+)+', '', it).strip(' -•*')
            if len(s) >= 2:
                items.append(s)
        if items:
            groups.append({'name': g['name'], 'items': items})
    return groups


def main():
    files = sorted(DIR.glob('*.json'))
    recs = [json.loads(f.read_text()) for f in files]
    for f in files:
        f.unlink()

    for r in recs:
        r['needs_review'] = [x for x in r.get('needs_review', []) if x != 'intro-truncated']
        r['title'] = clean_title(r)
        r['intro'] = clean_intro(r)
        r['method'] = clean_method(r)
        r['ingredients'] = clean_ingredients(r)
        r['tips'] = [cap(re.sub(r'(\s*#\w+)+\s*$', '', t)) for t in r.get('tips', []) if len(t.strip()) > 3]
        r.pop('duplicate_of', None)
        for k, v in OVR.get(r['id'], {}).items():
            r[k] = v
        r['needs_review'] = sorted(set(r['needs_review']))

    # duplicates: group by normalised title; canonical = most liked (ties: most complete)
    key = lambda t: re.sub(r'[^a-z0-9]+', ' ', t.lower()).strip()
    groups = collections.defaultdict(list)
    for r in recs:
        groups[key(r['title'])].append(r)
    for k, g in groups.items():
        g.sort(key=lambda r: (r['likes'], len(r['method']), r['posted']), reverse=True)
        canon = g[0]
        canon['slug'] = slugify(canon['title'])
        for d in g[1:]:
            d['duplicate_of'] = canon['slug']
            d['slug'] = f"{slugify(d['title'])}-{d['posted'][:10]}"
            if d['likes'] >= 100 and 'duplicate' not in canon['needs_review']:
                pass

    # final slug uniqueness
    seen = {}
    for r in sorted(recs, key=lambda r: (r.get('duplicate_of') is not None, -r['likes'])):
        s = r['slug'] or r['id'].lower()
        if s in seen:
            s = f"{s}-{r['posted'][:10]}"
        if s in seen:
            s = f"{s}-{r['id'].lower()}"
        seen[s] = True
        r['slug'] = s

    for r in recs:
        (DIR / f"{r['slug']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n')

    pub = [r for r in recs if r['ingredients'] and r['method'] and not r.get('duplicate_of')]
    dup = [r for r in recs if r.get('duplicate_of')]
    print(f"{len(recs)} recipes · {len(pub)} published · {len(dup)} marked duplicate · "
          f"{sum(1 for r in pub if r['needs_review'])} flagged for review")


if __name__ == '__main__':
    main()
