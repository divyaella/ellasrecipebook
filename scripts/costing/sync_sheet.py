"""Turn the price-list Sheet export (tabs as CSV) into content/costing/{prices,aliases,serves}.json.
Sheet: https://docs.google.com/spreadsheets/d/1A8bRc3UQcT9XekxbeCdJaZU2Zxk5jBtAMS03oxjzg8I"""
import json,re,sys,os
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..'))
S=json.load(open(f'{ROOT}/content/costing/sheet-export.json'))
def num(x):
    try: return float(str(x).replace(',','').replace('₹','').replace('%','').strip())
    except: return None
prices=[]
for r in S['Prices'][1:]:
    if not r or not r[0].strip(): continue
    r=r+['']*12
    q,p=num(r[4]),num(r[6])
    y=num(r[9]); y=(y/100 if y and y>1 else y) or 1.0
    prices.append(dict(item=r[0].strip(),category=r[1],brand=r[2],store=r[3],qty=q,unit=r[5].strip(),price=p,
                       default=(r[8].strip().upper()=='Y'),yield_=y,updated=r[10],note=r[11]))
def parse_pack(x):
    """'85 g' / '1 litre' / '200' -> (qty, unit or None)"""
    x=str(x).strip().lower()
    m=re.match(r'^([\d,.]+)\s*(kg|g|gm|gms|ml|l|litre|litres|liter|pc|pcs)?\b',x)
    if not m or not m.group(1).replace(',','').replace('.','').isdigit(): return None,None
    q=float(m.group(1).replace(',','')); u=m.group(2)
    if u in('kg',): q,u=q*1000,'g'
    elif u in('l','litre','litres','liter'): q,u=q*1000,'ml'
    elif u in('gm','gms'): u='g'
    elif u in('pcs',): u='pc'
    return q,u
def parse_price(x):
    m=re.match(r'^\s*₹?\s*([\d,]+(?:\.\d+)?)',str(x))
    return float(m.group(1).replace(',','')) if m else None
UNITFIX={'lemon':'g','lime':'g','orange':'g','roti / tortilla wraps (cooked)':'g','maggi noodles':'g'}   # sheet says pc but the pack is in grams
extra=[]; skipped=[]
have={p['item'].lower() for p in prices}
for r in S.get('Not on price list',[])[1:]:
    r=r+['']*14
    name=r[0].strip()
    if not name: continue
    q,u=parse_pack(r[4]); pr=parse_price(r[6]); unit=r[5].strip().lower() or u
    if name.lower() in UNITFIX: unit=UNITFIX[name.lower()]
    notes=[]
    if 'substitute' in r[2].lower() or 'alternative' in r[2].lower() or 'older' in str(r[6]).lower() or 'frozen alternative' in r[2].lower(): notes.append('substitute/older listing — Ella to confirm')
    if name=='Monk Fruit Sweetener': skipped.append((name,'pack weight needed (sheet says 1 g for ₹449)')); continue
    if q is None or pr is None or not unit: skipped.append((name,f'{r[4]} / {r[6]}'[:60])); continue
    if name.lower() in UNITFIX: notes.append('unit corrected to g (sheet had pc)')
    extra.append(dict(item=name,category=r[1],brand=r[2][:60],store=r[3],qty=q,unit=unit,price=pr,default=True,yield_=1.0,updated='22 Oct 2026',note='; '.join(notes)))
prices+= [e for e in extra if e['item'].lower() not in have]
aliases={}
for r in S['Aliases'][1:]:
    if len(r)>1 and r[0].strip(): aliases[r[0].strip().lower()]=r[1].strip()   # blank target = known gap / free
names_l={p['item'].lower():p['item'] for p in prices}
answers=[]
for r in S.get('Which one do you mean',[])[1:]:
    r=r+['']*6
    if r[5].strip():
        ans=r[5].strip()
        if ans.lower() in names_l: aliases[r[0].strip().lower()]=names_l[ans.lower()]
        else: answers.append((r[0],ans))
OV=json.load(open(f'{ROOT}/content/costing/overrides.json'))
aliases.update({k:v for k,v in OV['aliases'].items()})
serves={}
for r in S['Serves'][1:]:
    r=r+['']*4
    if not r[0].strip(): continue
    v=num(r[3]) or num(r[2])
    serves[r[1].strip().rstrip('/').split('/')[-1] if r[1] else r[0]]=dict(title=r[0],serves=v,confirmed=bool(num(r[3])))
units={r[1].strip():dict(type=r[0],value=num(r[2]),unit=r[3]) for r in S['Units'][1:] if len(r)>3 and r[1].strip()}
json.dump(dict(prices=prices,aliases=aliases,serves=serves,units=units,overrides=OV),open(f'{ROOT}/content/costing/sheet.json','w'),indent=1,ensure_ascii=False)
print('prices',len(prices),'aliases',len(aliases),'serves',len(serves),'units',len(units))

print('added from Not-on-list tab:',len(extra),'| skipped:',len(skipped)); [print('  skip',x) for x in skipped]
print('answers needing manual handling:',answers)
