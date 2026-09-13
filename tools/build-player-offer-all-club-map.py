"""Create the compact runtime club-name map from an existing native club export."""
import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clubs", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/qol/player-offer-all/plugins/FM27.PlayerOfferAll.clubs.csv")
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = args.clubs.resolve()
    output = (root / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    if not source.is_relative_to(root) or not output.is_relative_to(root / "data/qol/player-offer-all"):
        raise ValueError("Club map inputs and output must stay in the project")
    rows = list(csv.DictReader(source.open(encoding="utf-8-sig", newline="")))
    mapped = []
    seen = set()
    for row in rows:
        club_id = int(row["club_id"])
        name = row["club"].strip().replace("|", "/").replace("\r", " ").replace("\n", " ")
        if club_id <= 0 or not name or club_id in seen:
            raise ValueError(f"Invalid or duplicate club identity: {club_id}")
        seen.add(club_id)
        mapped.append((club_id, name))
    mapped.sort()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as writer:
        writer.write("club_id|club_name\n")
        for club_id, name in mapped:
            writer.write(f"{club_id}|{name}\n")
    print(f"Wrote {len(mapped)} unique club names to {output}")


if __name__ == "__main__":
    main()
