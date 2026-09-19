# Contributing

Use a separate branch for each change. Keep machine paths in ignored `configs/local.env`, model
weights and assets external, and evaluation outputs out of Git. Preserve third-party notices.

Run `python3 tools/validate_repo.py` and `python3 -m pytest -q tests`. Explain affected scenes,
protocol implications, and actual runtime validation in changes. Changes to frozen seeds, criteria,
geometry or instructions require a new documented protocol version, not a silent hash refresh.
For a new adapter, document upstream revision, environment, action convention and reset behavior.
