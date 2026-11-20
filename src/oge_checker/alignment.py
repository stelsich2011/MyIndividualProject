from functools import lru_cache
from itertools import product
from pathlib import Path
import cv2
import numpy as np
from .template import WIDTH, HEIGHT, MARKERS
from .grid import recovery_grid

REGIONS=((.18,.28,0,.08),(.78,.94,0,.08),(0,.14,.90,1),(.88,1,.90,1))


def marker_candidates(image):
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    height,width=gray.shape
    regions=[[] for _ in REGIONS]
    for threshold in (100,140,180,210):
        mask=cv2.threshold(gray,threshold,255,cv2.THRESH_BINARY_INV)[1]
        contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x,y,w,h=cv2.boundingRect(contour)
            if not (.012*width<=w<=.04*width and .012*width<=h<=.04*width
                    and .7<=w/h<=1.4 and cv2.contourArea(contour)/(w*h)>=.85):
                continue
            center=np.float32([x+w/2,y+h/2])
            for group,(left,right,top,bottom) in zip(regions,REGIONS):
                if left<=center[0]/width<=right and top<=center[1]/height<=bottom:
                    if all(np.linalg.norm(center-p)>width*.004 for p in group):
                        group.append(center)
    return regions


def grid_evidence(aligned):
    left,right=recovery_grid(aligned)
    return {'left':bool(left),'right':bool(right)}


def marker_fallback(image):
    groups=marker_candidates(image)
    if any(not g or len(g)>4 for g in groups):
        return None
    target=np.float32(MARKERS)
    options=[]
    for combination in product(*groups):
        source=np.float32(combination)


        design=np.column_stack((source,np.ones(4)))
        coefficients=np.linalg.lstsq(design,target,rcond=None)[0]
        residual=float(np.sqrt(np.mean(np.sum((design@coefficients-target)**2,axis=1))))
        options.append((residual,source))
    options.sort(key=lambda item:item[0])
    for residual,source in options:
        if residual>35:
            continue
        transform=cv2.getPerspectiveTransform(source,target)
        aligned=cv2.warpPerspective(image,transform,(WIDTH,HEIGHT),borderValue=(255,255,255))
        evidence=grid_evidence(aligned)
        if evidence['left'] and evidence['right']:
            return aligned,source.tolist(),{'method':'adaptive_markers','affine_residual':residual,'grid':evidence}
    return None


@lru_cache(maxsize=1)
def reference():
    with np.load(Path(__file__).with_name('models')/'form_anchors.npz',allow_pickle=False) as data:
        return data['points'],data['descriptors']


def printed_fallback(image):
    reference_points,reference_descriptors=reference()

    scale=min(1.,1240/image.shape[1])
    reduced=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    points,descriptors=cv2.SIFT_create(nfeatures=6000).detectAndCompute(cv2.cvtColor(reduced,cv2.COLOR_BGR2GRAY),None)
    if descriptors is None or len(descriptors)<2:
        raise ValueError('Недостаточно печатных элементов для восстановления обрезанного бланка')
    pairs=cv2.BFMatcher().knnMatch(reference_descriptors,descriptors,k=2)
    matches=[a for a,b in pairs if a.distance<.75*b.distance]


    groups=marker_candidates(image)
    if len(groups[0])==len(groups[1])==1:
        first,second=groups[0][0]*scale,groups[1][0]*scale
        v=second-first;target_v=np.float32(MARKERS[1])-np.float32(MARKERS[0])
        a=float(np.dot(v,target_v)/np.dot(v,v))
        b=float((v[0]*target_v[1]-v[1]*target_v[0])/np.dot(v,v))
        linear=np.float32([[a,-b],[b,a]])
        offset=np.float32(MARKERS[0])-linear@first
        matches=[m for m in matches if np.linalg.norm(linear@np.float32(points[m.trainIdx].pt)+offset-reference_points[m.queryIdx])<110]
    if len(matches)<30:
        raise ValueError('Не найдено достаточно совпадений с печатным шаблоном')
    source=np.float32([points[m.trainIdx].pt for m in matches])
    target=np.float32([reference_points[m.queryIdx] for m in matches])


    proposals=[]


    balanced=np.concatenate([np.flatnonzero((target[:,1]>=top)&(target[:,1]<bottom))[:70]
                             for top,bottom in ((0,900),(900,1500),(1500,2800))])
    for indices in (np.arange(len(source)),balanced):
        if len(indices)<30: continue
        for tolerance in (5.,10.,16.):
            matrix,_=cv2.estimateAffine2D(source[indices],target[indices],ransacReprojThreshold=tolerance,maxIters=10000,confidence=.999)
            if matrix is None: continue
            errors=np.linalg.norm(cv2.transform(source[None],matrix)[0]-target,axis=1)
            good=errors<=tolerance
            span=np.ptp(target[good],axis=0) if good.any() else np.zeros(2)
            if good.sum()>=30 and good.mean()>=.4 and span[0]>=WIDTH*.5 and span[1]>=HEIGHT*.5 and np.median(errors[good])<=3:
                proposals.append((int(good.sum()),matrix,good,span,errors))
    if not proposals:
        raise ValueError('Не удалось восстановить геометрию страницы')
    _,transform,good,span,errors=max(proposals,key=lambda item:item[0])
    linear=transform[:,:2]*scale
    singular=np.linalg.svd(linear,compute_uv=False)
    if (good.sum()<30 or good.mean()<.4 or span[0]<WIDTH*.5 or span[1]<HEIGHT*.5
            or np.median(errors[good])>3 or np.linalg.det(linear)<=0
            or singular.max()/singular.min()>1.25):
        raise ValueError('Совпадения печатного шаблона недостаточно надёжны для выравнивания')
    transform[:,:2]*=scale
    aligned=cv2.warpAffine(image,transform,(WIDTH,HEIGHT),borderValue=(255,255,255))
    evidence=grid_evidence(aligned)
    if not (evidence['left'] and evidence['right']):
        raise ValueError('После восстановления не подтверждены строки клеток ответов')
    return aligned,[],{'method':'printed_affine','matches':len(matches),'inliers':int(good.sum()),
                       'median_error':float(np.median(errors[good])),'span':span.tolist(),'grid':evidence}


def recover_alignment(image):
    found=marker_fallback(image)
    return found if found is not None else printed_fallback(image)
