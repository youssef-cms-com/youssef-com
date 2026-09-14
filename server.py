from __future__ import annotations
import os,secrets,math,hashlib,hmac
from email.parser import BytesParser
from email.policy import default
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from http.cookies import SimpleCookie
from pathlib import Path
from app import *

HOST=os.getenv('HOST','0.0.0.0'); PORT=int(os.getenv('PORT','5000'))
ADMIN_EMAIL=os.getenv('ADMIN_EMAIL','admin@youssef.com').lower(); ADMIN_PASSWORD=os.getenv('ADMIN_PASSWORD',''); SESS={}
CSS_FILE=BASE/'static'/'app.css'
try:
    APP_CSS=CSS_FILE.read_text(encoding='utf-8')
except Exception:
    APP_CSS='body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f7fb;color:#17304f}'

def hp(p,s=None):
 s=s or secrets.token_hex(16);return s+'$'+hashlib.pbkdf2_hmac('sha256',p.encode(),s.encode(),200000).hex()
def vp(p,h):
 try:s,x=h.split('$');return hmac.compare_digest(hp(p,s),h)
 except:return False
def ensure_admin():
 c=db();u=c.execute('select id from users where email=?',(ADMIN_EMAIL,)).fetchone()
 if not u and ADMIN_PASSWORD:c.execute('insert into users(email,name,password_hash,role,status,created_at) values(?,?,?,?,?,?)',(ADMIN_EMAIL,'Youssef Admin',hp(ADMIN_PASSWORD),'ADMIN','ACTIVE',datetime.now().isoformat()));c.commit()
 c.close()

def money(x): return f'{float(x or 0):,.2f}'
def period(pid):
    c=db();r=c.execute('select * from periods where id=?',(pid,)).fetchone();c.close();return dict(r) if r else None

def logo(size='normal'):
    cls='logo compact' if size=='compact' else 'logo'
    return f'''<div class="{cls}"><span class="logo-mark"><svg viewBox="0 0 44 44" aria-hidden="true"><path d="M6 8h8l8 12 8-12h8L25 29v8h-6v-8z"/><path d="M12 8h7l3 5 3-5h7l-10 16z" class="logo-cut"/></svg></span><span><b>YOUSSEF.COM</b><small>Commission Intelligence</small></span></div>'''

def nav(pid=None):
    if not pid:return ''
    links=[('Dashboard',f'/dashboard/{pid}','⌂'),('Months',f'/periods/{pid}','▦'),('Media Buyers',f'/buyers/{pid}','◎'),('Import Center',f'/imports/{pid}','⇧'),('USDT & Adjustments',f'/adjustments/{pid}','₮'),('Products',f'/products/{pid}','◇'),('Commission History',f'/commission-rules/{pid}','◷'),('African Upsells',f'/african-upsells/{pid}','✓'),('City Mapping',f'/cities/{pid}','⌖'),('Review Center',f'/review/{pid}','!'),('Rates & Rules',f'/settings/{pid}','⚙'),('Export Excel',f'/export/{pid}','↓')]
    return f'''<aside class="sidebar">{logo()}<nav>{''.join(f'<a href="{u}"><span>{i}</span>{t}</a>' for t,u,i in links)}<div class="nav-sep"></div><a href="/new"><span>＋</span>New Month</a><a href="/logout"><span>↗</span>Logout</a></nav><div class="sidebar-foot"><b>Private workspace</b><span>YOUSSEF.COM v9.1 Online</span></div></aside>'''

def page(title,body,p=None):
    pid=p['id'] if p else None
    selector=''
    if pid:
        opts=''.join(f'<option value="{x["id"]}" {"selected" if x["id"]==pid else ""}>{esc(x["label"])}</option>' for x in period_list())
        selector=f'''<label class="period-switch"><small>Period</small><select onchange="location.href='/dashboard/'+this.value">{opts}</select></label>'''
    topbar=f'''<header class="appbar"><div><span class="eyebrow">Commission & performance hub</span><strong>{esc(p['label']) if p else 'YOUSSEF.COM'}</strong></div><div class="appbar-actions">{selector}<span class="live-dot">● Live calculations</span><span class="admin-chip">AY</span></div></header>''' if pid else ''
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#102e57"><title>{esc(title)} · YOUSSEF.COM</title><style>{APP_CSS}</style><link rel="stylesheet" href="/static/app.css?v=9.1"></head><body><div class="shell">{nav(pid)}<div class="workspace">{topbar}<main class="content">{body}</main></div></div></body></html>'''.encode()

def bar_chart(items,value_key,label_key='market',currency=False):
    vals=[max(0,float(x.get(value_key,0) or 0)) for x in items]; mx=max(vals+[1])
    rows=[]
    for x,v in zip(items,vals):
        pct=max(2,min(100,v/mx*100)) if v else 0
        val=(f'MAD {money(v)}' if currency else f'{int(v):,}')
        rows.append(f'''<div class="chart-row"><div class="chart-label"><span>{esc(x.get(label_key,''))}</span><b>{val}</b></div><div class="chart-track"><i style="width:{pct:.1f}%"></i></div></div>''')
    return '<div class="bar-chart">'+''.join(rows)+'</div>'

def donut(segments,center_title,center_value):
    total=sum(max(0,float(v)) for _,v,_ in segments) or 1
    stops=[];cur=0
    for _,v,color in segments:
        nxt=cur+max(0,float(v))/total*360;stops.append(f'{color} {cur:.1f}deg {nxt:.1f}deg');cur=nxt
    legend=''.join(f'<div><i style="background:{c}"></i><span>{esc(n)}</span><b>{money(v)}</b></div>' for n,v,c in segments)
    return f'''<div class="donut-wrap"><div class="donut" style="background:conic-gradient({','.join(stops)})"><div><small>{esc(center_title)}</small><strong>{esc(center_value)}</strong></div></div><div class="donut-legend">{legend}</div></div>'''

