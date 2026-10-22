"""Cost every published recipe from the price list.
Reads content/costing/sheet.json + content/recipes/*.json ; writes content/costing/costs.json and review.json.
Statuses per ingredient line: ok | vague | free | missing (not on price list) | ambiguous | unit (cannot convert) | noprice"""
import json,glob,re,os,collections
from difflib import get_close_matches
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..'))
SH=json.load(open(f'{ROOT}/content/costing/sheet.json'))
PR=[p for p in SH['prices']]
ALIAS=SH['aliases']
OV=SH.get('overrides',{})
STANDIN={k:v.lower() for k,v in OV.get('standins',{}).items()}
UNITS=SH['units']
# ---- price lookup (default row per ingredient)
ITEMS={}
for p in PR:
    k=p['item'].lower()
    if k not in ITEMS or (p['default'] and not ITEMS[k]['default']): ITEMS[k]=p
# ---- text helpers
FR={'½':.5,'¼':.25,'¾':.75,'⅓':1/3,'⅔':2/3,'⅛':.125}
NUMW={'a':1,'an':1,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'half':.5}
CANON={'chilly':'chilli','chili':'chilli','chillies':'chilli','chilies':'chilli','chillis':'chilli','aamchur':'amchur','cornflour':'cornstarch','haldi':'turmeric','turmeric':'turmeric',
 'jeera':'cumin','dahi':'curd','avacado':'avocado','dessicated':'desiccated','gochugara':'gochugaru','turmetic':'turmeric','turmeeric':'turmeric','poweder':'powder','esesame':'sesame','knobb':'knob','springs':'sprig','schezuan':'schezwan','mozarella':'mozzarella','tuvar':'toor','bayleaf':'bay','grounud':'ground','mozzarela':'mozzarella','buttom':'button'}
PHRASE=[('maida','all purpose flour'),('ap flour','all purpose flour'),('methi seeds','fenugreek seeds'),('rai','mustard seeds'),('garlic cloves','garlic'),('garlic clove','garlic'),('plain flour','all purpose flour'),('chilli flakes','crushed red pepper'),
 ('red chilli flakes','crushed red pepper'),('wheat flour','whole wheat flour atta'),('garlic ginger paste','ginger garlic paste'),('gg paste','ginger garlic paste'),('ginger and garlic paste','ginger garlic paste'),('greek yoghurt','greek yogurt'),('saunf','fennel seeds'),('elaichi','green cardamom'),('cashew nuts','cashews whole'),('cashew nut','cashews whole'),('cashews','cashews whole'),('whipped cream','whipping cream'),('brown bread','whole wheat bread'),('cracked black pepper','black peppercorns'),('breadcrumbs','bread crumbs'),('breadcrumb','bread crumbs')]
def sing(w):
    w=CANON.get(w,w)
    if w.endswith('ies') and len(w)>4: return w[:-3]+'y'
    if w.endswith('lli es'): return w
    if w.endswith('oes') and len(w)>4: return w[:-2]
    if w.endswith('ves') and len(w)>4: return w[:-3]+'f'
    if w.endswith('s') and not w.endswith('ss') and len(w)>3: return w[:-1]
    return w
def toks(s): return [sing(w) for w in re.findall(r"[a-z]+",s.lower())]
def canon_name(n):
    n=' '.join(CANON.get(w,w) for w in n.split())
    for a,b in PHRASE:
        if n==a or n.startswith(a+' ') and a not in('rai',): n=b+n[len(a):]
    return n
NUM=r'(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?[½¼¾⅓⅔]?|[½¼¾⅓⅔⅛])'
def val(s):
    s=s.strip(); tot=0
    m=re.match(r'^(\d+)\s+(\d+)/(\d+)$',s)
    if m: return int(m[1])+int(m[2])/int(m[3])
    m=re.match(r'^(\d+)/(\d+)$',s)
    if m: return int(m[1])/int(m[2])
    m=re.match(r'^(\d+(?:\.\d+)?)([½¼¾⅓⅔⅛])?$',s)
    if m: return float(m[1])+(FR.get(m[2],0) if m[2] else 0)
    return FR.get(s,0)
