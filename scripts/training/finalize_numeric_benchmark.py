import json
from pathlib import Path
from oge_checker.pipeline import prepare
from oge_checker.recognize import recognize

root=Path('data/processed/accuracy_v2')
pages=json.loads((root/'split.json').read_text(encoding='utf-8'))['test_pages']
prepare(Path('data/raw/full_pdf.pdf'),root/'final_prepared',pages)
recognize(root/'final_prepared',root/'final_ocr')
print('Full application pipeline completed; frozen numeric model unchanged')
