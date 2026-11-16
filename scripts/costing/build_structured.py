"""Convert every live recipe into structured ingredient lines + an ingredient master list, and write the workbook
that becomes the two-Sheet source of truth (Ingredients, Lines, Review queue, Recipe totals, Units).

Reads  : content/costing/sheet.json, content/recipes/*.json, content/hidden.json  (via parse_costs)
Writes : content/structured/ingredients.json, content/structured/lines.json, content/structured/Recipes-and-ingredients.xlsx
"""
import sys, os, re, json, glob, collections
sys.path.insert(0, os.path.dirname(__file__))
import parse_costs as pc
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule, CellIsRule
from openpyxl.utils import get_column_letter as CL

ROOT = pc.ROOT
OUT = f'{ROOT}/content/structured'
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- units
UNITS = [  # unit, type, factor, meaning
    ('g', 'g', 1, 'grams'), ('kg', 'g', 1000, 'kilograms'),
    ('ml', 'ml', 1, 'millilitres'), ('l', 'ml', 1000, 'litres'),
    ('tsp', 'ml', 5, 'teaspoon'), ('tbsp', 'ml', 15, 'tablespoon'), ('cup', 'ml', 240, 'cup (240 ml)'),
    ('pc', 'piece', 1, 'one whole item: uses "1 piece weighs" on the Ingredients tab'),
    ('clove', 'piece', 1, 'garlic clove: uses "1 piece weighs"'), ('inch', 'piece', 1, 'inch of ginger: uses "1 piece weighs"'),
    ('slice', 'piece', 1, 'slice of bread: uses "1 piece weighs"'), ('stick', 'piece', 1, 'uses "1 piece weighs"'),
    ('sprig', 'g', 2, '2 g'), ('bunch', 'g', 100, '100 g'), ('handful', 'g', 25, '25 g'), ('leaf', 'g', 0.5, '0.5 g'),
    ('scoop', 'g', 30, '30 g'), ('pinch', 'g', 0.3, '0.3 g'), ('knob', 'g', 10, '10 g'),
    ('dash', 'ml', 0.5, '0.5 ml'), ('spray', 'ml', 0.5, '0.5 ml'),
    ('can', 'pack', 1, 'one whole pack: uses the pack size'), ('packet', 'pack', 1, 'one whole pack: uses the pack size'),
]
UNIT_NAMES = [u[0] for u in UNITS]

# ---------------------------------------------------------------- ingredient master
EXCL = ('paste', 'sauce', 'powder', 'ketchup', 'puree', 'crushed', 'peeled', 'sun-dried', 'pickle', 'juice', 'oil', 'seeds', 'flakes', 'dried', 'frozen', 'stock', 'masala', 'vinegar')
def piece_g(item):
    k = item.lower()
    if any(x in k for x in EXCL) and 'curry leaves' not in k:
        return None
    for key, g in pc.PIECE_G:
        if key in k:
            return g
    return None

TASTE = {'salt': 2, 'pepper': 1}
def taste_default(p):
    k = p['item'].lower(); c = p['category']
    if 'salt' in k: return 2
    if 'pepper' in k and 'bell' not in k: return 1
    if c == 'Spices & Seasonings': return 1
    if c == 'Herbs': return 5
    if c == 'Oils & Vinegars': return 5
    return None

def cup_weight(p):
    k = p['item'].lower()
    if p['unit'] == 'pc': return None
    if 'stock' in k and p['unit'] == 'g': return 4.8      # 10 g cube makes 500 ml
    d, _ = pc.density(p)
    return round(d * 240, 1)

items = {}  # lower name -> dict
for k, p in pc.ITEMS.items():
    items[k] = dict(name=p['item'], category=p['category'], base=p['unit'], pack=p['qty'], price=p['price'],
                    yield_=p['yield_'] or 1.0, piece=piece_g(p['item']), cup=cup_weight(p), taste=taste_default(p),
                    brand=p.get('brand') or '', updated=p.get('updated') or '', note=p.get('note') or '', aliases=[])
for a, t in pc.ALIAS.items():
    if t and t.lower() in items:
        items[t.lower()]['aliases'].append(a)

def ensure_item(name, like=None, note=''):
    k = name.lower()
    if k in items: return items[k]
    base = dict(name=name, category='Other', base='g', pack=None, price=None, yield_=1.0, piece=None, cup=None, taste=None, brand='', updated='', note=note, aliases=[])
    if like and like.lower() in items:
        s = items[like.lower()]
        base.update(category=s['category'], base=s['base'], pack=s['pack'], price=s['price'], yield_=s['yield_'], cup=s['cup'], taste=s['taste'], note=note)
    items[k] = base
    return base

