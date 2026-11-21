import os
import tempfile
from pathlib import Path

root = tempfile.TemporaryDirectory()
os.environ["DATA_DIR"] = root.name
os.environ["DB_PATH"] = str(Path(root.name) / "review-test.sqlite3")
os.environ["UPLOAD_DIR"] = str(Path(root.name) / "uploads")

import app

app.init_db()
period = app.ensure_period(2026, 9)
c = app.db()
gabon = app.market_id(c, "GABON")
buyer = c.execute("select id from buyers where name=?", ("Mohammed Oujghi",)).fetchone()["id"]
c.execute("insert into products(name,name_norm,market_id,commission_usd,price_local,local_mad) values(?,?,?,?,?,?)",
          ("VIRAMAX NUTRAFRIK", app.norm("VIRAMAX NUTRAFRIK"), gabon, 13, 22000, .015))
product = c.execute("select last_insert_rowid() id").fetchone()["id"]
c.execute("insert into product_offers(product_id,price,commission) values(?,?,?)",(product,22000,13))
c.execute("""insert into deliveries
(period_id,source,tracking_number,delivery_date,buyer_raw,city,product_raw,price,status)
values(?,?,?,?,?,?,?,?,?)""",
          (period,"GLOBAL","SYNC-COUNTRY-1","2026-09-09","Mohammed Oujghi",
           "Expédition","VIRAMAX NUTRAFRIK",22000,"UNMAPPED COUNTRY, UNMATCHED BUYER"))
d1=c.execute("select last_insert_rowid() id").fetchone()["id"]
c.execute("""insert into deliveries
(period_id,source,tracking_number,delivery_date,buyer_raw,city,product_raw,price,status)
values(?,?,?,?,?,?,?,?,?)""",
          (period,"GLOBAL","SYNC-COUNTRY-2","2026-09-10","Review Alias 99",
           "Expédition","New Serum",21000,"UNMAPPED COUNTRY, UNMATCHED BUYER"))
d2=c.execute("select last_insert_rowid() id").fetchone()["id"]
c.commit();c.close()
app.assign_delivery_country(period,d1,"GABON")
c=app.db()
row=c.execute("select * from deliveries where id=?",(d1,)).fetchone()
assert row["buyer_id"]==buyer,(row["buyer_id"],buyer)
assert row["market_id"]==gabon
assert row["product_id"]==product
assert row["base_commission_usd"]==13
assert "UNMATCHED BUYER" not in (row["status"] or "")
c.close()
app.assign_delivery_country(period,d2,"GABON")
c=app.db()
row=c.execute("select * from deliveries where id=?",(d2,)).fetchone()
assert row["product_id"] is None
assert "MISSING PRODUCT/RATE" in row["status"]
c.execute("insert into products(name,name_norm,market_id,commission_usd,price_local,local_mad) values(?,?,?,?,?,?)",
          ("New Serum",app.norm("New Serum"),gabon,10,22000,.015))
newproduct=c.execute("select last_insert_rowid() id").fetchone()["id"]
c.execute("insert into product_offers(product_id,price,commission) values(?,?,?)",(newproduct,22000,10))
c.commit();c.close()
result=app.assign_buyer_alias(period,"Review Alias 99",buyer)
assert result["deliveries"]>=1,result
sync=app.sync_review_center()
c=app.db()
row=c.execute("select * from deliveries where id=?",(d2,)).fetchone()
assert row["buyer_id"]==buyer
assert row["product_id"]==newproduct
assert row["base_commission_usd"]==10
remise=c.execute("select * from remise_reviews where delivery_id=?",(d2,)).fetchone()
assert remise is not None, "Expected remission review for 21000 vs offer 22000"
assert remise["decision"]=="PENDING"
assert sync["products_linked"]>=1,sync
c.close()
again=app.sync_review_center()
assert again["products_linked"]==0,again
print("PASS: country+buyer assignment, missing product recovery, remise review, repeat sync")
root.cleanup()
