import gzip
import json
from pathlib import Path
import re
import time
import argparse
import cv2
import numpy as np
from oge_checker.digits import split_symbols, features
from oge_checker.image_io import read_image

parser=argparse.ArgumentParser(description='Обучение локального HOG/SVM на MNIST и размеченных клетках ОГЭ.\n\nИспользуются только ранее опубликованные настроечные страницы: 1–23,44,88.\nНовые страницы data/processed/accuracy_v2 никогда не читаются этим сценарием.\n')
parser.add_argument('--weight',type=int,default=1)
parser.add_argument('--gamma',type=float,default=.5)
parser.add_argument('--output',type=Path,default=Path('data/processed/numeric_training'))
args=parser.parse_args()
out = args.output
out.mkdir(parents=True, exist_ok=True)
samples, labels, pages, fields = [], [], [], []
old = json.loads(Path('data/processed/recognition/corrections.json').read_text(encoding='utf-8'))
truth = {f['id']: f['corrected_text'] for f in old['fields'] if f['reviewed']}
extra = json.loads(Path('data/processed/benchmark/transcription.json').read_text(encoding='utf-8'))['answers']
truth.update({f'{p}:answer_{n:02}': text for p, values in extra.items() for n,text in enumerate(values,1) if text is not None})
for root in (Path('data/processed/numeric_training/prepared'),):
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    for page in manifest['pages']:
        if page['status'] != 'prepared':
            continue
        for name, item in page['fields'].items():
            identifier = f"{page['page']}:{name}"
            expected = truth.get(identifier)
            if not name.startswith('answer_') or expected is None:
                continue
            image = read_image(root/item['image'])
            symbols = split_symbols(image)
            accepted = re.fullmatch(r'-?[0-9]+(?:,[0-9]+)?', expected) is not None
            if accepted and len(symbols) == len(expected):
                for symbol, label in zip(symbols, expected):
                    samples.append(features(symbol['image'],symbol['geometry']))
                    labels.append(10 if label==',' else (11 if label=='-' else int(label))); pages.append(page['page'])
            fields.append({'id':identifier,'expected':expected,'symbols':symbols})
X = np.asarray(samples,np.float32); Y = np.asarray(labels,np.int32); groups = np.asarray(pages)
np.savez_compressed(out/'domain_samples.npz',features=X,labels=Y,pages=groups)
print('domain samples',len(Y),'pages',len(set(pages)),flush=True)
raw = gzip.decompress(Path('data/external/mnist/train-images-idx3-ubyte.gz').read_bytes())
images = np.frombuffer(raw,np.uint8,offset=16).reshape(-1,28,28)
targets = np.frombuffer(gzip.decompress(Path('data/external/mnist/train-labels-idx1-ubyte.gz').read_bytes()),np.uint8,offset=8)
rng = np.random.default_rng(42)
indices = np.concatenate([rng.choice(np.flatnonzero(targets==n),600,replace=False) for n in range(10)])
mnist = np.asarray([features(images[i]) for i in indices],np.float32)
mnist_y = targets[indices].astype(np.int32)
np.savez_compressed(out/'mnist_features.npz',features=mnist,labels=mnist_y)

def train(x,y):
    svm = cv2.ml.SVM_create()
    svm.setType(cv2.ml.SVM_C_SVC); svm.setKernel(cv2.ml.SVM_RBF)
    svm.setC(12); svm.setGamma(args.gamma)
    svm.train(np.vstack([mnist,np.tile(x,(args.weight,1))]),cv2.ml.ROW_SAMPLE,np.concatenate([mnist_y,np.tile(y,args.weight)]))
    knn = cv2.ml.KNearest_create()
    knn.train(np.vstack([mnist,x]),cv2.ml.ROW_SAMPLE,np.concatenate([mnist_y,y]).astype(np.float32))
    return svm,knn

def predict(svm,knn, symbols):
    if not symbols:
        return '',[],[],[]
    x = np.asarray([features(s['image'],s['geometry']) for s in symbols],np.float32)
    result = svm.predict(x)[1].reshape(-1).astype(int)
    _, _, near, distances = knn.findNearest(x,5)
    agreements = [(row==label).mean() for row,label in zip(near,result)]
    minima = [float(d[row==label].min()) if np.any(row==label) else 100. for row,d,label in zip(near,distances,result)]
    value = ''.join(',' if n==10 else ('-' if n==11 else str(n)) for n in result)
    return value,list(map(float,agreements)),minima,result.tolist()

validation = []
for fold in range(5):
    training = groups%5 != fold
    svm,knn = train(X[training],Y[training])
    for field in fields:
        if int(field['id'].split(':')[0])%5 != fold:
            continue
        value,agreements,distances,_ = predict(svm,knn,field['symbols'])
        validation.append({'id':field['id'],'expected':field['expected'],'numeric':value,'agreements':agreements,'distances':distances})
    print('fold',fold,'done',flush=True)
(out/'cross_validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
svm,knn = train(X,Y)
svm.save(str(out/'digits_svm.xml'))
np.savez_compressed(out/'digits_neighbors.npz',features=np.vstack([mnist,X]),labels=np.concatenate([mnist_y,Y]))
print('cross validated numeric matches',sum(x['numeric']==x['expected'] for x in validation),'/',len(validation),flush=True)
