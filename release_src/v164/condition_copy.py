"""Verified Hungarian condition labels for seller-approved marketplace drafts.

A catalog search hit is NOT evidence of factory-sealed packaging.
Only explicit confirmation in the product details enables condition claims.
"""
from __future__ import annotations

import re
from . import db

STATES = {'unknown': 'Unknown / verify',
          'new': 'Új (ellenőrizve)',
          'sealed': 'Új, bontatlan (ellenőrizve)'}
SUFFIXES = {'new': 'Új', 'sealed': 'Új, bontatlan'}
DETAILS = {'new': 'Állapot: új, nem használt.',
           'sealed': 'Állapot: új, bontatlan, gyári csomagolásban.'}
FOOTER = 'Hasonló termékekért nézd meg a többi hirdetésemet.'


def state_of(product):
    value = str((product or {}).get('condition_text') or '')
    if value == STATES['sealed']:
        return 'sealed'
    if value == STATES['new']:
        return 'new'
    return 'unknown'


def title_for(title, state):
    original = re.sub(r'\s*[–-]\s*Új(?:,\s*bontatlan)?\s*$', '',
                      str(title or '').strip(), flags=re.I)
    label = SUFFIXES.get(state)
    if not label:
        return original[:80]
    suffix = ' – ' + label
    return original[:80 - len(suffix)].rstrip(' -–') + suffix


def description_for(description, state, marketplace='Vinted'):
    raw = str(description or '').strip()
    # Only remove state lines produced by this application; keep seller copy.
    rows = [r for r in raw.splitlines() if r.strip() not in DETAILS.values()]
    raw = '\n'.join(rows).strip()
    # Strip only our standard trailer, to avoid duplicates across updates.
    while raw.endswith(FOOTER):
        raw = raw[:-len(FOOTER)].rstrip()
    detail = DETAILS.get(state)
    if detail:
        first, separator, remainder = raw.partition('\n\n')
        if separator:
            raw = first.strip() + '\n\n' + detail + '\n\n' + remainder.strip()
        else:
            raw = (raw + '\n\n' if raw else '') + detail
    if marketplace not in ('eBay', 'Amazon'):
        raw = (raw + '\n\n' if raw else '') + FOOTER
    return raw


def confirm_condition(product_id, selected, *, verified=False):
    """Change only draft/ready listings; do not modify published listings."""
    if selected not in STATES:
        raise ValueError('Ismeretlen termékállapot.')
    if selected != 'unknown' and not verified:
        raise ValueError('Előbb igazold a beszállító által megerősített állapotot.')
    product = db.row('SELECT * FROM products WHERE id=?', (product_id,))
    if not product:
        raise ValueError('Nem található a termék.')
    raw = description_for(product.get('description'), 'unknown')
    new_copy = description_for(raw, selected)
    db.update_product(product_id, condition_text=STATES[selected],
                      description=new_copy)
    for draft in db.rows(
        "SELECT * FROM listings WHERE product_id=? AND status IN ('draft','ready')",
        (product_id,)):
        db.update_listing(
            draft['id'],
            title=title_for(product['title'], selected),
            description=description_for(new_copy, selected,
                                        draft['marketplace']))
    return new_copy
