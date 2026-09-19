"""Explicitly update protocol hashes after reviewing a benchmark version change."""
import argparse
import hashlib
import json
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[1]

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", required=True)
    a = ap.parse_args()
    s = yaml.safe_load((ROOT / "suite/scenes_v2.yaml").read_text())
    names = [v["name"] for axis in s["axes"].values() for v in axis["scenes"]]
    files = {"suite/scenes_v2.yaml", "suite/table.py", "script/eval_policy.py", "task_config/_eval_step_limit.yml", "envs/_base_task.py", "envs/_compo_scene.py"}
    for n in names:
        files.update([f"envs/{n}.py", f"description/task_instruction/{n}.json", f"suite/seeds/{n}.json"])
    for folder in ["envs/utils", "envs/robot", "description/utils", "description/objects_description", "description/task_instruction", "task_config"]:
        for p in (ROOT / folder).rglob("*"):
            if p.is_file() and p.suffix in ['.py','.json','.yml','.yaml']: files.add(str(p.relative_to(ROOT)))
    (ROOT / "protocol.lock.json").write_text(json.dumps({"version": a.version, "sha256": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in sorted(files)}}, indent=2) + "\n")

if __name__ == "__main__": main()
