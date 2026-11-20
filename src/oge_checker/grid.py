
import cv2
import numpy as np
from .template import fields


def grid_rows(gray, area, expected):
    x1, y1, x2, y2 = area
    mask = (gray[y1:y2, x1:x2] < 220).astype(np.uint8)
    density = cv2.dilate(mask, np.ones((11, 1), np.uint8)).mean(axis=1)
    active = np.flatnonzero((density > .28) & (density < .85))
    if not len(active):
        return []
    groups = [g for g in np.split(active, np.where(np.diff(active) > 3)[0] + 1) if 2 <= g[-1]-g[0]+1 <= 18]
    centers = [float(np.average(g, weights=density[g])) + y1 for g in groups]
    pairs = [(a, b) for a, b in zip(centers, centers[1:]) if 38 <= b-a <= 75]
    if len(pairs) != expected or any(b[0]-a[1] < 5 for a,b in zip(pairs,pairs[1:])):
        return []
    return [(round(a-9), round(b+9)) for a,b in pairs]


def refine_boxes(image, boxes):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    regions = [('left', (650,1080,960,2290), 17, [f'answer_{n:02}' for n in range(1,18)]),
               ('right', (1580,1070,1910,1290), 2, ['answer_18','answer_19']),
               ('replacements', (570,2330,900,2560), 3, [])]
    result = {name:list(box) for name,box in boxes.items()}
    diagnostics = {}
    for label, area, count, names in regions:
        rows = grid_rows(gray, area, count)
        diagnostics[label] = bool(rows)
        if not rows:
            if label == 'right' and diagnostics.get('left'):
                reference = fields()
                shift = result['answer_01'][1]-reference['answer_01'][1]
                for name in names:
                    result[name][1] = reference[name][1] + shift
                    result[name][3] = reference[name][3] + shift
                diagnostics['right_fallback'] = True
            continue
        if names:
            for name, (top,bottom) in zip(names,rows):
                result[name][1], result[name][3] = top,bottom


    return result, diagnostics


def recovery_rows(gray, area, expected):
    pass
    x1,y1,x2,y2=area
    density=cv2.dilate((gray[y1:y2,x1:x2]<220).astype(np.uint8),np.ones((11,1),np.uint8)).mean(axis=1)
    active=np.flatnonzero((density>.22)&(density<.7))
    if not len(active): return []
    groups=[g for g in np.split(active,np.where(np.diff(active)>3)[0]+1)
            if 2<=g[-1]-g[0]+1<=18 and density[g].max()<.65]
    centers=[float(np.average(g,weights=density[g]))+y1 for g in groups]
    for start in range(min(3,len(centers))):
        borders=centers[start:start+expected*2]
        if len(borders)!=expected*2 or not 1090<=borders[0]<=1170: continue
        pairs=list(zip(borders[::2],borders[1::2]))
        if (all(35<=b-a<=85 for a,b in pairs)
                and all(10<=b[0]-a[1]<=50 for a,b in zip(pairs,pairs[1:]))):
            return [(round(a-9),round(b+9)) for a,b in pairs]
    return []


def recovery_grid(image):
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    left=recovery_rows(gray,(650,1095,960,2420),17)
    right=recovery_rows(gray,(1300,1085,1570,1270),2)
    return left,right


def refine_recovered_boxes(image, boxes):
    result={name:list(box) for name,box in boxes.items()}
    left,right=recovery_grid(image)
    if not left or not right:
        raise ValueError('Не подтверждены все 19 строк ответов восстановленного бланка')
    for name,row in zip([f'answer_{n:02}' for n in range(1,20)],left+right):
        result[name][1],result[name][3]=row


    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    replacement_rows=[]
    for x1,x2 in ((570,900),(1270,1500)):
        y1=left[-1][1]+60
        density=cv2.dilate((gray[y1:,x1:x2]<220).astype(np.uint8),np.ones((11,1),np.uint8)).mean(axis=1)
        active=np.flatnonzero((density>.22)&(density<.7))
        groups=[g for g in np.split(active,np.where(np.diff(active)>3)[0]+1)
                if len(g) and 8<=g[-1]-g[0]+1<=18 and density[g].max()<.6]
        centers=[float(np.average(g,weights=density[g]))+y1 for g in groups[:6]]
        pairs=list(zip(centers[::2],centers[1::2]))
        if len(pairs)!=3 or any(not 35<=b-a<=110 for a,b in pairs):
            replacement_rows=[];break
        replacement_rows.append([(round(a-7),round(b+7)) for a,b in pairs])
    if replacement_rows:
        top=min(row[0] for side in replacement_rows for row in side)
        bottom=max(row[1] for side in replacement_rows for row in side)
        result['replacements'][1:4:2]=[top,min(image.shape[0],bottom)]
        replacement_rows=[[(a-top,b-top) for a,b in side] for side in replacement_rows]
    return result,{'left':True,'right':True,'recovery_rows':True,'replacement_rows':replacement_rows}


def clean_recovered_grid(image):
    pass
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY) if image.ndim==3 else image.copy()
    mask=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    count,labels,stats,centers=cv2.connectedComponentsWithStats(mask)
    remove=np.zeros(count,np.uint8)
    thin=(stats[1:,2]<=7)&(stats[1:,3]<=.75*gray.shape[0])
    for i,((x,y,w,h,area),(cx,cy)) in enumerate(zip(stats[1:],centers[1:]),1):
        if not thin[i-1]: continue


        neighbors=centers[1:][thin & (np.abs(centers[1:,0]-cx)<=3)]
        bins=np.unique((neighbors[:,1]*7/gray.shape[0]).astype(int))
        if len(neighbors)>=4 and len(bins)>=4 and np.ptp(neighbors[:,1])>=.6*gray.shape[0]:
            remove[i]=1
    result=gray.copy();result[remove[labels]>0]=255
    return result,int(remove.sum())
