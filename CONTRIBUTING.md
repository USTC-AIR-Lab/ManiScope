# Contributing

Use a separate branch for each change. Keep machine paths in ignored `configs/local.env`, model
weights and assets external, and evaluation outputs out of Git. Preserve third-party notices.

Run `python3 tools/validate_repo.py` and `python3 -m pytest -q tests`. Explain affected scenes,
protocol implications, and actual runtime validation in changes. Changes to frozen seeds, criteria,
geometry or instructions require a new documented protocol version, not a silent hash refresh.
For a new adapter, document upstream revision, environment, action convention and reset behavior.

## Submitting an evaluation

Evaluation results are a separate path from code changes: run the development set, then file an
evaluation request so the organizers can run the private initial states. The process, the result
format, the two tracks and the cost split are in [docs/SUBMISSIONS.md](docs/SUBMISSIONS.md).
Requests and result files are filed in the website repository (https://github.com/embodied-ai-research/ManipScope_webpage), which is where the leaderboard
is built; this repository holds the protocol, the tooling and the scene-level issue templates. Check
a result file with `python3 tools/validate_submission.py <file>` before opening the issue or pull
request. Never put an API key, a token or a seed value in an issue, a pull request, a log or a
submission file.
