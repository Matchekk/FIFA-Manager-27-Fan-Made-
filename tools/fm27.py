"""Source-distribution entry point; requires Python 3.12+ on Windows."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27 import audit, database, reconcile, sources


def main() -> None:
    parser = argparse.ArgumentParser(description="FM27 read-only audit/data tooling")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("audit")
    scan.add_argument("--game-root", type=Path, required=True)
    scan.add_argument("--output", type=Path, required=True)
    data = sub.add_parser("export-identities")
    data.add_argument("--database", type=Path, required=True)
    data.add_argument("--output", type=Path, required=True)
    data.add_argument("--scope", type=Path, default=Path(__file__).resolve().parents[1] / "config/scope.json")
    transfer = sub.add_parser("reconcile")
    transfer.add_argument("--export", type=Path, required=True)
    transfer.add_argument("--evidence", type=Path, required=True)
    transfer.add_argument("--output", type=Path, required=True)
    transfer.add_argument("--snapshot", required=True)
    transfer.add_argument("--scope", type=Path, default=Path(__file__).resolve().parents[1] / "config/scope.json")
    fetch = sub.add_parser("fetch-fpl")
    fetch.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "audit":
        report = audit.run(args.game_root, args.output)
        print(json.dumps({"file_count": report["file_count"], "errors": report["errors"]}))
    elif args.command == "export-identities":
        report = database.export(args.database, args.output, args.scope)
        print(json.dumps({key: value for key, value in report.items() if key != "sources"}))
    elif args.command == "reconcile":
        print(json.dumps(reconcile.run(args.export, args.evidence, args.output, args.snapshot, args.scope)))
    elif args.command == "fetch-fpl":
        report = sources.fetch_fpl(args.output)
        print(json.dumps(report))
        print(json.dumps(sources.project_fpl(args.output / report["snapshot"],
                                            args.output / "fpl-roster.csv")))


if __name__ == "__main__":
    main()
