"""Shot planning: four distinct roles and context-appropriate home scenes.

Text/image generators can still distort markings; every generated photograph
remains a labelled illustration and must be checked against the real item.
"""
from __future__ import annotations
from io import BytesIO
from PIL import Image, UnidentifiedImageError

GLOBAL=(
    'You are editing a reference image for a casual secondhand listing. '
    'The product identity is fixed. Preserve exact product geometry, color, '
    'surface textures, brand logo, typography, printed words, pictograms, '
    'symbols, drawings, labels, and packaging graphics. '
    'Do NOT redesign, invent, repaint, hallucinate, retype, or substitute '
    'any logo, letter, symbol, graphic, control or accessory. '
    'Do not create an unopened box, security seal, barcode or packaging '
    'that is not in the reference. Never claim to show an unseen backside '
    'from a single reference. If a detail is not visible, use a visible detail. '
    'Natural home phone-photo feel: ordinary lighting, slightly imperfect '
    'framing, real shadows, no studio product-ad styling, no cinematic color, '
    'no added text, no watermark. Use only one scene, not a collage. '
)

SCENES={
    'gaming_headset':(
        'A tidy but realistic bedroom gaming desk beside a monitor or PC. '
        'Background softly blurred, ordinary desk lamp or window light. '
        'No kitchen, dining table, cooking utensils, studio or floating product.'),
    'gaming_accessory':(
        'A simple home computer desk with keyboard or monitor blurred in the '
        'distance. No kitchen, cooking counter or artificial studio props.'),
    'kitchen':(
        'A normal Hungarian home kitchen counter, imperfect natural daylight, '
        'no staged stock-photo aesthetic.'),
    'boardgame':(
        'A casual living-room or dining-room wooden tabletop, '
        'subtle home setting, no polished showroom styling.'),
    'lego':(
        'An ordinary living-room shelf or desk with softly blurred home '
        'decor, natural daylight, no showroom or fantasy setup.'),
    'clothes':(
        'An everyday bedroom dresser, wardrobe corner or neatly made bed. '
        'No showroom or fake mannequin.'),
    'other':(
        'An ordinary Hungarian home wooden tabletop or bookshelf, '
        'soft daylight and subtle natural shadows. No studio gear.')
}

def category(title):
    title=str(title or '').casefold()
    if any(x in title for x in ('fejhallgató','fülhallgató','headset','headphone',
                                'headphones','earbuds','airpods','buds')):
        return 'gaming_headset' if any(x in title for x in (
            'gamer','gaming','razer','hyperx','steelseries','logitech g')) else 'gaming_accessory'
    if any(x in title for x in ('controller','kontroller','billentyűzet',
                                'gaming egér','stream deck','webkamera','monitor')):
        return 'gaming_accessory'
    if any(x in title for x in ('airfryer','kávéfőző','robotporszívó',
                                'konyhai','főző','sütő','kávégép')):
        return 'kitchen'
    if any(x in title for x in ('társasjáték','kártyajáték','dobble','monopoly',
                                'dixit','azul','catan','hitster','ticket to ride')):
        return 'boardgame'
    if 'lego' in title:return 'lego'
    if any(x in title for x in ('cipő','ruha','farmer','kabát','pulóver',
                                'póló','dress','sneaker')):
        return 'clothes'
    return 'other'

def role(slot):
    if slot==1:return 'Teljes termék'
    if slot==2:return 'Közeli részlet'
    if slot==3:return 'Más kompozíció'
    if slot==4:return 'Csomagolás vagy másik részlet'
    raise ValueError('A képsorszámnak 1–4 között kell lennie.')

def prompt_for(title,slot):
    scene=SCENES[category(title)]
    c=category(title)
    if slot==1:
        framing=('SHOT 1/4: show the WHOLE item and all its visible parts '
                 'in one natural main listing shot. Entire outline in frame. '
                 'This is the hero photograph, not a close-up.')
    elif slot==2:
        detail={
          'gaming_headset':'ear cushion, ear cup stitching or visible headband padding',
          'gaming_accessory':'a visible button, port, label or distinctive surface',
          'lego':'an identifiable printed part or visible product-box detail',
          'kitchen':'a visible knob, control, label or surface texture',
          'boardgame':'visible box art or a visible game component',
          'clothes':'visible fabric weave, stitching, lace or label',
          'other':'a distinctive visible detail of the real product'
        }[c]
        framing=('SHOT 2/4: a distinct tight CLOSE-UP crop of '+detail+'. '
                 'Only select a detail actually present and legible in the '
                 'source image. Avoid inventing unseen surfaces or marks. '
                 'Do not reproduce the full item shot.')
    elif slot==3:
        framing=('SHOT 3/4: a clearly different, wide or medium framing '
                 'of the complete item, placed naturally on another part '
                 'of the appropriate home setting. Change composition and '
                 'camera position only within angles justified by the source; '
                 'do not synthesize an unseen product side. Not a copy '
                 'of shot 1.')
    elif slot==4:
        framing=('SHOT 4/4: if the ACTUAL source shows the manufacturer box, '
                 'make an accurate crop of that genuine visible packaging, '
                 'keeping every printed logo and letter unchanged. '
                 'Otherwise use a DIFFERENT close-up of another visible '
                 'product detail, such as the model label, cable port, '
                 'texture or control. Absolutely no invented boxes or seals. '
                 'Must differ substantially from shots 1, 2, and 3.')
    else:
        raise ValueError('Invalid shot number')
    return GLOBAL + 'SCENE: ' + scene + ' FRAMING: ' + framing

def difference_warning(images):
    """Find exact or near-identical previews to flag for manual regeneration.

    Never treats this heuristic as proof that an image preserves markings.
    """
    signatures=[]
    flagged=[]
    for slot,raw in images:
        if not raw:
            continue
        try:
            with Image.open(BytesIO(raw)) as image:
                image=image.convert('L').resize((9,8))
                pixels=list(image.getdata())
            bits=0
            for y in range(8):
                for x in range(8):
                    bits=(bits<<1)|int(pixels[y*9+x]>pixels[y*9+x+1])
        except (OSError,ValueError,UnidentifiedImageError):
            continue
        if any((bits^other).bit_count()<=3 for other in signatures):
            flagged.append(slot)
        signatures.append(bits)
    return flagged
