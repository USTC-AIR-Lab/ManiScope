#!/usr/bin/env python3
"""Turn an evaluation run directory into a submission file.

Reads the per-scene output written by suite/run_suite.sh (`_run_metadata.json`, `_latency.txt`,
`_instructions.txt`, and `_agent_timing.jsonl` for agent runs) together with the evaluator log under
`suite/logs/<run>/<scene>.log`, and writes one submission JSON following
submissions/schema/submission.schema.json. The evaluator itself is part of the frozen protocol and
is not modified: per-episode success comes from the cumulative success counter the evaluator prints
after every episode. Frozen seed values are organizer-held and are dropped from the output unless
--include-seeds is given, which must only be used for private internal copies.

    python3 tools/export_submission.py eval_result/<run> \
        --display-name "My Model" --track standard_agent --kind agent \
        --model-id my-model-2026-11 --out submission.json
"""
import argparse
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES = os.path.join(ROOT, "suite", "scenes_v2.yaml")
DEV_SET = os.path.join(ROOT, "suite", "dev_set.yaml")
# "Success rate: <suc>/<test_num> => ..., current seed: <seed>", printed once per episode.
RATE_RE = re.compile(r"Success rate:\s*(?:\x1b\[[0-9;]*m)?(\d+)/(\d+)")


def load_yaml(path):
    try:
        import yaml
    except ImportError:
        return None
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def scene_families():
    data = load_yaml(SCENES) or {}
    return {str(sc["name"]): axis for axis, block in (data.get("axes") or {}).items()
            for sc in (block.get("scenes") or []) if not str(sc.get("name", "<")).startswith("<")}


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    return rows


def read_instructions(path):
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3 and parts[0].startswith("episode"):
                try:
                    out[int(parts[0][7:])] = parts[2]
                except ValueError:
                    pass
    return out


def read_latency(path):
    """episode index -> timing fields recorded by the evaluator."""
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            fields = dict(p.split("=", 1) for p in line.strip().split("\t")[1:] if "=" in p)
            head = line.strip().split("\t")[0]
            if not head.startswith("episode"):
                continue
            try:
                index = int(head[7:])
            except ValueError:
                continue
            num = lambda k: (float(fields[k]) if fields.get(k, "-") not in ("-", "") else None)  # noqa: E731
            out[index] = {"model_calls": int(float(fields.get("calls", 0))),
                          "recorded_steps": int(float(fields.get("steps", 0))),
                          "eval_wall_s": num("eval_wall_total"),
                          "model_s": num("model_total"),
                          "episode_wall_s": num("episode_wall")}
    return out


def log_success_labels(log_path):
    """Per-episode success from the cumulative counter the evaluator prints after each episode."""
    if not os.path.exists(log_path):
        return None
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        pairs = [(int(a), int(b)) for a, b in RATE_RE.findall(fh.read())]
    labels, previous = [], 0
    for index, (successes, total) in enumerate(pairs):
        if total != index + 1:
            return None                      # interleaved or truncated log: refuse to guess
        labels.append(successes > previous)
        previous = successes
    return labels