# placeholder rows
for k, v in pc.STANDIN.items():
    ensure_item(k.title(), like=v, note=f'Placeholder price: using {pc.ITEMS[v]["item"]}. Replace with the real price.' if v in pc.ITEMS else '')
water = ensure_item('Water', note='Free')
water.update(category='Other', base='ml', pack=1000, price=0, cup=240, taste=None)

# ---------------------------------------------------------------- recipe lines
PREP = ['finely', 'roughly', 'thinly', 'freshly', 'chopped', 'diced', 'sliced', 'minced', 'grated', 'crushed', 'cubed', 'boiled', 'cooked', 'melted', 'softened', 'peeled', 'roasted', 'toasted', 'shredded', 'mashed', 'whisked', 'ground']
def prep_note(part):
    s = re.sub(r'^\s*[-•*]\s*', '', part.strip())
    bits = []
    m = re.search(r'\(([^)]*)\)', s)
    if m and not re.search(r'\d', m.group(1)): bits.append(m.group(1).strip())
    head = re.sub(r'\([^)]*\)', '', s)
    pre, _, post = head.partition(',')
    w = [x for x in re.findall(r"[a-z]+", pre.lower()) if x in PREP]
    if w: bits.insert(0, ' '.join(w))
    if post.strip(): bits.append(post.strip())
    out = ', '.join(dict.fromkeys(b for b in bits if b))
    return out[:120]

SIZEWORD = re.compile(r'\b(small|medium|large|big)\b', re.I)
def struct_part(part, raw):
    L = pc.parse_line(part)
    rec = dict(raw=raw, ingredient='', qty=None, unit='', prep=prep_note(part), needed='Yes', why='', suggestion='')
    sz = SIZEWORD.search(part)
    if sz and rec['prep'] == '': rec['prep'] = sz.group(1).lower()
    v = L['vague']
    if v and v[1] == 0:
        rec['needed'] = 'To taste'
    elif L['qty'] is None and not v:
        rec['needed'] = 'No amount'
    nm = pc.canon_name(L['name'])
    if nm and 'water' in nm.split() and not any(w in nm.split() for w in ('coconut', 'rose', 'soda', 'tonic', 'mineral', 'tuna', 'melon')) or nm in ('ice', 'ice cubes', 'ice cube'):
        rec['ingredient'] = 'Water'
        if rec['needed'] == 'Yes' and L['qty'] is not None:
            rec['qty'] = L['qty']; rec['unit'] = L['unit'] or 'ml'
        return rec
    if not nm:
        rec['needed'] = 'No amount'; rec['why'] = 'no ingredient name'; return rec
    st, key, cands = pc.match(L['name'])
    p = None
    if st in ('missing', 'suggest', 'ambiguous', 'gap'):
        rec['why'] = {'missing': 'Not on the ingredient list', 'gap': 'Not on the ingredient list', 'suggest': 'Needs a substitute', 'ambiguous': 'Which one?'}[st]
        rec['suggestion'] = (cands[0] if cands else '') if isinstance(cands, list) else ''
        if rec['needed'] == 'To taste' or rec['needed'] == 'No amount':
            pass
    else:
        p = pc.ITEMS.get(key)
        if p is None and key in pc.STANDIN:
            rec['ingredient'] = key.title()
        elif p is None:
            ensure_item(key.title(), note='Not priced yet.')
            rec['ingredient'] = key.title()
        else:
            rec['ingredient'] = p['item']
    if rec['needed'] != 'Yes':
        return rec
    # amount and unit
    if v:
        rec['qty'] = L['qty'] or 1; rec['unit'] = L['unit']
        return rec
    rec['qty'] = L['qty']
    rec['unit'] = L['unit'] or 'pc'
    if rec['unit'] not in UNIT_NAMES:
        rec['unit'] = {'tin': 'can', 'pack': 'packet'}.get(rec['unit'], rec['unit'])
    if p is not None and L['unit'] is None:
        amt, note = pc.to_base(L, p)
        if note == 'no-unit':
            rec['qty'] = None; rec['unit'] = ''; rec['needed'] = 'No amount'
    return rec

