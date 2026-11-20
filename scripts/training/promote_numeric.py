import hashlib
import json
from pathlib import Path
import shutil

source=Path('data/processed/numeric_training/w1')
destination=Path('src/oge_checker/models')
destination.mkdir(parents=True,exist_ok=True)
files={}
for filename in ('digits_svm.xml','digits_neighbors.npz'):
    shutil.copyfile(source/filename,destination/filename)
    files[filename]=hashlib.sha256((destination/filename).read_bytes()).hexdigest()
metadata={'model_id':'oge_digits_hog_svm_v1','features':'OpenCV HOG32 + relative height/top; deskew; 326 dimensions',
    'svm':{'C':12,'gamma':.5,'domain_weight':1},'policy':{'min_neighbor_agreement':.4,'max_squared_distance':3.,'combination':'supported edit alignment; preserve units; protect visible decimal punctuation'},
    'training_pages':list(range(1,24))+[44,88],'heldout_pages':[24,25,26,27,28,29,30,31,32,33,34,35,37,39,40,41,42,43,45,46],
    'training_characters':997,'mnist_characters':6000,'random_seed':42,'cross_validation':'5 folds, entire pages excluded from training',
    'cross_validation_baseline':405,'cross_validation_combined':434,'cross_validation_fields':468,
    'dataset_source':'https://github.com/cvdfoundation/mnist','dataset_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('data/external/mnist').glob('train-*-ubyte.gz')},
    'files':files}
(destination/'numeric_model.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
print({name:(destination/name).stat().st_size for name in files})
