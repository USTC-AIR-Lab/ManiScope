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

The `standard_agent` tool surface is exactly two tools: `move_eef`, the only tool that actuates the
robot, and `finish`, which ends the attempt without establishing success — the environment decides.
Two tools is not little information: the three camera views, the measured end-effector and joint
state and the execution, contact and tracking feedback are supplied with every request rather than
fetched by the model. What the surface excludes is code execution, a shell, file access and
retrieval, so the model solves the manipulation problem itself instead of orchestrating other
software. Declare the surface in `system.tools`; for this track it must be exactly
`["finish", "move_eef"]`, which is what the agent framework the organizers run provides. This is the
checked-in tool schema, not an audit of the raw call logs of the systems already published.

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

## 7. Fair comparison rules

These rules exist so a column can be read as a comparison. Each one says who enforces it, because
the difference matters: some are properties of the harness, others are declarations the organizers
cannot verify from the outside.

**1. Track separation.** The standard track is for controlled comparison. A system with extra
training on the evaluation scenes, custom tools or its own planning module belongs in
`open_system`, and the two are displayed separately. Choosing the wrong track is not a disagreement
about scores; it makes the row unreadable.

**2. Training boundary.** The standard generalization track forbids training or adaptation data
built from the 48 evaluation scenes, and any leaked formal trajectory. Declare the provenance of
training and adaptation data in `system.training_data`. *Enforcement:* the evaluation scenes ship
without demonstrations and the formal seed lists are organizer-held, so the data does not exist in
the release; beyond that this is a declaration, and the validator asks for it rather than proving it.

**3. Uniform inputs.** A system receives the three specified RGB views, proprioception and the
instruction. Target identifiers, ground-truth object poses, hidden seeds and expert trajectories are
not provided and must not be obtained. *Enforcement:* by construction in `task_config/demo_clean.yml`
— depth, point cloud, mesh and actor segmentation are off, and the agent request carries images,
measured end-effector and joint state and execution feedback only. No privileged object state is
exposed to either interface.

**4. Isolated run environment.** The evaluated system must not read or modify the simulator, the
evaluation files or the scoring logic. *Enforcement:* for agents this is structural — the model runs
behind an authenticated loopback bridge in its own process, with the fixed two-tool surface in which
only `move_eef` actuates and `finish` ends the attempt. For a policy the adapter is imported into
the evaluator process, so isolation there rests on review: an official run uses an adapter the
organizers have read, with the model reached over the network. Submitted adapter code is read before
it is run.

**5. Locked submission version.** Fix the code, weights, configuration and dependencies before the
official run and keep them fixed throughout. Record the checkpoint or image digest in
`system.weights_digest`. Selecting a prepared answer per test instance is prohibited.
*Enforcement:* every scene writes the repository commit and dirty state, and
`tools/export_submission.py` refuses to export a run whose scenes disagree on commit, episode count
or task configuration. Per-instance switching is addressed by the hidden initial states, the
retained action logs and the spot checks in rule 7, not by inspecting the submitter's process.

**6. Memory and adaptation.** Within an episode, history and ordinary planning are allowed. State
resets between episodes, and test experience must not accumulate across episodes, nor weights be
updated during evaluation. *Enforcement:* the evaluator calls the adapter's reset between episodes
and the bridge's reset clears per-episode history and the call count; earlier images are dropped
before the next request. For a service the organizers do not control, the absence of cross-episode
learning is a declaration, which is why `system.hosting` records where inference ran.

**7. Protecting the formal set.** The formal initial states stay organizer-held; a formal scene
without its seed file is refused rather than silently run on other seeds. Each system gets one
official run per protocol version, and published feedback is the per-episode outcome, termination
reason, call count and timings — not the initial states or instruction-to-seed mapping. The
organizers additionally spot-check with unpublished but legal layout and instruction variations, so
a system tuned to specific remembered episodes does not transfer.

**8. Organizer scoring and records.** The organizers run all specified episodes and record success,
timings, actions and anomalies, including retries and discarded runs. A result obtained through a
remote black-box service is labelled: `system.hosting` is `remote_blackbox` and
`run.verification_scope` states what the organizers could verify themselves and what rests on the
submitter's word.

None of this makes cheating impossible. It makes the comparable claim precise and the unverifiable
part visible, which is the most an evaluation-only benchmark can honestly offer.

## Who does what

The organizer-side procedure — batch planning, credential handling, the official run commands and
the review checklist applied before a result is merged — is in
[docs/ORGANIZER_RUNBOOK.md](ORGANIZER_RUNBOOK.md), so you can see exactly what happens to a request
after it is filed.
