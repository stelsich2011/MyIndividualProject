"""Постраничный рендеринг, выравнивание и вырезание полей."""

import html
import json
from pathlib import Path

import cv2
import numpy as np
import pymupdf

from .template import WIDTH, HEIGHT, MARKERS, fields


def detect_markers(image):
    """Ищет компактные чёрные квадраты в четырёх углах бланка."""
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)[1]
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if not (.012 * width <= w <= .04 * width and .012 * width <= h <= .04 * width):
            continue
        if not .7 <= w / h <= 1.4 or cv2.contourArea(contour) / (w * h) < .85:
            continue
        candidates.append((x + w / 2, y + h / 2))
    # Два верхних квадрата находятся примерно на 20% и 87% ширины.
    regions = [(.18, .28, 0, .08), (.78, .94, 0, .08),
               (0, .14, .90, 1), (.88, 1, .90, 1)]
    selected = []
    for left, right, top, bottom in regions:
        found = [(x, y) for x, y in candidates
                 if left <= x / width <= right and top <= y / height <= bottom]
        if len(found) != 1:
            raise ValueError(f"Неоднозначные опорные метки: найдено {len(found)} в области {left, right, top, bottom}")
        selected.append(found[0])
    return np.float32(selected)


def align(image):
    source = detect_markers(image)
    transform = cv2.getPerspectiveTransform(source, np.float32(MARKERS))
    return cv2.warpPerspective(image, transform, (WIDTH, HEIGHT),
                               borderValue=(255, 255, 255)), source.tolist()


def save_image(path, image):
    if not cv2.imwrite(str(path), image):
        raise OSError(f"Не удалось сохранить {path}")


def write_report(output, manifest):
    sections = []
    for page in manifest["pages"]:
        number = page["page"]
        if page["status"] != "prepared":
            sections.append(f'<section><h2>Страница {number}: требуется проверка</h2>'
                            f'<p>{html.escape(page["error"])}</p>'
                            f'<a href="{page["original"]}">Исходный скан</a></section>')
            continue
        crops = ''.join(f'<figure><figcaption>{name}</figcaption>'
                        f'<img loading="lazy" src="{item["image"]}"></figure>'
                        for name, item in page["fields"].items())
        sections.append(f'<section><h2>Страница {number}</h2>'
                        f'<a href="{page["preview"]}">Бланк с границами полей</a>'
                        f'<div class="crops">{crops}</div></section>')
    document = '''<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Подготовка бланков ОГЭ</title><style>
body{font-family:system-ui;margin:24px;background:#f4f5f7;color:#17212b}
section{background:white;padding:20px;margin:20px 0;border-radius:12px}
.crops{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0;max-width:100%}
figure img{max-width:560px;width:100%;border:1px solid #ccc}figcaption{padding:6px}
</style><h1>Подготовленные бланки</h1>
<p>Это проверка выделения полей. Распознавание и оценивание ещё не выполнялись.</p>'''
    (output / "report.html").write_text(document + ''.join(sections) + '</html>', encoding="utf-8")


def prepare(pdf_path: Path, output: Path, page_numbers, dpi=300):
    output.mkdir(parents=True, exist_ok=True)
    # Запрещаем перезапись предыдущего прогона, включая ручные исправления.
    if any(output.iterdir()):
        raise ValueError("Папка результата должна быть пустой. Укажите новую папку через --output.")
    manifest = {"schema_version": 1, "source_pdf": str(pdf_path.resolve()),
                "dpi": dpi, "template": "oge_math_form1_v1", "pages": []}
    with pymupdf.open(pdf_path) as document:
        if document.needs_pass:
            raise ValueError("PDF защищён паролем")
        numbers = list(page_numbers) if page_numbers is not None else list(range(1, len(document) + 1))
        if not numbers or any(n < 1 or n > len(document) for n in numbers):
            raise ValueError(f"Номера страниц должны быть от 1 до {len(document)}")
        for number in dict.fromkeys(numbers):
            folder = output / f"page_{number:03}"
            folder.mkdir()
            pixmap = document[number - 1].get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
            image = cv2.cvtColor(np.frombuffer(pixmap.samples, dtype=np.uint8)
                                .reshape(pixmap.height, pixmap.width, 3), cv2.COLOR_RGB2BGR)
            original = folder / "original.jpg"
            save_image(original, image)
            record = {"page": number, "original": original.relative_to(output).as_posix()}
            try:
                aligned, markers = align(image)
            except ValueError as exc:
                record.update(status="needs_review", error=str(exc))
            else:
                save_image(folder / "aligned.png", aligned)
                preview = aligned.copy()
                record.update(status="prepared", markers=markers, fields={},
                              aligned=f"{folder.name}/aligned.png", preview=f"{folder.name}/preview.jpg")
                for name, box in fields().items():
                    x1, y1, x2, y2 = box
                    crop_path = folder / f"{name}.png"
                    save_image(crop_path, aligned[y1:y2, x1:x2])
                    record["fields"][name] = {"box": box, "image": crop_path.relative_to(output).as_posix(),
                                              "raw_text": None, "value": None, "status": "not_recognized"}
                    cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 0, 220), 2)
                    cv2.putText(preview, name, (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 0, 220), 1)
                save_image(folder / "preview.jpg", preview)
            manifest["pages"].append(record)
            (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            write_report(output, manifest)
            print(f"Страница {number}: {record['status']}", flush=True)
    return manifest
