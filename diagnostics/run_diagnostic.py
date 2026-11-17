"""Run one language-following diagnostic for one registered policy, sequentially on one GPU.

  python diagnostics/run_diagnostic.py plan rotation                      list the jobs of a diagnostic
  python diagnostics/run_diagnostic.py run rotation --policy dm05         run them against a policy server
  python diagnostics/run_diagnostic.py run rotation --policy dm05 --start-server --gpu 0

Diagnostics (conditions in diagnostics/conditions.py):
  rotation          target reassignment on held-out scenes, plus the empty-instruction condition
  training_control  instruction change on unmodified RoboTwin training tasks
  source_baseline   linked RoboTwin source tasks with their training instruction (--extra: all 30 linked tasks)
  selection_events  formal pick-type scenes with gripper-state contact classification
  first_decision    first 16 commands under instruction x layout changes, three repeats

The policy is looked up in suite/policies.yaml. Without --start-server the server must already listen on
--port (default: the registry port). Each job writes <out>/<diagnostic>/<policy>/<task>/<job>/probe.jsonl with
one record per episode; finished jobs are skipped on re-run. Analyse with diagnostics/analysis/*.py.
"""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from conditions import (FIRST_DECISION, ROTATION, ROTATION_STATES, SELECTION_SCENES, SOURCE_SEEDS,  # noqa: E402
                        SOURCE_TASKS, SOURCE_TASKS_EXTRA, TRAINING_CONTROL, TRAINING_CONTROL_SEEDS)

DIAGNOSTICS = ("rotation", "training_control", "source_baseline", "selection_events", "first_decision")


def plan(diagnostic, episodes=5, extra=False, task_name_instruction=False):
    """Return [(job name, job dict)]."""
    jobs = []
    if diagnostic == "rotation":
        for scene, conds in ROTATION.items():
            for cond, role, instr in conds:
                jobs.append((f"{scene}__{cond}", dict(task=scene, condition=cond, target_role=role, instruction=instr,
                                                       episodes=ROTATION_STATES, seed=0, frozen=True)))
    elif diagnostic == "training_control":
        for task, spec in TRAINING_CONTROL.items():
            for seed in TRAINING_CONTROL_SEEDS:
                for cond, instr in spec["conditions"]:
                    jobs.append((f"{task}__{cond}__s{seed}", dict(
                        task=task, condition=cond, instruction=instr, roles=spec["roles"], seed=seed,
                        episodes=episodes, frozen=False, instruction_type="seen" if instr is None else None)))
    elif diagnostic == "source_baseline":
        for task in SOURCE_TASKS + (SOURCE_TASKS_EXTRA if extra else []):
            for seed in SOURCE_SEEDS:
                # some checkpoints are conditioned on the task name rather than a natural-language instruction
                instr = task.replace("_", " ") if task_name_instruction else None
                jobs.append((f"{task}__{'taskname' if instr else 'train'}__s{seed}", dict(
                    task=task, condition="taskname" if instr else "train", instruction=instr, seed=seed,
                    episodes=episodes, frozen=False, instruction_type=None if instr else "seen")))
    elif diagnostic == "selection_events":
        for scene in SELECTION_SCENES:
            jobs.append((f"{scene}__formal", dict(task=scene, condition="formal", instruction=None, episodes=20,
                                                  seed=0, frozen=True, grip=True)))
    elif diagnostic == "first_decision":
        fd = FIRST_DECISION
        for color, role in fd["colors"]:
            for layout in fd["layouts"]:
                for rep in range(fd["repeats"]):
                    jobs.append((f"{fd['task']}__{color}_{layout}__r{rep}", dict(
                        task=fd["task"], condition=f"{color}_{layout}_r{rep}", instruction=f"Pick up the {color} block.",
                        target_role=role, swap=fd["swap"] if layout == "swapped" else None,
                        first_chunk=fd["commands"], episodes=fd["states"], seed=0, frozen=True)))
    else:
        raise SystemExit(f"unknown diagnostic {diagnostic!r}; choose from {DIAGNOSTICS}")
    return jobs


def base_env():
    env = dict(os.environ)
    local = REPO / "configs/local.env"
    if local.exists():
        out = subprocess.run(["bash", "-c", f"set -a; source {local}; set +a; env -0"],
                             capture_output=True, check=True).stdout.decode()
        env.update(kv.split("=", 1) for kv in out.split("\0") if "=" in kv)
    env.setdefault("ROBOTWIN_PYTHON", "python3")
    return env


