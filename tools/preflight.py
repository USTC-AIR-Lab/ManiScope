"""Validate evaluation inputs without importing simulation or model packages."""
import argparse
import json
import os
from pathlib import Path
import re
import yaml
ROOT = Path(__file__).resolve().parents[1]

def validate(tasks, episodes, task_config, frozen=True, root=ROOT):
    errors = []
    if episodes < 1:
        errors.append("episodes must be positive")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", task_config) or not (root / "task_config" / (task_config + ".yml")).is_file():
        errors.append("unknown task configuration")
    for task in tasks:
        if not re.fullmatch(r"[A-Za-z0-9_]+", task):
            errors.append("invalid task name"); continue
        for folder, suffix in [("envs", ".py"), ("description/task_instruction", ".json")]:
            if not (root / folder / (task + suffix)).is_file():
                errors.append(f"{task}: missing {folder} file")
        if frozen:
            p = root / "suite/seeds" / (task + ".json")
            if not p.is_file():
                errors.append(f"{task}: missing frozen seeds (formal seed lists are held by the organizers; "
                              "generate development seeds with suite/gen_seeds.py)")
            else:
                data = json.loads(p.read_text())
                if len(data.get("seeds", [])) < episodes:
                    errors.append(f"{task}: fewer frozen seeds than requested episodes")
    return errors

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--episodes", type=int, default=50)
    ap.add_argument("--task-config", default="demo_clean")
    ap.add_argument("tasks", nargs="+")
    a = ap.parse_args()
    errors = validate(a.tasks, a.episodes, a.task_config, os.environ.get("ROBOTWIN_FROZEN_SEEDS", "1") != "0")
    if errors:
        raise SystemExit("Preflight failed:\n" + "\n".join(errors))

if __name__ == "__main__": main()
