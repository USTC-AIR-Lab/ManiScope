import json
from pathlib import Path
from paths import R
rows=json.loads((R/'analyses/future_targets_rule.json').read_text());review={x['id']:x for x in json.loads((R/'reports/future_visual_review.json').read_text())};assert len(rows)==len(review)==80
out=[]
for r in rows:
    a=r['last_frame']['label'];b=review[r['id']]['visible_approach'];r.update(review_label=b,rule_label=a,review_agrees=a==b,final_label=a if a==b else 'ambiguous');out.append(r)
(R/'analyses/future_targets_final.json').write_text(json.dumps(out,indent=2))
print('agreement',sum(r['review_agrees'] for r in out),'/',len(out))
