"""Export a copy of the frozen manifest without overwriting benchmark membership."""
import argparse
from pathlib import Path
import yaml

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", default="out/scenes_v2.yaml")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / "suite/scenes_v2.yaml"
    output = Path(args.output).resolve()
    if output == source.resolve():
        ap.error("Refusing to overwrite the frozen manifest; see docs/DEVELOPMENT.md")
    manifest = yaml.safe_load(source.read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False))
    print(output)

if __name__ == "__main__":
    main()