UNIT={'g':'g','gm':'g','gms':'g','gram':'g','grams':'g','kg':'kg','ml':'ml','l':'l','litre':'l','liter':'l','litres':'l',
 'tsp':'tsp','teaspoon':'tsp','teaspoons':'tsp','tbsp':'tbsp','tablespoon':'tbsp','tablespoons':'tbsp','tbs':'tbsp',
 'cup':'cup','cups':'cup','piece':'pc','pieces':'pc','pcs':'pc','pc':'pc','clove':'clove','cloves':'clove','inch':'inch',
 'slice':'slice','slices':'slice','sprig':'sprig','sprigs':'sprig','bunch':'bunch','can':'can','tin':'can','packet':'packet','stick':'stick','sticks':'stick',
 'handful':'handful','pinch':'pinch','dash':'dash','knob':'knob','scoop':'scoop','scoops':'scoop','leaf':'leaf','leaves':'leaf','knobb':'knob','nobb':'knob','pack':'packet','packets':'packet','spray':'spray','sprays':'spray','sachet':'packet','pods':'pc','pod':'pc','cubes':'pc','cube':'pc'}
VAGUE={'pinch':('g',.3),'dash':('ml',.5),'handful':('g',25),'knob':('g',10),'sprig':('g',2)}
SIZE={'small':.7,'medium':1,'large':1.3,'big':1.3}
NOISE=set('shredded lukewarm regular around finely roughly thinly freshly fresh chopped diced sliced minced grated crushed cubed cut boiled cooked ground powdered melted softened optional ripe raw frozen chilled warm room temperature soaked toasted roasted peeled deseeded seeded whole large medium small big extra about approx approximately of the and or for to taste garnish serving good quality'.split())
KEEP={'ground'}
def clean_name(s):
    s=re.sub(r'\(.*?\)','',s.lower())
    s=s.split(',')[0]
    s=re.split(r'\s+(?:for|if|so|but|as per|i use|i used|use|which|whichever|you|that|until|then|while|into|to be|at)\s+|\s[-–—/]\s|\s*\+\s*',s)[0]
    s=re.sub(r'\b(to taste|for garnish|for serving|as needed|as required|optional)\b','',s)
    ws=[w for w in re.findall(r"[a-z&']+",s)]
    ws=[w for w in ws if w not in NOISE]
    return ' '.join(ws).strip()
def parse_line(line):
    raw=line; s=line.strip().lstrip('-•* ').lower()
    s=re.sub(r'\(.*?\)',lambda m:'' if re.search(r'\d',m.group(0)) is None else m.group(0),s)
    qty=None; unit=None; size=1.0; vague=None
    m=re.match(r'^('+NUM+r')(?:\s*(?:-|–|to)\s*('+NUM+r'))?\s*',s)
    if m:
        qty=val(m[1]); 
        if m[2]: qty=(qty+val(m[2]))/2
        s=s[m.end():]
    else:
        m=re.match(r'^(a|an|one|two|three|four|five|six|half)\b\s*',s)
        if m and not re.match(r'^(a|an)\s+(little|bit|few|handful|pinch|dash|knob)',s) or (m and m[1] not in('a','an')):
            qty=NUMW[m[1]]; s=s[m.end():]
    for _ in range(3):
        m=re.match(r'^([a-z]+)\.?\s*',s)
        if not m: break
        w=m[1]
        if w in SIZE: size=SIZE[w]; s=s[m.end():]; continue
        if w in UNIT and (qty is not None or w in VAGUE):
            unit=UNIT[w]; s=s[m.end():]; s=re.sub(r'^of\s+','',s); break
        if w in('little','bit','few','some','generous','heaped','heaping','heapful','level','rounded','big','good','small'):
            s=s[m.end():]; continue
        break
    if unit in VAGUE and qty is None: qty=1
    if unit in VAGUE: vague=VAGUE[unit]
    if re.search(r'to taste|for garnish|as needed|as required|for serving|for greasing|for dusting|for frying',raw.lower()) and qty is None: vague=('g',0)
    return dict(raw=raw,qty=qty,unit=unit,size=size,name=clean_name(s),vague=vague)