def dashboard(pid):
    p=period(pid);xs=period_summary(pid);active=[x for x in xs if x['deliveries'] or x['spend_usd'] or x['adj']['usdt_sent'] or x['auto_credit'] or x['manual_credit']]
    td=sum(x['deliveries'] for x in active);gross=sum(x['gross'] for x in active);bonus=sum(x['bonus'] for x in active);profit=sum(x['net_profit'] for x in active);final=sum(x['final'] for x in active);ups=sum(x['upsell'] for x in active);usdt=sum(float(x['adj']['usdt_sent']) for x in active);ups_orders=sum(x['upsell_orders'] for x in active)
    ub,uc,mp=review(pid);warn=len(ub)+len(uc)+len(mp);afups=african_upsell_stats(pid)
    streak_alerts=[]
    for x in active:
        streak,_=negative_streak(pid,x['buyer']['id'])
        if streak>=3 and x['buyer']['status']=='CURRENT':streak_alerts.append((x['buyer']['name'],streak,x['final']))
    alert_html=''.join(f'<div class="risk-alert"><div><b>3-month negative payout alert</b><span>{esc(n)} has {st} consecutive negative payout months and should leave the team.</span></div><strong>MAD {money(v)}</strong></div>' for n,st,v in streak_alerts)
    rows=''.join(f'''<tr><td><a class="buyer-link" href="/buyer/{pid}/{x['buyer']['id']}"><span class="avatar">{''.join(z[0] for z in x['buyer']['name'].split()[:2])}</span><span><strong>{esc(x['buyer']['name'])}</strong><small>{esc(x['buyer']['status'])}</small></span></a></td><td class="num">{x['deliveries']:,}</td><td class="num">{money(x['gross'])}</td><td class="num">{money(x['upsell'])}<small>{x['upsell_orders']} orders</small></td><td class="num">{money(x['adj']['usdt_sent'])}</td><td class="num {'positive' if x['net_profit']>=0 else 'negative'}"><strong>{money(x['net_profit'])}</strong></td><td class="num"><strong>{money(x['final'])}</strong></td></tr>''' for x in active)
    top=sorted(active,key=lambda x:x['net_profit'],reverse=True)[:6]
    top_chart=bar_chart([{'market':x['buyer']['name'],'net_profit':x['net_profit']} for x in top],'net_profit',currency=True)
    ups_rank=sorted(active,key=lambda x:x['upsell'],reverse=True)[:6]
    ups_chart=bar_chart([{'market':x['buyer']['name'],'upsell':x['upsell']} for x in ups_rank],'upsell',currency=True)
    body=f'''<section class="hero"><div><span class="eyebrow">Executive overview</span><h1>Commission Dashboard</h1><p>Clear monthly view of delivery performance, commission, spend, upsells and payouts.</p></div><div class="hero-badge"><span>Period</span><strong>{esc(p['label'])}</strong><small>{esc(p['status'])}</small></div></section>
    {alert_html}<div class="kpis six"><div class="kpi blue"><span>Total Deliveries</span><strong>{td:,}</strong><small>All mapped markets</small></div><div class="kpi green"><span>Generated CMS</span><strong>MAD {money(gross)}</strong><small>Base commission + upsells</small></div><div class="kpi violet"><span>Total USDT Sent</span><strong>{money(usdt)} USDT</strong><small>Actual monthly transfers</small></div><div class="kpi teal"><span>Net Profit</span><strong>MAD {money(profit)}</strong><small>Commission − system spend</small></div><div class="kpi amber"><span>Paid Upsells</span><strong>MAD {money(ups)}</strong><small>{ups_orders:,} paid · {afups['pending']:,} Africa pending</small></div><div class="kpi coral"><span>Final Payout</span><strong>MAD {money(final)}</strong><small>After USDT, bonus, remise & credit</small></div></div>
    <div class="analytics-grid"><div class="panel"><div class="panel-head"><div><span class="eyebrow">Performance</span><h2>Top media buyers by net profit</h2></div><a class="text-link" href="/buyers/{pid}">View team →</a></div>{top_chart}</div><div class="panel"><div class="panel-head"><div><span class="eyebrow">Upsell intelligence</span><h2>Paid upsell commission by buyer</h2></div><a class="text-link" href="/african-upsells/{pid}">Review {afups['pending']} pending →</a></div>{ups_chart}</div></div>
    <div class="panel"><div class="panel-head"><div><span class="eyebrow">Team overview</span><h2>Media buyer profitability & payout</h2></div><div class="soft-stats"><span>Bonus <b>{money(bonus)} MAD</b></span><span>Alerts <b>{warn}</b></span></div></div><div class="table-wrap"><table><thead><tr><th>Media Buyer</th><th class="num">DLV</th><th class="num">Gross CMS MAD</th><th class="num">Upsell</th><th class="num">USDT Sent</th><th class="num">Net Profit MAD</th><th class="num">Final Payout MAD</th></tr></thead><tbody>{rows}</tbody></table></div></div>'''
    return page('Dashboard',body,p)

def buyers_page(pid):
    p=period(pid);xs=period_summary(pid);card_parts=[]
    for x in xs:
        streak,_=negative_streak(pid,x['buyer']['id']); risk=f'<span class="pill risk">{streak}× negative</span>' if streak else ''
        leave=(f'''<form method="post" action="/buyers/leave/{pid}/{x['buyer']['id']}" class="leave-form" onsubmit="return confirm('Mark this media buyer as LEFT TEAM? Historical data will be kept.')"><input name="reason" placeholder="Reason (optional)"><button class="btn danger compact-btn">Leave team</button></form>''' if x['buyer']['status']=='CURRENT' else f'''<form method="post" action="/buyers/reactivate/{pid}/{x['buyer']['id']}" class="leave-form"><button class="btn secondary compact-btn">Reactivate</button></form>''')
        card_parts.append(f'''<div class="buyer-card"><a class="buyer-card-main" href="/buyer/{pid}/{x['buyer']['id']}"><div class="buyer-card-top"><span class="avatar lg">{''.join(z[0] for z in x['buyer']['name'].split()[:2])}</span><span class="pill {'former' if x['buyer']['status']!='CURRENT' else ''}">{esc(x['buyer']['status'])}</span></div><h3>{esc(x['buyer']['name'])}</h3>{risk}<div class="buyer-metrics"><span><small>Deliveries</small><b>{x['deliveries']:,}</b></span><span><small>Net Profit</small><b class="{'positive' if x['net_profit']>=0 else 'negative'}">{money(x['net_profit'])}</b></span><span><small>Carry Credit</small><b>{money(x['carry_forward'])}</b></span><span><small>Payout</small><b>{money(x['final'])}</b></span></div></a>{leave}</div>''')
    cards=''.join(card_parts)
    c=db();bs=c.execute('select * from buyers order by case status when "CURRENT" then 0 else 1 end,name').fetchall();c.close()
    aliases=''
    body=f'''<section class="hero"><div><span class="eyebrow">Team management</span><h1>Media Buyers</h1><p>Open any buyer for complete calculation details, charts and analysis.</p></div></section><div class="panel add-panel"><div><h2>Add new media buyer</h2><p class="muted">New buyers become available immediately in imports, calculations and adjustments.</p></div><form method="post" action="/buyers/{pid}" class="inline-form"><input name="name" placeholder="Full media buyer name" required><select name="status"><option>CURRENT</option><option>FORMER / JULY</option></select><input name="aliases" placeholder="Aliases (comma separated)"><button class="btn">+ Add buyer</button></form></div><div class="buyer-grid">{cards}</div>'''
    return page('Media Buyers',body,p)

