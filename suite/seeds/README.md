# Seed files

The formal `formal48-v1` seed lists (100 expert-checked initial states per scene) are held by the
organizers to protect the fairness of the public evaluation; official runs reuse them. Their SHA-256
digests are recorded in `protocol.lock.json`, so an official run can be checked against the frozen
protocol. Formal evaluation of a new policy is run by the organizers on these lists.

For local development and for running the diagnostics on your own policy, generate seed files of
the same format under the configured simulator environment:

```bash
python suite/gen_seeds.py <scene> 100            # default search start 300000
python suite/gen_seeds.py <scene> 100 400000     # another development range
```

The runner and `script/eval_policy.py` read `suite/seeds/<scene>.json` in file order and refuse to
run a formal scene when the file is absent. Results on development seeds are not leaderboard
results and must be reported as such. Seed files placed here are ignored by git.
