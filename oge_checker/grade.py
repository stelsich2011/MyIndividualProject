"""Команда демонстрационной/реальной проверки готовой расшифровки."""

import argparse
import json
from pathlib import Path

from .grading import demo_key
from .session import Session, read_json


def main():
    parser = argparse.ArgumentParser(description='Проверка кратких ответов по JSON-ключам')
    parser.add_argument('recognition', type=Path)
    parser.add_argument('--keys', type=Path)
    parser.add_argument('--demo', action='store_true', help='Случайные цифры, только демонстрация')
    parser.add_argument('--corrections', type=Path)
    parser.add_argument('--output', type=Path, default=Path('output/graded'))
    args = parser.parse_args()
    try:
        if bool(args.keys) == args.demo:
            raise ValueError('Укажите либо --keys, либо --demo')
        session = Session.open(args.recognition)
        if args.corrections:
            session.load_corrections(args.corrections)
        session.set_key(demo_key() if args.demo else read_json(args.keys))
        if args.output.exists() and any(args.output.iterdir()):
            raise ValueError('Папка результата должна быть пустой')
        args.output.mkdir(parents=True, exist_ok=True)
        session.save(args.output / 'project.json')
        session.export_excel(args.output / 'students.xlsx')
        (args.output / 'answer_key.json').write_text(json.dumps(session.key, ensure_ascii=False, indent=2), encoding='utf-8')
        for page in session.snapshot()['pages']:
            score = page['grading']
            print(f'Страница {page["page"]}: {score["status"]}; сумма {score["provisional"]}/{score["maximum"]}')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Ошибка: {exc}\n')


if __name__ == '__main__':
    main()
