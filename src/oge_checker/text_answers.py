import re
from collections import Counter
import cv2

VISUAL=str.maketrans('ABCEHKMOPTXYΕΑΟΡΤΧΚΜ', 'АВСЕНКМОРТХУЕАОРТХКМ')


def canonical_word(text):
    text=''.join(text.split())
    letters=re.findall(r'[A-Za-zА-Яа-яЁёΑ-Ω]',text)

    if len(letters)<2 or not re.search(r'[А-Яа-яЁё]',text):return text
    if re.search(r'[^A-Za-zА-Яа-яЁёΑ-Ω03]',text):return text
    value=text.upper().translate(VISUAL)
    if not re.fullmatch(r'[А-ЯЁ03]+',value):return text
    return value.replace('0','О').replace('3','З')


def refine_text(value, cleaned, read):
    if len(re.findall(r'[A-Za-zА-Яа-яЁё]',value))<2:return value,[]
    readings=[value]
    for image in (cv2.resize(cleaned,None,fx=.7,fy=1,interpolation=cv2.INTER_LINEAR),
                  cv2.erode(cleaned,cv2.getStructuringElement(cv2.MORPH_RECT,(2,2)))):
        raw,_=read(image);readings.append(''.join(raw.split()))
    candidates=[canonical_word(t) for t in readings]
    common,count=Counter(candidates).most_common(1)[0]

    if count>=2 and len(common)==len(value) and re.fullmatch(r'[А-ЯЁ]+',common):
        return common,readings
    return value,readings
