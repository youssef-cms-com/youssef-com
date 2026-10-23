from __future__ import annotations
import os,re,sqlite3,unicodedata,difflib,secrets,html,io
from pathlib import Path
from datetime import datetime, timedelta
from openpyxl import load_workbook, Workbook

BASE=Path(__file__).resolve().parent
DATA_DIR=Path(os.getenv('DATA_DIR', str(BASE))).resolve(); DATA_DIR.mkdir(parents=True,exist_ok=True)
DB=Path(os.getenv('DB_PATH', str(DATA_DIR/'youssef.db'))); UPLOADS=Path(os.getenv('UPLOAD_DIR', str(DATA_DIR/'uploads'))); UPLOADS.mkdir(parents=True,exist_ok=True)
CURRENT_BUYERS=['Abdessamad Ech-chkaf','Abdeilah Afferyad','Mohamed Boussous','Mohamed Amine Kihi','Ali El ouahidi','Hairoure Hatim','Mohammed Oujghi','Lahcen El Ouarrad','Bilal Asbaghi','Achraf Largo','Saad Azmi']
FORMER_BUYERS=['Amine Hammouga','Abdelkoddos Samih','Nacreddine Bahaoui','Wissal Fekhar','Ayoub Ait Salah']
BUYERS=CURRENT_BUYERS+FORMER_BUYERS
MARKETS=[('MAROC','Morocco','MOROCCO'),('RDC','RDC','AFRICA'),('MALI','Mali','AFRICA'),('GUINEE','Guinée','AFRICA'),('CONGO','Congo','AFRICA'),('CAMEROUN','Cameroon','AFRICA'),('TOGO','Togo','AFRICA'),('BENIN','Benin','AFRICA'),('GABON','Gabon','AFRICA'),('TCHAD','Tchad','AFRICA'),('BURKINA_FASO','Burkina Faso','AFRICA'),('LEBANON','Lebanon','ARABIC'),('TUNISIA','Tunisia','ARABIC')]
AFRICA_CODES={'RDC','MALI','GUINEE','CONGO','CAMEROUN','TOGO','BENIN','GABON','TCHAD','BURKINA_FASO'}
CITY_MAP={'kinshasa':'RDC','lubumbashi':'RDC','kolwezi':'RDC','bukavu':'RDC','goma':'RDC','bamako':'MALI','conakry':'GUINEE','coyah':'GUINEE','kankan':'GUINEE','brazzaville':'CONGO','pointe noire':'CONGO','pointe-noire':'CONGO','yaounde':'CAMEROUN','douala':'CAMEROUN','lome':'TOGO','cotonou':'BENIN','libreville':'GABON','n djamena':'TCHAD','ndjamena':'TCHAD','ouagadougou':'BURKINA_FASO','beirut':'LEBANON','tripoli':'LEBANON','tunis':'TUNISIA','ben arous':'TUNISIA','mahdia':'TUNISIA','nabeul':'TUNISIA','ariana':'TUNISIA'}
COUNTRY_TEXT={'morocco':'MAROC','maroc':'MAROC','rdc':'RDC','mali':'MALI','guinee':'GUINEE','guinea':'GUINEE','congo':'CONGO','cameroun':'CAMEROUN','cameroon':'CAMEROUN','togo':'TOGO','benin':'BENIN','gabon':'GABON','tchad':'TCHAD','burkina':'BURKINA_FASO','lebanon':'LEBANON','liban':'LEBANON','tunisie':'TUNISIA','tunisia':'TUNISIA'}