recipes = []
for f in sorted(glob.glob(f'{ROOT}/content/recipes/*.json')):
    r = json.load(open(f))
    if r.get('duplicate_of') or not r.get('ingredients') or not r.get('method') or r['slug'] in pc.HIDDEN:
        continue
    sv = pc.SH['serves'].get(r['id'], {}).get('serves') or r.get('serves')
    lines = []
    for g in r['ingredients']:
        for it in g['items']:
            for part in pc.expand(it):
                rec = struct_part(part, it)
                rec['group'] = g['name'] or ''
                lines.append(rec)
    recipes.append(dict(slug=r['slug'], title=r['title'], serves=sv, url=f"https://www.ellasrecipebook.com/recipes/{r['slug']}", lines=lines))
recipes.sort(key=lambda x: x['title'].lower())

# ---------------------------------------------------------------- master order + ids
idfile = f'{ROOT}/content/costing/ingredient_ids.json'
ids = json.load(open(idfile)) if os.path.exists(idfile) else {}
nxt = max([int(v.split('-')[1]) for v in ids.values()] + [0]) + 1
master = sorted(items.values(), key=lambda x: (x['category'], x['name'].lower()))
for m in master:
    if m['name'] not in ids:
        ids[m['name']] = f'ING-{nxt:04d}'; nxt += 1
    m['id'] = ids[m['name']]
json.dump(ids, open(idfile, 'w'), indent=1, ensure_ascii=False)

def tier(m):
    if m['price'] == 0: return 'Free'
    if m['category'] == 'Spices & Seasonings' and m['pack'] and m['price'] and m['base'] in ('g', 'ml') and m['price'] / m['pack'] * 100 >= 150:
        return 'Premium'
    return 'Pantry'

json.dump(master, open(f'{OUT}/ingredients.json', 'w'), indent=1, ensure_ascii=False)
json.dump(recipes, open(f'{OUT}/lines.json', 'w'), indent=1, ensure_ascii=False)

# ---------------------------------------------------------------- workbook
PUR = '4342A8'; AMB = 'FFF1C2'; RED = 'FADBD8'; GRN = 'E3F4E6'; LAV = 'ECEBFB'
font = lambda **k: Font(name='Arial', size=10, **k)
H = PatternFill('solid', fgColor=PUR)
def head(ws, widths, height=32):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[CL(i)].width = w
    for c in ws[1]:
        c.font = font(bold=True, color='FFFFFF'); c.fill = H; c.alignment = Alignment(wrap_text=True, vertical='center')
    ws.row_dimensions[1].height = height
    ws.freeze_panes = 'A2'

wb = Workbook()
wsT = wb.active; wsT.title = 'Recipe totals'
wsL = wb.create_sheet('Lines')
wsQ = wb.create_sheet('Review queue')
wsI = wb.create_sheet('Ingredients')
wsU = wb.create_sheet('Units')
wsR = wb.create_sheet('How it works')

# ---- Ingredients
hdI = ['ID', 'Ingredient', 'Category', 'Tier', 'Pack size', 'Base unit', 'Pack price ₹', 'Yield %', '₹ per 100 g / ml', '1 piece weighs (g)', '1 cup weighs (g)', 'To-taste amount (g / ml)', 'Also called', 'Price updated', 'Notes']
wsI.append(hdI)
for i, m in enumerate(master, 2):
    wsI.append([m['id'], m['name'], m['category'], tier(m), m['pack'], m['base'], m['price'], m['yield_'],
                f'=IF(OR(G{i}="",E{i}="",E{i}=0),"",G{i}/E{i}*100/H{i})' if m['base'] != 'pc' else f'=IF(OR(G{i}="",E{i}="",E{i}=0),"",G{i}/E{i}/H{i})',
                m['piece'], m['cup'], m['taste'], ', '.join(sorted(set(m['aliases']))), m['updated'], m['note']])
    wsI.cell(i, 8).number_format = '0%'
    wsI.cell(i, 9).number_format = '0.00'
    for c in wsI[i]: c.font = font()
head(wsI, [10, 30, 20, 10, 10, 9, 12, 8, 14, 14, 14, 16, 36, 14, 44])
wsI['I1'].value = '₹ per 100 g / ml  (per piece for "pc" items)'
nI = len(master) + 1
wsI.auto_filter.ref = f'A1:O{nI}'
wsI.conditional_formatting.add(f'A2:O{nI+500}', FormulaRule(formula=['AND($B2<>"",OR($G2="",$E2=""))'], fill=PatternFill('solid', bgColor=AMB, fgColor=AMB)))
dv = DataValidation(type='list', formula1='"Pantry,Premium,Free"', allow_blank=True); wsI.add_data_validation(dv); dv.add(f'D2:D{nI+500}')
dv = DataValidation(type='list', formula1='"g,ml,pc"', allow_blank=True); wsI.add_data_validation(dv); dv.add(f'F2:F{nI+500}')

