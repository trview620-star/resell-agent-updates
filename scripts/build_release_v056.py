from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from hashlib import sha256
import sys

source=Path(sys.argv[1] if len(sys.argv)>1 else "resell-agent-mvp-v0.5.5.zip")
checksum=Path(str(source)+".sha256")
assert checksum.exists(), "Missing v0.5.5 published checksum"
expected=checksum.read_text(encoding="ascii").split()[0]
assert sha256(source.read_bytes()).hexdigest()==expected, "Source ZIP fails published checksum"
with ZipFile(source) as zipfile:
    files={i.filename:zipfile.read(i.filename) for i in zipfile.infolist() if not i.is_dir()}
ROOT="resell-agent-starter/"

def replace(path,before,after):
    key=ROOT+path
    content=files[key].decode("utf-8")
    if before not in content:raise RuntimeError("Base changed unexpectedly: "+path)
    files[key]=content.replace(before,after).encode("utf-8")

replace("agent/updater.py","VERSION = '0.5.5'","VERSION = '0.5.6'")
replace("tests/test_updater.py","0.5.6","0.5.7")
replace("agent/ui_shopping.py","from . import db, shopping","from . import db, shopping, deals")
replace("agent/ui_shopping.py",
"st.caption('v0.5.3 · Hungarian Google Shopping via Serper (recommended) or SerpApi (optional).')",
"st.caption('v0.5.6 · Hungarian shopping research and model-matched retail price gaps.')")

files[ROOT+"agent/deals.py"]=r'''"""Conservative retail price-gap scanner, not a resale price predictor."""
from collections import defaultdict
import re
from .shopping import ACCESSORY_RE, model_code_from_phrase, classify_product_match
LEGO_CODE=re.compile(r'(?<!\d)(?:10|21|31|40|42|60|70|75|76|77)\d{3}(?!\d)')
BUNDLE=re.compile(r'(?i)\b(?:bundle|lot|multi[ -]?pack|2[ -]?pack|3[ -]?pack|csomag|szettben|több\s*db|csak\s*doboz|üres\s*doboz)\b')

def product_key(title, phrase):
    if not isinstance(title,str) or ACCESSORY_RE.search(title) or BUNDLE.search(title):
        return ''
    model=model_code_from_phrase(phrase)
    if model:
        return model if classify_product_match(title,phrase)[0]=='Model code matches' else ''
    if 'lego' in phrase.casefold() and 'lego' in title.casefold():
        codes=set(LEGO_CODE.findall(title))
        return next(iter(codes)) if len(codes)==1 else ''
    return ''

def find_retail_gaps(rows,phrase,minimum_spread_pct=8):
    if not isinstance(minimum_spread_pct,int) or not 0<=minimum_spread_pct<=90:
        raise ValueError('Spread threshold outside 0..90')
    grouped=defaultdict(list)
    for r in rows:
        if not isinstance(r,dict):continue
        code=product_key(r.get('title',''),phrase)
        price=r.get('price_huf')
        seller=str(r.get('merchant') or '').strip()
        if code and isinstance(price,int) and not isinstance(price,bool) and price>0 and seller and seller.casefold()!='unspecified retailer':
            grouped[code].append(r)
    output=[]
    for code,offers in grouped.items():
        merchants={}
        for r in offers:
            key=r['merchant'].casefold().strip()
            if key not in merchants or r['price_huf']<merchants[key]['price_huf']:
                merchants[key]=r
        priced=sorted(merchants.values(),key=lambda r:r['price_huf'])
        if len(priced)<2:continue
        cheap,next_cheapest=priced[:2]
        difference=next_cheapest['price_huf']-cheap['price_huf']
        percent=round(difference/next_cheapest['price_huf']*100,1)
        if percent<minimum_spread_pct:continue
        output.append(dict(model=code,product=cheap['title'],supplier=cheap['merchant'],
                           purchase_huf=cheap['price_huf'],other_supplier=next_cheapest['merchant'],
                           other_price_huf=next_cheapest['price_huf'],difference_huf=difference,
                           difference_pct=percent,merchant_count=len(priced),cheapest_offer=cheap))
    return sorted(output,key=lambda r:(r['difference_pct'],r['difference_huf']),reverse=True)

def hypothetical_profit(*,sale_price_huf,purchase_huf,supplier_shipping_huf=0,outbound_shipping_huf=0,fees_huf=0,reserve_huf=0):
    v=(sale_price_huf,purchase_huf,supplier_shipping_huf,outbound_shipping_huf,fees_huf,reserve_huf)
    if any(not isinstance(x,int) or isinstance(x,bool) or x<0 for x in v) or not purchase_huf:
        raise ValueError('Invalid money amount')
    cost=sum(v[1:])
    profit=sale_price_huf-cost
    return dict(total_cost_huf=cost,profit_huf=profit,margin_pct=round(profit*100/sale_price_huf,1) if sale_price_huf else 0)
'''.encode('utf-8')

