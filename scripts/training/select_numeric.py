import json
from pathlib import Path
import argparse
from oge_checker.digits import combine_numeric, has_small_separator
from oge_checker.image_io import read_image

parser=argparse.ArgumentParser(description='Проверка правил объединения на страничной cross-validation, без нового test.')
parser.add_argument('directory',nargs='?',default='data/processed/numeric_training')
args=parser.parse_args()
rows = json.loads((Path(args.directory)/'cross_validation.json').read_text(encoding='utf-8'))
base = {}
paths = ['data/processed/numeric_training/baseline_v2/recognition.json'] if Path('data/processed/numeric_training/baseline_v2/recognition.json').is_file() else ['data/processed/dev_geometry/recognition.json', 'data/processed/benchmark/improved/recognition.json']
for path in paths:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    base.update({f['id']: f for p in data['pages'] for f in p['fields']})
separator_policy={}
for row in rows:
    page,name=row['id'].split(':')
    image=read_image(Path('data/processed/numeric_training/prepared')/f'page_{int(page):03}'/f'{name}.png')
    separator_policy[row['id']]=not has_small_separator(image)
policies = []
for agreement in (.4, .6, .8, 1.):
    for distance in (1.5,2.,3.,4.):
        correct, changed = 0, 0
        for row in rows:
            chosen = combine_numeric(base[row['id']]['candidate'],row['numeric'],row['agreements'],row['distances'],agreement,distance,allow_separator_deletion=separator_policy[row['id']])
            correct += chosen == row['expected']
            changed += chosen != base[row['id']]['candidate']
        policies.append({'agreement':agreement,'distance':distance,'correct':correct,'changed':changed})
print('baseline',sum(base[r['id']]['candidate']==r['expected'] for r in rows),'/',len(rows))
print('best',sorted(policies,key=lambda r:r['correct'],reverse=True)[:10])
print(json.dumps([dict(row,base=base[row['id']]['candidate']) for row in rows if row['numeric']!=row['expected']],ensure_ascii=True,indent=2))
