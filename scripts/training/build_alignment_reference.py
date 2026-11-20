from pathlib import Path
import hashlib
import json
import cv2
import numpy as np
from oge_checker.image_io import read_image, write_image

image=read_image('data/processed/calibration/page_001/aligned.png')
gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
sanitized=np.full_like(gray,255)
regions=[(70,610,1920,720),(70,1050,1920,1090),(1050,1300,1900,2280),(70,2300,1900,2330)]
for x1,y1,x2,y2 in regions:
    sanitized[y1:y2,x1:x2]=gray[y1:y2,x1:x2]
points,descriptors=cv2.SIFT_create(nfeatures=4000).detectAndCompute(sanitized,None)
root=Path('src/oge_checker/models')
path=root/'form_anchors.npz'
np.savez_compressed(path,points=np.float32([p.pt for p in points]),descriptors=descriptors)
metadata={'version':1,'template':'oge_math_form1_v1','features':len(points),'regions':regions,
          'description':'SIFT descriptors from whitelisted printed text; all other pixels replaced by white before extraction.',
          'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(root/'form_anchors.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
write_image('data/processed/alignment_reference_sanitized.png',sanitized)
print(json.dumps(metadata))
