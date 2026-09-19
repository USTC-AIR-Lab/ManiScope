"""Record reproducibility metadata; never serialize credentials or the full environment."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
out, policy, task, episodes, task_config = sys.argv[1:]
root = Path(__file__).resolve().parents[1]
def git(*args):
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None
paths = ["suite/scenes_v2.yaml", "suite/policies.yaml", f"suite/seeds/{task}.json", "protocol.lock.json"]
record = {"created_utc": datetime.now(timezone.utc).isoformat(), "commit": git("rev-parse", "HEAD"),
          "dirty": bool(git("status", "--porcelain")), "policy": policy, "task": task,
          "episodes": int(episodes), "task_config": task_config,
          "controls": {k: os.environ.get(k) for k in ["ROBOTWIN_FROZEN_SEEDS", "ROBOTWIN_VIDEO_FIRST_N", "EVAL_WRIST_VIDEO"]},
          "sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths if (root / p).is_file()}}
Path(out, "_run_metadata.json").write_text(json.dumps(record, indent=2) + "\n")
