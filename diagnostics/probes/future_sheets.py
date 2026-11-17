import json,gzip,base64,io
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from paths import R
OUT=R/'analyses/future_sheets';OUT.mkdir(parents=True,exist_ok=True)
font=ImageFont.load_default()
manifest=[]
for seed in range(200000,200020):
    cells=[]
    for layout in ('original','swapped'):
        for target in ('red','blue'):
            ident=f'motus_{seed}_{layout}_{target}';p=R/'predictions'/ident/'0/future.npz'
            if not p.exists():continue
            a=np.load(p)['frames'][0].transpose(1,2,3,0)
            with gzip.open(R/'runs'/ident/'model_io/0.json.gz','rt') as f:body=json.load(f)
            obs=Image.open(io.BytesIO(base64.b64decode(body['request']['observation']['images']['1']))).convert('RGB')
            cells.append((ident,obs,a))
    if len(cells)!=4:continue
    # Grounding labels omitted from image panels; row identifiers are stored separately.
    canvas=Image.new('RGB',(320*5,280*4),'white');d=ImageDraw.Draw(canvas)
    for row,(ident,obs,a) in enumerate(cells):
        ims=[obs]+[Image.fromarray((np.clip(a[k],0,1)*255).astype('uint8')).crop((0,12,320,252)) for k in (1,3,5,7)]
        for col,im in enumerate(ims):
            canvas.paste(im.resize((320,240)),(col*320,row*280+35));d.text((col*320+8,row*280+8),f'Row {row+1}: '+('Observed' if col==0 else f'Forecast {2*(2*col)} actions'),font=font,fill='black')
    path=OUT/f'seed{seed}.png';canvas.save(path)
    manifest.append(dict(seed=seed,path=str(path),rows=[c[0] for c in cells],forecast_indices=[1,3,5,7],labels_hidden=True))
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2));print('sheets',len(manifest))