def buyer_page(pid,bid):
    p=period(pid);x=buyer_calc(pid,bid);a=x['adj']; recon='good' if abs(x['recon_gap'])<.01 else 'warn';streak,_=negative_streak(pid,bid);hist=buyer_history(pid,bid)
    country=''.join(f'''<tr><td><strong>{esc(r['market'])}</strong><small>{esc(r['grp'])}</small></td><td class="num">{r['deliveries']}</td><td class="num">{money(r['base_native'])} {r['commission_currency']}</td><td class="num">{money(r['base_mad'])}</td><td class="num">{money(r['upsell_mad'])}</td><td class="num">{money(r['gross_mad'])}</td><td class="num">${money(r['spend_usd'])}</td><td class="num">${money(r['cpd'])}</td><td class="num {'positive' if r['profit_mad']>=0 else 'negative'}"><strong>{money(r['profit_mad'])}</strong></td></tr>''' for r in x['rows']) or '<tr><td colspan="9">No activity.</td></tr>'
    products=''.join(f'''<tr><td>{esc(r['market'])}</td><td>{esc(r['product'])}</td><td class="num">{r['deliveries']}</td><td class="num">{r['upsell_orders'] or 0}</td><td class="num">{money(r['base_generated_mad'] or 0)}</td><td class="num">{money(r['upsell_mad'] or 0)}</td></tr>''' for r in x['products'][:150])
    market_chart=bar_chart(x['rows'],'profit_mad',currency=True); delivery_chart=bar_chart(x['rows'],'deliveries')
    commission_donut=donut([('Base commission MAD',x['base_mad'],'#5b8def'),('Upsells MAD',x['upsell'],'#4ec7a5'),('Bonus MAD',x['bonus'],'#f3b35a')],'Generated + bonus',f"{money(x['gross']+x['bonus'])} MAD")
    analysis=[]
    if x['net_profit']>=0: analysis.append(f"Net profit is positive at {money(x['net_profit'])} MAD with a {x['profit_margin']:.1f}% margin on generated commission.")
    else: analysis.append(f"Net profit is negative by {money(abs(x['net_profit']))} MAD; system spend is above generated commission.")
    analysis.append(f"Generated commission is unified in MAD: Morocco stays native MAD, while non-Morocco commission is converted at {x['settings']['other_usd_mad']:.2f} MAD/USD.")
    if x['upsell_orders']: analysis.append(f"{x['upsell_orders']} paid upsells contribute {money(x['upsell'])} MAD ({x['upsell_share']:.1f}% of generated commission).")
    if x['african_upsells']['pending']: analysis.append(f"{x['african_upsells']['pending']} African upsell candidates are still pending approval and are not included in this buyer's commission.")
    if x['bonus']: analysis.append(f"Delivery targets generated {money(x['bonus'])} MAD in bonuses.")
    if x['auto_credit']: analysis.append(f"Automatic carried credit of {money(x['auto_credit'])} MAD from the previous month is deducted from this payout.")
    if streak>=3: analysis.append(f"CRITICAL: this is the {streak}rd consecutive negative payout month. Team-leave review is required.")
    if abs(x['recon_gap'])>.01: analysis.append(f"Spend reconciliation has a {money(x['recon_gap'])} USDT gap that should be reviewed.")
    insights=''.join(f'<li>{esc(t)}</li>' for t in analysis)
    body=f'''<section class="buyer-hero"><div class="buyer-title"><span class="avatar xl">{''.join(z[0] for z in x['buyer']['name'].split()[:2])}</span><div><span class="eyebrow">Media buyer analysis</span><h1>{esc(x['buyer']['name'])}</h1><p>{esc(p['label'])} · Morocco {x['morocco_del']} DLV · Africa {x['africa_del']} DLV</p></div></div><span class="pill {'former' if x['buyer']['status']!='CURRENT' else ''}">{esc(x['buyer']['status'])}</span></section>
    {f'<div class="risk-alert critical"><div><b>Successive negative payout alert</b><span>This buyer has {streak} consecutive negative payout months. Recommendation: leave the team.</span></div></div>' if streak>=3 else ''}<div class="kpis six"><div class="kpi blue"><span>Deliveries</span><strong>{x['deliveries']:,}</strong><small>Total delivered orders</small></div><div class="kpi green"><span>Generated Commission</span><strong>MAD {money(x['gross'])}</strong><small>All markets unified in MAD</small></div><div class="kpi amber"><span>Paid Upsell</span><strong>MAD {money(x['upsell'])}</strong><small>{x['upsell_orders']} paid · {x['african_upsells']['pending']} Africa pending</small></div><div class="kpi violet"><span>USDT Sent</span><strong>{money(a['usdt_sent'])}</strong><small>MAD {money(x['deductible_mad'])} deduction</small></div><div class="kpi teal featured"><span>NET PROFIT</span><strong>MAD {money(x['net_profit'])}</strong><small>{x['profit_margin']:.1f}% margin · CMS − spend</small></div><div class="kpi coral"><span>Final Payout</span><strong>MAD {money(x['final'])}</strong><small>After all deductions & bonus</small></div></div>
    <div class="analytics-grid buyer-analytics"><div class="panel"><div class="panel-head"><div><span class="eyebrow">Profit analysis</span><h2>Net profit by market</h2></div></div>{market_chart}</div><div class="panel"><div class="panel-head"><div><span class="eyebrow">Delivery mix</span><h2>Deliveries by market</h2></div></div>{delivery_chart}</div><div class="panel">{commission_donut}</div><div class="panel insight-panel"><span class="eyebrow">Automated analysis</span><h2>Performance insights</h2><ul class="insights">{insights}</ul></div></div>
    <div class="panel"><div class="panel-head"><div><span class="eyebrow">MAD-first payout</span><h2>Final payout bridge</h2></div><span class="pill">USD→MAD {x['settings']['other_usd_mad']:.2f} · USDT→MAD {x['settings']['usdt_mad']:.2f}</span></div><div class="bridge"><div class="step"><small>Generated CMS MAD</small><strong>{money(x['gross'])}</strong></div><div class="step danger"><small>− USDT sent MAD</small><strong>{money(x['deductible_mad'])}</strong></div><div class="step good"><small>+ Bonus MAD</small><strong>{money(x['bonus'])}</strong></div><div class="step danger"><small>− 80% Remise</small><strong>{money(x['remise_ded'])}</strong></div><div class="step danger"><small>− Auto carry credit</small><strong>{money(x['auto_credit'])}</strong></div><div class="step danger"><small>− Manual credit</small><strong>{money(x['manual_credit'])}</strong></div><div class="step final-step"><small>Final payout MAD</small><strong>{money(x['final'])}</strong></div><div class="step"><small>Next-month credit</small><strong>{money(x['carry_forward'])}</strong></div></div></div>
    <div class="grid2"><div class="panel"><div class="panel-head"><h2>Spend reconciliation</h2><span class="pill {recon}">{'Balanced' if abs(x['recon_gap'])<.01 else 'Review gap'}</span></div><table class="compact-table"><tr><td>System spend</td><td class="num">${money(x['spend_usd'])}</td></tr><tr><td>USDT sent</td><td class="num">{money(a['usdt_sent'])}</td></tr><tr><td>Charges</td><td class="num">{money(a['charges'])}</td></tr><tr><td>Test spend</td><td class="num">{money(a['test_spend'])}</td></tr><tr><td>Wallet rest</td><td class="num">{money(a['wallet_rest'])}</td></tr><tr class="{recon}"><td><strong>Reconciliation gap</strong></td><td class="num"><strong>{money(x['recon_gap'])}</strong></td></tr></table></div><div class="panel"><div class="panel-head"><h2>Commission composition</h2></div><table class="compact-table"><tr><td>Base commission MAD</td><td class="num">{money(x['base_mad'])}</td></tr><tr><td>Upsells MAD</td><td class="num">{money(x['upsell'])}</td></tr><tr><td><strong>Generated commission MAD</strong></td><td class="num"><strong>{money(x['gross'])}</strong></td></tr><tr><td>Bonus MAD</td><td class="num">{money(x['bonus'])}</td></tr><tr><td>Remise deducted MAD</td><td class="num">{money(x['remise_ded'])}</td></tr><tr><td>Auto carry credit MAD</td><td class="num">{money(x['auto_credit'])}</td></tr><tr><td>Manual credit MAD</td><td class="num">{money(x['manual_credit'])}</td></tr><tr><td>Next-month credit if negative</td><td class="num">{money(x['carry_forward'])}</td></tr><tr><td>System spend MAD</td><td class="num">{money(x['spend_mad'])}</td></tr><tr><td><strong>Net profit MAD</strong></td><td class="num {'positive' if x['net_profit']>=0 else 'negative'}"><strong>{money(x['net_profit'])}</strong></td></tr></table></div></div>
    <div class="panel"><div class="panel-head"><div><span class="eyebrow">Cross-month history</span><h2>Payout & carried credit</h2></div><span class="pill {'risk' if streak>=3 else ''}">{streak} consecutive negative</span></div><div class="table-wrap"><table><thead><tr><th>Month</th><th class="num">Final payout MAD</th><th class="num">Credit carried forward</th></tr></thead><tbody>{''.join(f'<tr><td><a class="text-link" href="/buyer/{h["period_id"]}/{bid}">{esc(h["label"])}</a></td><td class="num {"negative" if h["final"]<0 else "positive"}">{money(h["final"])}</td><td class="num">{money(h["carry_forward"])}</td></tr>' for h in hist)}</tbody></table></div></div>
    <div class="panel"><div class="panel-head"><div><span class="eyebrow">Country detail</span><h2>Market calculation</h2></div></div><div class="table-wrap"><table><thead><tr><th>Market</th><th class="num">DLV</th><th class="num">Native CMS</th><th class="num">Base CMS MAD</th><th class="num">Upsell MAD</th><th class="num">Generated MAD</th><th class="num">System Spend $</th><th class="num">CPD $</th><th class="num">Net Profit MAD</th></tr></thead><tbody>{country}</tbody></table></div></div>
    <div class="panel"><div class="panel-head"><div><span class="eyebrow">Upsell & products</span><h2>Product commission details</h2></div><span class="pill">{x['upsell_orders']} upsell orders</span></div><div class="table-wrap"><table><thead><tr><th>Market</th><th>Product</th><th class="num">DLV</th><th class="num">Upsell Orders</th><th class="num">Base CMS MAD</th><th class="num">Upsell MAD</th></tr></thead><tbody>{products}</tbody></table></div></div>'''
    return page(x['buyer']['name'],body,p)

