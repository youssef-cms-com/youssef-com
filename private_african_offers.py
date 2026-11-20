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
                missing.append((market, str(name)))
            else:
                checked.append((product["id"], price, comm, count))
        if missing:
            return {"status": "BLOCKED_MISSING_PRODUCTS",
                    "missing": missing, "matched": len(checked)}
        ids = sorted({row[0] for row in checked})
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