UI='''    if found:
        st.divider()
        st.subheader('Retail price-gap scanner')
        st.caption('Compares exact-model retailer offers. Price gaps are NOT completed sales, stock confirmation or guaranteed profit.')
        threshold=st.slider('Minimum retail gap (%)',0,60,10,1)
        gaps=deals.find_retail_gaps(found,st.session_state.get('shopping_phrase',''),threshold)
        if gaps:
            st.dataframe([{'Model':d['model'],'Cheapest store':d['supplier'],'Price':money(d['purchase_huf']),
                           'Next store':d['other_supplier'],'Next price':money(d['other_price_huf']),
                           'Retail gap':money(d['difference_huf']),'Gap %':d['difference_pct'],
                           'Stores':d['merchant_count'],'Stock':'Unknown'} for d in gaps],
                         use_container_width=True,hide_index=True)
            selected=st.selectbox('Review gap',gaps,
                format_func=lambda d:f"{d['model']} · {d['supplier']} {money(d['purchase_huf'])} · {d['difference_pct']}%")
            st.markdown(f"[Inspect cheapest offer]({selected['cheapest_offer']['url']})")
            st.warning('Verify exact product, checkout price, stock, shipping and completed-sale evidence before acting.')
            if st.button('Save cheapest offer to Product finder'):
                cid,created=shopping.save_result(selected['cheapest_offer'],st.session_state.get('shopping_phrase',''))
                st.success(f"Saved candidate #{cid}.")
            with st.expander('Hypothetical profit from verified resale evidence'):
                sale=st.number_input('Your evidence-based resale price (HUF)',0,100000000,0,100)
                left,right=st.columns(2)
                inbound=left.number_input('Supplier delivery HUF',0,100000,0,100)
                outbound=right.number_input('Your delivery HUF',0,100000,0,100)
                fees=left.number_input('Marketplace fees HUF',0,100000,0,100)
                reserve=right.number_input('Packaging/returns reserve HUF',0,100000,0,100)
                if sale:
                    value=deals.hypothetical_profit(sale_price_huf=int(sale),
                        purchase_huf=selected['purchase_huf'],supplier_shipping_huf=int(inbound),
                        outbound_shipping_huf=int(outbound),fees_huf=int(fees),reserve_huf=int(reserve))
                    st.metric('Illustrative pre-tax profit',money(value['profit_huf']))
        else:
            st.info('No matching model with a qualifying difference across at least two retailers in this search.')

'''
replace('agent/ui_shopping.py',"    st.divider()\n    st.subheader('Scheduled keyword radar')",
        UI+"    st.divider()\n    st.subheader('Scheduled keyword radar')")

files[ROOT+"tests/test_deals.py"]='''import unittest
from agent.deals import find_retail_gaps, product_key, hypothetical_profit
def o(name,seller,price):return {'title':name,'merchant':seller,'price_huf':price,'url':'https://example.org'}
class DealsTests(unittest.TestCase):
    def test_model(self):
        self.assertEqual(product_key('LEGO 42154 Ford GT','LEGO Technic'),'42154')
        self.assertEqual(product_key('LEGO 42154 compatible stand','LEGO Technic 42154'),'')
        self.assertEqual(product_key('LEGO 42155','LEGO Technic 42154'),'')
    def test_price_gap(self):
        result=find_retail_gaps([o('LEGO 42154 Ford GT','A',30000),o('LEGO 42154 Ford GT','B',40000),
                                o('LEGO 42155','C',50000)],'LEGO Technic')
        self.assertEqual(result[0]['difference_huf'],10000)
        self.assertEqual(result[0]['difference_pct'],25)
    def test_same_store_not_evidence(self):
        self.assertFalse(find_retail_gaps([o('LEGO 42154','A',10000),o('LEGO 42154','A',20000)],'LEGO'))
    def test_hypothetical_profit(self):
        self.assertEqual(hypothetical_profit(sale_price_huf=20000,purchase_huf=12000,
                supplier_shipping_huf=1000,outbound_shipping_huf=1500,fees_huf=500,reserve_huf=1000)['profit_huf'],4000)
'''.encode('utf-8')
files[ROOT+'UPGRADE_TO_V056.md']=b'# v0.5.6 - Retail price-gap scanner\n\nMatches model codes across retailers without claiming verified resale prices. Uses the existing Serper shopping response, requiring no additional API requests. User data remains untouched during upgrade.\n'
output=Path('resell-agent-mvp-v0.5.6.zip')
with ZipFile(output,'w',ZIP_DEFLATED) as z:
    for name,content in files.items():z.writestr(name,content)
digest=sha256(output.read_bytes()).hexdigest()
Path(str(output)+'.sha256').write_text(digest+'  '+output.name+'\n',encoding='ascii')
print('v0.5.6 build done',digest)
