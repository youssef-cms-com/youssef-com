"""Regression: assigned Expedition rows leave Review Center but remain in deliveries."""
import os
import tempfile
from pathlib import Path

tmp=tempfile.TemporaryDirectory()
os.environ["DATA_DIR"]=tmp.name
os.environ["DB_PATH"]=str(Path(tmp.name)/"test.sqlite3")
os.environ["UPLOAD_DIR"]=str(Path(tmp.name)/"uploads")

import app
import server

app.init_db()
period=app.ensure_period(2026,9)
c=app.db()
gabon=app.market_id(c,"GABON")
buyer=c.execute("select id from buyers limit 1").fetchone()["id"]
c.execute("""insert into products(name,name_norm,market_id,commission_usd,price_local,local_mad)
values(?,?,?,?,?,?)""",("Test Speaker",app.norm("Test Speaker"),gabon,12,22000,.015))
product=c.execute("select last_insert_rowid() id").fetchone()["id"]
c.execute("insert into product_offers(product_id,price,commission) values(?,?,?)",(product,22000,12))
for tracking in ("EXP-ASSIGN-1","EXP-PENDING-2"):
    c.execute("""insert into deliveries(period_id,source,tracking_number,delivery_date,
    buyer_id,buyer_raw,market_id,city,product_raw,product_norm,price,status)
    values(?,?,?,?,?,?,?,?,?,?,?,?)""",
    (period,"GLOBAL",tracking,"2026-09-10",buyer,"Test Buyer",None,
    "Expédition","Test Speaker",app.norm("Test Speaker"),22000,"UNMAPPED COUNTRY"))
c.commit()
one=c.execute("select id from deliveries where tracking_number='EXP-ASSIGN-1'").fetchone()["id"]
c.close()
assert len(app.expedition_review_rows(period))==2
app.assign_delivery_country(period,one,"GABON")
rows=app.expedition_review_rows(period)
assert len(rows)==1 and rows[0]["tracking_number"]=="EXP-PENDING-2",rows
c=app.db()
d=c.execute("select * from deliveries where id=?",(one,)).fetchone()
assert d["market_id"]==gabon
assert d["buyer_id"]==buyer
assert d["product_id"]==product
assert d["base_commission_usd"]==12
assert c.execute("select count(*) n from delivery_market_overrides where tracking_key=?",(app.norm("EXP-ASSIGN-1"),)).fetchone()["n"]==1
c.close()
page=server.review_page(period).decode("utf-8")
assert "1 pending" in page,page[-1000:]
assert "EXP-PENDING-2" in page
assert "EXP-ASSIGN-1" not in page
app.sync_review_center()
assert len(app.expedition_review_rows(period))==1
print("PASS: pending-only review, assignment saved, order and commission retained, repeated sync")
tmp.cleanup()
