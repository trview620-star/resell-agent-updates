"""Seven-marketplace listing packages plus opt-in, seller-authorized eBay adapter."""
from __future__ import annotations
import io,json,re,zipfile
from urllib.parse import quote
import requests
from . import db
from .listing import generate_draft

MODES={
    'Vinted':'Prepared listing packet; manual submission',
    'Facebook Marketplace':'Prepared listing packet; manual submission',
    'Jófogás':'Prepared packet; XML feed requires separate approved account setup',
    'Vatera':'Prepared packet; importer setup requires verification',
    'HardverApró':'Prepared listing packet; manual submission',
    'eBay':'Official Inventory API adapter; OAuth and seller setup required',
    'Amazon':'Prepared packet; SP-API account integration not yet configured',
}

def prepare_drafts(product_id,marketplaces=None):
    product=db.row('SELECT * FROM products WHERE id=?',(product_id,))
    if not product:raise ValueError('Unknown product')
    selected=list(marketplaces) if marketplaces is not None else list(db.PLATFORMS)
    if any(m not in db.PLATFORMS for m in selected):raise ValueError('Unsupported marketplace')
    result=[]
    for m in selected:
        title,description=generate_draft(product,m)
        lid=db.insert_listing(product_id,m,title,description,int(product['target_price']))
        result.append({'marketplace':m,'listing_id':lid})
    return result

def listing_package(product_id,marketplaces=None):
    p=db.row('SELECT * FROM products WHERE id=?',(product_id,))
    if not p:raise ValueError('Unknown product')
    selected=list(marketplaces) if marketplaces is not None else list(db.PLATFORMS)
    if any(m not in db.PLATFORMS for m in selected):raise ValueError('Unsupported marketplace')
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('master.json',json.dumps({
            'product_id':product_id,'created_at':db.utcnow(),
            'supplier_url':p['supplier_url'],'supplier_price_huf':p['supplier_price'],
            'stock_status':p['stock_status'],'fulfillment':p['fulfillment'],
            'caution':'Prepared drafts only; verify product, actual price and images before publication.'
        },ensure_ascii=False,indent=2))
        for m in selected:
            listing=db.row('SELECT * FROM listings WHERE product_id=? AND marketplace=? ORDER BY id DESC LIMIT 1',(product_id,m))
            title,desc=generate_draft(p,m)
            if listing:
                title,desc=listing['title'],listing['description']
                price=listing['price']
            else: price=p['target_price']
            name=re.sub(r'[^A-Za-z0-9_-]+','_',m)
            archive.writestr('listings/'+name+'.txt',
                'Marketplace: '+m+'\nTitle: '+title+'\nPrice (HUF): '+str(price)+'\n\n'+desc+'\n')
        for photo in db.rows('SELECT * FROM photos WHERE product_id=?',(product_id,)):
            path=db.PHOTOS/photo['filename']
            if path.is_file() and path.resolve().parent==db.PHOTOS.resolve():
                archive.write(path,'photos/original_'+str(photo['id'])+'_'+path.name)
        archive.writestr('README.txt','Drafts are not live listings. Original photos are preserved.\n')
    return output.getvalue()

class EbayInventory:
    """Explicit user-initiated API publishing. No background spending or auto-posting."""
    def __init__(self,token,environment='sandbox'):
        if environment not in ('sandbox','production'):raise ValueError('Invalid environment')
        if not isinstance(token,str) or not token.strip():raise ValueError('OAuth token needed')
        self.base='https://api.sandbox.ebay.com' if environment=='sandbox' else 'https://api.ebay.com'
        self.token=token
    def _call(self,method,path,data):
        try:
            r=requests.request(method,self.base+'/sell/inventory/v1/'+path,
                headers={'Authorization':'Bearer '+self.token,
                    'Content-Type':'application/json','Content-Language':'en-US'},
                json=data,timeout=(5,25))
            if not 200<=r.status_code<300:
                raise ValueError('eBay API returned HTTP '+str(r.status_code))
            return r.json() if r.content else {}
        except requests.RequestException as e:
            raise ValueError('eBay API request failed') from e
    def publish(self,*,sku,title,description,price,currency,category_id,condition,
                merchant_location_key,marketplace_id,payment_policy_id,return_policy_id,
                fulfillment_policy_id,image_urls,aspects,quantity=1):
        required=(sku,title,description,price,currency,category_id,condition,
                merchant_location_key,marketplace_id,payment_policy_id,
                return_policy_id,fulfillment_policy_id)
        if any(not str(x).strip() for x in required):raise ValueError('Missing mandatory listing fields')
        if not isinstance(image_urls,list) or not image_urls or any(not str(u).startswith('https://') for u in image_urls):
            raise ValueError('Provide public HTTPS product images')
        if not isinstance(aspects,dict) or not aspects or any(not isinstance(v,list) or not v for v in aspects.values()):
            raise ValueError('Provide category-specific aspects')
        try:
            if float(price)<=0 or quantity<1 or quantity>1000:raise ValueError()
        except (ValueError,TypeError):
            raise ValueError('Invalid price or quantity')
        code=quote(sku,safe='')
        self._call('PUT','inventory_item/'+code,{
            'availability':{'shipToLocationAvailability':{'quantity':quantity}},
            'condition':condition,
            'product':{'title':title,'description':description,'aspects':aspects,
                       'imageUrls':image_urls}})
        offer=self._call('POST','offer',{
            'sku':sku,'marketplaceId':marketplace_id,'format':'FIXED_PRICE',
            'availableQuantity':quantity,'categoryId':category_id,
            'merchantLocationKey':merchant_location_key,
            'listingPolicies':{'paymentPolicyId':payment_policy_id,
                'returnPolicyId':return_policy_id,'fulfillmentPolicyId':fulfillment_policy_id},
            'pricingSummary':{'price':{'currency':currency,'value':str(price)}},
            'listingDescription':description})
        offer_id=offer.get('offerId')
        if not offer_id:raise ValueError('eBay did not return an offer ID')
        published=self._call('POST','offer/'+quote(str(offer_id),safe='')+'/publish',{})
        return {'offer_id':offer_id,'listing_id':published.get('listingId')}
