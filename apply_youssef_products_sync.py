"""Apply the YOUSSEF.COM Products > Sync Calculations feature to a local checkout.
Run from the repository root: python apply_youssef_products_sync.py
Creates .bak copies; does not deploy, delete or alter production data.
"""
from pathlib import Path
import ast

root=Path.cwd()
app=root/'app.py'; server=root/'server.py'
if not app.is_file() or not server.is_file():
    raise SystemExit('Run this script from the repository root containing app.py and server.py')

def replace_once(text, old, new, label):
    count=text.count(old)
    if count!=1: raise RuntimeError(f'{label}: expected one insertion point, found {count}')
    return text.replace(old,new,1)

a=app.read_text(encoding='utf-8'); s=server.read_text(encoding='utf-8')
if 'def sync_all_product_deliveries(' in a or "'/products-sync/'" in s:
    raise SystemExit('Feature appears already installed; no files changed.')

helper='''def sync_all_product_deliveries():
    """Recalculate linked imported deliveries across every product and period.

    This uses the existing price-offer classifier, preserves manually reviewed
    decisions when still valid, and archives changes in offer_recalc_audit.
    Returns an aggregate report for the user interface. No source uploads are
    deleted; the dashboards read updated delivery commissions dynamically.
    """
    c=db()
    try:
        ids=[r['id'] for r in c.execute('select id from products order by id').fetchall()]
    finally:
        c.close()
    report={'products':len(ids),'orders':0,'changed':0,'upsells_cleared':0,
            'remises_cleared':0,'upsells_detected':0,'remises_detected':0}
    for product_id in ids:
        part=recalculate_offers(product_id)
        for k in ('orders','changed','upsells_cleared','remises_cleared',
                  'upsells_detected','remises_detected'):
            report[k]+=part[k]
    return report

'''
a=replace_once(a,'def remise_rows(period_id):',helper+'def remise_rows(period_id):','application helper')
a=replace_once(a, '            if not changed:continue\n            report[\'changed\']+=1',
    """            # A rate-only edit must also refresh stored conversions and remise values.
            changed = changed or abs(float(d['local_mad'] or 0)-rate)>.00001 or bool(old_r and new_remise and abs(float(old_r['rate_mad'] or 0)-rate)>.00001)
            if not changed:continue
            report['changed']+=1""", 'currency-rate change detection')

ui='''    <div class='panel' style='border:1px solid #cfe3ee;background:linear-gradient(120deg,#f5f9ff,#f2fcf9)'>
      <div class='panel-head' style='flex-wrap:wrap'>
        <div><span class='eyebrow'>Commission reconciliation</span><h2>Sync Calculations</h2>
          <p class='muted' style='margin:8px 0 0'>After updating product prices, commissions, offers or currency rates, refresh imported deliveries and the calculated buyer dashboards across all months.</p></div>
        <form method='post' action='/products-sync/{pid}' onsubmit="return confirm('Recalculate all product-linked deliveries across every month? Historical review changes will be audited.')">
          <button class='btn' type='submit'>↻ Sync Calculations</button>
        </form>
      </div>
    </div>
'''
s=replace_once(s, "    <div class='panel'><div class='panel-head'><div><span class='eyebrow'>Global settings</span><h2>Currency conversions to MAD</h2>",ui+"    <div class='panel'><div class='panel-head'><div><span class='eyebrow'>Global settings</span><h2>Currency conversions to MAD</h2>",'products UI')

route='''        if path.startswith('/products-sync/'):
            pid=int(path.split('/')[-1])
            try:
                result=sync_all_product_deliveries()
            except Exception as e:
                return self.out(page('Sync error',f'<div class="panel"><h2>Synchronization failed</h2><p>{esc(e)}</p><a class="btn" href="/products/{pid}">Back to products</a></div>',period(pid)),500)
            labels=[('Products checked','products'),('Linked deliveries checked','orders'),
                    ('Deliveries updated','changed'),('Upsells cleared','upsells_cleared'),
                    ('Remises cleared','remises_cleared'),('Upsells detected','upsells_detected'),
                    ('Remises detected','remises_detected')]
            items=''.join(f'<tr><td>{label}</td><td class="num"><strong>{result[key]:,}</strong></td></tr>' for label,key in labels)
            body=f'<section class="hero"><div><span class="eyebrow">Products &amp; Offers</span><h1>Sync complete</h1><p>Linked imported deliveries have been recalculated across all months. Buyer dashboards and exports now reflect updated values.</p></div></section><div class="panel"><h2>Synchronization report</h2><div class="table-wrap"><table>{items}</table></div><p class="muted">Existing imports are preserved. Financial review decisions are retained when still applicable; superseded decisions are audited.</p><a class="btn" href="/products/{pid}">Back to Products</a> <a class="btn secondary" href="/dashboard/{pid}">View dashboard</a></div>'
            return self.out(page('Products Sync',body,period(pid)))
'''
s=replace_once(s,"        if path.startswith('/product-edit/'):",route+"        if path.startswith('/product-edit/'):",'sync POST route')

# Fail closed if source files would be syntactically invalid.
ast.parse(a,filename='app.py');ast.parse(s,filename='server.py')
for path,content in ((app,a),(server,s)):
    path.with_name(path.name+'.pre-products-sync.bak').write_text(path.read_text(encoding='utf-8'),encoding='utf-8')
    path.write_text(content,encoding='utf-8')
print('Products synchronization installed in app.py and server.py. Run your tests, back up /data/youssef.db, then deploy through your normal GitHub workflow.')
