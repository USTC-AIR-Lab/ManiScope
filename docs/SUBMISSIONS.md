# Submitting an evaluation

Status: **v0.1 of the participation protocol.** The interfaces, file formats, schedule and
credential channel below are in force. Credentials go to
<sayleefilipski@gmail.com> and nowhere else — never into an issue, a pull request, a log or a
result file.

ManipScope is evaluation-only and its formal seed lists are private, so a score is only comparable
when it was produced on the organizer-held initial states. Participation therefore has three
stages: you verify your system locally on a **public development set**, you file a **request**, and
the organizers run the **official evaluation** on the private initial states.

Two kinds of contribution are in scope:

- **a new model** evaluated through the standard agent framework or an existing policy adapter;
- **a new method** — your own planner, memory, tools, skills or controller.

## 1. Local check on the development set

The development set is six scenes, one per task family, with locally generated expert-solvable
seeds (`suite/dev_set.yaml`). Its purpose is to prove that your model actually drives the robot and
that your logs export cleanly. **Development-set numbers are not leaderboard numbers**: every
participant generates their own development seeds, so the initial states differ between
participants and from the formal set.

```bash
# 1. environment and assets (see docs/INSTALLATION.md)
python3 tools/validate_repo.py && python3 -m pytest -q tests

# 2. interface check only, no simulator and no model calls
DRY_RUN=1 bash suite/run_dev_check.sh <policy_key>

# 3. generate development seeds, run the six scenes, export and validate a submission file
bash suite/run_dev_check.sh <policy_key>
```

`run_dev_check.sh` ends by calling `tools/export_submission.py` and `tools/validate_submission.py`,
so a clean run leaves you with the exact file the request asks for. Attach it to the request.