# ---- provisional defaults for generic names (to confirm in the Aliases tab)
SUGGESTED={'oil':'Groundnut Oil','milk':'Toned Milk','butter':'Salted Butter','vinegar':'White Vinegar','cheese':'Cheese Block','cream':'Fresh Cream','sesame seeds':'White Sesame Seeds',
 'chocolate':'Dark Chocolate (55%)','dark chocolate':'Dark Chocolate (55%)','peanut butter':'Peanut Butter (Smooth)','sugar':'White Sugar','oats':'Rolled Oats','chilli':'Green Chilli',
 'bread':'White Bread','mustard':'Dijon Mustard','rice':'Basmati Rice','vanilla':'Vanilla Extract','bell pepper':'Bell Pepper Red','pepper':'Black Pepper Powder','paprika':'Smoked Paprika',
 'chilli powder':'Red Chilli Powder','flour':'All Purpose Flour (Maida)','noodles':'Hakka Noodles','sourdough':'Sourdough Slices','mango':'Frozen Mango Chunks','pasta':'Penne','cinnamon':'Cinnamon Sticks',
 'wheat flour':'Whole Wheat Flour (Atta)','cheddar cheese':'Cheddar','mozzarella cheese':'Mozzarella','parmesan cheese':'Parmesan','coconut':'Desiccated Coconut','yogurt':'Curd'}
SUGGESTED={k:v for k,v in SUGGESTED.items() if v.lower() in ITEMS}
# ---- matching
ITEMTOK={k:tuple(toks(k)) for k in ITEMS}
ALIASK={clean_name(a):t for a,t in ALIAS.items() if t}
ALIASK.update({a.lower():t for a,t in ALIAS.items() if t})
def match(name):
    """-> (status, item_key, candidates)"""
    if not name: return ('empty',None,[])
    name=canon_name(name)
    if name in ALIASK:
        t=ALIASK[name]
        if not t: return ('gap',None,[])
        return ('alias',t.lower(),[])
    if name in SUGGESTED: return ('suggested',SUGGESTED[name].lower(),[])
    if name in ITEMS: return ('exact',name,[])
    N=set(toks(name))
    exact=[k for k,t in ITEMTOK.items() if set(t)==N]
    if len(exact)==1: return ('exact',exact[0],[])
    def jac(k): I=set(ITEMTOK[k]); return len(N&I)/len(N|I)
    sup=[k for k,t in ITEMTOK.items() if N<=set(t)]          # name words inside item words
    if len(sup)==1: return ('auto',sup[0],[]) if jac(sup[0])>=.5 else ('suggest',None,sup)
    if len(sup)>1:
        # prefer the item whose name has the fewest extra words, if unique
        sup.sort(key=lambda k:len(ITEMTOK[k])); 
        if len(ITEMTOK[sup[0]])<len(ITEMTOK[sup[1]]) and len(ITEMTOK[sup[0]])==len(N)+0: return ('auto',sup[0],[])
        return ('ambiguous',None,sup[:5])
    sub=[k for k,t in ITEMTOK.items() if set(t)<=N and len(t)>=1]   # item words inside the name
    if sub:
        sub.sort(key=lambda k:-len(ITEMTOK[k]))
        if len(sub)==1 or len(ITEMTOK[sub[0]])>len(ITEMTOK[sub[1]]): return ('auto',sub[0],[]) if jac(sub[0])>=.5 else ('suggest',None,sub[:3])
        return ('ambiguous',None,sub[:5])
    c=get_close_matches(name,list(ITEMS),3,0.84)
    c9=get_close_matches(name,list(ITEMS),2,0.9)
    if len(c9)==1 or (c9 and c9[0]==name): return ('fuzzy',c9[0],[])
    return ('suggest',None,c) if c else ('missing',None,[])
# ---- unit conversion
def density(p):
    k=p['item'].lower(); c=p['category']
    U=lambda n,d:(UNITS.get(n,{}).get('value') or d)
    if 'vinegar' in k or 'juice' in k or 'stock' in k or 'water' in k: return 1.0,False
    if c=='Oils & Vinegars': return U('Oil',.92),False
    if 'ghee' in k: return U('Ghee',.91),False
    if 'butter' in k and 'peanut' not in k and 'almond' not in k: return U('Butter',.95),False
    if any(x in k for x in('milk','curd','cream','yogurt','skyr','buttermilk','lassi')): return U('Milk / curd / yoghurt',1.03),False
    if any(x in k for x in('honey','syrup','jaggery','condensed','jam')): return U('Honey / syrup',1.4),False
    if 'salt' in k: return U('Salt',1.2),False
    if 'icing' in k: return U('Icing sugar',.52),False
    if 'brown sugar' in k: return U('Brown sugar',.9),False
    if 'sugar' in k: return U('Sugar (white)',.83),False
    if any(x in k for x in('flour','maida','atta','besan','cornflour','corn starch','cornstarch','semolina','rava')): return U('Flour (AP, wheat)',.52),False
    if 'rice' in k and 'flour' not in k: return U('Rice (uncooked)',.8),False
    if 'oats' in k: return U('Oats',.37),False
    if 'cocoa' in k: return U('Cocoa powder',.45),False
    if c=='Spices & Seasonings': return U('Spice powders',.55),False
    if c=='Nuts & Seeds': return U('Whole seeds / nuts',.6),False
    if c in('Vegetable','Herbs'): return U('Chopped veg',.55),False
    if c=='Sauces & Condiments': return 1.1,False
    return U('Anything not listed',.6),True
