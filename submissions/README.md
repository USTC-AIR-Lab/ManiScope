# submissions

Merged result files, one per evaluated system and scene set:

```
submissions/<track>/<system-slug>/<YYYY-MM-DD>/submission.json
```

`<track>` is `standard_agent` or `open_system`. Every file follows
[`schema/submission.schema.json`](schema/submission.schema.json) and is checked by
`tools/validate_submission.py` in CI on every pull request.

- `status: community_reported` — produced by the submitter, format-checked only.
- `status: officially_evaluated` — produced by the organizers on the private initial states. Only
  the organizers set this; the validator rejects it from a submitter.

Rules for files in this directory:

- no API keys, tokens or other credentials;
- no frozen seed values and no initial-pose dumps — episodes are identified by index;
- raw logs and videos live in the submitter's own storage and are referenced by URL and digest
  under `run.artifacts`, not committed here;
- the summary is kept small enough to review: one record per episode, nothing else.

`submissions/out/` is the default output directory of `suite/run_dev_check.sh` and is ignored.

See [docs/SUBMISSIONS.md](../docs/SUBMISSIONS.md) for the full process.
