import json
from pathlib import Path
from oge_checker.session import Session

root=Path('data/processed/accuracy_v2')
report=json.loads((root/'report.json').read_text(encoding='utf-8'))
session=Session.open(report['recognition_files']['improved'])
session.load_reference(root/'reference_improved.json')
session.save(root/'project.json')
session.export_excel(root/'results.xlsx')
print('saved',session.metrics()['matching_fields'],session.metrics()['reviewed_fields'])
