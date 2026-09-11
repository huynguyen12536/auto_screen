"""Convert a raw vacations JSONL file into Backend agenda-import JSON.

Does not crawl, upload, or modify Backend. Requires agenda date from crawl
context (never invents it from the machine clock).

Example:
  python -m feature.formatter.cli \\
    --raw runtime/data/vacations_20260910_2315.jsonl \\
    --agenda-code BRESSUIRE \\
    --agenda-label BRESSUIRE \\
    --agenda-date 10/09/2026
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from feature.formatter.payload_formatter import format_raw_jsonl_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Format raw UEGAR JSONL into Backend agenda-import JSON"
    )
    parser.add_argument("--raw", required=True, type=Path, help="Raw JSONL path")
    parser.add_argument("--agenda-code", required=True)
    parser.add_argument("--agenda-label", required=True)
    parser.add_argument(
        "--agenda-date",
        required=True,
        help="Selected agenda date from crawl context (DD/MM/YYYY)",
    )
    parser.add_argument("--scraped-at", default=None, help="ISO UTC scrapedAt")
    parser.add_argument("--display-name", default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    out, payload, warnings = format_raw_jsonl_file(
        args.raw,
        agenda_code=args.agenda_code,
        agenda_label=args.agenda_label,
        agenda_date=args.agenda_date,
        scraped_at=args.scraped_at,
        display_name=args.display_name,
        output_path=args.out,
    )
    print(f"Wrote {out}")
    print(
        f"appointments={len(payload['appointments'])} "
        f"resources={len(payload['resources'])} "
        f"warnings={len(warnings)}"
    )
    for w in warnings:
        print(f"WARN: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