def norm(s):
    s=unicodedata.normalize('NFKD',str(s or '')).encode('ascii','ignore').decode().lower().strip()
    s=re.sub(r'codglobal|cod global','',s); s=re.sub(r'\b\d+\b$','',s); s=re.sub(r'[^a-z0-9]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()

def esc(s): return html.escape(str(s if s is not None else ''))
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('pragma foreign_keys=on'); return c

def init_db(reset=False):
    if reset and DB.exists(): DB.unlink()
    c=db(); c.executescript('''
    create table if not exists buyers(id integer primary key,name text unique,name_norm text unique,status text);
    create table if not exists aliases(id integer primary key,buyer_id integer,alias text,alias_norm text unique);
    create table if not exists markets(id integer primary key,code text unique,name text,grp text);
    create table if not exists city_mappings(id integer primary key,city text not null,city_norm text unique not null,market_id integer not null,created_at text,source text default 'MANUAL');
    create table if not exists products(id integer primary key,name text,name_norm text,market_id integer,commission_usd real default 0,commission_mad real default 0,price_local real,local_mad real,unique(name_norm,market_id));
    create table if not exists commission_rules(id integer primary key,product_id integer,start_date text not null,end_date text,amount real not null,currency text not null,note text,created_at text,unique(product_id,start_date));
    create table if not exists periods(id integer primary key,label text unique,year int,month int,status text default 'OPEN',created_at text);
    create table if not exists settings(period_id integer primary key,maroc_spend_mad real default 9.77,other_usd_mad real default 9.40,usdt_mad real default 9.77,upsell_maroc real default .20,upsell_africa real default .25,remise_pct real default .80);
    create table if not exists deliveries(id integer primary key,period_id int,source text,source_row int,order_id text,tracking_number text,delivery_date text,buyer_id int,buyer_raw text,market_id int,city text,product_id int,commission_rule_id int,product_raw text,product_norm text,price real,base_commission_usd real default 0,base_commission_mad real default 0,base_price_local real,local_mad real,upsell_candidate_mad real default 0,upsell_mad real default 0,upsell_decision text default 'NONE',upsell_decided_at text,status text);
    create table if not exists spend(id integer primary key,period_id int,market_id int,buyer_id int,buyer_raw text,spend_usd real,leads real,deliveries_source real,filename text,source_row int);
    create table if not exists adjustments(id integer primary key,period_id int,buyer_id int,usdt_sent real default 0,charges real default 0,test_spend real default 0,wallet_rest real default 0,remise_mad real default 0,credit_mad real default 0,note text,unique(period_id,buyer_id));
    create table if not exists imports(id integer primary key,period_id int,kind text,market_code text,filename text,rows_imported int,warnings int,created_at text);
    create table if not exists users(id integer primary key,email text unique not null,name text not null,password_hash text not null,role text not null default 'MEDIA_BUYER_VIEWER',buyer_id integer,status text not null default 'ACTIVE',created_at text,last_login_at text);
    ''')
    c.executescript("""create table if not exists product_offers(id integer primary key,product_id integer not null,price real not null,commission real not null,effective_date text,note text,created_at text,unique(product_id,price));
    create table if not exists remise_reviews(id integer primary key,delivery_id integer not null unique,period_id integer not null,buyer_id integer,product_id integer,reference_price real,delivered_price real,gap_local real,rate_mad real,gap_mad real,decision text default 'PENDING',decided_at text);""")
    # Lightweight migrations for users upgrading an existing YOUSSEF.COM database.
    cols={r['name'] for r in c.execute('pragma table_info(deliveries)')}
    for col,ctype in [('delivery_date','text'),('product_id','integer'),('commission_rule_id','integer'),('tracking_number','text'),('upsell_candidate_mad','real default 0'),('upsell_decision',"text default 'NONE'"),('upsell_decided_at','text')]:
        if col not in cols:c.execute(f'alter table deliveries add column {col} {ctype}')
    bcols={r['name'] for r in c.execute('pragma table_info(buyers)')}
    for col,ctype in [('left_at','text'),('leave_reason','text')]:
        if col not in bcols:c.execute(f'alter table buyers add column {col} {ctype}')
    for n in BUYERS:c.execute('insert or ignore into buyers(name,name_norm,status) values(?,?,?)',(n,norm(n),'CURRENT' if n in CURRENT_BUYERS else 'FORMER / JULY'))
    aliases={
    'Oujghi Mohamed 3':'Mohammed Oujghi','Oujghi Mohamed':'Mohammed Oujghi','Mohamed Oujghi 3':'Mohammed Oujghi','Mohammed oujghi':'Mohammed Oujghi',
    'Hatim Hairoure':'Hairoure Hatim','Hatim Hairour':'Hairoure Hatim','Hatim Hairour 2':'Hairoure Hatim','Hatim Hairour 3':'Hairoure Hatim','Hairour Hatim':'Hairoure Hatim','Hatim hairour':'Hairoure Hatim',
    'Abdeilah aferyad 2':'Abdeilah Afferyad','Abdeilah aferyad 3':'Abdeilah Afferyad','Abdeilah Aferyad 3':'Abdeilah Afferyad','Abdeilah Aferyad 4':'Abdeilah Afferyad','Abdeilah Aferyad 5':'Abdeilah Afferyad','Abdeilah Aferyad':'Abdeilah Afferyad','ABDEILAH AFERYAD':'Abdeilah Afferyad',
    'Mohamed boussous':'Mohamed Boussous','Mohamed Amine Kihi 2':'Mohamed Amine Kihi','Mohamed Amine kihi 2':'Mohamed Amine Kihi','Mohamed Amine kihi':'Mohamed Amine Kihi','Mohamed amine Kihi':'Mohamed Amine Kihi',
    'Ali el ouahidi':'Ali El ouahidi','Ali El ouahidi':'Ali El ouahidi','Ali el Ouahidi':'Ali El ouahidi','Lahcen el ouarrad 3':'Lahcen El Ouarrad','Lahcen el ouarrad':'Lahcen El Ouarrad',
    'Bilal asbaghi 2':'Bilal Asbaghi','Bilal Asbaghi':'Bilal Asbaghi','Achraf largo':'Achraf Largo','Saad azmi':'Saad Azmi',
    'Abdessamad Ech':'Abdessamad Ech-chkaf','Abdessamad Echchkaf':'Abdessamad Ech-chkaf','Abdessamad ech':'Abdessamad Ech-chkaf','Abdessamad Echchkaf 2':'Abdessamad Ech-chkaf','Abdessamad ech chkaf':'Abdessamad Ech-chkaf','Abdessamad ech-chkaf':'Abdessamad Ech-chkaf','Abdessamad Ech Chkaf':'Abdessamad Ech-chkaf','ABDESSAMAD ECH CHKAF':'Abdessamad Ech-chkaf',
    'Amine hammouga':'Amine Hammouga','Abdelkodoss samih':'Abdelkoddos Samih','Abdelkodoss Samih':'Abdelkoddos Samih','Nacreddine Bahaoui':'Nacreddine Bahaoui','Wissal Fekhar':'Wissal Fekhar','Ayoub ait salah':'Ayoub Ait Salah'}
    for a,n in aliases.items():
        b=c.execute('select id from buyers where name=?',(n,)).fetchone();
        if b:c.execute('insert or ignore into aliases(buyer_id,alias,alias_norm) values(?,?,?)',(b['id'],a,norm(a)))
    for code,name,g in MARKETS:c.execute('insert or ignore into markets(code,name,grp) values(?,?,?)',(code,name,g))
    for city,code in CITY_MAP.items():
        mid=market_id(c,code)
        if mid:c.execute('insert or ignore into city_mappings(city,city_norm,market_id,created_at,source) values(?,?,?,?,?)',(city,norm(city),mid,datetime.now().isoformat(timespec='seconds'),'BUILT-IN'))
    c.commit(); c.close()

def market_id(c,code):
    r=c.execute('select id from markets where code=?',(code,)).fetchone(); return r['id'] if r else None

def market_from_country_text(s):
    n=norm(s)
    for k,v in COUNTRY_TEXT.items():
        if k in n:return v
    return None

def market_from_city(city,delivery_man='',c=None):
    n=norm(city); dm=norm(delivery_man); own=False
    if c is None:c=db();own=True
    r=c.execute('select m.code from city_mappings cm join markets m on m.id=cm.market_id where cm.city_norm=?',(n,)).fetchone() if n else None
    if own:c.close()
    if r:return r['code']
    if 'expedition' in n:
        if 'jaabilan' in dm:return 'MALI'
        if 'digital mobility' in dm:return 'CAMEROUN'
        if 'eyram' in dm:return 'TOGO'
        if 'msg' in dm:return 'GABON'
    return None

def add_city_mapping(city,code):
    city=str(city or '').strip();code=str(code or '').strip().upper()
    if not city:raise ValueError('City is required')
    c=db();mid=market_id(c,code)
    if not mid:c.close();raise ValueError('Country is not valid')
    c.execute('insert into city_mappings(city,city_norm,market_id,created_at,source) values(?,?,?,?,?) on conflict(city_norm) do update set city=excluded.city,market_id=excluded.market_id,source="MANUAL"',(city,norm(city),mid,datetime.now().isoformat(timespec='seconds'),'MANUAL'))
    c.commit();c.close();recalculate_city_deliveries(city)

def delete_city_mapping(mapping_id):
    c=db();r=c.execute('select * from city_mappings where id=?',(mapping_id,)).fetchone()
    if not r:c.close();return
    city=r['city'];c.execute('delete from city_mappings where id=?',(mapping_id,));c.commit();c.close();recalculate_city_deliveries(city)

def recalculate_city_deliveries(city):
    c=db();ncity=norm(city);rows=c.execute('select * from deliveries where source="GLOBAL"').fetchall();changed=0
    for d in rows:
        if norm(d['city'])!=ncity:continue
        code=market_from_city(d['city'],'',c);mid=market_id(c,code) if code else None
        bp=base_product_name(d['product_raw'] or '');prod=lookup_product(c,mid,bp) if mid else None
        product_id=rule_id=None;base_usd=base_mad=baseprice=localmad=candidate=paid=0.0;decision='NONE'
        parts=[x.strip() for x in str(d['status'] or '').split(',') if x.strip() and x.strip() not in ('OK','UNMAPPED COUNTRY','MISSING PRODUCT/RATE','MISSING COMMISSION PERIOD')]
        if not mid:parts.append('UNMAPPED COUNTRY')
        if prod:
            product_id=prod['id'];baseprice=float(prod['price_local'] or 0);localmad=float(prod['local_mad'] or 0);rule=commission_rule_for(c,product_id,d['delivery_date'])
            if rule:rule_id=rule['id'];base_usd,base_mad=apply_rule_amount(code,rule)
            else:parts.append('MISSING COMMISSION PERIOD')
            st=c.execute('select * from settings where period_id=?',(d['period_id'],)).fetchone();pct=float(st['upsell_africa']) if code in AFRICA_CODES else 0
            if pct>0 and baseprice>0 and float(d['price'] or 0)>baseprice:candidate=(float(d['price'])-baseprice)*pct*localmad
            if candidate>0 and code in AFRICA_CODES:
                old=(d['upsell_decision'] or '').upper();decision=old if old in ('APPROVED','REJECTED') else 'PENDING';paid=candidate if decision=='APPROVED' else 0.0
        elif mid:parts.append('MISSING PRODUCT/RATE')
        status='OK' if not parts else ', '.join(dict.fromkeys(parts))
        c.execute('update deliveries set market_id=?,product_id=?,commission_rule_id=?,base_commission_usd=?,base_commission_mad=?,base_price_local=?,local_mad=?,upsell_candidate_mad=?,upsell_mad=?,upsell_decision=?,status=? where id=?',(mid,product_id,rule_id,base_usd,base_mad,baseprice,localmad,candidate,paid,decision,status,d['id']));changed+=1
    c.commit();c.close();return changed

def african_upsell_stats(period_id,buyer_id=None):
    c=db();params=[period_id];where='d.period_id=? and m.grp="AFRICA" and d.upsell_candidate_mad>0'
    if buyer_id is not None:where+=' and d.buyer_id=?';params.append(buyer_id)
    r=c.execute(f'''select count(*) detected,
        sum(case when d.upsell_decision='PENDING' then 1 else 0 end) pending,
        sum(case when d.upsell_decision='APPROVED' then 1 else 0 end) approved,
        sum(case when d.upsell_decision='REJECTED' then 1 else 0 end) rejected,
        coalesce(sum(d.upsell_candidate_mad),0) potential_mad,
        coalesce(sum(case when d.upsell_decision='APPROVED' then d.upsell_candidate_mad else 0 end),0) approved_mad
        from deliveries d join markets m on m.id=d.market_id where {where}''',params).fetchone();c.close()
    return {k:(float(r[k] or 0) if k in ('potential_mad','approved_mad') else int(r[k] or 0)) for k in r.keys()}

def african_upsell_rows(period_id,decision='ALL',buyer_id=None):
    c=db();params=[period_id];where='d.period_id=? and m.grp="AFRICA" and d.upsell_candidate_mad>0'
    if decision and decision!='ALL':where+=' and d.upsell_decision=?';params.append(decision)
    if buyer_id is not None:where+=' and d.buyer_id=?';params.append(buyer_id)
    rs=c.execute(f'''select d.id,d.tracking_number,d.delivery_date,d.city,d.product_raw,d.price,d.base_price_local,d.local_mad,d.upsell_candidate_mad,d.upsell_mad,d.upsell_decision,b.name buyer,m.name market,m.code market_code
        from deliveries d join markets m on m.id=d.market_id left join buyers b on b.id=d.buyer_id where {where}
        order by case d.upsell_decision when 'PENDING' then 0 when 'APPROVED' then 1 else 2 end,d.delivery_date desc,d.id desc''',params).fetchall();c.close();return [dict(r) for r in rs]

def set_african_upsell_decision(period_id,delivery_ids,decision):
    decision=str(decision or '').upper()
    if decision not in ('APPROVED','REJECTED','PENDING'):raise ValueError('Invalid upsell decision')
    ids=[]
    for x in delivery_ids:
        try:ids.append(int(x))
        except:pass
    if not ids:return 0
    c=db();n=0;now=datetime.now().isoformat(timespec='seconds')
    for did in ids:
        d=c.execute('''select d.*,m.grp from deliveries d join markets m on m.id=d.market_id where d.id=? and d.period_id=?''',(did,period_id)).fetchone()
        if not d or d['grp']!='AFRICA' or float(d['upsell_candidate_mad'] or 0)<=0:continue
        paid=float(d['upsell_candidate_mad'] or 0) if decision=='APPROVED' else 0.0
        c.execute('update deliveries set upsell_decision=?,upsell_mad=?,upsell_decided_at=? where id=?',(decision,paid,now if decision!='PENDING' else None,did));n+=1
    c.commit();c.close();return n

def city_mappings():
    c=db();rs=c.execute('select cm.*,m.code market_code,m.name market_name from city_mappings cm join markets m on m.id=cm.market_id order by m.name,cm.city').fetchall();c.close();return [dict(r) for r in rs]

def find_buyer(c,raw):
    n=norm(raw)
    if not n or n=='manual':return None
    r=c.execute('select buyer_id from aliases where alias_norm=?',(n,)).fetchone()
    if r:return r['buyer_id']
    r=c.execute('select id from buyers where name_norm=?',(n,)).fetchone()
    if r:return r['id']
    best=None; score=0
    for b in c.execute('select id,name_norm from buyers'):
        s=difflib.SequenceMatcher(None,n,b['name_norm']).ratio()
        if s>score:best,score=b['id'],s
    if score>=.76:
        c.execute('insert or ignore into aliases(buyer_id,alias,alias_norm) values(?,?,?)',(best,str(raw).strip(),n)); return best
    return None

def ensure_period(year,month):
    label=f'{year}-{month:02d}'; c=db()
    existing=c.execute('select id from periods where label=?',(label,)).fetchone()
    if existing:
        c.execute('insert or ignore into settings(period_id) values(?)',(existing['id'],));c.commit();c.close();return existing['id']
    c.execute('insert into periods(label,year,month,created_at) values(?,?,?,?)',(label,year,month,datetime.now().isoformat(timespec='seconds')))
    pid=c.execute('select id from periods where label=?',(label,)).fetchone()['id']
    prev=c.execute('select s.* from periods p join settings s on s.period_id=p.id where (p.year<? or (p.year=? and p.month<?)) order by p.year desc,p.month desc limit 1',(year,year,month)).fetchone()
    if prev:
        c.execute('insert into settings(period_id,maroc_spend_mad,other_usd_mad,usdt_mad,upsell_maroc,upsell_africa,remise_pct) values(?,?,?,?,?,?,?)',(pid,prev['maroc_spend_mad'],prev['other_usd_mad'],prev['usdt_mad'],prev['upsell_maroc'],prev['upsell_africa'],prev['remise_pct']))
    else:c.execute('insert into settings(period_id) values(?)',(pid,))
    c.commit();c.close();return pid


def previous_period_id(period_id):
    c=db();p=c.execute('select year,month from periods where id=?',(period_id,)).fetchone()
    if not p:c.close();return None
    r=c.execute('select id from periods where (year<? or (year=? and month<?)) order by year desc,month desc limit 1',(p['year'],p['year'],p['month'])).fetchone();c.close()
    return r['id'] if r else None


def period_list():
    c=db();rs=c.execute('select * from periods order by year desc,month desc').fetchall();c.close();return [dict(r) for r in rs]


def import_global_product_offers(path):
    """Non-destructive all-market workbook import; never overwrite existing offers or history."""
    wb=load_workbook(path,read_only=True,data_only=True); ws=wb.active
    c=db(); added=0; offers_added=0; skipped=[]; touched=set()
    try:
        for line,row in enumerate(ws.iter_rows(min_row=2,values_only=True),2):
            if not row or not any(x is not None for x in row):continue
            if len(row)<5:skipped.append((line,'Missing columns'));continue
            name,country,comm,price,rate=row[:5]
            if not name or not country:skipped.append((line,'Missing product/market'));continue
            code=market_from_country_text(str(country))
            if not code:skipped.append((line,'Unknown market: '+str(country)));continue
            try:
                comm=float(comm);price=float(price);rate=float(rate or 0)
                if comm<0 or price<=0 or rate<0:raise ValueError()
            except (TypeError,ValueError):skipped.append((line,'Invalid price, commission or rate'));continue
            mid=market_id(c,code); n=norm(str(name).strip())
            existing=c.execute('select id from products where name_norm=? and market_id=?',(n,mid)).fetchone()
            if existing: product_id=existing['id']
            else:
                cu,cm=(0,comm) if code=='MAROC' else (comm,0)
                c.execute('insert into products(name,name_norm,market_id,commission_usd,commission_mad,price_local,local_mad) values(?,?,?,?,?,?,?)',(str(name).strip(),n,mid,cu,cm,price,rate))
                product_id=c.execute('select last_insert_rowid() id').fetchone()['id'];added+=1
                currency='MAD' if code=='MAROC' else 'USD'
                c.execute('insert into commission_rules(product_id,start_date,end_date,amount,currency,note,created_at) values(?,?,?,?,?,?,?)',(product_id,'1900-01-01',None,comm,currency,'Initial global workbook import',datetime.now().isoformat(timespec='seconds')))
            before=c.total_changes
            c.execute('insert or ignore into product_offers(product_id,price,commission,created_at) values(?,?,?,?)',(product_id,price,comm,datetime.now().isoformat(timespec='seconds')))
            if c.total_changes>before:offers_added+=1;touched.add(product_id)
        c.commit()
    except Exception:
        c.rollback();raise
    finally:c.close()
    return {'products_added':added,'offers_added':offers_added,'skipped':skipped,'affected_products':len(touched)}

def seed_products(path):
    """Import product master. Morocco commission values are native MAD; all other markets remain USD."""
    wb=load_workbook(path,read_only=True,data_only=True); ws=wb.active; c=db(); n=0
    for r in ws.iter_rows(min_row=2,values_only=True):
        prod,country,comm,price,rate=r[:5]
        if not prod or not country:continue
        code=market_from_country_text(country)
        if not code:continue
        mid=market_id(c,code); pn=norm(str(prod).strip())
        try:comm=float(comm or 0); price=float(price or 0); rate=float(rate or 0)
        except:continue
        comm_usd=0.0 if code=='MAROC' else comm; comm_mad=comm if code=='MAROC' else 0.0
        c.execute('insert into products(name,name_norm,market_id,commission_usd,commission_mad,price_local,local_mad) values(?,?,?,?,?,?,?) on conflict(name_norm,market_id) do update set commission_usd=excluded.commission_usd,commission_mad=excluded.commission_mad,price_local=excluded.price_local,local_mad=excluded.local_mad,name=excluded.name',(str(prod).strip(),pn,mid,comm_usd,comm_mad,price,rate))
        product_id=c.execute('select id from products where name_norm=? and market_id=?',(pn,mid)).fetchone()['id']
        rules=c.execute('select * from commission_rules where product_id=? order by start_date',(product_id,)).fetchall()
        currency='MAD' if code=='MAROC' else 'USD'
        if not rules:
            c.execute('insert into commission_rules(product_id,start_date,end_date,amount,currency,note,created_at) values(?,?,?,?,?,?,?)',(product_id,'1900-01-01',None,comm,currency,'Initial product master rate',datetime.now().isoformat(timespec='seconds')))
        elif len(rules)==1 and rules[0]['start_date']=='1900-01-01' and rules[0]['end_date'] is None:
            c.execute('update commission_rules set amount=?,currency=? where id=?',(comm,currency,rules[0]['id']))
        c.execute('insert or ignore into product_offers(product_id,price,commission,created_at) values(?,?,?,?)',(product_id,price,comm,datetime.now().isoformat(timespec='seconds')))
        n+=1
    c.commit();c.close();return n

def parse_product_lines(raw):
    lines=[x.strip() for x in str(raw or '').splitlines() if x.strip()]
    return [x for x in lines if not x.lower().startswith('-default at')]

def base_product_name(raw):
    ps=parse_product_lines(raw); return ps[0] if ps else ''

def lookup_product(c,mid,raw_name):
    n=norm(raw_name); r=c.execute('select * from products where market_id=? and name_norm=?',(mid,n)).fetchone()
    if r:return r
    # For single-line pack/x2 orders, use the single product as the base item if available.
    stripped=re.sub(r'\s*\(pack de \d+\)\s*',' ',raw_name,flags=re.I); stripped=re.sub(r'\s+x\s*\d+\s*$','',stripped,flags=re.I); sn=norm(stripped)
    if sn!=n:
        r=c.execute('select * from products where market_id=? and name_norm=?',(mid,sn)).fetchone()
        if r:return r
    return None

def parse_delivery_date(value):
    if isinstance(value,datetime):return value.date().isoformat()
    txt=str(value or '').strip()
    if not txt:return None
    try:return datetime.fromisoformat(txt.replace('Z','+00:00')).date().isoformat()
    except:pass
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%m/%d/%Y'):
        try:return datetime.strptime(txt[:10],fmt).date().isoformat()
        except:pass
    return None

def commission_rule_for(c,product_id,delivery_date):
    if not product_id or not delivery_date:return None
    return c.execute('''select * from commission_rules where product_id=? and start_date<=? and (end_date is null or end_date>=?) order by start_date desc limit 1''',(product_id,delivery_date,delivery_date)).fetchone()

def apply_rule_amount(code,rule):
    if not rule:return 0.0,0.0
    amount=float(rule['amount'] or 0)
    return (0.0,amount) if code=='MAROC' else (amount,0.0)

def recalculate_product_deliveries(product_id):
    c0=db();has_offers=c0.execute('select count(*) n from product_offers where product_id=?',(product_id,)).fetchone()['n'];c0.close()
    if has_offers:return recalculate_offers(product_id)
    c=db(); prod=c.execute('select p.*,m.code market_code from products p join markets m on m.id=p.market_id where p.id=?',(product_id,)).fetchone()
    if not prod:c.close();return 0
    changed=0
    for d in c.execute('select id,delivery_date,status from deliveries where product_id=?',(product_id,)).fetchall():
        rule=commission_rule_for(c,product_id,d['delivery_date']); usd,mad=apply_rule_amount(prod['market_code'],rule)
        parts=[x.strip() for x in str(d['status'] or '').split(',') if x.strip() and x.strip() not in ('OK','MISSING COMMISSION PERIOD')]
        if not rule:parts.append('MISSING COMMISSION PERIOD')
        status='OK' if not parts else ', '.join(parts)
        c.execute('update deliveries set base_commission_usd=?,base_commission_mad=?,commission_rule_id=?,status=? where id=?',(usd,mad,rule['id'] if rule else None,status,d['id']));changed+=1
    c.commit();c.close();return changed

def add_commission_rule(product_id,start_date,amount,end_date=None,note=''):
    start=parse_delivery_date(start_date); end=parse_delivery_date(end_date) if end_date else None
    if not start:raise ValueError('A valid start date is required')
    if end and end<start:raise ValueError('End date cannot be before start date')
    c=db(); prod=c.execute('select p.*,m.code market_code from products p join markets m on m.id=p.market_id where p.id=?',(product_id,)).fetchone()
    if not prod:c.close();raise ValueError('Product not found')
    currency='MAD' if prod['market_code']=='MAROC' else 'USD'; amount=float(amount or 0)
    next_rule=c.execute('select * from commission_rules where product_id=? and start_date>? order by start_date limit 1',(product_id,start)).fetchone()
    if next_rule:
        max_end=(datetime.fromisoformat(next_rule['start_date']).date()-timedelta(days=1)).isoformat()
        if end is None:end=max_end
        elif end>max_end:c.close();raise ValueError(f'End date overlaps the next commission period starting {next_rule["start_date"]}')
    existing=c.execute('select * from commission_rules where product_id=? and start_date=?',(product_id,start)).fetchone()
    if existing:
        c.execute('update commission_rules set end_date=?,amount=?,currency=?,note=? where id=?',(end,amount,currency,note,existing['id']))
    else:
        prev=c.execute('select * from commission_rules where product_id=? and start_date<? order by start_date desc limit 1',(product_id,start)).fetchone()
        if prev and (prev['end_date'] is None or prev['end_date']>=start):
            prev_end=(datetime.fromisoformat(start).date()-timedelta(days=1)).isoformat()
            c.execute('update commission_rules set end_date=? where id=?',(prev_end,prev['id']))
        c.execute('insert into commission_rules(product_id,start_date,end_date,amount,currency,note,created_at) values(?,?,?,?,?,?,?)',(product_id,start,end,amount,currency,note,datetime.now().isoformat(timespec='seconds')))
    # Keep the product master showing the latest effective commission for convenience.
    latest=c.execute('select amount,currency from commission_rules where product_id=? order by start_date desc limit 1',(product_id,)).fetchone()
    if latest:
        if latest['currency']=='MAD':c.execute('update products set commission_mad=?,commission_usd=0 where id=?',(latest['amount'],product_id))
        else:c.execute('update products set commission_usd=?,commission_mad=0 where id=?',(latest['amount'],product_id))
    c.commit();c.close();recalculate_product_deliveries(product_id)

def delete_commission_rule(rule_id):
    c=db(); r=c.execute('select * from commission_rules where id=?',(rule_id,)).fetchone()
    if not r:c.close();return
    pid=r['product_id']; count=c.execute('select count(*) cnt from commission_rules where product_id=?',(pid,)).fetchone()['cnt']
    if count<=1:c.close();raise ValueError('A product must keep at least one commission rule')
    prev=c.execute('select * from commission_rules where product_id=? and start_date<? order by start_date desc limit 1',(pid,r['start_date'])).fetchone()
    nxt=c.execute('select * from commission_rules where product_id=? and start_date>? order by start_date limit 1',(pid,r['start_date'])).fetchone()
    c.execute('delete from commission_rules where id=?',(rule_id,))
    if prev:
        repaired_end=(datetime.fromisoformat(nxt['start_date']).date()-timedelta(days=1)).isoformat() if nxt else None
        c.execute('update commission_rules set end_date=? where id=?',(repaired_end,prev['id']))
    c.commit();c.close();recalculate_product_deliveries(pid)

def offers_for(c,product_id):
    offers=c.execute('select * from product_offers where product_id=? order by price',(product_id,)).fetchall()
    if offers:return offers
    p=c.execute('select * from products where id=?',(product_id,)).fetchone()
    if not p:return []
    m=c.execute('select code from markets where id=?',(p['market_id'],)).fetchone()
    return [dict(id=None,price=p['price_local'],commission=p['commission_mad'] if m['code']=='MAROC' else p['commission_usd'])]

def match_offer(c,product_id,delivered_price,allow_remise=True):
    offers=offers_for(c,product_id)
    exact=[o for o in offers if abs(float(o['price'] or 0)-delivered_price)<0.005]
    if exact:return exact[0],False
    higher=[o for o in offers if float(o['price'] or 0)>delivered_price+0.005]
    if allow_remise and higher:return min(higher,key=lambda o:float(o['price'])),True
    return None,False

def order_is_multi(raw):
    lines=parse_product_lines(raw)
    if len(lines)>1:return True
    return bool(re.search(r'(?:\b(?:qty|quantity|quantit[eé])\s*[:x]?\s*[2-9]\b|\bx\s*[2-9]\b|\bpack\s+de\s+[2-9]\b)',str(raw),re.I))

def add_product_offer(product_id,price,commission,effective_date='',note=''):
    price=float(price);commission=float(commission)
    if price<=0 or commission<0:raise ValueError('Invalid price or commission')
    date=(effective_date or '').strip() or None
    if date:datetime.strptime(date,'%Y-%m-%d')
    c=db();c.execute('insert into product_offers(product_id,price,commission,effective_date,note,created_at) values(?,?,?,?,?,?) on conflict(product_id,price) do update set commission=excluded.commission,effective_date=excluded.effective_date,note=excluded.note',(product_id,price,commission,date,note,datetime.now().isoformat(timespec='seconds')));c.commit();c.close()
    recalculate_offers(product_id)

def recalculate_offers(product_id):
    c=db();ds=c.execute('select d.*,m.code market_code from deliveries d join markets m on m.id=d.market_id where d.product_id=?',(product_id,)).fetchall()
    for d in ds:
        multi=order_is_multi(d['product_raw']);offer,is_remise=match_offer(c,product_id,float(d['price'] or 0),not multi)
        code=d['market_code'];usd=mad=0
        if offer:usd,mad=(0,float(offer['commission'])) if code=='MAROC' else (float(offer['commission']),0)
        c.execute('update deliveries set base_commission_usd=?,base_commission_mad=?,base_price_local=?,commission_rule_id=NULL where id=?',(usd,mad,float(offer['price']) if offer else None,d['id']))
        if is_remise and offer and d['buyer_id']:
            p=c.execute('select local_mad from products where id=?',(product_id,)).fetchone();rate=float(p['local_mad'] or 0);gap=round(float(offer['price'])-float(d['price']),4)
            c.execute("""insert into remise_reviews(delivery_id,period_id,buyer_id,product_id,reference_price,delivered_price,gap_local,rate_mad,gap_mad,decision) values(?,?,?,?,?,?,?,?,?,'PENDING') on conflict(delivery_id) do update set reference_price=excluded.reference_price,delivered_price=excluded.delivered_price,gap_local=excluded.gap_local,rate_mad=excluded.rate_mad,gap_mad=excluded.gap_mad,decision=case when remise_reviews.reference_price=excluded.reference_price and remise_reviews.delivered_price=excluded.delivered_price and remise_reviews.rate_mad=excluded.rate_mad then remise_reviews.decision else 'PENDING' end""",(d['id'],d['period_id'],d['buyer_id'],product_id,float(offer['price']),float(d['price']),gap,rate,round(gap*rate,4)))
        else:c.execute('delete from remise_reviews where delivery_id=?',(d['id'],))
    c.commit();c.close()

def remise_rows(period_id):
    c=db();rows=c.execute("""select r.*,d.tracking_number,d.delivery_date,d.product_raw,b.name buyer,p.name product,m.code market from remise_reviews r join deliveries d on d.id=r.delivery_id join buyers b on b.id=r.buyer_id join products p on p.id=r.product_id join markets m on m.id=d.market_id where r.period_id=? order by r.decision desc,r.id desc""",(period_id,)).fetchall();c.close();return [dict(r) for r in rows]

def decide_remise(period_id,ids,decision):
    if decision not in ('APPROVED','REJECTED','PENDING'):raise ValueError('Invalid decision')
    c=db()
    for rid in ids:c.execute('update remise_reviews set decision=?,decided_at=? where id=? and period_id=?',(decision,datetime.now().isoformat(timespec='seconds'),int(rid),period_id))
    c.commit();c.close()

def import_deliveries(period_id,path,global_file=False):
    wb=load_workbook(path,read_only=True,data_only=True);ws=wb.active;it=ws.iter_rows(values_only=True); hdr=[str(x or '').strip() for x in next(it)];ix={h:i for i,h in enumerate(hdr)};c=db();src='GLOBAL' if global_file else 'MAROC'
    previous={}
    if global_file:
        for old in c.execute("select tracking_number,upsell_decision from deliveries where period_id=? and source='GLOBAL' and upsell_decision in ('APPROVED','REJECTED')",(period_id,)):
            if old['tracking_number']:previous[norm(old['tracking_number'])]=old['upsell_decision']
    old_remises={norm(r['tracking_number']):r['decision'] for r in c.execute('select d.tracking_number,r.decision from remise_reviews r join deliveries d on d.id=r.delivery_id where r.period_id=?',(period_id,)) if r['tracking_number']}
    c.execute('delete from remise_reviews where period_id=?',(period_id,));c.execute('delete from deliveries where period_id=? and source=?',(period_id,src)); settings=c.execute('select * from settings where period_id=?',(period_id,)).fetchone();n=w=0
    for rn,r in enumerate(it,2):
        if str(r[ix.get('Delivery',-1)] or '').strip().lower()!='delivered':continue
        delivery_date=parse_delivery_date(r[ix.get('Date',2)] if 'Date' in ix else None)
        rawbuyer=r[ix.get('Sales Channel',3)];tracking=str(r[ix.get('Tracking Number',4)] or '') if 'Tracking Number' in ix else '';bid=find_buyer(c,rawbuyer);city=r[ix.get('City',13)] if 'City' in ix else '';dm=r[ix.get('Delivery Man',17)] if 'Delivery Man' in ix else '';code=market_from_city(city,dm,c) if global_file else 'MAROC';mid=market_id(c,code) if code else None; rawprod=str(r[ix.get('Products',6)] or '');bp=base_product_name(rawprod); prod=lookup_product(c,mid,bp) if mid else None
        is_remise=False;price=float(r[ix.get('Price',7)] or 0); paid=0.0;candidate=0.0;decision='NONE'; base_usd=base_mad=baseprice=localmad=0.0; rule_id=None; product_id=None; status=[]
        if not delivery_date:status.append('MISSING DELIVERY DATE')
        if not bid:status.append('UNMATCHED BUYER')
        if not mid:status.append('UNMAPPED COUNTRY')
        if prod:
            product_id=prod['id'];baseprice=float(prod['price_local'] or 0);localmad=float(prod['local_mad'] or 0)
            multi=order_is_multi(rawprod);offer,is_remise=match_offer(c,product_id,price,not multi)
            if offer:baseprice=float(offer['price']);base_usd,base_mad=(0,float(offer['commission'])) if code=='MAROC' else (float(offer['commission']),0)
            else:status.append('UNMATCHED OFFER PRICE')
            if code=='MAROC':
                pct=float(settings['upsell_maroc'])
                if multi and pct>0 and baseprice>0 and price>baseprice:candidate=(price-baseprice)*pct*localmad
                paid=candidate;decision='AUTO' if candidate>0 else 'NONE'
            elif code in AFRICA_CODES:
                pct=float(settings['upsell_africa'])
                if multi and pct>0 and baseprice>0 and price>baseprice:candidate=(price-baseprice)*pct*localmad
                if candidate>0:
                    decision=previous.get(norm(tracking),'PENDING');paid=candidate if decision=='APPROVED' else 0.0
            else:
                candidate=paid=0.0;decision='NONE'
        else:status.append('MISSING PRODUCT/RATE')
        c.execute('insert into deliveries(period_id,source,source_row,order_id,tracking_number,delivery_date,buyer_id,buyer_raw,market_id,city,product_id,commission_rule_id,product_raw,product_norm,price,base_commission_usd,base_commission_mad,base_price_local,local_mad,upsell_candidate_mad,upsell_mad,upsell_decision,status) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(period_id,src,rn,str(r[ix.get('Id',0)] or ''),tracking,delivery_date,bid,str(rawbuyer or ''),mid,str(city or ''),product_id,rule_id,rawprod,norm(bp),price,base_usd,base_mad,baseprice,localmad,candidate,paid,decision,'OK' if not status else ', '.join(status)));
        if prod and not order_is_multi(rawprod) and is_remise and bid:
            gap=round(baseprice-price,4);gap_mad=round(gap*localmad,4);rid=c.execute('select last_insert_rowid() id').fetchone()['id'];c.execute('insert into remise_reviews(delivery_id,period_id,buyer_id,product_id,reference_price,delivered_price,gap_local,rate_mad,gap_mad,decision) values(?,?,?,?,?,?,?,?,?,?)',(rid,period_id,bid,product_id,baseprice,price,gap,localmad,gap_mad,old_remises.get(norm(tracking),'PENDING')))
        n+=1;w+=1 if status else 0
    c.execute('insert into imports(period_id,kind,filename,rows_imported,warnings,created_at) values(?,?,?,?,?,?)',(period_id,'DELIVERIES_'+src,Path(path).name,n,w,datetime.now().isoformat(timespec='seconds')));c.commit();c.close();return n,w

def import_spend(period_id,path,code):
    wb=load_workbook(path,read_only=True,data_only=True);ws=wb.active;it=ws.iter_rows(values_only=True);hdr=[str(x or '').strip() for x in next(it)];ix={h:i for i,h in enumerate(hdr)};c=db();mid=market_id(c,code);c.execute('delete from spend where period_id=? and market_id=?',(period_id,mid));n=w=0
    def num(r,k):
        try:return float(r[ix[k]] or 0) if k in ix else 0
        except:return 0
    for rn,r in enumerate(it,2):
        raw=r[ix.get('Affiliate',0)]
        if not raw:continue
        bid=find_buyer(c,raw); c.execute('insert into spend(period_id,market_id,buyer_id,buyer_raw,spend_usd,leads,deliveries_source,filename,source_row) values(?,?,?,?,?,?,?,?,?)',(period_id,mid,bid,str(raw),num(r,'Spend'),num(r,'Leads'),num(r,'Deliveries'),Path(path).name,rn));n+=1;w+=0 if bid else 1
    c.execute('insert into imports(period_id,kind,market_code,filename,rows_imported,warnings,created_at) values(?,?,?,?,?,?,?)',(period_id,'SPEND',code,Path(path).name,n,w,datetime.now().isoformat(timespec='seconds')));c.commit();c.close();return n,w

def bonus_for(delivs,grp,settings):
    if grp=='AFRICA':
        usd=1000 if delivs>=1000 else 500 if delivs>=700 else 250 if delivs>=600 else 150 if delivs>=500 else 0
        return usd*float(settings['other_usd_mad']), f'${usd:,.0f}' if usd else '—'
    if grp=='MOROCCO':
        mad=10000 if delivs>=2000 else 6000 if delivs>=1500 else 3500 if delivs>=1000 else 1500 if delivs>=500 else 0
        return mad, f'{mad:,.0f} MAD' if mad else '—'
    return 0,'—'

def buyer_calc(period_id,buyer_id,include_history=True):
    c=db();s=c.execute('select * from settings where period_id=?',(period_id,)).fetchone();b=c.execute('select * from buyers where id=?',(buyer_id,)).fetchone(); rows=[]; total_base_usd=total_base_mad=total_upsell=total_spend=total_spend_mad=0; total_del=0; africa_del=morocco_del=0
    for m in c.execute('select * from markets order by case code when "MAROC" then 0 else 1 end,name'):
        d=c.execute('select count(*) cnt,coalesce(sum(base_commission_usd),0) base_usd,coalesce(sum(base_commission_mad),0) base_native_mad,coalesce(sum(upsell_mad),0) ups from deliveries where period_id=? and buyer_id=? and market_id=?',(period_id,buyer_id,m['id'])).fetchone();sp=c.execute('select coalesce(sum(spend_usd),0) spend from spend where period_id=? and buyer_id=? and market_id=?',(period_id,buyer_id,m['id'])).fetchone()['spend']; cnt=d['cnt']; base_usd=float(d['base_usd']); native_mad=float(d['base_native_mad']); ups=float(d['ups'])
        if m['code']=='MAROC':
            base_mad=native_mad; spend_rate=float(s['maroc_spend_mad']); commission_currency='MAD'; native_commission=native_mad
        else:
            base_mad=base_usd*float(s['other_usd_mad']); spend_rate=float(s['other_usd_mad']); commission_currency='USD'; native_commission=base_usd
        spend_mad=float(sp)*spend_rate; gross=base_mad+ups; profit=gross-spend_mad
        if cnt or sp: rows.append(dict(market=m['name'],code=m['code'],grp=m['grp'],deliveries=cnt,base_usd=base_usd,base_native_mad=native_mad,base_native=native_commission,commission_currency=commission_currency,base_mad=base_mad,upsell_mad=ups,gross_mad=gross,spend_usd=float(sp),spend_mad=spend_mad,profit_mad=profit,cpd=float(sp)/cnt if cnt else 0))
        total_del+=cnt;total_base_usd+=base_usd;total_base_mad+=base_mad;total_upsell+=ups;total_spend+=float(sp);total_spend_mad+=spend_mad
        if m['grp']=='AFRICA':africa_del+=cnt
        if m['code']=='MAROC':morocco_del+=cnt
    mba,lab_a=bonus_for(africa_del,'AFRICA',s); mbm,lab_m=bonus_for(morocco_del,'MOROCCO',s);bonus=mba+mbm
    a=c.execute('select * from adjustments where period_id=? and buyer_id=?',(period_id,buyer_id)).fetchone(); a=dict(a) if a else dict(usdt_sent=0,charges=0,test_spend=0,wallet_rest=0,remise_mad=0,credit_mad=0,note='')
    usdt_ded_mad=float(a['usdt_sent'])*float(s['usdt_mad']); approved_remise=float(c.execute("select coalesce(sum(gap_mad),0) val from remise_reviews where period_id=? and buyer_id=? and decision='APPROVED'",(period_id,buyer_id)).fetchone()['val']);remise_ded=(float(a['remise_mad'])+approved_remise)*float(s['remise_pct']);a['approved_remise_mad']=approved_remise
    manual_credit=float(a.get('credit_mad',0) or 0)
    auto_credit=0.0
    if include_history:
        prev_id=previous_period_id(period_id)
        if prev_id:
            prev_calc=buyer_calc(prev_id,buyer_id,True)
            auto_credit=max(0.0,-float(prev_calc['final']))
    credit_ded=manual_credit+auto_credit
    gross=total_base_mad+total_upsell; final=gross-usdt_ded_mad+bonus-remise_ded-credit_ded; diff=float(a['usdt_sent'])-total_spend; recon_target=float(a['charges'])+float(a['test_spend'])+float(a['wallet_rest']); recon_gap=diff-recon_target
    prodrows=c.execute("""select m.name market,m.code market_code,substr(d.product_raw,1,instr(d.product_raw||char(10),char(10))-1) product,count(*) deliveries,sum(case when d.upsell_mad>0 then 1 else 0 end) upsell_orders,sum(d.base_commission_usd) base_usd,sum(d.base_commission_mad) base_native_mad,sum(d.upsell_mad) upsell_mad from deliveries d join markets m on m.id=d.market_id where d.period_id=? and d.buyer_id=? group by d.market_id,d.product_norm order by m.name,deliveries desc""",(period_id,buyer_id)).fetchall()
    products=[]
    for pr in prodrows:
        q=dict(pr);q['base_generated_mad']=float(q['base_native_mad'] or 0) if q['market_code']=='MAROC' else float(q['base_usd'] or 0)*float(s['other_usd_mad']);products.append(q)
    upsell_orders=c.execute('select count(*) cnt from deliveries where period_id=? and buyer_id=? and upsell_mad>0',(period_id,buyer_id)).fetchone()['cnt'];c.close();af_ups=african_upsell_stats(period_id,buyer_id)
    operating_profit=gross-total_spend_mad
    return dict(buyer=dict(b),rows=rows,products=products,deliveries=total_del,morocco_del=morocco_del,africa_del=africa_del,base_usd=total_base_usd,base_mad=total_base_mad,upsell=total_upsell,upsell_orders=upsell_orders,upsell_share=(total_upsell/gross*100 if gross else 0),gross=gross,spend_usd=total_spend,spend_mad=total_spend_mad,operating_profit=operating_profit,net_profit=operating_profit,profit_margin=(operating_profit/gross*100 if gross else 0),bonus=bonus,bonus_africa=mba,bonus_maroc=mbm,bonus_africa_label=lab_a,bonus_maroc_label=lab_m,adj=a,deductible_usdt=float(a['usdt_sent']),deductible_mad=usdt_ded_mad,remise_ded=remise_ded,manual_credit=manual_credit,auto_credit=auto_credit,credit_ded=credit_ded,final=final,carry_forward=max(0.0,-final),recon_gap=recon_gap,settings=dict(s),african_upsells=af_ups)

def negative_streak(period_id,buyer_id):
    c=db();p=c.execute('select year,month from periods where id=?',(period_id,)).fetchone()
    if not p:c.close();return 0,[]
    periods=c.execute('select id,label from periods where (year<? or (year=? and month<=?)) order by year desc,month desc',(p['year'],p['year'],p['month'])).fetchall();c.close()
    streak=0;history=[]
    for pr in periods:
        x=buyer_calc(pr['id'],buyer_id,True);neg=float(x['final'])<0
        history.append({'period_id':pr['id'],'label':pr['label'],'final':float(x['final']),'negative':neg})
        if neg:streak+=1
        else:break
    return streak,history


def buyer_history(period_id,buyer_id):
    c=db();p=c.execute('select year,month from periods where id=?',(period_id,)).fetchone()
    if not p:c.close();return []
    periods=c.execute('select id,label from periods where (year<? or (year=? and month<=?)) order by year,month',(p['year'],p['year'],p['month'])).fetchall();c.close()
    out=[]
    for pr in periods:
        x=buyer_calc(pr['id'],buyer_id,True);out.append({'period_id':pr['id'],'label':pr['label'],'final':float(x['final']),'carry_forward':max(0.0,-float(x['final']))})
    return out


def set_buyer_team_status(buyer_id,leave=True,reason=''):
    c=db()
    if leave:
        c.execute('update buyers set status=?,left_at=?,leave_reason=? where id=?',('LEFT TEAM',datetime.now().isoformat(timespec='seconds'),str(reason or '').strip(),buyer_id))
    else:
        c.execute('update buyers set status=?,left_at=null,leave_reason=null where id=?',('CURRENT',buyer_id))
    c.commit();c.close()


def period_summary(period_id):
    c=db(); buyers=c.execute('select id from buyers order by case status when "CURRENT" then 0 else 1 end,name').fetchall(); c.close(); return [buyer_calc(period_id,b['id']) for b in buyers]

def review(period_id):
    c=db(); ub=c.execute('select source,buyer_raw,count(*) cnt from deliveries where period_id=? and buyer_id is null group by source,buyer_raw order by cnt desc',(period_id,)).fetchall(); uc=c.execute('select city,count(*) cnt from deliveries where period_id=? and market_id is null group by city order by cnt desc',(period_id,)).fetchall(); mp=c.execute('select product_raw,count(*) cnt from deliveries where period_id=? and (status like "%MISSING PRODUCT%" or status like "%MISSING COMMISSION PERIOD%") group by product_norm order by cnt desc',(period_id,)).fetchall(); c.close(); return [dict(x) for x in ub],[dict(x) for x in uc],[dict(x) for x in mp]

def seed_all():
    init_db(True); seed_products(BASE/'seed'/'products.xlsx'); pid=ensure_period(2026,7);import_deliveries(pid,BASE/'seed'/'deliveries_maroc.xlsx',False);import_deliveries(pid,BASE/'seed'/'deliveries_global.xlsx',True)
    for code,_,_ in MARKETS:
        p=BASE/'seed'/f'spend_{code}.xlsx'
        if p.exists():import_spend(pid,p,code)
    return pid

def save_adjustments(pid,form):
    c=db()
    for b in c.execute('select id from buyers'):
        def f(k):
            try:return float(form.get(f'{k}_{b["id"]}','0') or 0)
            except:return 0
        c.execute('insert into adjustments(period_id,buyer_id,usdt_sent,charges,test_spend,wallet_rest,remise_mad,credit_mad,note) values(?,?,?,?,?,?,?,?,?) on conflict(period_id,buyer_id) do update set usdt_sent=excluded.usdt_sent,charges=excluded.charges,test_spend=excluded.test_spend,wallet_rest=excluded.wallet_rest,remise_mad=excluded.remise_mad,credit_mad=excluded.credit_mad,note=excluded.note',(pid,b['id'],f('usdt'),f('charges'),f('test'),f('rest'),f('remise'),f('credit'),form.get(f'note_{b["id"]}','')))
    c.commit();c.close()

def export_summary(pid,path):
    data=period_summary(pid);wb=Workbook();ws=wb.active;ws.title='Commission Summary';headers=['Media Buyer','Status','Deliveries','Morocco DLV','Africa DLV','Generated Commission MAD','Upsell MAD','Bonus MAD','System Spend USD','Operating Net Profit MAD','USDT Sent','USDT Deduction MAD','Remise Input MAD','80% Remise Deduction MAD','Manual Credit MAD','Auto Credit from Previous Month MAD','Total Credit Deduction MAD','Final Payout MAD','Carry Forward Credit MAD'];ws.append(headers)
    for x in data:ws.append([x['buyer']['name'],x['buyer']['status'],x['deliveries'],x['morocco_del'],x['africa_del'],x['gross'],x['upsell'],x['bonus'],x['spend_usd'],x['operating_profit'],x['adj']['usdt_sent'],x['deductible_mad'],x['adj']['remise_mad'],x['remise_ded'],x['manual_credit'],x['auto_credit'],x['credit_ded'],x['final'],x['carry_forward']])
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    for col in ws.columns:ws.column_dimensions[col[0].column_letter].width=min(30,max(12,max(len(str(c.value or '')) for c in col)+2))
    up=wb.create_sheet('African Upsells Review');up.append(['Tracking Number','Delivery Date','Media Buyer','Market','City','First Product','Order Total','Base Price','Potential Upsell MAD','Decision','Paid Upsell MAD'])
    for r in african_upsell_rows(pid,'ALL'):
        up.append([r['tracking_number'],r['delivery_date'],r['buyer'],r['market'],r['city'],base_product_name(r['product_raw'] or ''),r['price'],r['base_price_local'],r['upsell_candidate_mad'],r['upsell_decision'],r['upsell_mad']])
    up.freeze_panes='A2';up.auto_filter.ref=up.dimensions
    for col in up.columns:up.column_dimensions[col[0].column_letter].width=min(34,max(12,max(len(str(c.value or '')) for c in col)+2))
    wb.save(path)


def add_buyer(name,status="CURRENT",aliases=None):
    name=str(name or '').strip()
    if not name: raise ValueError('Media buyer name is required')
    c=db(); nn=norm(name)
    c.execute('insert into buyers(name,name_norm,status) values(?,?,?) on conflict(name_norm) do update set name=excluded.name,status=excluded.status',(name,nn,status))
    bid=c.execute('select id from buyers where name_norm=?',(nn,)).fetchone()['id']
    for alias in aliases or []:
        alias=str(alias or '').strip()
        if alias:c.execute('insert or ignore into aliases(buyer_id,alias,alias_norm) values(?,?,?)',(bid,alias,norm(alias)))
    c.commit();c.close();return bid

def add_product(name,market_code,commission_value,price_local,local_mad):
    name=str(name or '').strip()
    if not name: raise ValueError('Product name is required')
    c=db();mid=market_id(c,market_code)
    if not mid:
        c.close();raise ValueError('Unknown market')
    commission=float(commission_value or 0);comm_usd=0 if market_code=='MAROC' else commission;comm_mad=commission if market_code=='MAROC' else 0
    c.execute('insert into products(name,name_norm,market_id,commission_usd,commission_mad,price_local,local_mad) values(?,?,?,?,?,?,?) on conflict(name_norm,market_id) do update set name=excluded.name,commission_usd=excluded.commission_usd,commission_mad=excluded.commission_mad,price_local=excluded.price_local,local_mad=excluded.local_mad',(name,norm(name),mid,comm_usd,comm_mad,float(price_local or 0),float(local_mad or 0)))
    product_id=c.execute('select id from products where name_norm=? and market_id=?',(norm(name),mid)).fetchone()['id']
    rules=c.execute('select * from commission_rules where product_id=? order by start_date',(product_id,)).fetchall();currency='MAD' if market_code=='MAROC' else 'USD'
    if not rules:
        c.execute('insert into commission_rules(product_id,start_date,end_date,amount,currency,note,created_at) values(?,?,?,?,?,?,?)',(product_id,'1900-01-01',None,commission,currency,'Initial product rate',datetime.now().isoformat(timespec='seconds')))
    elif len(rules)==1 and rules[0]['start_date']=='1900-01-01' and rules[0]['end_date'] is None:
        c.execute('update commission_rules set amount=?,currency=? where id=?',(commission,currency,rules[0]['id']))
    c.commit();c.close();recalculate_product_deliveries(product_id)


def update_product_conversion(product_id,rate):
    rate=float(rate)
    if rate<=0:raise ValueError('Conversion must be positive')
    c=db();c.execute('update products set local_mad=? where id=?',(rate,product_id));c.commit();c.close();recalculate_offers(product_id)
