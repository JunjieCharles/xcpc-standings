import argparse
import sys
import json
import os

from src.update_contests import main as update_contests_main
from src.merge_standings import batch_process, merge_standings
from src.xcpcio_source import ICPCStandingsGenerator
from src.readme import main as readme_main

def main():
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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "update":
        print("Running update_contests...")
        update_contests_main()
        
    elif args.command == "merge":
        if args.batch:
            print(f"Running batch merge for years: {args.years}...")
            batch_process(args.years)
        else:
            if not args.base or not args.comp:
                parser_merge.print_help()
                sys.exit(1)
                
            print(f"Running manual merge: Base={args.base}, Comp={args.comp}")
            with open(args.base, "r", encoding="utf-8") as f:
                b = json.load(f)
            with open(args.comp, "r", encoding="utf-8") as f:
                c = json.load(f)
                
            m, w = merge_standings(b, c, source_name="Compl")
            for x in w: print(x)
            
            out_n = args.out if args.out else "merged_manual"
            os.makedirs("data/merged/json", exist_ok=True)
            os.makedirs("data/merged/csv", exist_ok=True)
            
            with open(f"data/merged/json/{out_n}.json", "w", encoding="utf-8") as f:
                json.dump(m, f, ensure_ascii=False, indent=2)
            ICPCStandingsGenerator.export_csv(f"data/merged/csv/{out_n}.csv", m)
            print(f"Saved to data/merged/json/{out_n}.json and data/merged/csv/{out_n}.csv")
            
    elif args.command == "readme":
        print("Running readme generation...")
        readme_main()

if __name__ == "__main__":
    main()