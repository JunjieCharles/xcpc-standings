import os
import csv
import re
import pandas as pd
from typing import Dict, List, Tuple
from tqdm import tqdm
import json
from datetime import datetime

from src.rating.utils import calculateRating, normalize, rating_color
from src.utils.school import normalize_school_name
from src.utils.text import contains_chinese
from src.utils.years import contest_matches_year_arg, normalize_year_arg

def get_zh_to_en():
    json_path = 'data/config/zh_to_en.json'
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def build_contest_schedule(rating_type: str = "member", year_arg: str = "2025", combine_same_day: bool = None) -> List[Dict]:
    """
    Reads contests.csv, filters for Regional/Final/Invitational category (based on requirement to include only relevant ones),
    groups by date, and builds the schedule order.
    Returns:
       [
         {
           'date': 'YYYY-MM-DD',
           'tag': 'ICPC南京/CCPC哈尔滨',
           'files': ['ICPC_2025_Regional_nanjing.csv', 'CCPC_2025_Regional_harbin.csv']
         },
         ...
       ]
    """
    year_arg = normalize_year_arg(year_arg)
    contests_file = 'data/contests/contests.csv'
    if not os.path.exists(contests_file):
        print(f"Error: {contests_file} not found.")
        return []

    # Map en_to_zh for tags
    en_to_zh = {v: k for k, v in get_zh_to_en().items()}

    # Read contests
    grouped = {}
    with open(contests_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            series = row.get('series', '')
            year = row.get('year', '')
            date_str = row.get('date', '')
            sub = row.get('category', '')
            name = row.get('name', '')

            if series == 'Other':
                continue

            if not contest_matches_year_arg(row, year_arg):
                continue

            if name.lower() == 'srni':
                continue

            if sub not in ['Regional', 'Final', 'Invitational', 'Preliminary', 'Online', 'Girls', 'Vocational']:
                continue

            if not name:
                if sub == 'Girls':
                    name = 'girls'
                elif sub == 'Vocational':
                    name = 'vocational'

            csv_filename = f"{series}_{year}_{sub}_{name}.csv"
            csv_path = os.path.join('data/merged/csv', csv_filename)

            if not os.path.exists(csv_path):
                continue

            if date_str not in grouped:
                grouped[date_str] = []

            grouped[date_str].append({
                'series': series,
                'name': name,
                'sub': sub,
                'file': csv_path
            })

    # Sort by date
    sorted_dates = sorted(grouped.keys())

    if combine_same_day is None:
        combine_same_day = rating_type != 'school'

    schedule = []
    for d in sorted_dates:
        items = grouped[d]
        # Priority: Vocational < Girls < Online = Invitational < Regional < Final
        # Series: CCPC (0) < ICPC (1)
        def get_priority(x):
            sub_p = {'Vocational': 0, 'Girls': 1, 'Online': 2, 'Preliminary': 3, 'Invitational': 4, 'Regional': 5, 'Final': 6}.get(x['sub'], 2)
            series_p = 1 if x['series'] == 'ICPC' else 0
            return (sub_p, series_p, x['name'])

        # Execute rating calculation from lowest to highest priority
        items_sorted = sorted(items, key=get_priority)

        if not combine_same_day:
            for item in items_sorted:
                schedule.append({
                    'date': d,
                    'tag': build_contest_tag(item, en_to_zh),
                    'files': [item['file']]
                })
        else:
            items_for_tag = sorted(items, key=get_priority, reverse=True)
            tags = [build_contest_tag(item, en_to_zh) for item in items_for_tag]
            files = [item['file'] for item in items_sorted]

            schedule.append({
                'date': d,
                'tag': "/".join(tags),
                'files': files
            })

    return schedule

def build_contest_tag(item: Dict, en_to_zh: Dict[str, str]) -> str:
    zh_name = translate_contest_name(item['name'], en_to_zh)
    tag = f"{item['series']}{zh_name}"
    if item['sub'] == 'Invitational':
        tag = f"{item['series']}{zh_name}邀请赛"
    if item['sub'] == 'Final' and item['name'] == 'final':
        tag = f"{item['series']}总决赛"
    if item['sub'] == 'Final' and item['name'] == 'ecfinal':
        tag = f"{item['series']} ECFinal"
    return tag

def translate_contest_name(name: str, en_to_zh: Dict[str, str]) -> str:
    if name in en_to_zh:
        return en_to_zh[name]
    match = re.match(r'^([a-z]+)(\d+)$', str(name or ''))
    if match and match.group(1) in en_to_zh:
        return f"{en_to_zh[match.group(1)]}{match.group(2)}"
    return name


def rating_output_paths(kind: str, year_arg: str) -> Tuple[str, str]:
    year_label = normalize_year_arg(year_arg)
    csv_dir = os.path.join('data', 'rating', 'csv')
    xlsx_dir = os.path.join('data', 'rating', 'xlsx')
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(xlsx_dir, exist_ok=True)
    return (
        os.path.join(csv_dir, f'rating_{kind}_{year_label}.csv'),
        os.path.join(xlsx_dir, f'rating_{kind}_{year_label}.xlsx'),
    )


def make_unique_tags(tags: List[str]) -> List[str]:
    seen = {}
    unique_tags = []
    for tag in tags:
        count = seen.get(tag, 0) + 1
        seen[tag] = count
        unique_tags.append(tag if count == 1 else f"{tag}({count})")
    return unique_tags


def collect_member_userrank(file: str) -> Dict:
    df = pd.read_csv(file, encoding='utf-8')
    userrank = {}
    for _, row in df.iterrows():
        if row.isnull().all():
            continue
        if 'Unofficial' in row and (row['Unofficial'] != 'N' and row['Unofficial'] != False):
            continue

        if 'Solved' in row and pd.notnull(row['Solved']) and str(row['Solved']).strip():
            try:
                if int(float(row['Solved'])) == 0:
                    continue
            except ValueError:
                pass
        elif 'A' in row:
            cnt = 0
            for ip in range(26):
                problem = chr(ord('A') + ip)
                if problem not in row:
                    break
                val = str(row[problem]).strip()
                if pd.notnull(row[problem]) and val not in ['-', '', 'nan', 'NaN']:
                    cnt += 1
            if cnt == 0:
                continue

        school_str = row['School'] if 'School' in row else str(row.get('Organization', ''))
        school = normalize_school_name(school_str)

        for j in range(1, 4):
            member_col = f'Member{j}'
            if member_col in row and pd.notnull(row[member_col]):
                member = normalize(row[member_col], '港' in school or '澳' in school)
                if member.endswith('教练') or member.endswith('coach'):
                    continue
                if not member:
                    continue
                user = (school, member)
                rank = row['Rank'] if 'Rank' in row else row.get('Organization Rank', 0)
                if pd.notnull(rank):
                    userrank[user] = int(rank)
    return userrank


def build_member_dataframe(users, ratings_history, tags, diff=None, include_delta=True):
    datas = []
    for school, member in users:
        data = {'学校': school, '姓名': member}
        for i in range(len(ratings_history)):
            rating = ratings_history[i].get((school, member), None)
            data[tags[i]] = rating
        if include_delta:
            data['Δ'] = diff.get((school, member)) if diff else None
        datas.append(data)

    df = pd.DataFrame(datas)
    if not df.empty and tags:
        df = df.sort_values(by=[tags[-1], '学校'], ascending=[False, True])
    return df


def generate_member_rating(rating_type="member", year_arg="2025"):
    csv_schedule = build_contest_schedule(rating_type, year_arg, combine_same_day=False)
    xlsx_schedule = build_contest_schedule(rating_type, year_arg, combine_same_day=True)
    if not csv_schedule or not xlsx_schedule:
        return

    file_to_tag = {schedule_item['files'][0]: schedule_item['tag'] for schedule_item in csv_schedule}
    csv_tags = []
    xlsx_tags = []
    csv_history = []
    xlsx_history = []
    curratings = {}
    xlsx_diff = {}
    skipped_files = []

    print("Generating Member Rating...")
    for day_group in tqdm(xlsx_schedule):
        group_diff = {}
        wrote_xlsx_snapshot = False
        day_tags = []
        for file in day_group['files']:
            userrank = collect_member_userrank(file)
            if not userrank:
                skipped_files.append(file)
                continue
            newrating = calculateRating(userrank, curratings)
            cur_diff = {u: newrating[u] - curratings.get(u, 1400) for u in newrating}
            curratings.update(newrating)
            for user, value in cur_diff.items():
                group_diff[user] = group_diff.get(user, 0) + value
            csv_history.append(curratings.copy())
            csv_tags.append(file_to_tag[file])
            day_tags.append(file_to_tag[file])
            wrote_xlsx_snapshot = True

        xlsx_diff = group_diff
        if wrote_xlsx_snapshot:
            xlsx_tags.append("/".join(reversed(day_tags)))
            xlsx_history.append(curratings.copy())

    if skipped_files:
        print("Skipped member rating for contests without member data:")
        for file in skipped_files:
            print(f"  - {file}")

    users = curratings.keys()
    effective_csv_tags = make_unique_tags(csv_tags)
    effective_xlsx_tags = make_unique_tags(xlsx_tags)
    csv_df = build_member_dataframe(users, csv_history, effective_csv_tags, include_delta=False)
    xlsx_df = build_member_dataframe(users, xlsx_history, effective_xlsx_tags, xlsx_diff, include_delta=True)

    csv_path, xlsx_path = rating_output_paths('member', year_arg)
    csv_df.to_csv(csv_path, index=False, encoding='utf-8', lineterminator='\n')

    if not xlsx_df.empty:
        styled_df = xlsx_df.style.map(rating_color, subset=effective_xlsx_tags)
        styled_df = styled_df.map(lambda v:'color:red;' if pd.notnull(v) and float(v)>=0 else 'color:gray;', subset=['Δ'])
        # Handle NaN formatting
        def format_delta(v):
            if pd.isnull(v): return ''
            return f'{int(v):+d}'
        styled_df = styled_df.format(format_delta, subset=['Δ'])
        styled_df.to_excel(xlsx_path, index=False)
    print(f"Member Rating exported to {csv_path} & {xlsx_path}")

def generate_school_rating(rating_type="school", year_arg="2025"):
    schedule = build_contest_schedule(rating_type, year_arg, combine_same_day=False)
    if not schedule:
        return

    tags = make_unique_tags([s['tag'] for s in schedule])

    ratings_history = []
    curratings = {}
    diff = {}

    print("Generating School Rating...")
    for day_group in tqdm(schedule):

        # Merge userrank per day across all parallel files
        # to handle parallel matches properly for school as well.
        # Although school could be updated per file, doing it per date is cleaner
        # and more mathematically consistent if a school participates in both. Wait,
        # old logic says "Process exactly sequentially".

        for file in day_group['files']:
            df = pd.read_csv(file, encoding='utf-8')
            if 'Organization' in df.columns and 'School' not in df.columns:
                df.rename(columns={'Organization': 'School'}, inplace=True)
            if 'Organization Rank' in df.columns and 'School Rank' not in df.columns:
                df.rename(columns={'Organization Rank': 'School Rank'}, inplace=True)

            userrank = {}

            if 'School Rank' not in df.columns:
                school_ranks = {}
                df_school = df.drop_duplicates(subset=['School'], keep='first').reset_index(drop=True)
                for _, row in df_school.iterrows():
                    if row.isnull().all():
                        continue
                    if 'Unofficial' in row and (row['Unofficial'] != 'N' and row['Unofficial'] != False):
                        continue

                    school = normalize_school_name(str(row['School']))
                    if school not in school_ranks:
                        school_ranks[school] = len(school_ranks) + 1

                school_norm = df['School'].apply(lambda x: normalize_school_name(str(x)))
                df['School Rank'] = school_norm.map(school_ranks)

            for _, row in df.iterrows():
                if row.isnull().all():
                    continue
                if 'Unofficial' in row and (row['Unofficial'] != 'N' and row['Unofficial'] != False):
                    continue

                schoolrank = row.get('School Rank')
                if pd.isnull(schoolrank):
                    continue

                if 'A' in row:
                    cnt = 0
                    for ip in range(26):
                        problem = chr(ord('A') + ip)
                        if problem not in row:
                            break
                        if not pd.isnull(row[problem]) and str(row[problem]) != '-':
                            cnt += 1
                    if cnt == 0:
                        continue

                school = normalize_school_name(str(row['School']))
                userrank[school] = int(schoolrank)

            newrating = calculateRating(userrank, curratings)
            diff = {s: newrating[s] - curratings.get(s, 1400) for s in newrating}
            curratings.update(newrating)

        ratings_history.append(curratings.copy())

    datas = []
    users = list(curratings.keys())
    for school in users:
        data = {'学校': school}
        for i in range(len(ratings_history)):
            rating = ratings_history[i].get(school, None)
            data[tags[i]] = rating
        datas.append(data)

    df = pd.DataFrame(datas)
    if not df.empty:
        df = df.sort_values(by=[tags[-1], '学校'], ascending=[False, True])

    csv_path, xlsx_path = rating_output_paths('school', year_arg)
    df.to_csv(csv_path, index=False, encoding='utf-8', lineterminator='\n')

    if not df.empty:
        xlsx_df = df.copy()
        xlsx_df['Δ'] = xlsx_df['学校'].map(diff)
        styled_df = xlsx_df.style.map(rating_color, subset=tags)
        styled_df = styled_df.map(lambda v:'color:red;' if pd.notnull(v) and float(v)>=0 else 'color:gray;', subset=['Δ'])
        def format_delta(v):
            if pd.isnull(v): return ''
            return f'{int(v):+d}'
        styled_df = styled_df.format(format_delta, subset=['Δ'])
        styled_df.to_excel(xlsx_path, index=False)
    print(f"School Rating exported to {csv_path} & {xlsx_path}")

def main(rating_type: str, year_arg: str):
    year_arg = normalize_year_arg(year_arg)
    if rating_type in ['member', 'all']:
        generate_member_rating("member", year_arg)
    if rating_type in ['school', 'all']:
        generate_school_rating("school", year_arg)