def african_upsells_page(pid,decision='PENDING'):
    p=period(pid);decision=(decision or 'PENDING').upper();decision=decision if decision in ('ALL','PENDING','APPROVED','REJECTED') else 'PENDING'
    stats=african_upsell_stats(pid);rs=african_upsell_rows(pid,decision)
    tabs=''.join(f'<a class="upsell-tab {"active" if decision==st else ""}" href="/african-upsells/{pid}?status={st}">{label}<b>{stats.get(st.lower(),stats["detected"]) if st!="ALL" else stats["detected"]}</b></a>' for st,label in [('PENDING','Pending'),('APPROVED','Approved'),('REJECTED','Rejected'),('ALL','All detected')])
    rows=[]
    for r in rs:
        extra=max(0,float(r['price'] or 0)-float(r['base_price_local'] or 0));product=base_product_name(r['product_raw'] or '')
        status=r['upsell_decision'];cls=status.lower()
        rows.append(f'''<tr><td><input class="upsell-check" type="checkbox" name="selected" value="{r['id']}"></td><td><strong>{esc(r['tracking_number'] or '—')}</strong><small>{esc(r['delivery_date'] or '—')}</small></td><td>{esc(r['buyer'] or 'Unmatched')}</td><td>{esc(r['market'])}<small>{esc(r['city'] or '')}</small></td><td class="product-cell">{esc(product)}</td><td class="num">{money(r['base_price_local'])}</td><td class="num">{money(r['price'])}</td><td class="num">{money(extra)}</td><td class="num"><strong>{money(r['upsell_candidate_mad'])} MAD</strong></td><td><span class="decision {cls}">{status.title()}</span></td><td class="actions"><button class="approve-btn" name="single" value="APPROVED:{r['id']}">Approve</button><button class="reject-btn" name="single" value="REJECTED:{r['id']}">Reject</button></td></tr>''')
    body=f'''<section class="hero"><div><span class="eyebrow">Controlled African upsells</span><h1>African Upsells Review</h1><p>YOUSSEF.COM detects potential African upsells automatically. Only <strong>Approved</strong> rows are added to media-buyer commission.</p></div><div class="hero-badge"><span>Approval rule</span><strong>25%</strong><small>Africa only · manual decision</small></div></section>
    <div class="kpis four"><div class="kpi amber"><span>Detected</span><strong>{stats['detected']:,}</strong><small>MAD {money(stats['potential_mad'])} potential</small></div><div class="kpi blue"><span>Pending</span><strong>{stats['pending']:,}</strong><small>Not included in commission</small></div><div class="kpi green"><span>Approved</span><strong>{stats['approved']:,}</strong><small>MAD {money(stats['approved_mad'])} included</small></div><div class="kpi coral"><span>Rejected</span><strong>{stats['rejected']:,}</strong><small>Base product only</small></div></div>
    <div class="panel upsell-policy"><div><span class="eyebrow">Calculation policy</span><h2>African orders are paid safely</h2></div><div class="policy-flow"><span>Detected candidate</span><b>→</b><span>Pending</span><b>→</b><span>Approve / Reject</span><b>→</b><span>Commission recalculates</span></div><p>Pending and rejected candidates keep the normal first-product commission only. Approval adds the calculated 25% upsell in MAD. Morocco remains automatic at 20%; Tunisia and Lebanon have no upsell.</p></div>
    <div class="panel"><div class="panel-head"><div>{tabs}</div><span class="pill">{len(rs)} shown</span></div><form method="post" action="/african-upsells/{pid}"><div class="bulkbar"><label><input id="checkAll" type="checkbox"> Select all shown</label><div><button class="approve-btn" name="decision" value="APPROVED">Approve selected</button><button class="reject-btn" name="decision" value="REJECTED">Reject selected</button><button class="secondary-action" name="decision" value="PENDING">Reset to pending</button></div></div><div class="table-wrap"><table><thead><tr><th></th><th>Tracking</th><th>Media Buyer</th><th>Market</th><th>First Product</th><th class="num">Base Price</th><th class="num">Order Total</th><th class="num">Extra Sale</th><th class="num">Potential Upsell</th><th>Status</th><th>Decision</th></tr></thead><tbody>{''.join(rows) if rows else '<tr><td colspan="11" class="empty">No upsells in this status.</td></tr>'}</tbody></table></div></form></div>
    <script>document.getElementById('checkAll')?.addEventListener('change',function(){{document.querySelectorAll('.upsell-check').forEach(x=>x.checked=this.checked)}});</script>'''
    return page('African Upsells',body,p)

def settings_page(pid):
    p=period(pid);c=db();s=dict(c.execute('select * from settings where period_id=?',(pid,)).fetchone());c.close()
    body=f'''<section class="hero"><div><span class="eyebrow">Controls</span><h1>Rates & Rules</h1><p>The payout engine is MAD-first: Morocco commission is native MAD, other commission is converted from USD.</p></div></section><div class="panel"><form method="post"><div class="formrow"><div class="field"><label>Morocco system spend USD → MAD</label><input name="maroc_spend_mad" value="{s['maroc_spend_mad']}"></div><div class="field"><label>Other markets Commission USD → MAD</label><input name="other_usd_mad" value="{s['other_usd_mad']}"></div><div class="field"><label>USDT Sent → MAD</label><input name="usdt_mad" value="{s['usdt_mad']}"></div></div><div class="formrow"><div class="field"><label>Morocco Upsell %</label><input name="upsell_maroc" value="{s['upsell_maroc']*100}"></div><div class="field"><label>Africa Upsell %</label><input name="upsell_africa" value="{s['upsell_africa']*100}"></div><div class="field"><label>Remise deduction %</label><input name="remise_pct" value="{s['remise_pct']*100}"></div></div><button class="btn">Save settings</button></form></div><div class="grid3"><div class="panel rule-card"><span class="eyebrow">Morocco commission</span><h2>No conversion</h2><p>Product commission is stored and calculated directly in MAD. Upsells are also MAD.</p></div><div class="panel rule-card"><span class="eyebrow">Other markets</span><h2>USD commission → MAD</h2><p>Generated USD commission is converted at the fixed monthly rate, currently {s['other_usd_mad']:.2f} MAD/USD.</p></div><div class="panel rule-card"><span class="eyebrow">Payout deduction</span><h2>USDT → MAD</h2><p>Total USDT sent is converted at {s['usdt_mad']:.2f} MAD/USDT and deducted from generated commission.</p></div></div><div class="grid2"><div class="panel rule-card"><span class="eyebrow">Africa bonus</span><h2>Combined African deliveries</h2><p>500 → $150 · 600 → $250 · 700 → $500 · 1000+ → $1,000 (converted at USD→MAD rate)</p></div><div class="panel rule-card"><span class="eyebrow">Morocco bonus</span><h2>Moroccan deliveries only</h2><p>500–999 → 1,500 MAD · 1000–1499 → 3,500 MAD · 1500–1999 → 6,000 MAD · 2000+ → 10,000 MAD</p></div></div>'''
    return page('Settings',body,p)

