import argparse, getpass
from app import init_db,db,norm
from server import hp
p=argparse.ArgumentParser(description='YOUSSEF.COM user manager')
p.add_argument('--email',required=True);p.add_argument('--name',required=True);p.add_argument('--role',choices=['ADMIN','MANAGER','MEDIA_BUYER_VIEWER'],required=True);p.add_argument('--buyer',default='');p.add_argument('--password',default='')
a=p.parse_args(); init_db(); password=a.password or getpass.getpass('Password: ')
c=db();bid=None
if a.role=='MEDIA_BUYER_VIEWER':
 r=c.execute('select id from buyers where name_norm=?',(norm(a.buyer),)).fetchone()
 if not r:raise SystemExit('Viewer requires --buyer with an existing media buyer name')
 bid=r['id']
c.execute('insert into users(email,name,password_hash,role,buyer_id,status,created_at) values(?,?,?,?,?,"ACTIVE",datetime("now")) on conflict(email) do update set name=excluded.name,password_hash=excluded.password_hash,role=excluded.role,buyer_id=excluded.buyer_id,status="ACTIVE"',(a.email.lower(),a.name,hp(password),a.role,bid));c.commit();c.close();print('User saved:',a.email,a.role)
