# Results provenance

The paper and website distinguish checkpoint policies from API-driven agents. Formal policy
comparisons use 48 scenes and 100 episodes per scene. The matched comparison uses the first five
fixed evaluation seeds per scene (240 episodes). Do not pool these two denominators or treat an
agent's `finish` statement as simulator success.

The public source snapshot is a portable implementation, not a rerun certificate for historical
scores. Record the Git revision, protocol-lock version, checkpoint, instruction configuration,
control space, seed subset and deployment settings with every new result. See
[EVALUATION.md](EVALUATION.md) and [EXTERNAL_AGENT.md](EXTERNAL_AGENT.md).

Internal working reports, incomplete runs and superseded checkpoint runs are excluded from this
source release. The paper and website are the published result records; no unverified score is
reconstructed from removed working notes. Website maintainers should cite this document for the
release protocol and retain the audited per-scene inputs used to generate their score tables.

New logs use English diagnostic field names. Historical private logs with localized field names
must be converted explicitly before passing them to the current reporting scripts.
