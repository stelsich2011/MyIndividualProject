import re
import cv2
import numpy as np

HOMOGLYPHS = str.maketrans('ABCEHKMOPTXY', 'АВСЕНКМОРТХУ')


FIRST_NAMES = frozenset('''
АВГУСТ АВДОТЬЯ АГАТА АГНИЯ АДАМ АДЕЛИНА АЗАМАТ АИДА АКИМ АКСИНЬЯ
АЛЕВТИНА АЛЕКСАНДР АЛЕКСАНДРА АЛЕКСЕЙ АЛЕНА АЛЁНА АЛИНА АЛИСА АЛЛА
АЛЬБЕРТ АЛЬБИНА АМИНА АМИР АНАСТАСИЯ АНАТОЛИЙ АНГЕЛИНА АНДРЕЙ АНЖЕЛИКА
АННА АНТОН АНТОНИНА АНФИСА АРИНА АРИСТАРХ АРКАДИЙ АРСЕНИЙ АРТЕМ АРТЁМ
АРТЕМИЙ АРТУР АСЯ АФАНАСИЙ БОГДАН БОРИС ВАДИМ ВАЛЕНТИН ВАЛЕНТИНА
ВАЛЕРИЙ ВАЛЕРИЯ ВАРВАРА ВАСИЛИЙ ВАСИЛИСА ВЕРА ВЕРОНИКА ВИКТОР ВИКТОРИЯ
ВИЛЕН ВИТАЛИЙ ВЛАД ВЛАДИМИР ВЛАДИСЛАВ ВЛАДИСЛАВА ВЛАДЛЕН ВСЕВОЛОД
ВЯЧЕСЛАВ ГАЛИНА ГЕВОРГ ГЕННАДИЙ ГЕОРГИЙ ГЕРМАН ГЛЕБ ГОРДЕЙ ГРИГОРИЙ
ДАВИД ДАМИР ДАНИИЛ ДАНИЛ ДАНИЛА ДАНИЯР ДАРИНА ДАРЬЯ ДЕНИС ДИАНА ДИНА
ДМИТРИЙ ДОБРЫНЯ ЕВА ЕВГЕНИЙ ЕВГЕНИЯ ЕВДОКИЯ ЕГОР ЕКАТЕРИНА ЕЛЕНА
ЕЛИЗАВЕТА ЕЛИСЕЙ ЕСЕНИЯ ЕФИМ ЗАХАР ЗИНАИДА ЗЛАТА ЗОЯ ИВАН ИГНАТ ИГОРЬ
ИЗАБЕЛЛА ИЛОНА ИЛЬЯ ИНГА ИННА ИНОКЕНТИЙ ИРИНА КАМИЛА КАМИЛЛА КАРИНА
КИРА КИРИЛЛ КЛИМ КОНСТАНТИН КРИСТИНА КСЕНИЯ ЛАДА ЛАРИСА ЛЕВ ЛЕОНИД
ЛИАНА ЛИДИЯ ЛИЛИЯ ЛИНА ЛИЯ ЛУКА ЛЮБОВЬ ЛЮДМИЛА МАЙЯ МАКАР МАКСИМ
МАРАТ МАРГАРИТА МАРИНА МАРИЯ МАРК МАРТА МАТВЕЙ МИЛАНА МИЛЕНА МИРОН
МИРОСЛАВ МИРОСЛАВА МИХАИЛ НАДЕЖДА НАТАЛИЯ НАТАЛЬЯ НЕЛЛИ НИКИТА
НИКОЛАЙ НИНА ОКСАНА ОЛЕГ ОЛЕСЯ ОЛЬГА ПАВЕЛ ПЕЛАГЕЯ ПЕТР ПЁТР ПЛАТОН
ПОЛИНА ПРОХОР РАДМИР РАИСА РЕГИНА РЕНАТ РИНАТ РОБЕРТ РОДИОН РОМАН
РОСТИСЛАВ РУСЛАН РУСТАМ САВВА САВЕЛИЙ СВЕТЛАНА СВЯТОСЛАВ СЕМЕН СЕМЁН
СЕРАФИМ СЕРГЕЙ СОФИЯ СОФЬЯ СТАНИСЛАВ СТЕПАН ТАИСИЯ ТАМАРА ТАТЬЯНА
ТИМОФЕЙ ТИМУР ТИХОН УЛЬЯНА ФЕДОР ФЁДОР ФИЛИПП ЭВЕЛИНА ЭДУАРД ЭЛИНА
ЭЛЬВИРА ЭМИЛИЯ ЭМИН ЭММА ЮЛИАН ЮЛИЯ ЮРИЙ ЯН ЯНА ЯРОСЛАВ ЯРОСЛАВА
'''.split())
CONFUSIONS = {frozenset(pair) for pair in ('УИ', 'НП', 'NП', 'ЛП', '4Ч', '0О', '3З')}


def russian(text):
    return ''.join(text.split()).upper().translate(HOMOGLYPHS)


def name_candidate(text, name, confidence):
    value = russian(text)
    if name != 'first_name' or value in FIRST_NAMES or confidence is None or confidence >= .85:
        return value, False
    alternatives = []
    for word in FIRST_NAMES:
        if len(word) != len(value):
            continue
        changes = [(a,b) for a,b in zip(value,word) if a != b]
        if len(changes) == 1 and frozenset(changes[0]) in CONFUSIONS:
            alternatives.append(word)
    return (alternatives[0], True) if len(alternatives) == 1 else (value, False)


def valid_class(text):
    value = russian(text)
    value = re.sub(r'^[GД](?=[А-ЯЁ]$)', '9', value)
    match = re.fullmatch(r'(0?[1-9]|10|11)([А-ЯЁ])', value)
    return value if match else None


def read_class(text, cleaned, read):
    pass
    initial = valid_class(text)
    if initial:
        return initial, []
    variants=[]
    occupied=(cleaned<128).any(axis=0)
    runs=[]; start=None
    for x,yes in enumerate(list(occupied)+[False]):
        if yes and start is None: start=x
        if not yes and start is not None:
            runs.append(cleaned[:,start:x]); start=None
    if runs:
        variants.append(np.concatenate([part for run in runs for part in
                        (run,np.full((cleaned.shape[0],2),255,np.uint8))],axis=1))
    variants += [cv2.resize(cleaned,None,fx=factor,fy=1,interpolation=cv2.INTER_CUBIC)
                 for factor in (.3,1.7)]
    readings=[]
    for variant in variants:
        raw,score=read(variant)
        readings.append({'text':raw,'confidence':score})
    choices={valid_class(item['text']) for item in readings} - {None}

    prefix=re.match(r'^(10|11|0?[1-9])',russian(text))
    if prefix:
        choices={value for value in choices if re.match(r'^\d+',value)[0]==prefix[0]}
    return (next(iter(choices)) if len(choices)==1 else russian(text)), readings
