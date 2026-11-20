
import cv2
from .decimal_mark import restore_decimal
from .geometry import restore_strokes


def recognize_block(image, engine, preprocess, normalize, row_bounds=None):
    if image is None:
        return {}, ['Блок замен недоступен'], []
    height, width = image.shape[:2]
    entries, issues, grouped = [], [], {}

    for row in range(3):
        for side in range(2):
            left = 0 if side == 0 else 470 / 911
            number_box = (left + .006, left + (.051 if side == 0 else .048))


            answer_box = (left + .073, left + .488) if side == 0 else (left + .073, .998)
            y1, y2 = round((row / 3 + .015) * height), round(((row + 1) / 3 - .012) * height)
            if row == 2:
                y2 = min(y2, round(.95 * height))
            if row_bounds is not None:
                y1,y2=row_bounds[side][row]
            def crop(box):
                return image[y1:y2, round(box[0] * width):round(box[1] * width)]
            try:
                number_crop,answer_crop=crop(number_box),crop(answer_box)
                if row_bounds is not None:
                    from .grid import clean_recovered_grid
                    number_crop,_=clean_recovered_grid(number_crop)
                    answer_crop,_=clean_recovered_grid(answer_crop)
                number_image, number_empty = preprocess(number_crop)
                answer_image, answer_empty = preprocess(answer_crop)
                if number_empty and answer_empty:
                    continue
                raw_number, number_score = ('', None) if number_empty else engine.read(number_image)
                raw_answer, score = ('', None) if answer_empty else engine.read(answer_image)
                number, text = normalize(raw_number), normalize(raw_answer)
                number, _ = restore_strokes(number, number_image)
                text, adjustments = restore_strokes(text, answer_image)
                text, decimals = restore_decimal(text, answer_image)
                item = {'row': row, 'side': side, 'number': number, 'text': text, 'confidence': score}
                item['adjustments'] = adjustments + decimals
                entries.append(item)
                if not number.isdecimal() or not 1 <= int(number) <= 19 or answer_empty:
                    issues.append(f'Неоднозначная замена: ряд {row + 1}, колонка {side + 1}')
                    continue
                if number_score is None or number_score < .90:
                    issues.append(f'Неуверенный номер замены {number}; использован основной ответ')
                    continue
                grouped.setdefault(str(int(number)), []).append(item)
            except Exception as exc:
                issues.append(f'Ошибка чтения замены {row + 1}/{side + 1}: {exc}')
    changes = {}
    for number, values in grouped.items():
        if len({v['text'] for v in values}) == 1:
            changes[number] = values[-1]
        else:
            issues.append(f'Конфликт замен задания {number}; использован основной ответ')
    return changes, issues, entries
