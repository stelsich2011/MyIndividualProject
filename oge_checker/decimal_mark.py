"""Консервативное восстановление запятой по геометрии очищенной строки."""

import re

import cv2
import numpy as np


def restore_decimal(candidate, cleaned):
    # Только числовой ответ без разделителя. Буквы, единицы и скобки не трогаем.
    if not re.fullmatch(r'-?[0-9]+', candidate):
        return candidate, []
    _, _, stats, _ = cv2.connectedComponentsWithStats((cleaned < 128).astype(np.uint8))
    shapes = sorted(stats[1:].tolist(), key=lambda shape: shape[0])
    height = max((shape[3] for shape in shapes), default=0)
    digits = [shape for shape in shapes if shape[3] >= .65 * height]
    if len(digits) != len(candidate.lstrip('-')):
        return candidate, []
    top = min((shape[1] for shape in digits), default=0)
    commas = [shape for shape in shapes
              if 7 <= shape[3] < .65 * height and shape[1] >= top + .4 * height
              and shape[2] <= .65 * height]
    if len(commas) != 1:
        return candidate, []
    position = sum(shape[0] < commas[0][0] for shape in digits)
    if not 0 < position < len(digits):
        return candidate, []
    # Запятая должна находиться в свободном промежутке между двумя цифрами.
    previous, following = digits[position - 1], digits[position]
    comma = commas[0]
    if not previous[0] + previous[2] <= comma[0] < comma[0] + comma[2] <= following[0]:
        return candidate, []
    index = position + int(candidate.startswith('-'))
    return candidate[:index] + ',' + candidate[index:], [{
        'rule': 'decimal_mark_geometry_v1', 'box_in_cleaned': comma[:4],
        'before': candidate, 'after': candidate[:index] + ',' + candidate[index:],
    }]
