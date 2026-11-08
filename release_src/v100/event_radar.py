"""Event keyword matches: ideas only, never claims of measured buyer demand."""
from datetime import date
import re

def candidate_event_matches(product,events,today=None):
    today=today or date.today()
    terms=set(re.findall(r'\w{3,}', ' '.join(str(product.get(k,'') or '').lower()
                   for k in ('title','brand','model','category'))))
    out=[]
    for event in events:
        try:when=date.fromisoformat(event['event_date'])
        except (ValueError,KeyError,TypeError):continue
        days=(when-today).days
        if not 0<=days<=120:continue
        keywords=set(re.findall(r'\w{3,}',str(event.get('product_ideas','')).lower()))
        matches=sorted(terms & keywords)
        if matches:out.append(dict(name=event['name'],date=str(when),
                                   days_until=days,matching_keywords=matches))
    return sorted(out,key=lambda e:e['days_until'])
