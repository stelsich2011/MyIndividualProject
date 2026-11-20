import json
from pathlib import Path
import sys
from oge_checker.grid import refine_boxes
from oge_checker.image_io import read_image,write_image

for argument in sys.argv[1:]:
    root=Path(argument)
    path=root/'manifest.json'
    original=path.read_bytes()
    backup=root/'manifest_before_grid_v2.json'
    if not backup.exists():
        backup.write_bytes(original)
    data=json.loads(original)
    count=0
    for page in data['pages']:
        if page['status']!='prepared':
            continue
        image=read_image(root/page['aligned'])
        boxes={name:item['box'] for name,item in page['fields'].items()}
        boxes,diagnostics=refine_boxes(image,boxes)
        page['field_alignment']=diagnostics
        count+=bool(diagnostics['left'])
        for name,box in boxes.items():
            item=page['fields'][name]
            item['box']=box
            x1,y1,x2,y2=box
            write_image(root/item['image'],image[y1:y2,x1:x2])
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(argument,'adapted',count,'/',len(data['pages']))
