import hashlib
import json
from pathlib import Path
from oge_checker.evaluate import evaluate

root=Path('data/processed/accuracy_v2')
truth=json.loads((root/'transcription.json').read_text(encoding='utf-8'))
split=json.loads((root/'split.json').read_text(encoding='utf-8'))
model=json.loads(Path('src/oge_checker/models/numeric_model.json').read_text(encoding='utf-8'))
assert not set(split['test_pages'])&set(model['training_pages'])
report={'method':truth['method'],'split':split,'model':model,'total_fields':380,'excluded':[],'comparisons':{}}
for version in ('baseline','improved'):
    directory=('release_ocr' if (root/'release_ocr/recognition.json').is_file() else 'final_ocr') if version=='improved' and (root/'final_ocr/recognition.json').is_file() else version
    data=json.loads((root/directory/'recognition.json').read_text(encoding='utf-8'))
    reference={'schema_version':1,'source_id':data['source_id'],'fields':[]}
    for page,answers in truth['answers'].items():
        assert len(answers)==19,page
        for number,text in enumerate(answers,1):
            identifier=f'{page}:answer_{number:02}'
            if text is None:
                if version=='baseline':report['excluded'].append(identifier)
                continue
            reference['fields'].append({'id':identifier,'corrected_text':text,'reviewed':True})
    (root/f'reference_{version}.json').write_text(json.dumps(reference,ensure_ascii=False,indent=2),encoding='utf-8')
    metrics=evaluate(data,reference)
    report['comparisons'][version]=metrics
    report.setdefault('recognition_files',{})[version]=str(root/directory/'recognition.json')
    print(version,metrics['matching_fields'],metrics['reviewed_fields'],metrics['exact_match_rate'])
report['improvement_percentage_points']=100*(report['comparisons']['improved']['exact_match_rate']-report['comparisons']['baseline']['exact_match_rate'])
report['target_met']=report['comparisons']['improved']['exact_match_rate']>=.95
report['reference_sha256']=hashlib.sha256((root/'transcription.json').read_bytes()).hexdigest()
if (root/'report.json').exists() and not (root/'report-initial.json').exists():
    (root/'report-initial.json').write_bytes((root/'report.json').read_bytes())
(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('target_met',report['target_met'])
print(json.dumps(report['comparisons']['improved']['mismatches'],ensure_ascii=True,indent=2))
