import copy
import json
from pathlib import Path
import runpy
import cv2
from oge_checker.evaluate import evaluate
from oge_checker.session import rebase

root = Path('data/processed/benchmark')
data = json.loads((root / 'improved/recognition.json').read_text(encoding='utf-8'))
transcription = json.loads((root / 'transcription.json').read_text(encoding='utf-8'))
reference = {'schema_version': 1, 'source_id': data['source_id'], 'fields': [], 'method': transcription['method']}
excluded = []
for page, values in transcription['answers'].items():
    assert len(values) == 19, page
    for number, text in enumerate(values, 1):
        identifier = f'{page}:answer_{number:02}'
        if text is None:
            excluded.append(identifier)
        else:
            reference['fields'].append({'id': identifier, 'corrected_text': text, 'reviewed': True})
(root / 'reference.json').write_text(json.dumps(reference, ensure_ascii=False, indent=2), encoding='utf-8')
baseline = copy.deepcopy(data)
restore = runpy.run_path(str(root / 'baseline_decimal.py'))['restore_decimal']
for page in baseline['pages']:
    for field in page['fields']:
        image = cv2.imread(str(root / 'improved' / field['cleaned']), cv2.IMREAD_GRAYSCALE)
        field['candidate'] = restore(field['base_candidate'], image)[0] if field['name'].startswith('answer_') else field['base_candidate']
baseline['postprocessing'] = 'decimal_mark_geometry_v1'
(root / 'baseline.json').write_text(json.dumps(rebase(baseline, root / 'improved', root), ensure_ascii=False, indent=2), encoding='utf-8')
report = {'method': transcription['method'], 'split': json.loads((root / 'split.json').read_text(encoding='utf-8')),
    'reference_revisions': transcription.get('reference_revisions', []),
    'excluded_fields': excluded, 'annotated_fields': len(reference['fields']), 'possible_answer_fields': 380,
    'baseline': evaluate(baseline, reference), 'improved': evaluate(data, reference)}
report['target_met'] = report['improved']['exact_match_rate'] >= .95
(root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
for label in ('baseline', 'improved'):
    print(label, report[label]['matching_fields'], report[label]['reviewed_fields'], report[label]['exact_match_rate'])
print('target_met', report['target_met'], 'excluded', excluded)
print(json.dumps(report['improved']['mismatches'], ensure_ascii=True, indent=2))