PIECE_G=[('cherry tomato',15),('chicken breast',180),('cheese slice',20),('jalapeno',15),('cardamom',.5),('peppercorn',.1),('cinnamon',2),('apple',180),('pickle',30),('avocado',170),('mushroom',20),('spring onion',15),('curry leaves',1),('coriander',100),('green chilli',5),('garlic',4),('ginger',10),('onion',110),('tomato',100),('potato',150),('carrot',70),('banana',120),('lemon',30),('bread',30),('cucumber',200),('capsicum',150),('bell pepper',150)]
PIECE_G=[(k,v) for k,v in OV.get('piece_weights_g',{}).items()]+PIECE_G
SLICE_G=30
def to_base(L,p):
    """qty/unit -> amount in the price row's base unit (g/ml/pc). returns (amt, note) or (None, reason)"""
    q=L['qty']; u=L['unit']; base=p['unit']; k=p['item'].lower()
    if q is None: return (None,'noqty')
    if u=='spray': return (q*.5,'')
    q=q*L['size'] if u in(None,'pc','slice') and L['size']!=1 else q
    if u=='kg': q,u=q*1000,'g'
    if u=='l': q,u=q*1000,'ml'
    if u in('tsp','tbsp','cup'): q=q*{'tsp':5,'tbsp':15,'cup':240}[u]; u='ml'
    if u in('packet','can') and base in('g','ml'): return (q*p['qty'],'pack size')
    if base=='g' and u in('sprig','bunch','handful','leaf','scoop'): return (q*{'sprig':2,'bunch':100,'handful':25,'leaf':.5,'scoop':30}[u],'')
    if base=='ml':
        if u=='ml': return (q,'')
        if u=='g': d,_=density(p); return (q/d,'')
    if base=='g':
        if u=='g': return (q,'')
        if u=='ml': d,guess=density(p); return (q*d,'density-guess' if guess else '')
        if u=='clove': return (q*4,'') if 'garlic' in k else (None,'piece-weight')
        if u=='inch': return (q*10,'') if 'ginger' in k else (None,'piece-weight')
        if u=='slice': return (q*SLICE_G,'') if 'bread' in k else (None,'piece-weight')
        if u in(None,'pc'):
            if any(x in k for x in('paste','sauce','powder','ketchup','puree','crushed','peeled','sun-dried','pickle','juice','oil','seeds','flakes','dried','frozen')) and 'curry leaves' not in k: return (None,'piece-weight')
            for key,g in PIECE_G:
                if key in k: return (q*g,'')
            return (None,'piece-weight')
        if u=='spray': return (q*.5,'')
        if u in('stick',): return (None,'unit-'+u)
    if base=='pc':
        if u in(None,'pc'): return (q,'')
        if u=='slice' and 'bread' in k: return (q,'')
        return (None,'unit-'+str(u))
    return (None,'unit-'+str(u))
# ---- run
def expand(line):
    l=line.strip()
    m=re.match(r'^([A-Za-z ]{2,18}):\s*(.+)$',l)
    if m and not re.search(r'\d',m.group(1)): l=m.group(2)
    l=re.split(r'\s+OR\s+',l)[0]
    parts=re.split(r'\s*\+\s*',l)
    if len(parts)>1 and all(re.match(r'^\s*(\d|[½¼¾]|a |an |one |pinch|dash)',x.lower()) for x in parts[1:]) and re.match(r'^\s*(\d|[½¼¾])',parts[0]): return parts
    return [l]
