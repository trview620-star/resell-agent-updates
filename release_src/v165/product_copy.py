"""Short, human Hungarian resale copy based only on confirmed product facts."""
from __future__ import annotations
import hashlib,re

FOOTER='Hasonló termékekért nézd meg a többi hirdetésemet.'
BANNED=('a termékkel kapcsolatos kérdéseket szívesen fogadom',
        'a részleteket üzenetben egyeztetjük',
        'tökéletes választás','lenyűgöző','igazán különleges',
        'minden igényt kielégít','prémium minőség','kihagyhatatlan')

def product_line(title):
    title=' '.join(str(title or '').split()).strip(' .!')
    if not title:return ''
    return (title if title.casefold().startswith('eladó ') else 'Eladó '+title)+'.'

def category_text(title):
    name=title.casefold()
    if 'lego' in name and any(x in name for x in ('vidra','vidrá','állat','madár','kutya','macska')):
        return ('Nagyon aranyos, részletgazdag LEGO szett, ami összerakva is jól mutat a polcon. '
                'Ajándéknak is jó ötlet, főleg ha valaki szereti a LEGO-t vagy az állatokat.')
    if 'lego' in name and any(x in name for x in ('botanical','virág','orchidea','csokor','növény')):
        return ('Jó élmény összerakni, és elkészülve a polcon is szépen mutat. '
                'Ajándéknak is jó ötlet annak, aki szereti a LEGO-t vagy a virágokat.')
    if 'lego' in name:
        return ('Jó kis LEGO készlet, amit élmény összerakni. '
                'Ajándéknak is jó ötlet, de saját gyűjteménybe is szívesen választják.')
    if any(x in name for x in ('dobble','dixit','azul','catan','hitster','ticket to ride',
                                'társasjáték','kártyajáték','exploding kittens')):
        return ('Jó választás egy közös játékhoz, akár családdal, akár barátokkal. '
                'Ajándéknak is jó ötlet.')
    if any(x in name for x in ('switch','playstation','xbox','dualsense','nintendo','8bitdo','kontroller','kormány')):
        return ('Ha játékhoz keresel ilyet, érdemes megnézni. '
                'A pontos változattal kapcsolatban szívesen válaszolok.')
    if any(x in name for x in ('jbl','soundcore','sony wh','airpods','buds','hangszóró','fejhallgató','headset')):
        return ('Jó választás lehet zenehallgatáshoz vagy a mindennapokra. '
                'Ha pont ezt a modellt keresed, írj nyugodtan.')
    if any(x in name for x in ('egér','webkamera','ssd','ram','stream deck','billentyűzet','dock')):
        return ('Hasznos darab lehet a géped mellé, akár munkához, akár otthonra. '
                'Ha kérdésed van a pontos modellről, írj nyugodtan.')
    if any(x in name for x in ('airfryer','sütő','kávéfőző','porszívó','nespresso','fogkefe')):
        return ('Praktikus darab otthonra, ha épp ilyet keresel. '
                'A részletekről szívesen válaszolok üzenetben.')
    if any(x in name for x in ('nike','adidas','new balance','cipő','farmer','kabát','pulóver','levis')):
        return ('Jól kombinálható darab a hétköznapokra. '
                'Ha a mérettel vagy a fazonnal kapcsolatban kérdésed van, írj.')
    return 'Ha érdekel, írj nyugodtan, szívesen válaszolok a kérdéseidre.'

def fallback(title):
    head=product_line(title)
    if not head:return ''
    body=category_text(title)
    # Don't repeat the same call-to-action twice in short descriptions.
    question='' if any(x in body.casefold() for x in ('írj','válaszolok')) else '\n\nHa bármi kérdésed van, írj nyugodtan!'
    return head+'\n\n'+body+question+'\n\n'+FOOTER

def cloud_prompt(product):
    title=str(product.get('title') or '').strip()[:180]
    context=['Termék: '+title]
    for key,label in [('brand','Márka'),('model','Modell'),('category','Kategória')]:
        val=str(product.get(key) or '').strip()[:110]
        if val:context.append(label+': '+val)
    condition=str(product.get('condition_text') or '')
    if condition in ('Új (ellenőrizve)','Új, bontatlan (ellenőrizve)'):
        context.append('Igazolt állapot: '+condition)
    verified=str(product.get('verified_facts') or '').strip()
    if verified:context.append('Külön ellenőrzött adatok: '+verified[:600])
    return (
        'Írj egy rövid, természetes magyar apróhirdetést, mintha egy hétköznapi magáneladó írná a Vinteden. Kizárólag a megadott terméket és '
        'ellenőrzött tényeket használd. A stílus legyen egyszerű, meleg, '
        'barátságos, pár rövid mondatban, nem marketinges. Ne legyen gépies. '
        'Először: "Eladó [termék neve]." Majd 1-2 olyan mondat, ami az adott '
        'termékre illik, érdeklődést kelt, de nem állít ellenőrizetlen műszaki '
        'tulajdonságokat, tartozékokat, bontatlan állapotot vagy működést. '
        'Így írj például egy LEGO-hoz: "Nagyon aranyos, részletgazdag LEGO szett, '
        'ami összerakva is jól mutat a polcon. Ajándéknak is jó ötlet, '
        'főleg ha valaki szereti a LEGO-t vagy az állatokat." '
        'A példát csak akkor alkalmazd, ha az adott termékhez való. '
        'Kerüld az olyan robotikus kifejezéseket, mint "a termékkel kapcsolatos '
        'kérdéseket szívesen fogadom", "tökéletes választás", "igazán '
        'különleges" vagy "a részleteket üzenetben egyeztetjük". '
        'Ne használj emojit, felsorolást, reklámszöveget. '
        'Az állapotot csak akkor említsd, ha az adatokban igazolt. '
        'Zárás: "Ha bármi kérdésed van, írj nyugodtan!" majd külön sorban '
        '"'+FOOTER+'". Csak a kész leírást add vissza.\n'
        +'\n'.join(context))

def clean_ai(text,product):
    raw=str(text or '').strip()
    if len(raw)<40 or len(raw)>1500:return fallback(product.get('title'))
    lower=raw.casefold()
    if any(bad in lower for bad in BANNED):return fallback(product.get('title'))
    condition=str(product.get('condition_text') or '')
    if ('bontatlan' in lower or 'gyári csomagolás' in lower) and condition!='Új, bontatlan (ellenőrizve)':
        return fallback(product.get('title'))
    if ('hibátlanul működik' in lower or 'kipróbáltam' in lower) and not product.get('verified_facts'):
        return fallback(product.get('title'))
    while raw.endswith(FOOTER):
        raw=raw[:-len(FOOTER)].strip()
    raw=re.sub(r'\n{3,}','\n\n',raw)
    if not raw.lower().startswith('eladó '):
        raw=product_line(product.get('title'))+'\n\n'+raw
    if 'írj' not in raw.casefold() and 'kérdés' not in raw.casefold():
        raw+='\n\nHa bármi kérdésed van, írj nyugodtan!'
    return raw.strip()+'\n\n'+FOOTER
