"""Шаблон бланка № 1 из full_pdf.pdf. Координаты по эталону 987 × 1400."""

WIDTH, HEIGHT = 2000, 2800
MARKERS = [(211 * WIDTH / 987, 50 * 2), (845 * WIDTH / 987, 45 * 2),
           (57 * WIDTH / 987, 1350 * 2), (945 * WIDTH / 987, 1340 * 2)]


def rect(x1, y1, x2, y2):
    return [round(x1 * WIDTH / 987), round(y1 * 2),
            round(x2 * WIDTH / 987), round(y2 * 2)]


def fields():
    result = {
        "surname": rect(155, 374, 935, 408),
        "first_name": rect(155, 411, 935, 444),
        "patronymic": rect(155, 447, 935, 481),
        "class": rect(485, 130, 571, 169),
        "barcode": rect(85, 198, 320, 275),
        "replacements": rect(42, 1172, 953, 1270),
    }
    for number in range(1, 20):
        if number <= 17:
            y = 554 + (number - 1) * 34.8
            result[f"answer_{number:02}"] = rect(58, y, 482, y + 31)
        else:
            y = 550 + (number - 18) * 34.8
            result[f"answer_{number:02}"] = rect(529, y, 954, y + 31)
    return result