def adjustments_page(pid):
    p=period(pid);c=db();rows=c.execute('select b.*,coalesce(a.usdt_sent,0) usdt_sent,coalesce(a.charges,0) charges,coalesce(a.test_spend,0) test_spend,coalesce(a.wallet_rest,0) wallet_rest,coalesce(a.remise_mad,0) remise_mad,coalesce(a.credit_mad,0) credit_mad,coalesce(a.note,"") note from buyers b left join adjustments a on a.buyer_id=b.id and a.period_id=? order by case b.status when "CURRENT" then 0 else 1 end,b.name',(pid,)).fetchall();c.close()
    trs=''.join(f'''<tr><td><strong>{esc(r['name'])}</strong><small>{esc(r['status'])}</small></td><td><input name="usdt_{r['id']}" value="{r['usdt_sent']}"></td><td><input name="charges_{r['id']}" value="{r['charges']}"></td><td><input name="test_{r['id']}" value="{r['test_spend']}"></td><td><input name="rest_{r['id']}" value="{r['wallet_rest']}"></td><td><input name="remise_{r['id']}" value="{r['remise_mad']}"></td><td><input name="credit_{r['id']}" value="{r['credit_mad']}"></td><td><input name="note_{r['id']}" value="{esc(r['note'])}"></td></tr>''' for r in rows)
    body=f'''<section class="hero"><div><span class="eyebrow">Payout controls</span><h1>USDT & Adjustments</h1><p>USDT sent drives the payout deduction. Charges, test spend and wallet rest remain visible for reconciliation. Remise is deducted in MAD. Previous negative payout credit is carried automatically; the Credit field below is only for legacy or exceptional manual adjustments.</p></div></section><form method="post"><div class="panel"><div class="table-wrap"><table><thead><tr><th>Buyer</th><th>USDT Sent</th><th>Charges</th><th>Test Spend</th><th>Wallet Rest</th><th>Remise MAD</th><th>Manual / Legacy Credit MAD</th><th>Note</th></tr></thead><tbody>{trs}</tbody></table></div><div class="form-actions"><button class="btn">Save adjustments</button></div></div></form>'''
    return page('Adjustments',body,p)

def cities_page(pid,error=''):
    p=period(pid);maps=city_mappings();c=db();unknown=c.execute('select city,count(*) cnt from deliveries where period_id=? and source="GLOBAL" and market_id is null group by city order by cnt desc',(pid,)).fetchall();c.close()
    opts=''.join(f'<option value="{code}">{name}</option>' for code,name,_ in MARKETS if code!='MAROC')
    rows=''.join(f'''<tr><td><strong>{esc(r["city"])}</strong></td><td>{esc(r["market_name"])}</td><td><span class="pill">{esc(r["source"])}</span></td><td><form method="post" action="/cities/delete/{pid}/{r["id"]}"><button class="btn secondary compact-btn">Delete</button></form></td></tr>''' for r in maps)
    unk=''.join(f'''<tr><td><strong>{esc(r["city"] or "(blank)")}</strong></td><td class="num">{r["cnt"]}</td><td><form class="inline-map" method="post" action="/cities/{pid}"><input type="hidden" name="city" value="{esc(r["city"])}"><select name="market">{opts}</select><button class="btn compact-btn">Map & recalculate</button></form></td></tr>''' for r in unknown) or '<tr><td colspan="3" class="empty">All cities in this month are mapped.</td></tr>'
    err=f'<div class="notice">{esc(error)}</div>' if error else ''
    body=f'''<section class="hero"><div><span class="eyebrow">Persistent geography rules</span><h1>City Mapping</h1><p>Every saved city is remembered for future months. Unknown cities are stopped for review instead of being assigned to the wrong country.</p></div></section>{err}<div class="grid2"><div class="panel"><div class="panel-head"><div><span class="eyebrow">New mapping</span><h2>Add city</h2></div></div><form method="post" action="/cities/{pid}"><div class="field"><label>City name exactly as it appears in exports</label><input name="city" required placeholder="Example: Tshikapa"></div><div class="field"><label>Country</label><select name="market">{opts}</select></div><button class="btn">+ Save city mapping</button></form></div><div class="panel info-card"><span class="eyebrow">Automatic behavior</span><h2>Saved once, reused every month</h2><p>When a new city is mapped, YOUSSEF.COM immediately reclassifies already imported rows for that city and recalculates product commission, date-based rate and upsell. Future imports recognize it automatically.</p><div class="kpi-mini"><strong>{len(maps)}</strong><span>saved city mappings</span></div></div></div><div class="panel"><div class="panel-head"><div><span class="eyebrow">Needs attention</span><h2>Unknown cities in {esc(p['label'])}</h2></div><span class="pill">{len(unknown)} cities</span></div><div class="table-wrap"><table><thead><tr><th>City</th><th class="num">Deliveries</th><th>Assign country</th></tr></thead><tbody>{unk}</tbody></table></div></div><div class="panel"><div class="panel-head"><div><span class="eyebrow">Master data</span><h2>Saved City to Country mappings</h2></div><span class="pill">Persistent</span></div><div class="table-wrap"><table><thead><tr><th>City</th><th>Country</th><th>Source</th><th></th></tr></thead><tbody>{rows}</tbody></table></div></div>'''
    return page('City Mapping',body,p)

def review_page(pid):
    p=period(pid);ub,uc,mp=review(pid)
    a=''.join(f'<tr><td>{esc(x["source"])}</td><td>{esc(x["buyer_raw"])}</td><td class="num">{x["cnt"]}</td></tr>' for x in ub) or '<tr><td colspan=3 class="empty">No unmatched buyer names.</td></tr>'
    b=''.join(f'<tr><td>{esc(x["city"])}</td><td class="num">{x["cnt"]}</td></tr>' for x in uc) or '<tr><td colspan=2 class="empty">All cities mapped.</td></tr>'
    d=''.join(f'<tr><td>{esc(str(x["product_raw"]).split(chr(10))[0])}</td><td class="num">{x["cnt"]}</td></tr>' for x in mp) or '<tr><td colspan=2 class="empty">All product rates found.</td></tr>'
    body=f'''<section class="hero"><div><span class="eyebrow">Quality control</span><h1>Review Center</h1><p>Unmatched data is isolated instead of silently affecting commission.</p></div></section><div class="grid3"><div class="panel"><h2>Unmatched buyers</h2><table><tr><th>Source</th><th>Name</th><th class="num">Rows</th></tr>{a}</table></div><div class="panel"><h2>Unknown cities</h2><a class="text-link" href="/cities/{pid}">Manage city mappings →</a><table><tr><th>City</th><th class="num">Rows</th></tr>{b}</table></div><div class="panel"><h2>Missing products/rates</h2><table><tr><th>Product</th><th class="num">Rows</th></tr>{d}</table></div></div>'''
    return page('Review',body,p)

