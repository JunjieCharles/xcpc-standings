import json
import argparse
import sys
import os
import pandas as pd
from typing import Dict, Tuple, List
from src.sources.xcpcio_source import XCPCIODataSource, ICPCStandingsGenerator
from src.sources.rankland_source import RanklandDataSource, SRKStandingsGenerator
from src.sources.archive_source import ArchiveDataSource, ArchiveStandingsGenerator
from src.providers import ArchiveProvider, XCPCIOProvider, RanklandProvider, PTAProvider
from src.models import TeamStanding, ContestStandings, ProblemStatus, calculate_canonical_ranks

import pypinyin
import re
import csv
import logging

from src.utils.text import normalize_text, get_name_pinyin_set
from src.utils.school import normalize_school_name, get_canonical_school_name, init_school_mapping, is_ambiguous_school

def matches_members(t1: TeamStanding, t2: TeamStanding) -> bool:
    m1 = [t1.member1, t1.member2, t1.member3]
    m2 = [t2.member1, t2.member2, t2.member3]
    
    m1 = [m for m in m1 if m]
    m2 = [m for m in m2 if m]
    
    if not m1 or not m2:
        return False
        
    matched = 0
    used_j = set()
    for name1 in m1:
        s1 = "".join(sorted(get_name_pinyin_set(name1)))
        for j, name2 in enumerate(m2):
            if j in used_j:
                continue
            s2 = "".join(sorted(get_name_pinyin_set(name2)))
            if s1 == s2 or normalize_text(name1) == normalize_text(name2):
                matched += 1
                used_j.add(j)
                break
                
    return matched >= min(len(m1), len(m2), 2)

def is_same_team(t1: TeamStanding, t2: TeamStanding) -> bool:
    s1 = normalize_school_name(t1.school)
    s2 = normalize_school_name(t2.school)
    if s1 and s2 and s1 != s2:
        return False
        
    name1 = normalize_text(t1.team_name)
    name2 = normalize_text(t2.team_name)
    if name1 == name2 and name1:
        return True
        
    return matches_members(t1, t2)

