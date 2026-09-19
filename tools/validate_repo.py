"""Check the portable repository and frozen evaluation contract without a GPU."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import yaml
ROOT = Path(__file__).resolve().parents[1]

def validate(root=ROOT):
    errors = []
    manifest = yaml.safe_load((root / "suite/scenes_v2.yaml").read_text())
    tasks = [v["name"] for a in manifest["axes"].values() for v in a["scenes"]]
    if len(tasks) != 48 or len(set(tasks)) != 48: errors.append("formal48 requires 48 unique scenes")
    step_limits = yaml.safe_load((root / "task_config/_eval_step_limit.yml").read_text())
    for task in tasks:
        for folder, suffix in [("envs", ".py"), ("description/task_instruction", ".json"), ("suite/seeds", ".json")]:
            if not (root / folder / (task + suffix)).is_file(): errors.append(f"missing {folder}/{task}{suffix}")
        if task not in step_limits: errors.append(f"missing step limit: {task}")
        p = root / "suite/seeds" / (task + ".json")
        if p.is_file():
            d = json.loads(p.read_text()); seeds = d.get("seeds", [])
            if len(seeds) != 100 or len(set(seeds)) != 100 or d.get("count") != len(seeds): errors.append(f"invalid frozen seeds: {task}")
        p = root / "description/task_instruction" / (task + ".json")
        if p.is_file():
            d = json.loads(p.read_text())
            if not d.get("seen") or not d.get("unseen"): errors.append(f"empty instruction pool: {task}")
    policies = yaml.safe_load((root / "suite/policies.yaml").read_text())["policies"]
    for name, p in policies.items():
        for f in ["deploy_policy.py", "deploy_policy.yml"]:
            if not (root / "policy" / p["policy_name"] / f).is_file(): errors.append(f"missing adapter: {name}/{f}")
        if p.get("launch") and not (root / p["launch"]).is_file(): errors.append(f"missing launcher: {name}")
        if not p.get("launch") and not p.get("external_only"): errors.append(f"undocumented external backend: {name}")
    files = []
    for folder in ["envs", "policy", "suite", "script", "tools", "tests", "description", "code_gen", "data", "configs", "requirements", "docs"]:
        for p in (root / folder).rglob("*"):
            if any(x in p.parts for x in ["__pycache__", "logs", "results", "out"]): continue
            if p == root / "configs/local.env" or "private" in p.parts: continue
            if p.is_symlink(): errors.append(f"nonportable symlink: {p.relative_to(root)}"); continue
            if p.is_file(): files.append(p)
    credential = re.compile(r"-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{30,}")
    for p in files:
        if p.suffix not in [".py", ".sh", ".md", ".txt", ".json", ".yml", ".yaml", ".env"]: continue
        try: text = p.read_text()
        except UnicodeError: continue
        rel = str(p.relative_to(root))
        if p.suffix == ".py":
            try: ast.parse(text, filename=rel)
            except SyntaxError as exc: errors.append(f"{rel}:{exc.lineno}: syntax error")
        if 'curobo' in p.parts: continue  # Keep third-party snapshots unmodified.
        if re.search(r"/(?:mnt/netdata|sharpa_vepfs_d)/", text): errors.append(f"personal deployment path: {rel}")
        if credential.search(text): errors.append(f"credential-like content: {rel}")
        if p.suffix == ".sh":
            result = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
            if result.returncode: errors.append(f"{rel}: shell syntax error")
    lock = root / "protocol.lock.json"
    if lock.is_file():
        for f, expected in json.loads(lock.read_text())["sha256"].items():
            p = root / f
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected: errors.append(f"frozen protocol changed: {f}")
    else: errors.append("missing protocol.lock.json")
    return errors, {"scenes": len(tasks), "policies": len(policies), "checked_files": len(files)}

if __name__ == "__main__":
    errors, counts = validate()
    print(json.dumps({"ok": not errors, **counts, "errors": errors}, indent=2))
    sys.exit(bool(errors))
