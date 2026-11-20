
from pathlib import Path
import re
import cv2
import numpy as np

HOG = cv2.HOGDescriptor((32, 32), (16, 16), (8, 8), (8, 8), 9)


def grid_geometry(gray):
    pitch = gray.shape[1] / 17
    def score(offset):
        xs=np.rint(offset+np.arange(7,17)*pitch).astype(int)
        xs=xs[(xs>=0)&(xs<gray.shape[1])]
        return float(np.median((gray[:,xs]<128).sum(axis=0))) if len(xs) else 0
    offset=max(np.arange(max(1,round(pitch))),key=score)
    return pitch, offset-pitch if offset>pitch/2 else offset


def separator_marks(image):
    pass
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY) if image.ndim==3 else image
    mask=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    _,_,stats,centers=cv2.connectedComponentsWithStats(mask)
    pitch,offset=grid_geometry(gray)
    marks=[]
    for (x,y,w,h,area),(cx,cy) in zip(stats[1:],centers[1:]):
        border_distance=abs((cx-offset+pitch/2)%pitch-pitch/2)
        if 3<=area and w<=8 and h<=10 and .3*gray.shape[0]<cy<.78*gray.shape[0] and border_distance>7:
            marks.append([float(cx),float(cy)])
    return marks


def has_small_separator(image):
    return bool(separator_marks(image))