# ---- Units
wsU.append(['Unit', 'Type', 'Factor', 'Meaning'])
for u in UNITS: wsU.append(list(u))
for r in wsU.iter_rows(min_row=2):
    for c in r: c.font = font()
head(wsU, [10, 10, 10, 70])

# ---- Lines + Queue
hdL = ['Recipe', 'Group', 'Ingredient', 'Amount', 'Unit', 'Prep note', 'Needed?', 'Status', 'Cost ₹', 'Shown on the site as', 'As written on Instagram',
       'Recipe ID', '_row', '_base', '_pack', '_price', '_piece', '_cup', '_taste', '_type', '_factor', '_amount', '_yield']
wsL.append(hdL)
LROW0 = 2
queue = []
n = LROW0
rows_for_json = []
for r in recipes:
    for ln in r['lines']:
        ln['_row'] = n
        unresolved = (ln['ingredient'] == '' and ln['needed'] != 'No amount')
        if unresolved:
            queue.append((n, r, ln))
        n += 1
LAST = n - 1
nq = {}
for qi, (row, r, ln) in enumerate(queue, 2):
    nq[row] = qi

IM = lambda col: f'INDEX(Ingredients!${col}$2:${col}$3000,M{{r}})'
for r in recipes:
    for ln in r['lines']:
        i = ln['_row']
        q = nq.get(i)
        C = f"='Review queue'!D{q}&\"\"" if q else ln['ingredient']
        D = f"=IF('Review queue'!E{q}=\"\",\"\",'Review queue'!E{q})" if q else ln['qty']
        E = f"='Review queue'!F{q}&\"\"" if q else ln['unit']
        f = lambda s: s.replace('{r}', str(i))
        row = [r['title'], ln['group'], C, D, E, ln['prep'], ln['needed'],
               # Status
               f('=IF(G{r}="No amount","No amount given",IF(C{r}="","Pick ingredient",IF(M{r}=0,"Not in ingredient list",IF(OR(NOT(ISNUMBER(O{r})),NOT(ISNUMBER(P{r}))),"Price needed",IF(G{r}="To taste","OK",IF(D{r}="","No amount given",IF(NOT(ISNUMBER(V{r})),"Weight needed","OK"))))))) '.strip()),
               # Cost
               f('=IF(H{r}="OK",ROUND(V{r}*P{r}/O{r}/W{r},2),0)'),
               # Shown as
               f('=IF(G{r}="To taste",IF(C{r}="",K{r},C{r}&", to taste"),IF(OR(C{r}="",D{r}=""),K{r},TRIM(D{r}&" "&IF(E{r}="pc","",E{r}&" ")&C{r}&IF(F{r}<>"",", "&F{r},""))))'),
               ln['raw'], r['slug'],
               # helpers
               f('=IFERROR(MATCH(C{r},Ingredients!$B$2:$B$3000,0),0)'),
               f('=IF(M{r}=0,"",INDEX(Ingredients!$F$2:$F$3000,M{r}))'),
               f('=IF(M{r}=0,"",INDEX(Ingredients!$E$2:$E$3000,M{r}))'),
               f('=IF(M{r}=0,"",INDEX(Ingredients!$G$2:$G$3000,M{r}))'),
               f('=IF(M{r}=0,"",INDEX(Ingredients!$J$2:$J$3000,M{r}))'),
               f('=IF(M{r}=0,"",INDEX(Ingredients!$K$2:$K$3000,M{r}))'),
               f('=IF(M{r}=0,"",INDEX(Ingredients!$L$2:$L$3000,M{r}))'),
               f('=IFERROR(VLOOKUP(E{r},Units!$A$2:$C$60,2,FALSE),"")'),
               f('=IFERROR(VLOOKUP(E{r},Units!$A$2:$C$60,3,FALSE),"")'),
               # amount in base unit (g / ml / pc)
               f('=IF(OR(M{r}=0,NOT(ISNUMBER(P{r}))),"",IF(G{r}="To taste",IF(ISNUMBER(S{r}),S{r},0),IF(NOT(ISNUMBER(D{r})),"",'
                 'IF(T{r}="piece",IF(N{r}="pc",D{r},IF(ISNUMBER(Q{r}),D{r}*Q{r},"")),'
                 'IF(T{r}="pack",IF(ISNUMBER(O{r}),D{r}*O{r},""),'
                 'IF(T{r}="g",IF(N{r}="g",D{r}*U{r},IF(AND(N{r}="ml",ISNUMBER(R{r})),D{r}*U{r}/(R{r}/240),"")),'
                 'IF(T{r}="ml",IF(N{r}="ml",D{r}*U{r},IF(AND(N{r}="g",ISNUMBER(R{r})),D{r}*U{r}*(R{r}/240),"")),"")))))))'),
               f('=IF(M{r}=0,1,IF(INDEX(Ingredients!$H$2:$H$3000,M{r})="",1,INDEX(Ingredients!$H$2:$H$3000,M{r})))'),
               ]
        wsL.append(row)
        for c in wsL[i]: c.font = font()
        wsL.cell(i, 9).number_format = '0.00'
