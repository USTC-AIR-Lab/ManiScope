"""Descriptive observed patterns, not a claim about a learned internal shortcut."""
import json
from pathlib import Path
from analyze import interval
from paths import R
rows=json.loads((R/'analyses/episodes.json').read_text());lookup={(x['policy'],x['seed'],x['layout'],x['target']):x for x in rows}
out=[]
for policy in ('Pi05','Motus'):
 for seed in range(200000,200020):
    cells=[lookup.get((policy,seed,l,t)) for l in ('original','swapped') for t in ('red','blue')]
    if any(x is None for x in cells):continue
    labels=[x['contact_label'] for x in cells];valid=all(x in ('red','blue','green') for x in labels)
    invariant_original=valid and labels[0]==labels[1];invariant_swapped=valid and labels[2]==labels[3]
    if not valid:pattern='unresolved'
    elif invariant_original and invariant_swapped:
        if labels[0]==labels[2]=='green':pattern='fixed_green_distractor'
        elif labels[0]==labels[2]:pattern='same_color_across_layouts'
        elif {labels[0],labels[2]}=={'red','blue'}:pattern='same_spatial_slot_across_layouts'
        else:pattern='instruction_invariant_other'
    else:pattern='instruction_dependent_in_some_layout'
    out.append(dict(policy=policy,seed=seed,labels=labels,pattern=pattern,instruction_invariant_layout_fraction=(int(invariant_original)+int(invariant_swapped))/2))
(R/'analyses/shortcut_patterns.json').write_text(json.dumps(out,indent=2));print('pattern scenes',len(out))
