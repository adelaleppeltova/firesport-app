"""Move legacy hash files without changing a single payload byte.

python -m app.extraction.migrate [--data-root PATH] [--apply] [--git]
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from jsonschema import ValidationError
from .paths import resolve_path, read_existing, StorageConflict
from .validation import validate


def migrate(data_root, *, apply=False, use_git=False):
    root = Path(data_root)
    legacy = root / "results"
    report = []
    for source in sorted(legacy.glob("*.json")):
        try:
            raw = source.read_bytes()
            data = read_existing(source)
            validate(data)
            target = resolve_path(data, root)
            if target.exists():
                identical = target.read_bytes() == raw
                raise StorageConflict(
                    f"Existing same-race file: {target}; identical bytes={identical}. No file overwritten or removed."
                )
            entry = {
                "source": str(source),
                "target": str(target),
                "status": "planned",
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            if apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                if use_git:
                    subprocess.run(
                        ["git", "mv", "--", str(source), str(target)], check=True
                    )
                else:
                    # Hard-link publication fails atomically if destination already exists.
                    target.hardlink_to(source)
                try:
                    if target.read_bytes() != raw:
                        raise StorageConflict(
                            f"Migration byte verification failed: {target}"
                        )
                    validate(read_existing(target))
                except Exception:
                    if use_git:
                        subprocess.run(
                            ["git", "mv", "--", str(target), str(source)], check=True
                        )
                    else:
                        target.unlink()
                    raise
                if not use_git:
                    source.unlink()
                entry["status"] = "moved"
            report.append(entry)
        except (
            ValueError,
            OSError,
            ValidationError,
            subprocess.SubprocessError,
        ) as exc:
            report.append(
                {"source": str(source), "status": "conflict", "error": str(exc)}
            )
    if apply and legacy.exists() and not any(legacy.iterdir()):
        legacy.rmdir()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root", type=Path, default=Path(__file__).resolve().parents[3] / "data"
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--git", action="store_true", dest="use_git")
    args = parser.parse_args(argv)
    report = migrate(args.data_root, apply=args.apply, use_git=args.use_git)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(any(r["status"] == "conflict" for r in report))


if __name__ == "__main__":
    raise SystemExit(main())