def split_symbols(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)

    keep = np.zeros(count, np.uint8)
    for i, (x, y, w, h, area) in enumerate(stats[1:], 1):
        if not (w <= 6 and h <= 7) and area >= 12:
            keep[i] = 1
    mask = keep[labels] * 255
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask)
    parts = [(s, centers[i + 1]) for i, s in enumerate(stats[1:])]
    if not parts:
        return []

    pitch,offset = grid_geometry(gray)
    grouped = {}
    for (x, y, w, h, area), center in parts:
        cell = max(0, int((center[0] - offset) // pitch))
        grouped.setdefault(cell, []).append((x, y, w, h, area))
    symbols = []
    for cell, shapes in sorted(grouped.items()):
        x1, y1 = min(s[0] for s in shapes), min(s[1] for s in shapes)
        x2, y2 = max(s[0] + s[2] for s in shapes), max(s[1] + s[3] for s in shapes)
        patch = mask[y1:y2, x1:x2]
        if patch.size:
            symbols.append({'cell': cell, 'box': [x1, y1, x2-x1, y2-y1], 'image': patch})
    max_height = max((s['box'][3] for s in symbols), default=1)
    top = min((s['box'][1] for s in symbols if s['box'][3] >= .65 * max_height), default=0)
    for s in symbols:
        x, y, w, h = s['box']
        s['geometry'] = [h / max_height, (y - top) / max_height]
        if w >= 1.8 * h and h < .4 * max_height:
            s['kind'] = '-'
        elif h < .82 * max_height and y >= top + .35 * max_height and w < .85 * max_height:
            s['kind'] = ','
        else:
            s['kind'] = 'digit'
    return symbols


def normalize_digit(mask):
    ys, xs = np.where(mask > 0)
    if not len(xs):
        return np.zeros((32, 32), np.uint8)
    mask = mask[ys.min():ys.max()+1, xs.min():xs.max()+1]
    h, w = mask.shape
    scale = 22 / max(h, w)
    patch = cv2.resize(mask, (max(1, round(w*scale)), max(1, round(h*scale))), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((32, 32), np.uint8)
    h, w = patch.shape
    canvas[(32-h)//2:(32-h)//2+h, (32-w)//2:(32-w)//2+w] = patch
    m = cv2.moments(canvas)
    if abs(m['mu02']) > 1e-2:
        skew = np.clip(m['mu11'] / m['mu02'], -.7, .7)
        canvas = cv2.warpAffine(canvas, np.float32([[1, skew, -16*skew], [0, 1, 0]]), (32,32), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR)
    return canvas


def features(mask, geometry=None):
    geometry = geometry if geometry is not None else [1., 0.]
    return np.concatenate([HOG.compute(normalize_digit(mask)).reshape(-1), np.asarray(geometry, np.float32)*2])


def combine_numeric(base, numeric, agreements, distances, agreement=.4, distance=3., allow_separator_deletion=False, boxes=None, small_separators=None):
    pass
    if not re.fullmatch(r'-?[0-9]+(?:,[0-9]+)?', numeric):
        return base
    if re.search(r'[A-Za-zА-Яа-я]{2}|[0-9][A-Za-zА-Яа-я]|[()%°²³]', base):
        return base
    good = [a>=agreement and d<=distance for a,d in zip(agreements,distances)]
    if len(good) != len(numeric):
        return base


    table = [[0]*(len(numeric)+1) for _ in range(len(base)+1)]
    for i in range(len(base)+1): table[i][0]=i
    for j in range(len(numeric)+1): table[0][j]=j
    for i in range(1,len(base)+1):
        for j in range(1,len(numeric)+1):
            table[i][j]=min(table[i-1][j]+1,table[i][j-1]+1,table[i-1][j-1]+(base[i-1]!=numeric[j-1]))
    i,j=len(base),len(numeric)
    parts=[]
    while i or j:
        if i and j and table[i][j]==table[i-1][j-1]+(base[i-1]!=numeric[j-1]):
            parts.append(numeric[j-1] if good[j-1] else base[i-1]); i-=1; j-=1
        elif j and table[i][j]==table[i][j-1]+1:
            if good[j-1]: parts.append(numeric[j-1])
            j-=1
        else:



            protect_point=not allow_separator_deletion
            if boxes is not None and len(boxes)==len(numeric) and small_separators is not None:
                left=boxes[j-1][0]+boxes[j-1][2] if j else 0
                right=boxes[j][0] if j<len(boxes) else float('inf')
                protect_point=left>right or any(left-2<=mark[0]<=right+2 for mark in small_separators)
            if not all(good) or base[i-1]==',' or (base[i-1]=='.' and protect_point): parts.append(base[i-1])
            i-=1
    result=''.join(reversed(parts))
    return result if re.fullmatch(r'-?[0-9]+(?:,[0-9]+)?',result) else base


class NumericOCR:
    def __init__(self, model_dir=None):
        self.root = Path(model_dir) if model_dir else Path(__file__).with_name('models')


        storage = cv2.FileStorage((self.root/'digits_svm.xml').read_text(encoding='utf-8'),
                                 cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
        self.svm = cv2.ml.SVM_create()
        self.svm.read(storage.getFirstTopLevelNode())
        storage.release()
        with np.load(self.root/'digits_neighbors.npz',allow_pickle=False) as data:
            self.knn = cv2.ml.KNearest_create()
            self.knn.train(data['features'],cv2.ml.ROW_SAMPLE,data['labels'].astype(np.float32))

    def read(self, image):
        symbols = split_symbols(image)
        if not symbols:
            return {'candidate':'','agreements':[],'distances':[],'boxes':[]}
        x = np.asarray([features(s['image'],s['geometry']) for s in symbols],np.float32)
        values = self.svm.predict(x)[1].reshape(-1).astype(int)
        _,_,near,distances = self.knn.findNearest(x,5)
        result = ''.join(',' if n==10 else ('-' if n==11 else str(n)) for n in values)
        agreement = [float((row==label).mean()) for row,label in zip(near,values)]
        distance = [float(d[row==label].min()) if np.any(row==label) else 100. for row,d,label in zip(near,distances,values)]
        marks=separator_marks(image)
        return {'candidate':result,'agreements':agreement,'distances':distance,
                'boxes':[list(map(int,s['box'])) for s in symbols],
                'allow_separator_deletion':not marks,'small_separators':marks}
