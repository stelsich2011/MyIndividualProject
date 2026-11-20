# Разработка

## Установка из исходников

Нужен Python 3.10+ с Tcl/Tk. Локальная сборка проверена на Windows и Python 3.14.
GitHub Actions запускает тесты на Python 3.11 под Windows и Linux.

```powershell
py -3 -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[desktop,build]"
.venv/Scripts/python.exe -m oge_checker.desktop
.venv/Scripts/python.exe -m unittest discover -s tests -q
```

На Linux используйте `python3`, `.venv/bin/python` и установленный пакет Tcl/Tk.
GUI-тесты без графического сеанса пропускаются. Проверки на реальных сканах
пропускаются, если локальные датасеты отсутствуют. Остальные тесты используют
синтетические данные и временные каталоги.

## Обучение

Сценарии в `scripts/training` запускаются из корня репозитория после установки
пакета. Они используют локальные наборы в `data/processed` и MNIST в
`data/external/mnist`. Эти данные не входят в публичный архив исходников.

```powershell
.venv/Scripts/python.exe scripts/training/train_numeric.py --help
.venv/Scripts/python.exe scripts/training/select_numeric.py --help
```

`train_numeric.py` обучает экспериментальную модель, `select_numeric.py`
оценивает правила объединения, `promote_numeric.py` заменяет поставляемые веса.
Последний сценарий запускайте только после проверки модели на отдельной выборке.
Подробности обучения и источников: [карточка моделей](../src/oge_checker/models/README.md).

## Сборка Windows

```powershell
.venv/Scripts/python.exe packaging/build_windows.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File packaging/smoke_windows.ps1
```

Для установщика требуется Inno Setup: локально используется
`build_tools/InnoSetup/ISCC.exe`, другой путь передаётся через `--iscc`.
Каталог компилятора исключён из Git. Зафиксированные версии зависимостей
находятся в `packaging/requirements-windows.lock.txt`.

Сборщик проверяет контрольные суммы моделей, собирает приложение через
PyInstaller и создаёт `dist/installer/OGEChecker-Setup.exe`.
Для полной установочной проверки нужен `data/raw/full_pdf.pdf`; проверяются
обычный, обрезанный, неоднозначный и бледный бланки. Тестовая установка
использует отдельный каталог и удаляется после проверки.

## Публикация

```powershell
.venv/Scripts/python.exe scripts/export_repository.py
```

Полученный ZIP `dist/source/oge-checker-0.6.0-source.zip` содержит только
исходники, тесты, документацию, примеры ключей и модели. Датасеты, окружение,
установщики и каталог `.git` не включаются. Установщик можно прикрепить
отдельным файлом к GitHub Release.

В прежней истории Git уже есть исходный скан. Добавление `.gitignore` не
удаляет файлы из истории. Для публикации без старых сканов распакуйте чистый
ZIP в новую папку и создайте там новый репозиторий. Скрипт экспорта не изменяет
существующую историю и ничего не загружает на GitHub.
