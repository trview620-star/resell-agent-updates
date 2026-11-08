"""Non-destructive light improvement. Does not replace original photographs."""
from pathlib import Path
from PIL import Image, ImageEnhance
from . import db

def improve_light(photo_id,brightness=1.1,contrast=1.06,sharpness=1.03):
    if not all(0.7<=v<=1.5 for v in (brightness,contrast,sharpness)):
        raise ValueError('Adjustment exceeds safe range')
    photo=db.row('SELECT * FROM photos WHERE id=?',(photo_id,))
    if not photo:raise ValueError('Unknown photo')
    path=db.PHOTOS/photo['filename']
    if not path.is_file() or path.resolve().parent!=db.PHOTOS.resolve():
        raise ValueError('Original photo missing')
    with Image.open(path) as original:
        original.load()
        if original.width*original.height>30_000_000:
            raise ValueError('Photo exceeds safe pixel limit')
        image=ImageEnhance.Brightness(original.convert('RGB')).enhance(brightness)
        image=ImageEnhance.Contrast(image).enhance(contrast)
        image=ImageEnhance.Sharpness(image).enhance(sharpness)
        output=path.with_name('enhanced_'+str(photo['id'])+'_'+path.stem+'.jpg')
        image.save(output,'JPEG',quality=92,optimize=True)
    return output