def imports_page(pid):
    p=period(pid);c=db();hist=c.execute('select * from imports where period_id=? order by id desc',(pid,)).fetchall();c.close();opts=''.join(f'<option value="{code}">{name}</option>' for code,name,_ in MARKETS);trs=''.join(f'<tr><td>{esc(r["created_at"])}</td><td>{esc(r["kind"])}</td><td>{esc(r["market_code"] or "—")}</td><td>{esc(r["filename"])}</td><td class="num">{r["rows_imported"]}</td><td class="num">{r["warnings"]}</td></tr>' for r in hist)
    body=f'''<section class="hero"><div><span class="eyebrow">Automation</span><h1>Import Center</h1><p>Upload the monthly exports. Country filtering, buyer matching, product linking and calculations run automatically.</p></div></section><div class="grid2"><div class="panel upload-panel"><form method="post" enctype="multipart/form-data"><div class="field"><label>Import type</label><select name="kind"><option value="deliveries_maroc">Morocco deliveries</option><option value="deliveries_global">Global deliveries</option><option value="spend">Country spend</option><option value="products">Products / commissions / prices</option></select></div><div class="field"><label>Country (spend only)</label><select name="market">{opts}</select></div><div class="field"><label>Excel file</label><input type="file" name="file" accept=".xlsx"></div><button class="btn">Import & recalculate</button></form></div><div class="panel info-card"><span class="eyebrow">Automatic workflow</span><h2>One upload → complete recalculation</h2><p>Global deliveries are filtered by city. Buyer aliases are matched. Products, commissions, original prices and upsells are linked by market. Bonuses and payout rules then recalculate automatically.</p></div></div><div class="panel"><h2>Import history</h2><div class="table-wrap"><table><tr><th>Time</th><th>Type</th><th>Market</th><th>File</th><th class="num">Rows</th><th class="num">Warnings</th></tr>{trs}</table></div></div>'''
    return page('Imports',body,p)

def products_page(pid):
    p=period(pid);c=db();rs=c.execute('''select p.*,m.name market,m.code market_code,(select count(*) from commission_rules cr where cr.product_id=p.id) rule_count,(select cr.amount from commission_rules cr where cr.product_id=p.id order by cr.start_date desc limit 1) latest_amount,(select cr.currency from commission_rules cr where cr.product_id=p.id order by cr.start_date desc limit 1) latest_currency from products p join markets m on m.id=p.market_id order by m.name,p.name limit 2000''').fetchall();c.close();opts=''.join(f'<option value="{code}">{name}</option>' for code,name,_ in MARKETS)
    trs=''.join(f'''<tr><td>{esc(r["market"])}</td><td><strong>{esc(r["name"])}</strong></td><td class="num"><strong>{money(r["latest_amount"] or (r["commission_mad"] if r["market_code"]=="MAROC" else r["commission_usd"]))} {esc(r["latest_currency"] or ("MAD" if r["market_code"]=="MAROC" else "USD"))}</strong><small>{r["rule_count"]} period(s)</small></td><td class="num">{money(r["price_local"])}</td><td class="num">{money(r["local_mad"])}</td><td><a class="btn secondary compact-btn" href="/commission-rules/{pid}/{r['id']}">Manage dates</a></td></tr>''' for r in rs)
    body=f'''<section class="hero"><div><span class="eyebrow">Master data</span><h1>Products</h1><p>Products keep their price master here. Commission can now change during the month using effective-date history.</p></div><div class="hero-badge"><span>New in v5</span><strong>Date-aware commission</strong><small>Each delivery uses its own date</small></div></section><div class="panel add-panel"><div><h2>Add product</h2><p class="muted">The commission entered here becomes the initial/default rate. Use Commission History for future or mid-month changes.</p></div><form method="post" action="/products/{pid}" class="product-form"><input name="name" placeholder="Product name" required><select name="market">{opts}</select><input name="commission" type="number" step="0.01" placeholder="Initial commission" required><input name="price" type="number" step="0.01" placeholder="Original price" required><input name="local_mad" type="number" step="0.0001" placeholder="Local price → MAD rate" required><button class="btn">+ Save product</button></form></div><div class="panel"><div class="panel-head"><div><span class="eyebrow">Commission master</span><h2>Products & current rates</h2></div><a class="text-link" href="/commission-rules/{pid}">View all commission periods →</a></div><div class="table-wrap"><table><thead><tr><th>Market</th><th>Product</th><th class="num">Latest Commission</th><th class="num">Original Price</th><th class="num">Local → MAD</th><th>History</th></tr></thead><tbody>{trs}</tbody></table></div></div>'''
    return page('Products',body,p)

def commission_rules_page(pid,product_id=None,error=''):
    p=period(pid);c=db()
    if product_id:
        prod=c.execute('select p.*,m.name market,m.code market_code from products p join markets m on m.id=p.market_id where p.id=?',(product_id,)).fetchone()
        if not prod:c.close();return page('Commission History','<div class="panel"><h2>Product not found</h2></div>',p)
        rules=c.execute('select * from commission_rules where product_id=? order by start_date desc',(product_id,)).fetchall();c.close()
        curr='MAD' if prod['market_code']=='MAROC' else 'USD'
        rows=''.join(f'''<tr><td><strong>{esc(r['start_date'])}</strong></td><td>{esc(r['end_date'] or 'Open / current')}</td><td class="num"><strong>{money(r['amount'])} {esc(r['currency'])}</strong></td><td>{esc(r['note'] or '—')}</td><td><form method="post" action="/commission-rules/delete/{pid}/{r['id']}" onsubmit="return confirm('Delete this commission period?')"><button class="btn danger-btn compact-btn" type="submit">Delete</button></form></td></tr>''' for r in rules)
        err=f'<div class="notice error-note">{esc(error)}</div>' if error else ''
        body=f'''<section class="hero"><div><span class="eyebrow">Effective-date engine</span><h1>{esc(prod['name'])}</h1><p>{esc(prod['market'])} · Commission currency: <strong>{curr}</strong>. Every delivered order automatically selects the rate active on its delivery date.</p></div><div class="hero-badge"><span>Current periods</span><strong>{len(rules)}</strong><small>Historical rates preserved</small></div></section>{err}<div class="grid2 rules-layout"><div class="panel"><span class="eyebrow">Add change</span><h2>New commission period</h2><p class="muted">If you add a new start date, the previous open period is automatically closed the day before. Leave End Date empty to keep the new rate active until the next change.</p><form method="post" action="/commission-rules/{pid}/{product_id}"><div class="field"><label>Commission ({curr})</label><input name="amount" type="number" step="0.01" required></div><div class="formrow two"><div class="field"><label>Start date</label><input name="start_date" type="date" required></div><div class="field"><label>End date (optional)</label><input name="end_date" type="date"></div></div><div class="field"><label>Note</label><input name="note" placeholder="Example: New commission from 15 July"></div><button class="btn">+ Add commission period</button></form></div><div class="panel info-card"><span class="eyebrow">How calculation works</span><h2>Date of delivery decides the rate</h2><div class="rule-example"><span>01 Jul → 14 Jul</span><strong>Old commission</strong><span>15 Jul → current</span><strong>New commission</strong></div><p>The platform recalculates already imported deliveries immediately after you save a period. July remains historically correct even if the current commission changes later.</p></div></div><div class="panel"><div class="panel-head"><div><span class="eyebrow">Audit trail</span><h2>Commission history</h2></div><a class="text-link" href="/products/{pid}">← Back to products</a></div><div class="table-wrap"><table><thead><tr><th>Start</th><th>End</th><th class="num">Commission</th><th>Note</th><th></th></tr></thead><tbody>{rows}</tbody></table></div></div>'''
        return page('Commission History',body,p)
    rs=c.execute('''select p.id,p.name,m.name market,m.code market_code,count(cr.id) periods,max(cr.start_date) latest_start from products p join markets m on m.id=p.market_id left join commission_rules cr on cr.product_id=p.id group by p.id order by m.name,p.name''').fetchall();c.close()
    rows=''.join(f'''<tr><td>{esc(r['market'])}</td><td><strong>{esc(r['name'])}</strong></td><td class="num">{r['periods']}</td><td>{esc(r['latest_start'] or '—')}</td><td><a class="btn secondary compact-btn" href="/commission-rules/{pid}/{r['id']}">Open history</a></td></tr>''' for r in rs)
    body=f'''<section class="hero"><div><span class="eyebrow">Commission control</span><h1>Commission History</h1><p>Manage mid-month commission changes without splitting files or editing old orders manually.</p></div></section><div class="panel"><div class="panel-head"><div><span class="eyebrow">All products</span><h2>Effective-date coverage</h2></div><span class="pill">{len(rs)} products</span></div><div class="table-wrap"><table><thead><tr><th>Market</th><th>Product</th><th class="num">Periods</th><th>Latest start</th><th></th></tr></thead><tbody>{rows}</tbody></table></div></div>'''
    return page('Commission History',body,p)

