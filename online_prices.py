"""Refresh supported product links; never infer prices from category pages."""
import json, re, sqlite3, threading, time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from html.parser import HTMLParser
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parent
DB = ROOT / 'data' / 'online-prices.sqlite3'
INTERVAL = 21600
WORKER_LOCK = threading.Lock()
def run_refresh(rows):
    try: refresh(rows)
    finally: WORKER_LOCK.release()
class StructuredData(HTMLParser):
    def __init__(self):
        super().__init__(); self.capture=False; self.parts=[]; self.documents=[]
    def handle_starttag(self, tag, attrs):
        if tag=='script' and dict(attrs).get('type','').lower()=='application/ld+json':
            self.capture=True; self.parts=[]
    def handle_data(self, data):
        if self.capture: self.parts.append(data)
    def handle_endtag(self, tag):
        if tag=='script' and self.capture:
            self.capture=False
            try: self.documents.append(json.loads(''.join(self.parts)))
            except ValueError: pass
def products(value):
    if isinstance(value,list):
        for child in value: yield from products(child)
    elif isinstance(value,dict):
        kind=value.get('@type',[])
        if kind=='Product' or isinstance(kind,list) and 'Product' in kind: yield value
        if '@graph' in value: yield from products(value['@graph'])
def read_price(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname!='www.jumia.ci' or not parsed.path.endswith('.html') or parsed.username or parsed.password:
        raise ValueError('Lien produit non pris en charge')
    request=Request(url,headers={'User-Agent':'ComparePrix/1.0 (price observation)'})
    with urlopen(request,timeout=12) as response:
        if urlsplit(response.url).hostname!='www.jumia.ci': raise ValueError('Redirection inattendue')
        raw=response.read(2000001)
        if len(raw)>2000000: raise ValueError('Page trop volumineuse')
    parser=StructuredData(); parser.feed(raw.decode('utf-8','replace'))
    found=[p for doc in parser.documents for p in products(doc)]
    if len(found)!=1: raise ValueError('Produit non identifiable')
    offer=found[0].get('offers',{})
    if isinstance(offer,list):
        if len(offer)!=1: raise ValueError('Plusieurs offres')
        offer=offer[0]
    if offer.get('@type')=='AggregateOffer' or offer.get('priceCurrency')!='XOF': raise ValueError('Prix unique en FCFA indisponible')
    value=float(offer.get('price',0))
    if not 1<=value<=100000000 or not value.is_integer(): raise ValueError('Prix invalide')
    stock=str(offer.get('availability','')).rsplit('/',1)[-1]
    return {'prix':int(value),'disponibilite':{'InStock':'available','OutOfStock':'out_of_stock'}.get(stock,'unknown'),'date_consultation':datetime.now(timezone.utc).date().isoformat(),'actualisation':'ok'}
def connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DB,timeout=3)
    db.execute('CREATE TABLE IF NOT EXISTS prices (url TEXT PRIMARY KEY, checked REAL, payload TEXT, state TEXT)')
    return db
def refresh(rows):
    for row in rows:
        url=row.get('url','')
        if row.get('source')!='prix_internet': continue
        try:
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                old=db.execute('SELECT checked,payload,state FROM prices WHERE url=?',(url,)).fetchone()
                if old and time.time()-old[0]<INTERVAL: continue
                db.execute('INSERT OR REPLACE INTO prices VALUES (?,?,?,?)',(url,time.time(),old[1] if old else None,'checking'))
            try: payload=json.dumps(read_price(url)); state='ok'
            except Exception: payload=old[1] if old else None; state='unavailable'
            with connect() as db: db.execute('UPDATE prices SET payload=?,state=? WHERE url=?',(payload,state,url))
        except sqlite3.Error: continue
def apply_updates(rows):
    try:
        with connect() as db: saved={r[0]:(r[1],r[2],r[3]) for r in db.execute('SELECT url,payload,state,checked FROM prices')}
        for row in rows:
            if row.get('source')!='prix_internet': continue
            payload,state,_=saved.get(row.get('url'),(None,'pending',0))
            previous=row.get('prix')
            if payload:
                update=json.loads(payload); row.update(update)
                if previous and row.get('prix_unitaire'):
                    row['prix_unitaire']=round(row['prix_unitaire']*row['prix']/previous,2)
            row['actualisation']=state
        due=any(r.get('source')=='prix_internet' and time.time()-saved.get(r.get('url'),(None,None,0))[2]>=INTERVAL for r in rows)
        if due and WORKER_LOCK.acquire(blocking=False):
            threading.Thread(target=run_refresh,args=([dict(r) for r in rows],),daemon=True).start()
    except sqlite3.Error: pass
    return rows
if __name__=='__main__':
    refresh(json.loads((ROOT/'data'/'articles.json').read_text(encoding='utf-8')))
