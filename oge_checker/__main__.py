import argparse
import sys
from pathlib import Path

from .pipeline import prepare


def parse_pages(value):
    try:
        pages = []
        for part in value.split(','):
            bounds = [int(n) for n in part.split('-')]
            if len(bounds) == 1 and bounds[0] > 0:
                pages.append(bounds[0])
            elif len(bounds) == 2 and 0 < bounds[0] <= bounds[1]:
                pages.extend(range(bounds[0], bounds[1] + 1))
            else:
                raise ValueError
        return list(dict.fromkeys(pages))
    except ValueError:
        raise argparse.ArgumentTypeError("Используйте номера с 1, например: 1-3,7,10") from None


def main():
    if len(sys.argv) == 1:
        from .desktop import main as desktop_main
        desktop_main()
        return
    parser = argparse.ArgumentParser(description="Подготовка бланков ОГЭ к распознаванию")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output/prepared"))
    parser.add_argument("--pages", type=parse_pages, help="Например: 1-3,7. По умолчанию все страницы.")
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()
    if not args.pdf.is_file():
        parser.error(f"Файл не найден: {args.pdf}")
    if not 150 <= args.dpi <= 600:
        parser.error("DPI должен быть в пределах 150–600")
    try:
        manifest = prepare(args.pdf, args.output, args.pages, args.dpi)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Ошибка: {exc}\n")
    ready = sum(page["status"] == "prepared" for page in manifest["pages"])
    print(f"Подготовлено: {ready}/{len(manifest['pages'])}. Отчёт: {args.output / 'report.html'}")


if __name__ == "__main__":
    main()