def periods_page(pid):
    p=period(pid);ps=period_list();rows=[]
    for pr in ps:
        xs=period_summary(pr['id']);active=[x for x in xs if x['deliveries'] or x['spend_usd'] or x['adj']['usdt_sent'] or x['auto_credit']]
        neg=sum(1 for x in active if x['final']<0);carry=sum(x['carry_forward'] for x in active);total=sum(x['final'] for x in active)
        rows.append(f'<tr><td><strong>{esc(pr["label"])}</strong><small>{esc(pr["status"])}</small></td><td class="num">{len(active)}</td><td class="num {"negative" if total<0 else "positive"}">{money(total)}</td><td class="num">{neg}</td><td class="num">{money(carry)}</td><td><a class="btn secondary compact-btn" href="/dashboard/{pr["id"]}">Open month</a></td></tr>')
    body=f'''<section class="hero"><div><span class="eyebrow">Period history</span><h1>Months</h1><p>Every month remains available. Negative payouts automatically become credit in the next month.</p></div><a class="btn" href="/new">+ New Month</a></section><div class="panel"><div class="table-wrap"><table><thead><tr><th>Period</th><th class="num">Active Buyers</th><th class="num">Total Payout MAD</th><th class="num">Negative Buyers</th><th class="num">Credit to Next Month MAD</th><th></th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></div><div class="panel info-card"><span class="eyebrow">Automatic relation between months</span><h2>Credit carry-forward</h2><p>If a buyer closes a month at <strong>-1,200 MAD</strong>, the next month automatically starts with a <strong>1,200 MAD credit deduction</strong>. If the next month remains negative, the new negative balance is carried again. After 3 consecutive negative payout months, YOUSSEF.COM raises a team-leave alert.</p></div>'''
    return page('Months',body,p)


def login(error=''):
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#102e57"><title>YOUSSEF.COM</title><style>{APP_CSS}</style><link rel="stylesheet" href="/static/app.css?v=9.1"></head><body><div class="loginwrap"><div class="login-visual">{logo()}<div><span class="eyebrow light">Private commission intelligence</span><h1>Turn monthly exports into clear, auditable payouts.</h1><p>Performance, spend, upsells, bonuses and final commission — in one workspace.</p></div></div><div class="login"><div class="mobile-logo">{logo('compact')}</div><span class="eyebrow">Secure access</span><h1>Welcome back</h1><p class="muted">Sign in to YOUSSEF.COM.</p>{f'<div class="notice">{esc(error)}</div>' if error else ''}<form method="post" autocomplete="on"><div class="field"><label>Email</label><input name="email" type="email" autocomplete="username" value="{esc(ADMIN_EMAIL)}"></div><div class="field"><label>Password</label><input name="password" type="password" autocomplete="current-password"></div><button class="btn" style="width:100%">Sign in</button></form></div></div></body></html>'''.encode()