def port_open(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_server(meta, gpu, port, log):
    if port_open(port):
        raise SystemExit(f"port {port} already in use")
    env = base_env()
    env.update(GPU=str(gpu), PORT=str(port))
    p = subprocess.Popen(["bash", str(REPO / meta["launch"])], cwd=REPO, env=env, stdout=open(log, "ab"),
                         stderr=subprocess.STDOUT, start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 1800:
        if port_open(port):
            return p
        if p.poll() is not None:
            raise SystemExit(f"server exited rc={p.returncode}; see {log}")
        time.sleep(5)
    os.killpg(p.pid, signal.SIGTERM)
    raise SystemExit("server start timeout")


def run_job(meta, port, gpu, outdir, job):
    outdir.mkdir(parents=True, exist_ok=True)
    probe_log = outdir / "probe.jsonl"
    if probe_log.exists():
        probe_log.unlink()
    env = base_env()
    env.update(CUDA_VISIBLE_DEVICES=str(gpu), ROBOTWIN_FROZEN_SEEDS="1" if job["frozen"] else "0",
               ROBOTWIN_VIDEO_FIRST_N="2", EVAL_WRIST_VIDEO="0", PROBE_LOG=str(probe_log),
               PROBE_CONDITION=job["condition"], PROBE_SEED_OFFSET=str(job.get("seed_offset", 0)),
               PROBE_TOOLS=str(REPO / "diagnostics"))
    for key, var in (("target_role", "PROBE_TARGET_ROLE"), ("swap", "PROBE_SWAP")):
        if job.get(key):
            env[var] = job[key]
    if job.get("instruction") is not None:
        env["PROBE_INSTRUCTION"] = job["instruction"]
    if job.get("roles"):
        env["PROBE_ROLES"] = json.dumps(job["roles"])
    if job.get("grip"):
        env["PROBE_GRIP"] = "1"
    if job.get("first_chunk"):
        env["PROBE_FIRST_CHUNK"] = str(int(job["first_chunk"]))
    conn = (["--policy_port", str(port)] if meta.get("server") == "socket"
            else ["--base_url", f"http://127.0.0.1:{port}"])
    cmd = [env["ROBOTWIN_PYTHON"], "script/eval_diagnostic.py",
           "--config", f"policy/{meta['policy_name']}/deploy_policy.yml", "--overrides",
           "--task_name", job["task"], "--task_config", "demo_clean", "--ckpt_setting", meta["ckpt_setting"],
           "--seed", str(job["seed"]), "--policy_name", meta["policy_name"],
           "--eval_num_episodes", str(job["episodes"]), "--max_success_videos", "2",
           "--max_failure_videos", "2", "--eval_output_dir", str(outdir)] + conn
    if job.get("instruction_type"):
        cmd += ["--instruction_type", job["instruction_type"]]
    with open(outdir / "eval.log", "wb") as f:
        rc = subprocess.run(cmd, cwd=REPO, env=env, stdout=f, stderr=subprocess.STDOUT).returncode
    n = sum(1 for _ in open(probe_log)) if probe_log.exists() else 0
    (outdir / "job.json").write_text(json.dumps(dict(job, rc=rc, records=n), indent=1))
    return rc == 0 and n == job["episodes"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("plan", "run"))
    ap.add_argument("diagnostic", choices=DIAGNOSTICS)
    ap.add_argument("--policy", help="key in suite/policies.yaml")
    ap.add_argument("--port", type=int, help="policy server port (default: registry port)")
    ap.add_argument("--gpu", type=int, default=0, help="GPU for the simulator (and the server with --start-server)")
    ap.add_argument("--start-server", action="store_true", help="launch the registry launcher with configs/local.env")
    ap.add_argument("--out", default=str(REPO / "runs/diagnostics"))
    ap.add_argument("--episodes", type=int, default=5, help="episodes per RoboTwin seed (training_control, source_baseline)")
    ap.add_argument("--extra", action="store_true", help="source_baseline: all 30 linked source tasks")
    ap.add_argument("--task-name-instruction", action="store_true",
                    help="source_baseline: give the task name as the instruction (task-name-conditioned checkpoints)")
    ap.add_argument("--only", default="", help="comma-separated task names")
    a = ap.parse_args()
    jobs = plan(a.diagnostic, a.episodes, a.extra, a.task_name_instruction)
    if a.only:
        jobs = [(n, j) for n, j in jobs if j["task"] in a.only.split(",")]
    if a.cmd == "plan":
        for name, job in jobs:
            print(json.dumps(dict(name=name, **job)))
        return
    if not a.policy:
        raise SystemExit("--policy is required for run")
    meta = yaml.safe_load(open(REPO / "suite/policies.yaml"))["policies"][a.policy]
    port = a.port or int(meta["port"])
    root = Path(a.out) / a.diagnostic / a.policy
    root.mkdir(parents=True, exist_ok=True)
    srv = start_server(meta, a.gpu, port, root / "server.log") if a.start_server else None
    failed = []
    try:
        for i, (name, job) in enumerate(jobs, 1):
            outdir = root / job["task"] / name
            done = outdir / "job.json"
            if done.exists() and json.loads(done.read_text()).get("records") == job["episodes"]:
                continue
            t0 = time.time()
            ok = run_job(meta, port, a.gpu, outdir, job)
            print(f"[{i}/{len(jobs)}] {name}: {'ok' if ok else 'FAILED'} ({time.time() - t0:.0f} s)", flush=True)
            if not ok:
                failed.append(name)
    finally:
        if srv and srv.poll() is None:
            os.killpg(srv.pid, signal.SIGTERM)
    if failed:
        raise SystemExit(f"{len(failed)} job(s) failed, see eval.log in: {', '.join(failed)}")


if __name__ == "__main__":
    main()