def cost_line(line):
    L=parse_line(line)
    out=dict(raw=line,name=L['name'])
    if L['vague'] and L['vague'][1]==0: out['status']='vague'; out['cost']=0; return out
    if L['qty'] is None and not L['vague']: out.update(status='vague',cost=0,note='no quantity given — not costed'); return out
    nm=canon_name(L['name'])
    if nm and set(nm.split())<={'water','warm','hot','cold','ice','milk water'}-{'milk water'} and 'water' in nm.split() or nm in('ice','ice cubes','ice cube'): out.update(status='free',cost=0); return out
    if nm and set(nm.split())<={'salt','pepper','black','and','white','sea','rock','table'} : out.update(status='vague',cost=0); return out
    st,key,cands=match(L['name'])
    if st=='gap': out.update(status='missing',reason='gap-list'); return out
    if st=='empty': out.update(status='vague',cost=0); return out
    if st in('missing','suggest','ambiguous'):
        out.update(status=st,candidates=cands); return out
    p=ITEMS.get(key)
    if p is None and key in STANDIN and STANDIN[key] in ITEMS: p=ITEMS[STANDIN[key]]; out['standin']=f"{key} not priced yet — using {p['item']}"
    if p is None: out.update(status='missing',reason='no price yet',item_wanted=key); return out
    out['item']=p['item']; out['via']=st
    if not p['qty'] or not p['price']: out['status']='noprice'; return out
    rate=p['price']/p['qty']/(p['yield_'] or 1)
    if L['vague']:
        u,a=L['vague']; amt=a*(L['qty'] or 1)
        base=p['unit']; 
        if base=='pc': out.update(status='vague',cost=0); return out
        out.update(status='ok',cost=round(amt*rate,2),amount=amt,note='vague amount'); return out
    if L['qty'] is None: out.update(status='vague',cost=0,note='no quantity given — not costed'); return out
    amt,note=to_base(L,p)
    if amt is None: out.update(status='unit',reason=note,qty=L['qty'],unit=L['unit']); return out
    out.update(status='ok',cost=round(amt*rate,2),amount=round(amt,1),note=note)
    return out
def main():
    res={}; review=collections.defaultdict(lambda:dict(count=0,recipes=set(),examples=[],cands=[],status=None))
    tot=collections.Counter()
    for f in sorted(glob.glob(f'{ROOT}/content/recipes/*.json')):
        r=json.load(open(f))
        if r.get('duplicate_of') or not r.get('ingredients') or not r.get('method'): continue
        lines=[]
        for g in r['ingredients']:
            for it in g['items']: lines.extend(cost_line(x) for x in expand(it))
        sv=SH['serves'].get(r['id'],{}).get('serves') or r.get('serves')
        ok=[l for l in lines if l['status'] in('ok','vague','free')]
        unresolved=[l for l in lines if l['status'] not in('ok','vague','free')]
        total=round(sum(l.get('cost',0) for l in ok),0)
        for l in lines: tot[l['status']]+=1
        for l in unresolved:
            key=(l['status'] if l['status'] in('missing',) else l['status'], l['name'] if l['status']!='unit' else (l.get('item') or l['name'])+'|'+l.get('reason',''))
            e=review[key]; e['count']+=1; e['recipes'].add(r['slug']); e['status']=l['status']
            if len(e['examples'])<3: e['examples'].append(l['raw'])
            e['cands']=l.get('candidates',[]) or e['cands']
        nlines=sum(len(g['items']) for g in r['ingredients'])
        res[r['slug']]=dict(check_source=nlines<=4,title=r['title'],serves=sv,total=total,lines=len(lines),resolved=len(ok),unresolved=len(unresolved),
                            complete=not unresolved,per_serve=round(total/sv) if sv else None,for_two=round(total/sv*2) if sv else None,detail=lines)
    json.dump(res,open(f'{ROOT}/content/costing/costs.json','w'),indent=1,ensure_ascii=False)
    rv=[dict(status=k[0],key=k[1],recipes=len(v['recipes']),lines=v['count'],examples=v['examples'],candidates=v['cands']) for k,v in review.items()]
    rv.sort(key=lambda x:-x['recipes'])
    json.dump(rv,open(f'{ROOT}/content/costing/review.json','w'),indent=1,ensure_ascii=False)
    n=sum(tot.values()); print('lines',n,dict(tot))
    print('resolved %',round(100*(tot['ok']+tot['vague']+tot['free'])/n,1))
    comp=sum(1 for v in res.values() if v['complete']); print('recipes fully costed',comp,'of',len(res),'| of which ingredient list looks short:',sum(1 for v in res.values() if v['complete'] and v['check_source']))
    print('review items',len(rv),dict(collections.Counter(x['status'] for x in rv)))
if __name__=='__main__': main()
