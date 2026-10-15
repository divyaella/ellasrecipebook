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
aliases={}
for r in S['Aliases'][1:]:
    if len(r)>1 and r[0].strip(): aliases[r[0].strip().lower()]=r[1].strip()   # blank target = known gap / free
serves={}
for r in S['Serves'][1:]:
    r=r+['']*4
    if not r[0].strip(): continue
    v=num(r[3]) or num(r[2])
    serves[r[1].strip().rstrip('/').split('/')[-1] if r[1] else r[0]]=dict(title=r[0],serves=v,confirmed=bool(num(r[3])))
units={r[1].strip():dict(type=r[0],value=num(r[2]),unit=r[3]) for r in S['Units'][1:] if len(r)>3 and r[1].strip()}
json.dump(dict(prices=prices,aliases=aliases,serves=serves,units=units),open(f'{ROOT}/content/costing/sheet.json','w'),indent=1,ensure_ascii=False)
print('prices',len(prices),'aliases',len(aliases),'serves',len(serves),'units',len(units))
