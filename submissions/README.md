# submissions

This directory holds the **contract**, not the results: the schema every submission follows, an
example file, and the validator and exporter in `../tools/`. Results and evaluation requests are
filed in the website repository, where the leaderboard is built:

https://github.com/embodied-ai-research/ManipScope_webpage

The validator runs in both repositories from the same file, reading the scene list from
`suite/scenes_v2.yaml` here and from `data/tasks.json` there, so the two copies stay identical and
can be compared with `diff`.

- [`schema/submission.schema.json`](schema/submission.schema.json) — the format, version
  `manipscope-submission-0.1`.
- [`examples/example_submission.json`](examples/example_submission.json) — a filled template. The
  numbers are illustrative and describe no real system.
- `../tools/export_submission.py` — builds a submission from an evaluation run directory.
- `../tools/validate_submission.py` — schema, scene and episode coverage, recomputed Overall and
  Pooled, call-budget ceiling and a credential scan.

Rules for any submission file, here or there:

- no API keys, tokens or other credentials;
- no frozen seed values and no initial-pose dumps — episodes are identified by index;
- raw logs and videos live in the submitter's own storage and are referenced by URL and digest under
  `run.artifacts`;
- `status: community_reported` for a submitter's own run, `officially_evaluated` only for a run the
  organizers performed; the validator rejects the latter from a submitter.

`submissions/out/` is the default output directory of `suite/run_dev_check.sh` and is ignored.

See [docs/SUBMISSIONS.md](../docs/SUBMISSIONS.md) for the process and
[docs/ORGANIZER_RUNBOOK.md](../docs/ORGANIZER_RUNBOOK.md) for the organizer side.