# data validation (only on rows that are not fed by the queue)
head(wsL, [34, 16, 26, 9, 9, 28, 11, 20, 9, 38, 44, 12, 6, 7, 7, 7, 7, 7, 7, 7, 7, 8, 7])
for col in range(13, 24): wsL.column_dimensions[CL(col)].hidden = True
wsL.auto_filter.ref = f'A1:K{LAST}'
dvI = DataValidation(type='list', formula1='=Ingredients!$B$2:$B$3000', allow_blank=True, showErrorMessage=False)
dvU = DataValidation(type='list', formula1='=Units!$A$2:$A$40', allow_blank=True)
dvN = DataValidation(type='list', formula1='"Yes,To taste,No amount"', allow_blank=True)
wsL.add_data_validation(dvI); wsL.add_data_validation(dvU); wsL.add_data_validation(dvN)
for r in recipes:
    for ln in r['lines']:
        i = ln['_row']
        if i not in nq:
            dvI.add(f'C{i}'); dvU.add(f'E{i}')
        dvN.add(f'G{i}')
wsL.conditional_formatting.add(f'H2:H{LAST}', FormulaRule(formula=['$H2="OK"'], fill=PatternFill('solid', bgColor=GRN, fgColor=GRN)))
wsL.conditional_formatting.add(f'H2:H{LAST}', FormulaRule(formula=['OR($H2="Pick ingredient",$H2="Not in ingredient list",$H2="Price needed",$H2="Weight needed")'], fill=PatternFill('solid', bgColor=RED, fgColor=RED)))
wsL.conditional_formatting.add(f'H2:H{LAST}', FormulaRule(formula=['$H2="No amount given"'], fill=PatternFill('solid', bgColor=AMB, fgColor=AMB)))

# queue
wsQ.append(['Recipe', 'Line as written on Instagram', "What's unclear", 'Pick the ingredient', 'Amount', 'Unit', 'Done', 'Suggestion', 'Row on Lines'])
for qi, (row, r, ln) in enumerate(queue, 2):
    wsQ.append([r['title'], ln['raw'], ln['why'] or 'Which ingredient?', None, ln['qty'], ln['unit'], f'=IF(D{qi}<>"","✓","")', ln['suggestion'], row])
    for c in wsQ[qi]: c.font = font()
    wsQ.cell(qi, 4).fill = PatternFill('solid', fgColor=AMB)
head(wsQ, [34, 56, 26, 30, 9, 9, 7, 30, 10])
nQ = len(queue) + 1
wsQ.auto_filter.ref = f'A1:I{max(nQ,2)}'
dvq = DataValidation(type='list', formula1='=Ingredients!$B$2:$B$3000', allow_blank=True, showErrorMessage=False); wsQ.add_data_validation(dvq); dvq.add(f'D2:D{max(nQ,2)}')
dvq2 = DataValidation(type='list', formula1='=Units!$A$2:$A$40', allow_blank=True); wsQ.add_data_validation(dvq2); dvq2.add(f'F2:F{max(nQ,2)}')
wsQ.conditional_formatting.add(f'A2:I{max(nQ,2)}', FormulaRule(formula=['$G2="✓"'], fill=PatternFill('solid', bgColor=GRN, fgColor=GRN)))

