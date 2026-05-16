import argparse
import sys
import json
import os
from dataclasses import dataclass
from typing import Callable, Optional

from src.update_contests import main as update_contests_main
from src.merge_standings import batch_process, merge_standings
from src.sources.xcpcio_source import ICPCStandingsGenerator
from src.readme import main as readme_main
from src.rating.calculator import main as rating_main


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
    parser_merge.add_argument("--years", help="Year or year range for batch (e.g. 2025, 2024-2025, all)", default="2025")
    parser_merge.add_argument("base", nargs="?", help="Base JSON file (only used if --batch is not specified)")
    parser_merge.add_argument("comp", nargs="?", help="Complement JSON file (only used if --batch is not specified)")
    parser_merge.add_argument("out", nargs="?", help="Output name (only used if --batch is not specified)")
    
    # 3. Readme
    parser_readme = subparsers.add_parser("readme", help="Regenerate README.md based on merged data")

    # 4. Rating
    parser_rating = subparsers.add_parser("rating", help="Generate rating CSVs and XLSX based on current standings")
    parser_rating.add_argument("--type", choices=['member', 'school', 'all'], default='all', help="Type of rating calculation to perform")

    return parser, parser_merge


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
            print(f"Running batch merge for years: {args.years}...")
            batch_process(args.years)
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
        print(f"Running rating calculations for {args.type}...")
        rating_main(args.type)
        return 0

    parser.print_help()
    return 1


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def read_key():
    if os.name == "nt":
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


def prompt_text(label, default=""):
    value = input(f"{label} [{default}]: ").strip()
    return value or default


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
    years_options = ["2025", "2024-2025", "2021-2025", "all"]
    rating_options = ["all", "member", "school"]
    state = {
        "years_index": 0,
        "custom_years": "",
        "rating_index": 0,
    }

    def selected_years():
        return state["custom_years"] or years_options[state["years_index"]]

    def adjust_years(direction):
        state["custom_years"] = ""
        state["years_index"] = (state["years_index"] + direction) % len(years_options)

    def edit_years():
        clear_screen()
        state["custom_years"] = prompt_text("Year, year range, or all", selected_years())

    def adjust_rating(direction):
        state["rating_index"] = (state["rating_index"] + direction) % len(rating_options)

    def current_rating_type():
        return rating_options[state["rating_index"]]

    items = [
        MenuItem(
            title=lambda: "Update contests",
            description="Fetch and merge contest metadata into data/contests/contests.csv.",
            run=lambda: update_contests_main(),
        ),
        MenuItem(
            title=lambda: f"Batch merge standings   years={selected_years()}",
            description="Use data/contests/contests.csv to generate merged JSON and CSV standings.",
            run=lambda: batch_process(selected_years()),
            adjust=adjust_years,
            edit=edit_years,
        ),
        MenuItem(
            title=lambda: "Manual merge standings",
            description="Merge two standard JSON files and write data/merged outputs.",
            run=run_manual_merge_prompt,
        ),
        MenuItem(
            title=lambda: f"Generate rating         type={current_rating_type()}",
            description="Generate member, school, or both rating outputs.",
            run=lambda: rating_main(current_rating_type()),
            adjust=adjust_rating,
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
        print("Use Up/Down to choose, Left/Right to configure, Enter to run, E to edit, Q to quit.\n")
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