def episode_records(scene_dir, scene, log_path, include_seeds):
    """Per-episode records for one scene, from the richest source available."""
    agent = os.path.join(scene_dir, "_agent_timing.jsonl")
    latency = os.path.join(scene_dir, "_latency.txt")
    instructions_path = os.path.join(scene_dir, "_instructions.txt")
    instructions = read_instructions(instructions_path) if os.path.exists(instructions_path) else {}
    timings = read_latency(latency) if os.path.exists(latency) else {}
    labels = log_success_labels(log_path)

    rows = []
    if os.path.exists(agent):
        # Agent runs: the adapter ledger carries success, termination, calls and timings directly.
        for row in read_jsonl(agent):
            index = int(row.get("episode", 0))
            timing = timings.get(index, {})
            success = bool(row.get("success"))
            if labels is not None and index < len(labels) and labels[index] != success:
                raise SystemExit("%s episode %d: adapter ledger says success=%s, evaluator log says %s"
                                 % (scene, index, success, labels[index]))
            rec = {"scene": scene, "index": index, "success": success,
                   "termination": normalise_termination(row.get("termination"), success),
                   "model_calls": int(row.get("api_calls") or 0),
                   "recorded_steps": int(row.get("sim_steps") or timing.get("recorded_steps") or 0),
                   "model_s": round(float(row.get("api_seconds") or 0.0), 4),
                   "episode_wall_s": round(float(row.get("wall_seconds") or 0.0), 4)}
            for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
                if row.get(key):
                    rec[key] = int(row[key])
            if timing.get("eval_wall_s") is not None:
                rec["eval_wall_s"] = round(timing["eval_wall_s"], 4)
            rows.append((rec, row.get("seed")))
    elif labels:
        # Policy runs: success from the evaluator log, timings from the evaluator's own latency file.
        for index, success in enumerate(labels):
            timing = timings.get(index, {})
            rec = {"scene": scene, "index": index, "success": success,
                   "termination": "success" if success else "unknown"}
            for key in ("model_calls", "recorded_steps", "model_s", "eval_wall_s", "episode_wall_s"):
                if timing.get(key) is not None:
                    rec[key] = round(timing[key], 4) if key.endswith("_s") else int(timing[key])
            rows.append((rec, None))
    else:
        raise SystemExit(
            "%s: no per-episode success labels.\n"
            "Expected either %s (agent runs) or the evaluator log %s, which records the cumulative\n"
            "success counter after every episode. Keep the run log produced by suite/run_suite.sh."
            % (scene, agent, log_path))

    out = []
    for rec, seed in sorted(rows, key=lambda r: r[0]["index"]):
        if rec["index"] in instructions:
            rec["instruction"] = instructions[rec["index"]]
        if include_seeds and seed is not None:
            rec["seed"] = seed            # private copies only; never in a public submission
        out.append(rec)
    return out