class H(BaseHTTPRequestHandler):
    def out(self,data,status=200,ctype='text/html; charset=utf-8',headers=None):
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)));[self.send_header(k,v) for k,v in (headers or {}).items()];self.end_headers();self.wfile.write(data)
    def redirect(self,loc,headers=None): self.out(b'',302,'text/plain',{'Location':loc,**(headers or {})})
    def authed(self):
        c=SimpleCookie(self.headers.get('Cookie'));s=c.get('sid');return bool(s and s.value in SESS)
    def user(self):
        c=SimpleCookie(self.headers.get('Cookie'));s=c.get('sid');return SESS.get(s.value) if s else None
    def form(self):
        n=int(self.headers.get('Content-Length','0'));return {k:v[-1] for k,v in parse_qs(self.rfile.read(n).decode()).items()}
    def do_GET(self):
        u=urlparse(self.path);path=u.path;query=parse_qs(u.query)
        if path.startswith('/static/'):
            f=(BASE/path.lstrip('/')).resolve()
            static_root=(BASE/'static').resolve()
            if static_root not in f.parents and f != static_root:
                return self.out(b'Not found',404,'text/plain')
            if not f.exists() or not f.is_file():
                return self.out(b'Not found',404,'text/plain')
            ctype={'css':'text/css; charset=utf-8','svg':'image/svg+xml','png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','webp':'image/webp'}.get(f.suffix.lower().lstrip('.'),'application/octet-stream')
            return self.out(f.read_bytes(),200,ctype,{'Cache-Control':'public, max-age=300'})
        if path=='/login':return self.out(login())
        if path=='/logout':return self.redirect('/login',{'Set-Cookie':'sid=; Max-Age=0; Path=/'})
        if not self.authed():return self.redirect('/login')
        if path=='/':
            c=db();p=c.execute('select id from periods order by year desc,month desc limit 1').fetchone();c.close();return self.redirect(f'/dashboard/{p["id"]}' if p else '/new')
        if path.startswith('/dashboard/'):return self.out(dashboard(int(path.split('/')[-1])))
        if path.startswith('/periods/'):return self.out(periods_page(int(path.split('/')[-1])))
        if path.startswith('/buyers/'):return self.out(buyers_page(int(path.split('/')[-1])))
        if path.startswith('/buyer/'):
            _,_,pid,bid=path.split('/');return self.out(buyer_page(int(pid),int(bid)))
        if path.startswith('/settings/'):return self.out(settings_page(int(path.split('/')[-1])))
        if path.startswith('/adjustments/'):return self.out(adjustments_page(int(path.split('/')[-1])))
        if path.startswith('/cities/'):return self.out(cities_page(int(path.split('/')[-1])))
        if self.user().get('role')=='MEDIA_BUYER_VIEWER':return self.out(b'Read-only account',403,'text/plain')
        if path.startswith('/african-upsells/'):return self.out(african_upsells_page(int(path.split('/')[-1]),query.get('status',['PENDING'])[0]))
        if path.startswith('/review/'):return self.out(review_page(int(path.split('/')[-1])))
        if path.startswith('/imports/'):return self.out(imports_page(int(path.split('/')[-1])))
        if path.startswith('/commission-rules/'):
            parts=path.strip('/').split('/');pid=int(parts[1]);product_id=int(parts[2]) if len(parts)>2 else None;return self.out(commission_rules_page(pid,product_id))
        if path.startswith('/products/'):return self.out(products_page(int(path.split('/')[-1])))
        if path.startswith('/export/'):
            pid=int(path.split('/')[-1]);out=BASE/f'YOUSSEF_COM_Commission_{pid}.xlsx';export_summary(pid,out);return self.out(out.read_bytes(),200,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',{'Content-Disposition':f'attachment; filename="{out.name}"'})
        if path=='/new':return self.out(page('New Month','''<section class="hero"><div><span class="eyebrow">New workspace</span><h1>Create commission month</h1><p>Start a clean monthly calculation period.</p></div></section><div class="panel narrow"><form method="post" action="/new"><div class="formrow two"><div class="field"><label>Year</label><input name="year" value="2026"></div><div class="field"><label>Month</label><input name="month" value="8"></div></div><button class="btn">Create month</button></form></div>'''))
        self.out(b'Not found',404,'text/plain')
    def do_POST(self):
        u=urlparse(self.path);path=u.path;query=parse_qs(u.query)
        if path=='/login':
            f=self.form()
            c=db();u=c.execute('select * from users where email=? and status="ACTIVE"',(f.get('email','').lower(),)).fetchone();c.close()
            if u and vp(f.get('password',''),u['password_hash']):
                sid=secrets.token_urlsafe(24);SESS[sid]={'id':u['id'],'role':u['role'],'buyer_id':u['buyer_id'],'name':u['name']};return self.redirect('/',{'Set-Cookie':f'sid={sid}; HttpOnly; SameSite=Lax; Path=/; Max-Age=43200'})
            return self.out(login('Invalid email or password.'),401)
        if not self.authed():return self.redirect('/login')
        if path=='/new':
            if self.user().get('role')=='MEDIA_BUYER_VIEWER':return self.out(b'Read-only account',403,'text/plain')
            f=self.form();pid=ensure_period(int(f['year']),int(f['month']));return self.redirect(f'/dashboard/{pid}')
        if path.startswith('/african-upsells/'):
            pid=int(path.split('/')[-1]);n=int(self.headers.get('Content-Length','0'));f=parse_qs(self.rfile.read(n).decode());single=f.get('single',[None])[0]
            if single and ':' in single:
                decision,did=single.split(':',1);set_african_upsell_decision(pid,[did],decision)
            else:
                set_african_upsell_decision(pid,f.get('selected',[]),f.get('decision',['PENDING'])[0])
            return self.redirect(f'/african-upsells/{pid}')
        if path.startswith('/cities/delete/'):
            parts=path.strip('/').split('/');pid=int(parts[2]);mapping_id=int(parts[3]);delete_city_mapping(mapping_id);return self.redirect(f'/cities/{pid}')
        if path.startswith('/cities/'):
            pid=int(path.split('/')[-1]);f=self.form()
            try:add_city_mapping(f.get('city'),f.get('market'))
            except ValueError as e:return self.out(cities_page(pid,str(e)),400)
            return self.redirect(f'/cities/{pid}')
        if path.startswith('/buyers/leave/'):
            parts=path.strip('/').split('/');pid=int(parts[2]);bid=int(parts[3]);f=self.form();set_buyer_team_status(bid,True,f.get('reason',''));return self.redirect(f'/buyers/{pid}')
        if path.startswith('/buyers/reactivate/'):
            parts=path.strip('/').split('/');pid=int(parts[2]);bid=int(parts[3]);set_buyer_team_status(bid,False);return self.redirect(f'/buyers/{pid}')
        if path.startswith('/buyers/'):
            pid=int(path.split('/')[-1]);f=self.form();aliases=[a.strip() for a in f.get('aliases','').split(',') if a.strip()];add_buyer(f.get('name'),f.get('status','CURRENT'),aliases);return self.redirect(f'/buyers/{pid}')
        if path.startswith('/commission-rules/delete/'):
            parts=path.strip('/').split('/');pid=int(parts[2]);rule_id=int(parts[3])
            try:delete_commission_rule(rule_id)
            except ValueError as e:return self.out(page('Commission History',f'<div class="panel"><h2>Cannot delete rule</h2><p>{esc(e)}</p><a class="btn" href="/commission-rules/{pid}">Back</a></div>',period(pid)),400)
            return self.redirect(f'/commission-rules/{pid}')
        if path.startswith('/commission-rules/'):
            parts=path.strip('/').split('/');pid=int(parts[1]);product_id=int(parts[2]);f=self.form()
            try:add_commission_rule(product_id,f.get('start_date'),f.get('amount'),f.get('end_date'),f.get('note',''))
            except ValueError as e:return self.out(commission_rules_page(pid,product_id,str(e)),400)
            return self.redirect(f'/commission-rules/{pid}/{product_id}')
        if path.startswith('/products/'):
            pid=int(path.split('/')[-1]);f=self.form();add_product(f.get('name'),f.get('market'),f.get('commission'),f.get('price'),f.get('local_mad'));return self.redirect(f'/products/{pid}')
        if path.startswith('/settings/'):
            pid=int(path.split('/')[-1]);f=self.form();c=db();c.execute('update settings set maroc_spend_mad=?,other_usd_mad=?,usdt_mad=?,upsell_maroc=?,upsell_africa=?,remise_pct=? where period_id=?',(float(f['maroc_spend_mad']),float(f['other_usd_mad']),float(f['usdt_mad']),float(f['upsell_maroc'])/100,float(f['upsell_africa'])/100,float(f['remise_pct'])/100,pid));c.commit();c.close();return self.redirect(f'/settings/{pid}')
        if path.startswith('/adjustments/'):
            pid=int(path.split('/')[-1]);save_adjustments(pid,self.form());return self.redirect(f'/adjustments/{pid}')
        if path.startswith('/imports/'):
            pid=int(path.split('/')[-1]);n=int(self.headers.get('Content-Length','0'));raw=self.rfile.read(n);ctype=self.headers.get('Content-Type','');msg=BytesParser(policy=default).parsebytes((f'Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw);fields={};file_name=None;file_bytes=None
            for part in msg.iter_parts():
                name=part.get_param('name',header='content-disposition');fn=part.get_filename();payload=part.get_payload(decode=True) or b''
                if fn:file_name=Path(fn).name;file_bytes=payload
                elif name:fields[name]=payload.decode(errors='replace')
            if not file_name or file_bytes is None:return self.out(b'Missing upload',400,'text/plain')
            kind=fields.get('kind');market=fields.get('market');dest=UPLOADS/file_name;dest.write_bytes(file_bytes)
            if kind=='deliveries_maroc':import_deliveries(pid,dest,False)
            elif kind=='deliveries_global':import_deliveries(pid,dest,True)
            elif kind=='spend':import_spend(pid,dest,market)
            elif kind=='products':seed_products(dest)
            return self.redirect(f'/imports/{pid}')
        self.out(b'Not found',404,'text/plain')

if __name__=='__main__':
    init_db();ensure_admin();print(f'YOUSSEF.COM v9.1 Online running at http://{HOST}:{PORT}');ThreadingHTTPServer((HOST,PORT),H).serve_forever()