def merge_standings(base_json: dict, complement_json: dict, source_name: str = "Complement", contest_name: str = "", resolutions: dict = None) -> Tuple[dict, list]:
    warnings = []
    if resolutions is None:
        resolutions = {}
    
    base_cs = ContestStandings.from_dict(base_json)
    comp_cs = ContestStandings.from_dict(complement_json)
    
    # Normalize school names immediately
    for t in base_cs.standings:
        t.school = get_canonical_school_name(t.school)
    for t in comp_cs.standings:
        t.school = get_canonical_school_name(t.school)

    calculate_canonical_ranks(base_cs.standings)
    calculate_canonical_ranks(comp_cs.standings)
    
    comp_rank_map = {}
    for t in comp_cs.standings:
        match_rank = t.rank if t.is_official else f"U{getattr(t, '_unofficial_rank', '')}"
        if match_rank:
            comp_rank_map.setdefault(match_rank, []).append(t)
            
    used_comp_teams = set()
    merged_teams = []
    
    for base_t in base_cs.standings:
        comp_t = None
        base_rank = base_t.rank if base_t.is_official else f"U{getattr(base_t, '_unofficial_rank', '')}"
        
        candidates = comp_rank_map.get(base_rank, []) if base_rank else []
        if candidates:
            comp_t = candidates[0]
        
        if not comp_t:
            merged_teams.append(base_t.to_dict())
            continue
            
        used_comp_teams.add(comp_cs.standings.index(comp_t))
        
        # 特殊修复逗号导致的名字被截断分格进不同成员属性的问题
        if comp_t.team_name == "HKUST5" and getattr(comp_t, "member2", "") == "AWADALLA":
            comp_t.member2 = "AWADALLA, bdelrahman HossamEldin A. A."
            comp_t.member3 = "Vu Duy Tung"

        merged_t = base_t.to_dict()
        comp_t_dict = comp_t.to_dict()
        
        fields_to_check = ["school", "team_name", "member1", "member2", "member3", "coach", "is_girl", "is_official", "score", "penalty", "medal"]
        
        for f in fields_to_check:
            val_base = merged_t.get(f)
            val_comp = comp_t_dict.get(f)
            
            if not val_base and val_comp:
                merged_t[f] = val_comp
            elif val_base is not None and val_comp is not None and str(val_base) != str(val_comp):
                # Only check strings that are truly different
                if str(val_base).strip() != str(val_comp).strip() and str(val_base).strip() and str(val_comp).strip():
                    is_penalty_rounding = False
                    is_pinyin_match = False
                    is_permutation_match = False
                    
                    if f in ["member1", "member2", "member3"]:
                        b1 = str(merged_t.get("member1") or "").strip()
                        b2 = str(merged_t.get("member2") or "").strip()
                        b3 = str(merged_t.get("member3") or "").strip()
                        c1 = str(comp_t_dict.get("member1") or "").strip()
                        c2 = str(comp_t_dict.get("member2") or "").strip()
                        c3 = str(comp_t_dict.get("member3") or "").strip()
                        base_members = set([b1, b2, b3])
                        comp_members = set([c1, c2, c3])
                        base_members.discard("")
                        comp_members.discard("")
                        if len(base_members) > 0 and base_members == comp_members:
                            is_permutation_match = True

                    if f in ["member1", "member2", "member3", "coach"]:
                        import itertools
                        def get_all_pinyin(text):
                            res = pypinyin.pinyin(str(text), style=pypinyin.NORMAL, heteronym=True)
                            return ["".join(p).lower().replace(" ", "").replace("-", "").replace("'", "") for p in itertools.product(*res)]
                        p1s = get_all_pinyin(val_base)
                        p2s = get_all_pinyin(val_comp)
                        for curr_p1 in p1s:
                            for curr_p2 in p2s:
                                if curr_p1 == curr_p2 or sorted(list(curr_p1)) == sorted(list(curr_p2)):
                                    is_pinyin_match = True
                                    # Keep the Chinese version
                                    has_chinese1 = any('\u4e00' <= char <= '\u9fff' for char in str(val_base))
                                    has_chinese2 = any('\u4e00' <= char <= '\u9fff' for char in str(val_comp))
                                    if has_chinese2 and not has_chinese1:
                                        merged_t[f] = val_comp
                                    break
                            if is_pinyin_match:
                                break
                            
                    if f == "penalty":
                        try:
                            v_base = int(val_base)
                            v_comp = int(val_comp)
                            if abs(v_base - v_comp) <= 15:
                                is_penalty_rounding = True
                                merged_t[f] = v_comp
                        except ValueError:
                            pass
                    
                    if not is_penalty_rounding and not is_pinyin_match and not is_permutation_match:
                        s_name = merged_t.get('school', '')
                        t_name = merged_t.get('team_name', '')
                        
                        is_official = merged_t.get('is_official', True)
                        if is_official:
                            display_rank = str(merged_t.get('rank', ''))
                        else:
                            display_rank = f"U{merged_t.get('_unofficial_rank', '')}"
                            
                        if display_rank == 'None':
                            display_rank = ''
                            
                        key = (contest_name, display_rank, f)
                        
                        conflict_obj = {
                            'Contest': contest_name,
                            'Rank': display_rank,
                            'School': s_name,
                            'Team Name': t_name,
                            'Field': f,
                            'Resolution': ''
                        }
                        
                        if key in resolutions:
                            merged_t[f] = resolutions[key]
                            conflict_obj['Resolution'] = resolutions[key]
                        
                        # Only add if we haven't already reported this exact item from another source
                        if not any(w['Contest'] == contest_name and w['Rank'] == display_rank and w['Field'] == f for w in warnings):
                            warnings.append(conflict_obj)
                
        base_probs = merged_t.get("problem_scores", {})
        comp_probs = comp_t_dict.get("problem_scores", {})
        for p_id, p_stats in comp_probs.items():
            if p_id not in base_probs or not base_probs[p_id].get("solved"):
                base_probs[p_id] = p_stats
        merged_t["problem_scores"] = base_probs
        merged_teams.append(merged_t)
        
    for j, ct in enumerate(comp_cs.standings):
        if j not in used_comp_teams:
            merged_teams.append(ct.to_dict())
            
    final_cs = ContestStandings(
        contest_name=base_cs.contest_name or comp_cs.contest_name,
        problem_ids=base_cs.problem_ids if base_cs.problem_ids else comp_cs.problem_ids,
        standings=[TeamStanding.from_dict(t) for t in merged_teams]
    )
    calculate_canonical_ranks(final_cs.standings)
    
    return final_cs.to_dict(), warnings

