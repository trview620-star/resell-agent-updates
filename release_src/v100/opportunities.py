"""Evidence-first opportunity ranking; no invented sales, shipping or stock."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from statistics import median
from collections import Counter
from . import db
from .pricing import projected_profit

def _time(text):
    try:
        value=datetime.fromisoformat(str(text).replace('Z','+00:00'))
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    except (ValueError,TypeError): return None

def _fresh(text, now, max_hours):
    timestamp=_time(text)
    return bool(timestamp and timedelta(0)<=now-timestamp<=timedelta(hours=max_hours))

def analyze_product(product, offers, comps, *, now=None, min_profit=3000, min_margin_pct=15):
    """Return comparable-informed screen. Verified SOLD samples required for 'qualified'."""
    now=now or datetime.now(timezone.utc)
    evidence=[c for c in comps if c.get('price_huf',0)>0 and _fresh(c.get('observed_at'),now,60*24)]
    sales=[c['price_huf'] for c in evidence if c.get('completed_sale')]
    asking=[c['price_huf'] for c in evidence if not c.get('completed_sale')]
    recent_offers=[x for x in offers if x.get('price_huf',0)>0 and _fresh(x.get('observed_at'),now,72)]
    selected=min(recent_offers,key=lambda x:x['price_huf']+x.get('shipping_huf',0)) if recent_offers else None
    stock=(selected['stock_status'] if selected else product.get('stock_status','unknown'))
    if selected:
        buy=selected['price_huf']
        inbound=selected.get('shipping_huf',0)
    else:
        buy=int(product.get('supplier_price') or 0)
        inbound=int(product.get('inbound_shipping') or 0)
    # Only completed-sale comps establish evidence-backed selling price.
    sold_med=int(median(sales)) if sales else None
    asking_med=int(median(asking)) if asking else None
    estimate=sold_med if sold_med else int(asking_med*0.85) if asking_med else None
    target=int(product.get('target_price') or 0)
    sale_price=estimate if estimate else target
    calc=projected_profit(target_price=sale_price,supplier_price=buy,inbound_shipping=inbound,
        outbound_shipping=int(product.get('outbound_shipping') or 0),
        packaging=int(product.get('packaging') or 0),
        marketplace_fees=int(product.get('marketplace_fees') or 0),
        risk_buffer=int(product.get('risk_buffer') or 0))
    flags=[]
    if buy<=0:flags.append('Missing supplier price')
    if not selected:flags.append('No supplier quote from the last 72 hours')
    if stock!='available':flags.append('Stock not confirmed available')
    if len(sales)<2:flags.append('Fewer than 2 recent confirmed completed-sale comparisons')
    if not sales and asking:flags.append('Price estimate uses discounted asking prices, not sales')
    if not estimate:flags.append('No market-supported resale estimate')
    if calc['profit']<min_profit:flags.append('Below minimum profit')
    if calc['margin_pct']<min_margin_pct:flags.append('Below minimum margin')
    eta=selected.get('eta_days') if selected else product.get('eta_days')
    if eta is None:flags.append('Delivery ETA unknown')
    if product.get('fulfillment','').startswith('System 1') and eta is not None and eta>3:
        flags.append('Local sourcing route may be too slow')
    if product.get('status') in ('paused','archived'):flags.append('Product is not active')
    if not flags:
        status='Qualified for review'
    elif buy<=0 or (estimate and calc['profit']<=0) or stock=='unavailable':
        status='Reject / pause'
    else:
        status='Needs evidence'
    score=max(0,min(100,
        22*(min(1,max(0,calc['profit'])/6000))
        +18*(min(1,max(0,calc['margin_pct'])/25))
        +25*(min(1,len(sales)/3))
        +10*(1 if selected else 0)
        +10*(1 if stock=='available' else 0)
        +8*(1 if eta is not None and eta<=2 else 0)
        +7*(1 if len(evidence)>=3 else 0)))
    return {'product_id':product['id'],'title':product['title'],'status':status,'score':round(score),
        'suggested_price_huf':estimate,'selling_price_used_huf':sale_price,
        'asking_median_huf':asking_med,'sold_median_huf':sold_med,
        'completed_comps':len(sales),'asking_comps':len(asking),
        'supplier_price_huf':buy,'supplier_total_huf':buy+inbound,
        'stock_status':stock,'eta_days':eta,
        'projected_profit_huf':calc['profit'],'margin_pct':calc['margin_pct'],
        'evidence':'completed sales' if sales else 'asking prices only' if asking else 'manual target only',
        'warnings':flags,'supplier_url':selected.get('url') if selected else product.get('supplier_url','')}

def rank_database(*,min_profit=3000,min_margin_pct=15):
    products=db.rows('SELECT * FROM products ORDER BY id DESC')
    offers=db.rows('SELECT * FROM supplier_offers ORDER BY observed_at DESC')
    comps=db.rows('SELECT * FROM resale_comparables ORDER BY observed_at DESC')
    offer_by={}; comp_by={}
    for row in offers:offer_by.setdefault(row['product_id'],[]).append(row)
    for row in comps:comp_by.setdefault(row['product_id'],[]).append(row)
    result=[analyze_product(p,offer_by.get(p['id'],[]),comp_by.get(p['id'],[]),
                            min_profit=min_profit,min_margin_pct=min_margin_pct)
            for p in products]
    return sorted(result,key=lambda p:(p['status']=='Qualified for review',p['score']),reverse=True)

def fulfillment_flags(orders,listings,*,today=None):
    from datetime import date
    today=today or date.today()
    out=[]
    for o in orders:
        if o['status'] in ('delivered','cancelled','refunded'):continue
        if o.get('due_date'):
            try:
                left=(date.fromisoformat(o['due_date'][:10])-today).days
                if left<=3:
                    out.append({'severity':'urgent' if left<=1 else 'warning','order_id':o['id'],
                        'message':f"Shipping due in {left} day(s) — {o['marketplace']}"})
            except ValueError:pass
        conflicts=[l for l in listings if l['product_id']==o['product_id'] and
                   l['status']=='published' and l['marketplace']!=o['marketplace']]
        if conflicts:out.append({'severity':'warning','order_id':o['id'],
                   'message':f"{len(conflicts)} cross-listed active offer(s) still recorded"})
    return out
