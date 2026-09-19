"""Create an ignored local assets link; never edit the resource directory."""
import argparse
from pathlib import Path

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("directory", type=Path)
    a = ap.parse_args()
    target = a.directory.resolve(strict=True)
    for name in ("objects", "embodiments"):
        if not (target / name).is_dir(): ap.error(f"missing assets/{name}")
    link = Path(__file__).resolve().parents[1] / "assets"
    if link.exists() or link.is_symlink():
        if link.is_symlink() and link.resolve() == target: print("Assets already linked"); return
        ap.error("assets already exists; refusing to replace it")
    link.symlink_to(target, target_is_directory=True)
    print("Local assets linked (gitignored)")

if __name__ == "__main__": main()
