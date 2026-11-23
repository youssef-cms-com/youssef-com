"""Test month-only reset with master data preservation and private SQLite backup."""
import os
import sqlite3
import tempfile
from pathlib import Path

tmp=tempfile.TemporaryDirectory()
os.environ["DATA_DIR"]=tmp.name
os.environ["DB_PATH"]=str(Path(tmp.name)/"month-reset.sqlite3")
os.environ["UPLOAD_DIR"]=str(Path(tmp.name)/"uploads")

import app
import server

app.init_db()
old=app.ensure_period(2026,8)
month=app.ensure_period(2026,9)
c=app.db()
market=app.market_id(c,"GABON")
buyer=c.execute("select id from buyers limit 1").fetchone()["id"]
c.execute("insert into products(name,name_norm,market_id,commission_usd,price_local,local_mad) values(?,?,?,?,?,?)",
    ("Reset Test Product",app.norm("Reset Test Product"),market,13,22000,.015))
product=c.execute("select last_insert_rowid() id").fetchone()["id"]
c.execute("insert into product_offers(product_id,price,commission) values(?,?,?)",(product,22000,13))
c.execute("insert into commission_rules(product_id,start_date,amount,currency) values(?,'1900-01-01',13,'USD')",(product,))
c.execute("insert into adjustments(period_id,buyer_id,usdt_sent) values(?,?,?)",(month,buyer,42))
for per,tracking in ((month,"R-SEP"),(old,"R-AUG")):
    c.execute("""insert into deliveries(period_id,source,tracking_number,buyer_id,market_id,
        city,product_id,product_raw,product_norm,price,base_commission_usd,status)
        values(?,'GLOBAL',?,?,?,?,?,?,?,?,?,'OK')""",
        (per,tracking,buyer,market,"Expédition",product,"Reset Test Product",
         app.norm("Reset Test Product"),22000,13))
    delivery=c.execute("select last_insert_rowid() id").fetchone()["id"]
    c.execute("insert into spend(period_id,buyer_id,market_id,spend_usd) values(?,?,?,?)",
              (per,buyer,market,100))
    c.execute("insert into remise_reviews(delivery_id,period_id,buyer_id,product_id,decision) values(?,?,?,?,'PENDING')",
              (delivery,per,buyer,product))
    c.execute("insert into delivery_market_overrides(period_id,source,tracking_key,market_id) values(?,'GLOBAL',?,?)",
              (per,app.norm(tracking),market))
    c.execute("insert into imports(period_id,kind,filename) values(?,'DELIVERIES_GLOBAL','deliveries.xlsx')",(per,))
    c.execute("insert into imports(period_id,kind,filename) values(?,'SPEND','spend.xlsx')",(per,))
c.execute("insert into imports(period_id,kind,filename) values(?,'PRODUCTS','products.xlsx')",(month,))
c.commit();c.close()
original=app.month_reset_counts(month)
assert original["deliveries"]==1 and original["spend"]==1
try:
    app.reset_month_delivery_spend_data(month,"2026-08",actor_id=buyer)
    raise AssertionError("Reset accepted incorrect typed month")
except ValueError:
    pass
assert app.month_reset_counts(month)==original
result=app.reset_month_delivery_spend_data(month,"2026-09",actor_id=buyer)
assert result["backup_created"] is True
assert result["deliveries"]==1 and result["spend"]==1
assert all(v==0 for v in app.month_reset_counts(month).values())
assert app.month_reset_counts(old)["deliveries"]==1
assert app.month_reset_counts(old)["spend"]==1
c=app.db()
assert c.execute("select count(*) n from products where id=?",(product,)).fetchone()["n"]==1
assert c.execute("select commission_usd from products where id=?",(product,)).fetchone()[0]==13
assert c.execute("select commission from product_offers where product_id=?",(product,)).fetchone()[0]==13
assert c.execute("select amount from commission_rules where product_id=?",(product,)).fetchone()[0]==13
assert c.execute("select usdt_sent from adjustments where period_id=?",(month,)).fetchone()[0]==42
assert c.execute("select count(*) n from imports where period_id=? and kind='PRODUCTS'",(month,)).fetchone()["n"]==1
assert c.execute("select count(*) n from remise_reviews where period_id=?",(old,)).fetchone()["n"]==1
audit=c.execute("select * from month_reset_audit where period_id=?",(month,)).fetchone()
assert audit and Path(audit["backup_path"]).exists()
with sqlite3.connect(audit["backup_path"]) as backed:
    assert backed.execute("select count(*) from deliveries where period_id=?",(month,)).fetchone()[0]==1
    assert backed.execute("select count(*) from spend where period_id=?",(month,)).fetchone()[0]==1
c.close()
# Admin-only reset panel. Do not show it to a viewer.
token=server.REQUEST_USER.set({"role":"ADMIN","name":"Administrator"})
html=server.imports_page(month).decode()
assert "Reset Month Data" in html and "Reset selected month" in html
server.REQUEST_USER.reset(token)
token=server.REQUEST_USER.set({"role":"MANAGER","name":"Manager"})
html=server.imports_page(month).decode()
assert "Reset selected month" not in html
server.REQUEST_USER.reset(token)
print("PASS: reset backed up, scoped to month/imports, products/offers/adjustments preserved, admin-only UI")
tmp.cleanup()