# ---- Totals
wsT.append(['Recipe', 'Serves', 'Total ₹', 'Per serve ₹', 'For two ₹', 'Status', 'Lines', 'Costed', 'Need a price or pick', 'No amount given', 'Recipe ID', 'URL'])
for i, r in enumerate(recipes, 2):
    rng = lambda col: f'Lines!${col}$2:${col}${LAST}'
    wsT.append([r['title'], r['serves'],
                f'=SUMIFS({rng("I")},{rng("L")},K{i})',
                f'=IF(OR(B{i}="",B{i}=0),"",ROUND(C{i}/B{i},0))',
                f'=IF(OR(B{i}="",B{i}=0),"",ROUND(C{i}/B{i}*2,0))',
                f'=IF(B{i}="","Serves needed",IF(I{i}>0,"Partly costed",IF(J{i}>0,"Costed, "&J{i}&IF(J{i}=1," line has"," lines have")&" no amount","Fully costed")))',
                f'=COUNTIFS({rng("L")},K{i})',
                f'=COUNTIFS({rng("L")},K{i},{rng("H")},"OK")',
                f'=G{i}-H{i}-J{i}',
                f'=COUNTIFS({rng("L")},K{i},{rng("H")},"No amount given")',
                r['slug'], r['url']])
    for c in wsT[i]: c.font = font()
    wsT.cell(i, 3).number_format = '#,##0'
head(wsT, [44, 8, 10, 11, 11, 36, 7, 8, 14, 12, 40, 60])
wsT.auto_filter.ref = f'A1:L{len(recipes)+1}'
wsT.conditional_formatting.add(f'F2:F{len(recipes)+1}', FormulaRule(formula=['LEFT($F2,5)="Fully"'], fill=PatternFill('solid', bgColor=GRN, fgColor=GRN)))
wsT.conditional_formatting.add(f'F2:F{len(recipes)+1}', FormulaRule(formula=['OR($F2="Partly costed",$F2="Serves needed")'], fill=PatternFill('solid', bgColor=RED, fgColor=RED)))
wsT.conditional_formatting.add(f'F2:F{len(recipes)+1}', FormulaRule(formula=['LEFT($F2,6)="Costed"'], fill=PatternFill('solid', bgColor=AMB, fgColor=AMB)))

# ---- How it works
T = [
    ('How this workbook works', ''),
    ('Ingredients', 'One row per ingredient, ever. Pack size and price live here once. Change a price and every recipe that uses it re-costs. Amber rows still need a price.'),
    ('Lines', 'One row per ingredient line in every live recipe. Pick the ingredient from the dropdown; it can only ever be spelled one way. Grey columns to the right are calculations (hidden). Do not type over Status or Cost.'),
    ('Review queue', 'The lines that could not be matched automatically. Pick the ingredient (and fix the amount or unit if needed). Once picked, the matching row on Lines fills itself in.'),
    ('Recipe totals', 'Total, per-serve and for-two cost for every recipe, worked out from Lines. Fully costed means every line has a price and an amount.'),
    ('Units', 'g, kg, ml, l, tsp, tbsp, cup and pc, plus a few cook units. Cups, tsp and tbsp stay as written; the sheet converts them to g or ml using the "1 cup weighs" column on Ingredients.'),
    ('To taste', 'Salt, pepper and garnishes marked To taste cost the "To-taste amount" set on Ingredients (2 g salt, 1 g pepper). Spices are costed from their own pack price. Premium spices are flagged in the Tier column.'),
    ('No amount given', 'A line with no amount is not costed and is counted separately, so you can add an amount or leave it out on purpose.'),
    ('Placeholders', 'Canola Oil uses the Sunflower Oil price until you enter the real one.'),
    ('Example row colours', 'Green = fine, amber = needs your attention, red = a price or ingredient is missing.'),
]
for a, b in T: wsR.append([a, b])
wsR['A1'].font = Font(name='Arial', size=14, bold=True, color=PUR)
for r in wsR.iter_rows(min_row=2):
    r[0].font = font(bold=True); r[1].font = font(); r[1].alignment = Alignment(wrap_text=True, vertical='top'); r[0].alignment = Alignment(vertical='top')
wsR.column_dimensions['A'].width = 22; wsR.column_dimensions['B'].width = 110

wb.save(f'{OUT}/Recipes-and-ingredients.xlsx')
nl = sum(len(r['lines']) for r in recipes)
print('recipes', len(recipes), 'lines', nl, 'queue', len(queue), 'ingredients', len(master))
print(collections.Counter(l['needed'] for r in recipes for l in r['lines']))