For an API model behind the standard agent framework, `<policy_key>` is the registered `eef_bridge`
agent and the only thing you change is a provider config file — see
[`configs/model_configs/README.md`](../configs/model_configs/README.md) and
[`docs/EXTERNAL_AGENT.md`](EXTERNAL_AGENT.md). For a model you host yourself, write an adapter as in
[policy integration](https://embodied-ai-research.github.io/ManipScope_webpage/usage/policy-integration/).

## 2. Filing a request

Requests and results are filed in the **website repository**, where the leaderboard is built:
<https://github.com/embodied-ai-research/ManipScope_webpage>. Open an issue there with the *Evaluation request* template, or a pull request adding
`submissions/<track>/<system>/<date>/submission.json`. Scene, seed and evaluator problems and new
task proposals belong in this repository instead, because they are code and protocol changes.

The request must contain:

- the exact system name and version as it should appear on the leaderboard;
- the track (`standard_agent` or `open_system`, see below);
- the model identifier, API interface, reasoning setting and output cap, or the checkpoint and
  weights location for an open-weights model;
- the commit of this repository you ran, and the commit or archive of your own code;
- the development-set `submission.json` produced above;
- a runnable recipe: launch command, config file contents **without credentials**, budgets;
- who pays for what (see [Cost](#5-cost-and-scheduling)).

Never put an API key, a bearer token or a private seed list in an issue, a pull request, a log or a
submission file. Credentials are exchanged over the private channel named below, and a key that
appears in a public place is treated as compromised and must be revoked.
`tools/validate_submission.py` rejects files that contain key-shaped strings or raw seed values;
the website repository runs the same check on every submission pull request.

Requests are acknowledged within **5 working days**, with a list of anything missing.

## 3. Official evaluation

The organizers run the same evaluator on the private initial states, with the budgets recorded in
the request, and publish the resulting score with the logs they produced. The protocol is the frozen
`formal48-v1` release: 48 scenes, and for agent systems the first 5 initial states per scene, 240
episodes in total. Policies use all 100 per scene (4,800 episodes).

A run is scheduled as a batch, not on demand:

| Stage | When |
| --- | --- |
| Development-set check | self-serve, any time |
| Request acknowledged, with anything missing listed | 5 working days |
| Batch cutoff | the 1st of each month; requests complete by then enter that batch |
| Official result published | within 15 days of the batch starting |
| Community-reported pull request merged or declined with a reason | 5 working days after CI passes |

Each system gets **one official run per protocol version**. A second run happens only when the
organizers change the harness or the protocol, or when a defect on the organizer side is recorded;
both results then stay visible with their dates and the superseded one is labelled. Re-requesting
does not buy a retry, and a failed or aborted official run is reported with its reason.

Admission to a batch is by measured cost, not by quota. Simulation time dominates and differs by an
order of magnitude between systems: at 240 episodes, the five agent runs in the paper cost between
18 and 188 GPU-hours. A batch holds roughly 150 GPU-hours, so in practice two to four agent systems
a month, or one policy checkpoint (4,800 episodes). A single system projected above 200 GPU-hours is
held over to its own batch and told why. The development set is one eighth of an agent run: report
its measured wall time per episode in the request, because that is what the batch is planned from.

## 4. Result status and tracks

Every leaderboard row carries two labels that must not be collapsed:

| Status | Meaning |
| --- | --- |
| `officially_evaluated` | produced by the organizers' evaluator on the private initial states |
| `community_reported` | produced by the submitter; format-checked only |

A schema check proves a file is well formed. It does not prove the numbers came from a real run, so
community-reported rows are useful for reproduction and are never presented as verified scores.
Development-set and formal-set results are displayed separately and never pooled.

Tracks separate two different questions:

| Track | Fixed by the organizers | Chosen by the participant |
| --- | --- | --- |
| `standard_agent` | prompt, tool schema, memory handling, controller, budgets | the base model and its request settings |
| `open_system` | the environment, the scenes, the seeds, the success rule | planner, tools, memory, skills, control policy |

The `standard_agent` track is the one that answers "which base model follows instructions better";
`open_system` compares complete systems. A single frozen protocol per track is a precondition for
reading a column as a model comparison: the five agent results in the paper were obtained under
differing instruction delivery and time budgets and are reported with those differences, not as a
controlled model comparison.

## 5. Cost and scheduling

Simulation is the organizers' cost; inference is normally the submitter's. State explicitly in the
request which side pays for the simulator GPU hours, the API tokens and, for open-weights models,
the inference GPUs.

- **API models**: provide an endpoint and a credential over the private channel; the organizers run
  the simulator and the agent framework against it.
- **Open-weights models**: provide a container image and a weights location; the organizers run both.

**Send the least dangerous thing that works.** The bridge accepts any HTTPS base URL, so the
preferred form is a gateway you control — your own proxy endpoint with a disposable token, a hard
spend cap and metering you can watch — rather than a provider root key. Whatever you send, scope it
to this evaluation, cap the spend and set an expiry where the provider supports one: a 188 GPU-hour
run is also a long billing window, and the cap protects you, not the organizers.

Credentials go to **<sayleefilipski@gmail.com>** and nowhere else — not an issue, not a pull
request, not a log, not a result file. A credential that appears in a public place is treated as
compromised and must be revoked. The organizers hold it only in the evaluation machine's private
runtime directory, and ask you to revoke it when the batch ends.

Start with the development set, then request the full 48-scene batch. One request per system per
batch; the organizers say in the acknowledgement which batch it entered.

## 6. What every result must record

The submission schema (`submissions/schema/submission.schema.json`) requires:

- exact model identifier, evaluation date, repository commit, protocol version;
- prompt/tool revision, reasoning setting, and the token, call and wall-time budgets, including
  whether the wall-time budget excludes provider waiting;
- per episode: success, termination reason, model calls, recorded steps and the three timings;
- all attempts, including retries and aborted runs. Partial uploads of successful episodes only are
  rejected: coverage is checked against the scene list and the declared episode count.

Action and environment feedback logs are enough. Hidden reasoning traces are not requested.

`tools/export_submission.py` fills these fields from what the evaluator already writes — the
per-scene `_run_metadata.json`, `_latency.txt` and `_instructions.txt`, the agent adapter's
`_agent_timing.jsonl`, and the per-episode success counter in `suite/logs/<run>/<scene>.log`. Keep
the run log: without it a policy run has no per-episode success labels. The evaluator is part of the
frozen protocol and is not modified to produce submissions.

Large logs and videos stay in your own storage (Hugging Face, object storage); the submission file
carries the summary plus links and digests.

## 7. New scenes and new tasks

Proposals for new scenes enter a development area first and are released with a new protocol
version, so the existing 48-scene leaderboard stays comparable. Changing scenes, seeds, instruction
pools or step limits requires a new protocol version, never a silent hash refresh
(see [docs/DEVELOPMENT.md](DEVELOPMENT.md)).

## Who does what

The organizer-side procedure — batch planning, credential handling, the official run commands and
the review checklist applied before a result is merged — is in
[docs/ORGANIZER_RUNBOOK.md](ORGANIZER_RUNBOOK.md), so you can see exactly what happens to a request
after it is filed.