def normalise_termination(value, success):
    if success:
        return "success"
    text = str(value or "").lower()
    if not text or text == "none":
        return "unknown"
    for needle, label in (("model_finish", "model_finish"), ("finish", "model_finish"),
                          ("wall", "wall_budget"), ("call_budget", "call_budget"),
                          ("step", "step_limit"), ("reject", "rejected"), ("error", "error")):
        if needle in text:
            return label
    return "unknown"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", help="eval_result/<RUN_NAME>")
    parser.add_argument("--out", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--track", choices=["standard_agent", "open_system"], required=True)
    parser.add_argument("--kind", choices=["agent", "policy"], required=True)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--api-interface", default=None,
                        choices=["responses", "chat", "anthropic", "generateContent", "local", "other"])
    parser.add_argument("--reasoning", default=None)
    parser.add_argument("--output-cap-tokens", type=int, default=None)
    parser.add_argument("--max-model-calls", type=int, default=120)
    parser.add_argument("--wall-time-s", type=float, default=3300)
    parser.add_argument("--wall-excludes-api-wait", action="store_true")
    parser.add_argument("--protocol-version", default="formal48-v1")
    parser.add_argument("--evaluated-by", choices=["submitter", "organizers"], default="submitter")
    parser.add_argument("--hardware", default=None)
    parser.add_argument("--log-dir", default=None,
                        help="evaluator logs; default suite/logs/<run name>")
    parser.add_argument("--include-seeds", action="store_true",
                        help="internal use only: keep frozen seed values in the output")
    args = parser.parse_args()

    scene_dirs = []
    for dirpath, _dirnames, filenames in os.walk(args.run_dir):
        if "_run_metadata.json" in filenames:
            scene_dirs.append(dirpath)
    if not scene_dirs:
        raise SystemExit("no _run_metadata.json under %s" % args.run_dir)

    families = scene_families()
    dev = set((load_yaml(DEV_SET) or {}).get("scenes") or [])
    scenes, episodes = [], []
    commits, episode_counts, configs = {}, {}, {}
    dirty = False
    instruction_type = None
    for scene_dir in sorted(scene_dirs):
        with open(os.path.join(scene_dir, "_run_metadata.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
        scene = meta["task"]
        commits.setdefault(meta.get("commit"), []).append(scene)
        episode_counts.setdefault(int(meta.get("episodes") or 0), []).append(scene)
        configs.setdefault(meta.get("task_config"), []).append(scene)
        dirty = dirty or bool(meta.get("dirty"))
        log_dir = args.log_dir or os.path.join(ROOT, "suite", "logs", os.path.basename(args.run_dir.rstrip("/")))
        records = episode_records(scene_dir, scene, os.path.join(log_dir, scene + ".log"),
                                  args.include_seeds)
        episodes.extend(records)
        scenes.append({"name": scene, "family": families.get(scene, "unknown"),
                       "episodes": len(records),
                       "successes": sum(1 for r in records if r["success"])})

    # One run, one commit, one episode count, one task config: anything else is not a single
    # evaluation and must not be exported as one.
    for label, groups in (("commit", commits), ("episodes per scene", episode_counts),
                          ("task config", configs)):
        if len(groups) > 1:
            detail = "; ".join("%s: %s%s" % (k, ", ".join(v[:3]), " ..." if len(v) > 3 else "")
                               for k, v in groups.items())
            raise SystemExit("scenes in this run disagree on %s - %s\n"
                             "An official result names one configuration. Re-run the scenes that "
                             "differ, or export them as separate submissions." % (label, detail))
    commit = next(iter(commits))
    per_scene = next(iter(episode_counts))
    task_config = next(iter(configs))

    names = {s["name"] for s in scenes}
    scene_set = "formal48" if len(names) == 48 else ("dev6" if dev and names == dev else "other")
    doc = {
        "schema_version": "manipscope-submission-0.1",
        "status": "community_reported" if args.evaluated_by == "submitter" else "officially_evaluated",
        "system": {"display_name": args.display_name, "track": args.track, "kind": args.kind},
        "protocol": {"version": args.protocol_version, "scene_set": scene_set,
                     "episodes_per_scene": per_scene or (len(episodes) // max(1, len(scenes))),
                     "task_config": task_config or "demo_clean",
                     "instruction_type": instruction_type or "unseen",
                     "seed_source": "organizer_formal" if scene_set == "formal48" else "self_generated_dev"},
        "run": {"date": date.today().isoformat(), "repo_commit": (commit or "")[:40],
                "repo_dirty": bool(dirty), "evaluated_by": args.evaluated_by},
        "budgets": {"max_model_calls_per_episode": args.max_model_calls,
                    "wall_time_s_per_episode": args.wall_time_s,
                    "wall_time_excludes_api_wait": bool(args.wall_excludes_api_wait),
                    "step_limit_source": "task_config/_eval_step_limit.yml"},
        "scenes": sorted(scenes, key=lambda s: s["name"]),
        "episodes": episodes,
    }
    for key, value in (("model_id", args.model_id), ("api_interface", args.api_interface),
                       ("reasoning", args.reasoning), ("output_cap_tokens", args.output_cap_tokens)):
        if value is not None:
            doc["system"][key] = value
    if args.hardware:
        doc["run"]["hardware"] = args.hardware

    total_ep = sum(s["episodes"] for s in scenes)
    total_su = sum(s["successes"] for s in scenes)
    by_family = {}
    for scene in scenes:
        by_family.setdefault(scene["family"], []).append(scene["successes"] / max(1, scene["episodes"]))
    family_pct = {f: round(100.0 * sum(v) / len(v), 4) for f, v in by_family.items()}
    doc["results"] = {"overall_pct": round(sum(family_pct.values()) / max(1, len(family_pct)), 4),
                      "pooled_pct": round(100.0 * total_su / max(1, total_ep), 4),
                      "family_pct": family_pct}

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("wrote %s: %d scenes, %d episodes, Overall %.2f%%, Pooled %.2f%%"
          % (args.out, len(scenes), total_ep, doc["results"]["overall_pct"], doc["results"]["pooled_pct"]))
    if args.include_seeds:
        print("WARNING: seed values retained; this file must not be published or attached to an issue.")
    print("next: python3 tools/validate_submission.py %s" % args.out)


if __name__ == "__main__":
    sys.exit(main())