def parse_rankland_config():
    ds = RanklandDataSource()
    conf = ds.get_contest_list()
    lookup = {}
    for top in conf.get('root', {}).get('children', []):
        cat = top.get('path', '')
        if cat in ('icpc', 'ccpc', 'provincial', 'invitational'):
            for group in top.get('children', []):
                y = group.get('path', '')
                for child in group.get('children', []):
                    path_id = child.get('path', '')
                    if path_id:
                        lookup[path_id] = (cat, y)
    return lookup

def batch_process(year_arg="2025"):
    df = pd.read_csv('data/contests/contests.csv', dtype=str).fillna('')
    
    if year_arg.lower() == 'all':
        year_mask = pd.Series(True, index=df.index)
    elif '-' in year_arg:
        try:
            start_y, end_y = map(int, year_arg.split('-'))
            valid_years = [str(y) for y in range(start_y, end_y + 1)]
            year_mask = df['year'].isin(valid_years)
        except ValueError:
            print("Invalid year range format. Use YYYY-YYYY.")
            return
    else:
        year_mask = df['year'] == year_arg

    target_df = df[year_mask & (df['category'].isin(['Regional', 'Final', 'Online', 'Girls', 'Vocational'])) & (df['name'].str.lower() != 'worldfinals')]
    
    if target_df.empty:
        print(f"No Regional/Final records found for year(s): {year_arg}.")
        return

    os.makedirs("data/merged/json", exist_ok=True)
    os.makedirs("data/merged/csv", exist_ok=True)
    
    print("Fetching Rankland Config for lookup...")
    rl_lookup = parse_rankland_config()

    resolutions_file = "data/merged/resolutions.csv"
    resolutions = {}
    existing_rows = []
    if os.path.exists(resolutions_file):
        with open(resolutions_file, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_rows.append(row)
                if row.get('Resolution'):
                    key = (row.get('Contest', ''), row.get('Rank', ''), row.get('Field', ''))
                    resolutions[key] = row['Resolution']

    all_warnings = []
    
    for idx, row in target_df.iterrows():
        name = row['name']
        if not name:
            if row['category'] == 'Girls':
                name = 'girls'
            elif row['category'] == 'Vocational':
                name = 'vocational'
        xcpcio_id = row['xcpcio_id']
        rankland_id = row['rankland_id']
        archive_id = row['archive_id']
        pta_id = str(row.get('pta_id', ''))
        if pta_id == 'nan': pta_id = ''
        
        
        out_name = f"{row['series']}_{row['year']}_{row['category']}_{name}"
        out_json = f"data/merged/json/{out_name}.json"
        out_csv = f"data/merged/csv/{out_name}.csv"
        

            
        print(f"\nProcessing: {name} (XCPCIO={xcpcio_id}, Rankland={rankland_id}, Archive={archive_id}, PTA={pta_id})")
        
        jsons = []
        
        providers = [
            ArchiveProvider(archive_id, name),
            PTAProvider(pta_id, name),
            XCPCIOProvider(xcpcio_id, name),
            RanklandProvider(rankland_id, name, rl_lookup.get(rankland_id))
        ]
        
        for p in providers:
            if p.is_valid():
                std_json = p.get_standings()
                if std_json and std_json.get("standings"):
                    jsons.append((p.source_name, std_json))

        if not jsons:
            print("  [SKIP] No data sources available.")
            continue
            
        # Merge them
        # Let's use XCPCIO as base if available, else Archive, else Rankland
        # Actually jsons has whatever we loaded in order. Let's just fold right.
        # Let's sort jsons priority: 1. XCPCIO 2. Rankland 3. Archive
        # This determines BASE.
        priority = {"XCPCIO": 1, "Rankland": 2, "Archive": 3}
        jsons.sort(key=lambda x: priority.get(x[0], 99))
        
        # Resolve ambiguous schools before merging
        for src_idx, (src_name, src_json) in enumerate(jsons):
            src_cs = ContestStandings.from_dict(src_json)
            calculate_canonical_ranks(src_cs.standings)
            changed = False
            for t in src_cs.standings:
                norm_school = normalize_text(t.school)
                if is_ambiguous_school(norm_school):
                    key = (out_name, str(t.rank) if t.rank is not None else '', 'school')
                    team_name = t.team_name or ''
                    rank_str = str(t.rank) if t.rank is not None else ''
                    
                    existing = next((w for w in all_warnings if w['Contest']==out_name and w['Rank']==rank_str and w['Field']=='school' and w['Team Name']==team_name), None)
                    original_name = getattr(t, 'original_school', t.school)
                    
                    if key in resolutions:
                        print(f"    [RESOLVED] {team_name} 'school': {original_name} -> {resolutions[key]}")
                        t.school = resolutions[key]
                        changed = True
                        if existing:
                            existing['Sources'][src_name] = original_name
                        else:
                            all_warnings.append({
                                'Contest': out_name,
                                'Rank': rank_str,
                                'School': t.school,
                                'Team Name': team_name,
                                'Field': 'school',
                                'Sources': {src_name: original_name},
                                'Resolution': resolutions[key]
                            })
                    else:
                        if existing:
                            existing['Sources'][src_name] = original_name
                        else:
                            all_warnings.append({
                                'Contest': out_name,
                                'Rank': rank_str,
                                'School': t.school,
                                'Team Name': team_name,
                                'Field': 'school',
                                'Sources': {src_name: original_name},
                                'Resolution': ''
                            })
            if changed:
                jsons[src_idx] = (src_name, src_cs.to_dict())

        base_name, current_merged = jsons[0]
        print(f"  Base source: {base_name}")
        
        contest_warnings = {}
        for i in range(1, len(jsons)):
            comp_name, comp_json = jsons[i]
            print(f"  Merging {comp_name} into Base...")
            current_merged, warns = merge_standings(current_merged, comp_json, source_name=comp_name, contest_name=out_name, resolutions=resolutions)
            for w in warns:
                key = (w['Contest'], w['Rank'], w['Field'])
                if key not in contest_warnings:
                    w['Sources'] = {}
                    contest_warnings[key] = w
                    
        # Extract values for each conflict from all sources
        for key, w in contest_warnings.items():
            rank, f = w['Rank'], w['Field']
            s_name, t_name = w['School'], w['Team Name']
            
            for src_name, src_json in jsons:
                src_cs = ContestStandings.from_dict(src_json)
                calculate_canonical_ranks(src_cs.standings)
                found_val = ''
                for t in src_cs.standings:
                    t_rank = str(t.rank) if t.is_official else f"U{getattr(t, '_unofficial_rank', '')}"
                    if t_rank == rank:
                        found_val = t.to_dict().get(f)
                        if found_val is None:
                            found_val = ''
                        break
                w['Sources'][src_name] = found_val
                
            status = "RESOLVED" if w['Resolution'] else "CONFLICT"
            # Just print the first two available source values to save terminal space
            vals = [str(v) for v in w['Sources'].values() if str(v)]
            try:
                print(f"    [{status}] {s_name} {t_name} '{f}': " + " vs ".join(vals))
            except UnicodeEncodeError:
                print(f"    [{status}] {s_name} (Encode Error) '{f}'")
            
            all_warnings.append(w)
                
        # Make sure current_merged is canonical even if 1 source
        final_cs_obj = ContestStandings.from_dict(current_merged)

        # Schools are already normalized at the top of merge_standings, but we 
        # also apply it here in case a contest only had 1 source and bypassed merge.
        for t in final_cs_obj.standings:
            t.school = get_canonical_school_name(t.school)

        calculate_canonical_ranks(final_cs_obj.standings)
        current_merged = final_cs_obj.to_dict()
                
        out_name = f"{row['series']}_{row['year']}_{row['category']}_{name}"
        out_json = f"data/merged/json/{out_name}.json"
        out_csv = f"data/merged/csv/{out_name}.csv"
        
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(current_merged, f, ensure_ascii=False, indent=2)
            
        ICPCStandingsGenerator.export_csv(out_csv, current_merged)
        print(f"  Saved {len(current_merged['standings'])} teams to {out_csv}")

    print("\n================== CONFLICT REPORT ==================")
    resolutions_file = "data/merged/resolutions.csv"

    # Write resolutions.csv
    if all_warnings:
        resolved = [w for w in all_warnings if w.get('Resolution')]
        unresolved = [w for w in all_warnings if not w.get('Resolution')]
        
        if unresolved:
            print(f"\n--- UNRESOLVED CONFLICTS ({len(unresolved)}) ---")
            print("Please fix these by adding resolutions to `resolutions.csv`:")
            for w in unresolved:
                vals = [f"{src}: {v}" for src, v in w.get('Sources', {}).items() if str(v)]
                try:
                    print(f"  [{w['Contest']}] Rank {w['Rank']} - {w['School']} {w['Team Name']} | {w['Field']} -> " + " vs ".join(vals))
                except UnicodeEncodeError:
                    print(f"  [{w['Contest']}] Rank {w['Rank']} - {w['School']} (Encode Error) | {w['Field']}")
                
        if resolved:
            print(f"\n--- RESOLVED CONFLICTS ({len(resolved)}) ---")
            for w in resolved:
                print(f"  [{w['Contest']}] Rank {w['Rank']} - {w['School']} {w['Team Name']} | {w['Field']} resolved to: '{w['Resolution']}'")

        # Merge existing rows with new warnings
        final_rows = {}
        # Load existing first, keeping only those that have a manual resolution saved
        for row in existing_rows:
            if row.get('Resolution'):
                k = (row.get('Contest', ''), row.get('Rank', ''), row.get('Field', ''), row.get('Team Name', ''))
                final_rows[k] = row
            
        # Update with new runs
        all_sources = ["XCPCIO", "Rankland", "Archive", "PTA"]
        for w in all_warnings:
            k = (w['Contest'], w['Rank'], w['Field'], w['Team Name'])
            out = {
                'Contest': w['Contest'],
                'Rank': w['Rank'],
                'School': w['School'],
                'Team Name': w['Team Name'],
                'Field': w['Field'],
                'Resolution': w['Resolution']
            }
            for src in all_sources:
                out[src] = w.get('Sources', {}).get(src, '')
            final_rows[k] = out
            
        with open(resolutions_file, 'w', encoding='utf-8-sig', newline='') as csvfile:
            # Reconstruct fieldnames from data because existing rows might have extra source columns
            all_sources_set = set(["XCPCIO", "Rankland", "Archive", "PTA"])
            for row in final_rows.values():
                for k in row.keys():
                    if k not in ['Contest', 'Rank', 'School', 'Team Name', 'Field', 'Resolution']:
                        all_sources_set.add(k)
                        
            fieldnames = ['Contest', 'Rank', 'School', 'Team Name', 'Field'] + sorted(list(all_sources_set)) + ['Resolution']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for r in final_rows.values():
                writer.writerow(r)
                
        print(f"Resolutions file updated at {resolutions_file}")
    else:
        # Create empty template if none exist
        if not os.path.exists(resolutions_file):
            with open(resolutions_file, 'w', encoding='utf-8-sig', newline='') as csvfile:
                all_sources = ["XCPCIO", "Rankland", "Archive"]
                fieldnames = ['Contest', 'Rank', 'School', 'Team Name', 'Field'] + all_sources + ['Resolution']
                writer = csv.writer(csvfile)
                writer.writerow(fieldnames)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="store_true", help="Batch process Regional and Final contests")
    parser.add_argument("--years", help="Year or year range for batch (e.g. 2025, 2024-2025, all)", default="2025")
    parser.add_argument("base", nargs="?", help="Base JSON file")
    parser.add_argument("comp", nargs="?", help="Complement JSON file")
    parser.add_argument("out", nargs="?", help="Output name")
    
    args = parser.parse_args()
    
    if args.batch:
        batch_process(args.years)
    else:
        if not args.base or not args.comp:
            parser.print_help()
            sys.exit(1)
            
        with open(args.base, "r", encoding="utf-8") as f:
            b = json.load(f)
        with open(args.comp, "r", encoding="utf-8") as f:
            c = json.load(f)
            
        m, w = merge_standings(b, c, source_name="Compl")
        for x in w: print(x)
        
        out_n = args.out if args.out else "merged_manual"
        with open(f"data/merged/json/{out_n}.json", "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
        ICPCStandingsGenerator.export_csv(f"data/merged/csv/{out_n}.csv", m)
        print(f"Saved to {out_n}.csv")