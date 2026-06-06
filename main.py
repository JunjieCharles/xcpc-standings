import argparse
import sys
import json
import os
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

from src.update_contests import main as update_contests_main
from src.merge_standings import batch_process, merge_standings
from src.sources.xcpcio_source import ICPCStandingsGenerator
from src.readme import main as readme_main
from src.rating.calculator import main as rating_main
from src.utils.years import normalize_year_arg


DEFAULT_RATING_HISTORY_START = "2024H2"


@dataclass
class MenuItem:
    title: Callable[[], str]
    description: str
    run: Callable[[], None]
    adjust: Optional[Callable[[int], None]] = None
    edit: Optional[Callable[[], None]] = None


def build_parser():
    parser = argparse.ArgumentParser(description="XCPC Standings CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # 1. Update Contests
    parser_update = subparsers.add_parser("update", help="Update the list of contests from sources")
    
    # 2. Merge Standings
    parser_merge = subparsers.add_parser("merge", help="Merge standings into unified CSVs and JSONs")
    parser_merge.add_argument("--batch", action="store_true", help="Batch process Regional and Final contests")
    parser_merge.add_argument("--years", help="Year or range for batch (e.g. 2025, 25, 25-26, 25H2-26H1, 25下半年-26上半年, all)")
    parser_merge.add_argument("--contest", help="Single batch output name to process, e.g. CCPC_2024_Online_online")
    parser_merge.add_argument("base", nargs="?", help="Base JSON file (only used if --batch is not specified)")
    parser_merge.add_argument("comp", nargs="?", help="Complement JSON file (only used if --batch is not specified)")
    parser_merge.add_argument("out", nargs="?", help="Output name (only used if --batch is not specified)")
    
    # 3. Readme
    parser_readme = subparsers.add_parser("readme", help="Regenerate README.md based on merged data")

    # 4. Rating
    parser_rating = subparsers.add_parser("rating", help="Generate rating CSVs and XLSX based on current standings")
    parser_rating.add_argument("--type", choices=['member', 'school', 'all'], default='all', help="Type of rating calculation to perform")
    rating_period = parser_rating.add_mutually_exclusive_group(required=True)
    rating_period.add_argument("--years", help="Year or range for rating (e.g. 2025, 25, 25-26, 25H2-26H1, 25下半年-26上半年, all)")
    rating_period.add_argument("--current", action="store_true", help="Generate rating for the current rating season based on today's date")
    rating_period.add_argument("--history", action="store_true", help="Generate rating from --history-start through the current rating season")
    parser_rating.add_argument("--history-start", default=DEFAULT_RATING_HISTORY_START, help=f"Earliest half-year for --history (default: {DEFAULT_RATING_HISTORY_START})")

    return parser, parser_merge


def current_rating_season(today: date | None = None) -> str:
    today = today or date.today()
    if today.month <= 6:
        return f"{today.year - 1}H2-{today.year}H1"
    return f"{today.year}H2-{today.year + 1}H1"


def rating_history_range(start: str = DEFAULT_RATING_HISTORY_START, today: date | None = None) -> str:
    start_period = normalize_year_arg(start)
    if "H" not in start_period or "-" in start_period or start_period == "all":
        raise ValueError("Rating history start must be a single half-year, such as 24H2.")
    current_season = current_rating_season(today)
    return normalize_year_arg(f"{start_period}-{current_season.split('-', 1)[1]}")


def resolve_rating_years(args) -> str:
    if args.current:
        return current_rating_season()
    if args.history:
        return rating_history_range(args.history_start)
    return normalize_year_arg(args.years)


def run_manual_merge(base, comp, out=None):
    print(f"Running manual merge: Base={base}, Comp={comp}")
    with open(base, "r", encoding="utf-8") as f:
        b = json.load(f)
    with open(comp, "r", encoding="utf-8") as f:
        c = json.load(f)

    m, w = merge_standings(b, c, source_name="Compl")
    for x in w:
        print(x)

    out_n = out if out else "merged_manual"
    os.makedirs("data/merged/json", exist_ok=True)
    os.makedirs("data/merged/csv", exist_ok=True)

    with open(f"data/merged/json/{out_n}.json", "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    ICPCStandingsGenerator.export_csv(f"data/merged/csv/{out_n}.csv", m)
    print(f"Saved to data/merged/json/{out_n}.json and data/merged/csv/{out_n}.csv")


def dispatch_args(args, parser, parser_merge):
    if not args.command:
        parser.print_help()
        return 1

    if args.command == "update":
        print("Running update_contests...")
        update_contests_main()
        return 0

    if args.command == "merge":
        if args.batch:
            if not args.years:
                print("Batch merge requires --years (e.g. 2025, 25, 25-26, 25H2-26H1, 25下半年-26上半年).")
                return 1
            try:
                years = normalize_year_arg(args.years)
            except ValueError as exc:
                print(exc)
                return 1
            print(f"Running batch merge for years: {years}...")
            batch_process(years, args.contest or "")
            return 0

        if not args.base or not args.comp:
            parser_merge.print_help()
            return 1

        run_manual_merge(args.base, args.comp, args.out)
        return 0

    if args.command == "readme":
        print("Running readme generation...")
        readme_main()
        return 0

    if args.command == "rating":
        try:
            years = resolve_rating_years(args)
        except ValueError as exc:
            print(exc)
            return 1
        print(f"Running rating calculations for {args.type}, years: {years}...")
        rating_main(args.type, years)
        return 0

    parser.print_help()
    return 1


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def read_windows_key():
    import msvcrt

    ch = msvcrt.getwch()
    if ch in ("\x00", "\xe0"):
        code = msvcrt.getwch()
        return {
            "H": "up",
            "P": "down",
            "K": "left",
            "M": "right",
        }.get(code, "")
    if ch == "\r":
        return "enter"
    if ch == "\x1b":
        return "escape"
    if ch == "\x03":
        raise KeyboardInterrupt
    return ch.lower()


def read_posix_key():
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            return {
                "[A": "up",
                "[B": "down",
                "[D": "left",
                "[C": "right",
            }.get(seq, "escape")
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x03":
            raise KeyboardInterrupt
        return ch.lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def read_key():
    if os.name == "nt":
        return read_windows_key()
    return read_posix_key()


def prompt_text(label, default=""):
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def prompt_years(label="Year or year range"):
    while True:
        value = input(f"{label} (e.g. 2025, 25, 25-26, 25H2-26H1, 25下半年-26上半年): ").strip()
        try:
            return normalize_year_arg(value)
        except ValueError as exc:
            print(exc)


def run_with_pause(action):
    clear_screen()
    try:
        action()
    finally:
        input("\nPress Enter to return to the menu...")


def run_manual_merge_prompt():
    base = prompt_text("Base JSON file")
    comp = prompt_text("Complement JSON file")
    out = prompt_text("Output name", "merged_manual")
    if not base or not comp:
        print("Base and complement JSON files are required.")
        return
    run_manual_merge(base, comp, out)


def run_terminal_ui():
    rating_options = ["all", "member", "school"]
    state = {
        "batch_years": "",
        "rating_years": "",
        "rating_history_start": DEFAULT_RATING_HISTORY_START,
        "rating_index": 0,
    }

    def edit_batch_years():
        clear_screen()
        state["batch_years"] = prompt_years("Batch merge years")

    def run_batch_merge_prompt():
        if not state["batch_years"]:
            edit_batch_years()
        batch_process(state["batch_years"])

    def adjust_rating(direction):
        state["rating_index"] = (state["rating_index"] + direction) % len(rating_options)

    def current_rating_type():
        return rating_options[state["rating_index"]]

    def edit_rating_years():
        clear_screen()
        state["rating_years"] = prompt_years("Rating years")

    def run_rating_prompt():
        if not state["rating_years"]:
            edit_rating_years()
        rating_main(current_rating_type(), state["rating_years"])

    def edit_rating_history_start():
        clear_screen()
        state["rating_history_start"] = prompt_years("Rating history start")

    def run_current_season_rating_prompt():
        years = current_rating_season()
        print(f"Running rating for current season: {years}")
        rating_main(current_rating_type(), years)

    def run_history_rating_prompt():
        years = rating_history_range(state["rating_history_start"])
        print(f"Running rating history: {years}")
        rating_main(current_rating_type(), years)

    items = [
        MenuItem(
            title=lambda: "Update contests",
            description="Fetch and merge contest metadata into data/contests/contests.csv.",
            run=lambda: update_contests_main(),
        ),
        MenuItem(
            title=lambda: f"Batch merge standings   years={state['batch_years'] or '<required>'}",
            description="Use the rated contest index to generate merged JSON and CSV standings.",
            run=run_batch_merge_prompt,
            edit=edit_batch_years,
        ),
        MenuItem(
            title=lambda: f"Generate rating         type={current_rating_type()} years={state['rating_years'] or '<required>'}",
            description="Generate member, school, or both rating outputs.",
            run=run_rating_prompt,
            adjust=adjust_rating,
            edit=edit_rating_years,
        ),
        MenuItem(
            title=lambda: f"Generate current rating  type={current_rating_type()} years={current_rating_season()}",
            description="Generate rating for the current rating season based on today's date.",
            run=run_current_season_rating_prompt,
            adjust=adjust_rating,
        ),
        MenuItem(
            title=lambda: f"Generate history rating  type={current_rating_type()} start={state['rating_history_start']}",
            description="Generate rating from the configured history start through the current rating season.",
            run=run_history_rating_prompt,
            adjust=adjust_rating,
            edit=edit_rating_history_start,
        ),
        MenuItem(
            title=lambda: "Regenerate README",
            description="Update the README data completeness table from merged CSV files.",
            run=lambda: readme_main(),
        ),
        MenuItem(
            title=lambda: "Exit",
            description="Close this terminal menu.",
            run=lambda: None,
        ),
    ]

    selected = 0
    while True:
        clear_screen()
        print("XCPC Standings")
        print("Use Up/Down to choose, Left/Right to configure type, Enter to run, E to edit years, Q to quit.\n")
        for index, item in enumerate(items):
            marker = ">" if index == selected else " "
            print(f" {marker} {item.title()}")
        print(f"\n{items[selected].description}")

        key = read_key()
        if key == "up":
            selected = (selected - 1) % len(items)
        elif key == "down":
            selected = (selected + 1) % len(items)
        elif key == "left" and items[selected].adjust:
            items[selected].adjust(-1)
        elif key == "right" and items[selected].adjust:
            items[selected].adjust(1)
        elif key == "e" and items[selected].edit:
            items[selected].edit()
        elif key in ("q", "escape"):
            return 0
        elif key == "enter":
            if selected == len(items) - 1:
                return 0
            run_with_pause(items[selected].run)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser, parser_merge = build_parser()

    if not argv:
        try:
            return run_terminal_ui()
        except KeyboardInterrupt:
            print("\nCancelled.")
            return 130

    args = parser.parse_args(argv)
    return dispatch_args(args, parser, parser_merge)

if __name__ == "__main__":
    sys.exit(main())
