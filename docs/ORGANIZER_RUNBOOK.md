# Organizer runbook

Internal counterpart to [SUBMISSIONS.md](SUBMISSIONS.md). The public page states the commitments;
this page states how they are met. One value is deliberately left for the organizers to create: the
role address in [Credentials](#credentials).

## Capacity: what an official run costs

Simulation time dominates and is measured, not estimated. From the five agent runs in the paper, at
240 episodes per system (48 scenes x 5 initial states):

| System | Evaluator wall time per episode | One official run |
| --- | --- | --- |
| GPT-6.2 Astra | 276 s | 18 GPU-hours |
| GPT-6 Astra (September) | 710 s | 47 GPU-hours |
| Opus 5.5 | 822 s | 55 GPU-hours |
| Gemini 3.8 Flash | 1,984 s | 132 GPU-hours |
| Gemini 4 Argon | 2,816 s | 188 GPU-hours |

A slow model therefore costs ten times a fast one, so capacity is set per batch from measurement
rather than per system from a quota. The development set is 30 episodes, one eighth of an agent run:
multiply the development run's measured wall time per episode by 240 to plan the official run, and
require that figure in the request.

A policy checkpoint is 4,800 episodes (100 initial states per scene) and is scheduled separately;
quote it from the submitter's own measured per-episode time the same way.

**Batch rule.** One simulation GPU, run back to back, covers roughly 150 GPU-hours a week with
headroom for failures and reruns. Admit systems to a batch until the projected total reaches that
figure — in practice two to four agent systems per month, or one policy checkpoint. Projected cost
above 200 GPU-hours for a single system is held over to its own batch and the submitter is told why.

## Schedule

| Stage | Commitment |
| --- | --- |
| Development-set check | self-serve, any time, no organizer involvement |
| Acknowledging a request and saying what is missing | 5 working days |
| Batch cutoff | the 1st of each month; requests complete by then enter that batch |
| Official result published | within 15 days of the batch starting |
| Community-reported pull request merged or declined with a reason | 5 working days after CI passes |

Each system gets **one official run per protocol version**. A second run happens only when the
organizers change the harness or the protocol, or when a defect on the organizer side is identified
and recorded; both results then stay visible with their dates, the superseded one labelled as such.
A submitter cannot buy a retry by re-requesting, and a failed or aborted official run is reported
with the reason rather than silently repeated.

## Credentials

`TODO(organizers)`: create a role address — a mailbox or forwarding alias owned by the group, not a
personal account — and put it in SUBMISSIONS.md where the private channel is named. A role address
survives personnel changes and keeps a personal identity out of a public repository, which also
matters while the paper is under anonymous review.

Rules that apply once it exists:

- Keys arrive only at that address, never in an issue, a pull request, a log or a result file. A key
  that appears in a public place is treated as compromised: ask the submitter to revoke it.
- Require a key scoped to the submitter's own project with a spending cap and, where the provider
  supports it, an expiry date. The cap is the submitter's protection, not the organizers'.
- Store it only in the evaluation machine's private runtime directory (`AGENT_RUNTIME_DIR`, mode
  700, files 600), never in the repository, never in a shell history, never in a scheduler job file.
- Delete the key locally and ask the submitter to revoke it when the batch ends; record the date of
  revocation in the private run record, not in the published result.
- A stronger option once the group has an OpenPGP key: publish the public key in SECURITY.md and ask
  submitters to encrypt the credential to it. Do this before accepting high-value keys.

## Running an official evaluation

```bash
# 1. the submitter's declared configuration, reproduced from the request
export AGENT_RUNTIME_DIR=/private/run/<system>        # mode 700
#    provider.json and api_key from the private channel; budget_config.json and budget_ledger.json
#    per docs/EXTERNAL_AGENT.md, with a cap that covers this batch and nothing more

# 2. the formal scene set with the organizer-held seed lists in place
AUTO_LAUNCH=0 PORT=18770 GPT6_BRIDGE_TOKEN_FILE=$AGENT_RUNTIME_DIR/bridge.token \
  EPISODES=5 RUN_NAME=official_<system>_<date> bash suite/run_suite.sh eef_bridge

# 3. export, mark as official, and validate
python3 tools/export_submission.py eval_result/official_<system>_<date> \
  --out submissions/standard_agent/<system>/<date>/submission.json \
  --display-name "<System>" --track standard_agent --kind agent \
  --model-id <exact id> --evaluated-by organizers
python3 tools/validate_submission.py --allow-official --strict \
  submissions/standard_agent/<system>/<date>/submission.json
```

Keep the run log directory: `tools/export_submission.py` reads the per-episode success counter from
`suite/logs/<run>/<scene>.log`, and the raw logs are the evidence behind an official row.

Never publish the seed-bearing material: `--include-seeds` is for private internal copies only, and
per-episode initial poses, seed lists and instruction-to-seed mappings stay in the private analysis
space. The published submission file identifies episodes by index.

## Review checklist before merging a result

1. CI passed on the pull request (schema, coverage, recomputed Overall and Pooled, credential scan).
2. `status` matches reality: `officially_evaluated` only for a run the organizers performed.
3. Coverage is complete: 48 scenes, the declared episode count, every attempt reported including
   retries and discarded runs.
4. The declared configuration matches what was actually run — model id, reasoning setting, output
   cap, call and wall-time budgets, and whether the wall-time budget excluded provider waiting.
5. Artifact links resolve and their digests match.
6. The row's protocol version is recorded, and a result from a different protocol version is not
   placed in the same table as `formal48-v1` rows.

## Notifications

Nothing in this repository sends mail. Workflow runs and submission activity reach the organizers
through their own GitHub notification settings, which keeps personal addresses out of a public
repository:

- watch the repository with **Custom**: Issues, Pull requests and Actions failures;
- set the notification email for this organization in the GitHub account settings;
- `.github/CODEOWNERS` requests review from the organizer team on every `submissions/**` change, so
  a submission pull request produces a review-request notification.

Do not add an SMTP-based mail action to the submission workflow: pull requests from forks cannot read
repository secrets, so it would fail exactly when it is needed.
