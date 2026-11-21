import os
import tempfile
from pathlib import Path

temp = tempfile.TemporaryDirectory()
os.environ["DATA_DIR"] = temp.name
os.environ["DB_PATH"] = str(Path(temp.name) / "review-add.sqlite3")
os.environ["UPLOAD_DIR"] = str(Path(temp.name) / "uploads")

import app
import server

app.init_db()
pid = app.ensure_period(2026,9)
c = app.db()
rdc = app.market_id(c,"RDC")
gabon = app.market_id(c,"GABON")
buyer = c.execute("select id from buyers limit 1").fetchone()["id"]
c.execute("""insert into deliveries(period_id,source,tracking_number,delivery_date,
 buyer_id,buyer_raw,market_id,product_raw,product_norm,price,status)
 values(?,?,?,?,?,?,?,?,?,?,?)""",
 (pid,"GLOBAL","MISSING-A","2026-09-10",buyer,"Sample",rdc,
 "Test Product",app.norm("Test Product"),35,"MISSING PRODUCT/RATE"))
a = c.execute("select last_insert_rowid() id").fetchone()["id"]
c.execute("""insert into deliveries(period_id,source,tracking_number,delivery_date,
 buyer_id,buyer_raw,market_id,product_raw,product_norm,price,status)
 values(?,?,?,?,?,?,?,?,?,?,?)""",
 (pid,"GLOBAL","MISSING-B","2026-09-10",buyer,"Sample",rdc,
 "Test Product",app.norm("Test Product"),35,"MISSING PRODUCT/RATE"))
c.execute("""insert into deliveries(period_id,source,tracking_number,delivery_date,
 buyer_id,buyer_raw,market_id,product_raw,product_norm,price,status)
 values(?,?,?,?,?,?,?,?,?,?,?)""",
 (pid,"GLOBAL","MISSING-MULTI","2026-09-10",buyer,"Sample",gabon,
 "Item X\nItem Y",app.norm("Item X"),22000,"MISSING PRODUCT/RATE"))
c.commit()
c.close()
rows=app.missing_product_offer_rows(pid)
assert any(r["name"]=="Test Product" and r["count"]==2 and r["market_code"]=="RDC" and r["price"]==35 for r in rows),rows
page=server.review_page(pid)
assert "Add product" in page and "Save &amp; auto-sync" in page
try:
    app.add_missing_product_offer(pid,"RDC","Test Product",33,11)
    raise AssertionError("Unobserved price was accepted")
except ValueError:
    pass
result=app.add_missing_product_offer(pid,"RDC","Test Product",35,12)
assert result["product_id"]>0
c=app.db()
row=c.execute("select * from deliveries where id=?",(a,)).fetchone()
assert row["product_id"]==result["product_id"],row
assert row["base_commission_usd"]==12,row
product=c.execute("select * from products where id=?",(result["product_id"],)).fetchone()
assert product["price_local"]==35
assert product["commission_usd"]==12
c.close()
rows2=app.missing_product_offer_rows(pid)
assert not any(r["name"]=="Test Product" and r["market_code"]=="RDC" for r in rows2), rows2
assert any(not r["single_product"] for r in rows2),rows2
print("PASS: country-specific missing product creation, commission link, grouped counts, and multi-product review")
temp.cleanup()
