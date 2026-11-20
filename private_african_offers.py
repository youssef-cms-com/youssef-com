"""Apply private African price/commission updates supplied as a Railway variable.

No commission amounts are committed to the public source repository.
"""
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def apply_african_batch(db_factory, db_path, norm, recalculate):
    raw = os.environ.get("AFRICAN_OFFER_BATCH_V1", "").strip()
    if not raw:
        return {"status": "NO_BATCH"}
    entries = json.loads(raw)
    if not isinstance(entries, list) or not 0 < len(entries) <= 5000:
        raise ValueError("Invalid African offer payload")
    key = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    c = db_factory()
    try:
        c.execute("""create table if not exists private_offer_batch_runs (
            digest text primary key, status text not null,
            backup_path text, offers int, products int, stamp text)""")
        c.commit()
        previous = c.execute("select status from private_offer_batch_runs where digest=?", (key,)).fetchone()
        if previous and previous["status"] == "COMPLETE":
            return {"status": "ALREADY_COMPLETE", "batch": key[:12]}
        checked, missing, seen = [], [], set()
        for i, entry in enumerate(entries, 1):
            if not isinstance(entry, list) or len(entry) != 5:
                raise ValueError("Invalid row " + str(i))
            market, name, raw_price, raw_comm, raw_count = entry
            if market not in ("RDC", "GABON", "MALI", "CAMEROUN", "CONGO",
                              "TOGO", "BENIN", "GUINEE", "TCHAD", "BURKINA_FASO"):
                raise ValueError("Non-African market in row " + str(i))
            price, comm, count = float(raw_price), float(raw_comm), int(raw_count)
            if not (price > 0 and 0 <= comm < 100000 and count > 0):
                raise ValueError("Invalid price or commission in row " + str(i))
            k = (market, norm(name), price)
            if k in seen:
                raise ValueError("Duplicate price in row " + str(i))
            seen.add(k)
            product = c.execute("""select p.id from products p
                join markets m on m.id=p.market_id
                where m.code=? and p.name_norm=?""", (market, norm(name))).fetchone()
            if product is None:
                missing.append((market, str(name), price, comm, count))
            else:
                checked.append((product["id"], price, comm, count))
        # Missing exact-name products can be created from the reviewed workbook,
        # rather than silently borrowing a different product's commission.
        # This happens only after the persistent database has been backed up.
        if not previous:
            root = Path(db_path).parent / "offer_batch_backups"
            root.mkdir(parents=True, exist_ok=True)
            dest = root / ("before_african_batch_" + key[:16] + ".sqlite3")
            if not dest.exists():
                with sqlite3.connect(str(dest)) as backup:
                    c.backup(backup)
            if not dest.is_file() or dest.stat().st_size == 0:
                raise RuntimeError("Failed to verify database backup")
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            c.execute("begin immediate")
            try:
                if missing:
                    by_name = {}
                    for market, name, price, comm, count in missing:
                        key_name = (market, norm(name))
                        if key_name not in by_name or count > by_name[key_name][3]:
                            by_name[key_name] = (name, price, comm, count)
                    for (market, normalized), (name, price, comm, count) in by_name.items():
                        market_row = c.execute("select id from markets where code=?", (market,)).fetchone()
                        if not market_row:
                            raise ValueError("Missing market: " + market)
                        currency = "USD" if market == "RDC" else "XAF" if market in ("GABON","CAMEROUN","CONGO","TCHAD") else "XOF"
                        rate_row = c.execute("select mad_rate from currency_rates where currency=?", (currency,)).fetchone()
                        rate = float(rate_row["mad_rate"] or 0) if rate_row else 0.0
                        c.execute("""insert into products(name,name_norm,market_id,
                            commission_usd,commission_mad,price_local,local_mad)
                            values(?,?,?,?,?,?,?)""",
                            (name, normalized, market_row["id"], comm, 0, price, rate))
                        new_id = c.execute("select last_insert_rowid() id").fetchone()["id"]
                        c.execute("""insert into commission_rules
                            (product_id,start_date,end_date,amount,currency,note,created_at)
                            values(?,'1900-01-01',null,?,'USD','Initial reviewed African offer',?)""",
                            (new_id,comm,stamp))
                        for mkt, nm, pr, cm, cnt in missing:
                            if (mkt,norm(nm)) == (market,normalized):
                                checked.append((new_id,pr,cm,cnt))
                        # Link only unassigned deliveries of this exact single product,
                        # preserving multi-product orders and existing manual mappings.
                        unlinked = c.execute("""select id,product_raw,status from deliveries
                            where product_id is null and market_id=?""",
                            (market_row["id"],)).fetchall()
                        for delivery in unlinked:
                            lines = [line.strip() for line in str(delivery["product_raw"] or "").splitlines()
                                     if line.strip() and not line.strip().lower().startswith("-default at")]
                            if len(lines) != 1 or norm(lines[0]) != normalized:
                                continue
                            flags = [f.strip() for f in str(delivery["status"] or "").split(",")
                                     if f.strip() not in ("OK","MISSING PRODUCT/RATE")]
                            c.execute("update deliveries set product_id=?,status=? where id=?",
                                (new_id,", ".join(flags) or "OK",delivery["id"]))
                ids = sorted({row[0] for row in checked})
                for product_id, price, comm, count in checked:
                    c.execute("""insert into product_offers
                       (product_id,price,commission,note,created_at)
                       values(?,?,?,'Reviewed African commission workbook',?)
                       on conflict(product_id,price) do update set
                       commission=excluded.commission,note=excluded.note""",
                       (product_id, price, comm, stamp))
                    # Preserve the master selling price. Update its commission only
                    # when an explicit workbook offer matches that master price.
                    c.execute("""update products set commission_usd=?
                        where id=? and abs(coalesce(price_local,0)-?)<0.005""",
                        (comm, product_id, price))
                c.execute("""insert into private_offer_batch_runs
                    (digest,status,backup_path,offers,products,stamp)
                    values(?,?,?,?,?,?)""",
                    (key, "PENDING", str(dest), len(checked), len(ids), stamp))
                c.commit()
            except Exception:
                c.rollback()
                raise
    finally:
        c.close()
    totals = {"orders": 0, "changed": 0, "upsells_cleared": 0, "remises_cleared": 0}
    for product_id in ids:
        part = recalculate(product_id)
        for metric in totals:
            totals[metric] += part.get(metric, 0)
    c = db_factory()
    try:
        c.execute("update private_offer_batch_runs set status='COMPLETE' where digest=?", (key,))
        c.commit()
    finally:
        c.close()
    return {"status": "COMPLETE", "batch": key[:12],
            "offers": len(checked), "products": len(ids), **totals}
