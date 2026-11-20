
import re
import cv2
import numpy as np


def restore_strokes(candidate, cleaned):
    _, _, stats, _ = cv2.connectedComponentsWithStats((cleaned < 128).astype(np.uint8))
    shapes = sorted(stats[1:].tolist(), key=lambda s: s[0])
    changes = []
    if not shapes:
        return candidate, changes
    height = max(s[3] for s in shapes)
    first = shapes[0]
    before = candidate
    if re.fullmatch(r'\+[0-9]+(?:,[0-9]+)?', candidate) and first[2] >= 2 * first[3] and first[3] < .35 * height:
        candidate = '-' + candidate[1:]

    tall = [s for s in shapes if s[3] >= .65 * height]
    if first in tall and first[2] <= .25 * first[3]:
        if re.fullmatch(r'\|[0-9]+', candidate) and len(tall) == len(candidate):
            candidate = '1' + candidate[1:]
        elif candidate.isascii() and candidate.isdecimal() and len(tall) == len(candidate) + 1:
            candidate = '1' + candidate
    if candidate != before:
        changes.append({'rule': 'visible_strokes_v1', 'before': before, 'after': candidate, 'box_in_cleaned': first[:4]})
    return candidate, changes
