
import argparse
import hashlib
import json
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

from .pipeline import prepare, align
import cv2
import numpy as np


def prepare_benchmark(pdf, output, count=20, excluded=None):
    output = Path(output)
    excluded = set(excluded or (1, 2, 3, 44, 88))
    pages, fingerprints = [], set()
    with pymupdf.open(pdf) as doc:
        for number in sorted(excluded):
            fingerprints.add(hashlib.sha256(doc[number - 1].get_pixmap(dpi=72).samples).hexdigest())
        for index, page in enumerate(doc):
            if index + 1 in excluded:
                continue
            pix = page.get_pixmap(dpi=150, colorspace=pymupdf.csRGB, alpha=False)
            image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            try:
                align(cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
            except ValueError:
                continue
            digest = hashlib.sha256(page.get_pixmap(dpi=72).samples).hexdigest()
            if digest in fingerprints:
                continue
            fingerprints.add(digest)
            pages.append(index + 1)
            if len(pages) == count:
                break
    if len(pages) != count:
        raise ValueError(f'Найдено только {len(pages)} подходящих новых страниц')
    root = output / 'prepared'
    manifest = prepare(Path(pdf), root, pages)
    write_sheets(root, output)
    (output / 'split.json').write_text(json.dumps({'development_pages': sorted(excluded),
        'test_pages': pages, 'rule': 'first 20 new aligned pages, exact scan hashes deduplicated'}, indent=2), encoding='utf-8')
    return pages


def write_sheets(root, output):
    root, output = Path(root), Path(output)
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    for start in range(0, len(manifest['pages']), 4):
        canvas = Image.new('RGB', (2240, 1140), 'white')
        draw = ImageDraw.Draw(canvas)
        for column, page in enumerate(manifest['pages'][start:start + 4]):
            x = column * 560
            draw.text((x + 10, 10), f"PAGE {page['page']}", fill='black')
            for number in range(1, 20):
                path = root / page['fields'][f'answer_{number:02}']['image']
                with Image.open(path) as img:
                    img.thumbnail((510, 50))
                    canvas.paste(img, (x + 42, number * 56))
                draw.text((x + 5, number * 56 + 12), str(number), fill='black')
        canvas.save(output / f'transcription_{start // 4 + 1}.png')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Подготовка независимых страниц и листов для визуальной расшифровки.\n\npython -m oge_checker.benchmark full_pdf.pdf --output output/benchmark\nРезультаты содержат персональные данные и не включаются в сборку.\n')
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--output', type=Path, default=Path('output/benchmark'))
    parser.add_argument('--exclude', default='1-3,44,88', help='Уже использованные страницы')
    args = parser.parse_args()
    from .__main__ import parse_pages
    print(prepare_benchmark(args.pdf, args.output, excluded=parse_pages(args.exclude)))
