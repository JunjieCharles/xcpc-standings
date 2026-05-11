import os
import csv
import pandas as pd
from typing import Dict, List, Tuple
from tqdm import tqdm
import json
from datetime import datetime

from src.rating.utils import calculateRating, normalize, rating_color
from src.utils.school import normalize_school_name
from src.utils.text import contains_chinese

def get_zh_to_en():
    json_path = 'data/config/zh_to_en.json'
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def build_contest_schedule(rating_type: str = "member") -> List[Dict]:
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
            
            if sub not in ['Regional', 'Final', 'Invitational', 'Online', 'Girls', 'Vocational']:
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
    
    schedule = []
    for d in sorted_dates:
        items = grouped[d]
        # Order: CCPC before ICPC, Vocational -> Girls -> others
        def sort_key(x):
            series_order = 1 if x['series'] == 'ICPC' else 0
            sub_order = 0 if x['sub'] == 'Vocational' else (1 if x['sub'] == 'Girls' else 2)
            return (series_order, sub_order, x['name'])
            
        items_sorted = sorted(items, key=sort_key)
        
        if rating_type == 'school':
            # For school rating, do not merge contests on the same day into a single column
            for item in items_sorted:
                zh_name = en_to_zh.get(item['name'], item['name'])
                tag = f"{item['series']}{zh_name}"
                if item['sub'] == 'Final' and item['name'] == 'final':
                    tag = f"{item['series']}总决赛"
                if item['sub'] == 'Final' and item['name'] == 'ecfinal':
                    tag = f"{item['series']} ECFinal"
                schedule.append({
                    'date': d,
                    'tag': tag,
                    'files': [item['file']]
                })
        else:
            # Build tag like "ICPC南京/CCPC哈尔滨" for member rating
            tags = []
            files = []
            for item in items_sorted:
                zh_name = en_to_zh.get(item['name'], item['name'])
                tag = f"{item['series']}{zh_name}"
                if item['sub'] == 'Final' and item['name'] == 'final':
                    tag = f"{item['series']}总决赛"
                if item['sub'] == 'Final' and item['name'] == 'ecfinal':
                    tag = f"{item['series']} ECFinal"
                tags.append(tag)
                files.append(item['file'])
                
            schedule.append({
                'date': d,
                'tag': "/".join(tags),
                'files': files
            })
        
    return schedule

def generate_member_rating(rating_type="member"):
    schedule = build_contest_schedule(rating_type)
    if not schedule:
        return
        
    tags = [s['tag'] for s in schedule]
    
    ratings_history = []
    curratings = {}
    diff = {}
    pending_diff = {}

    print("Generating Member Rating...")
    for day_group in tqdm(schedule):
        skip = len(day_group['files']) > 1
        
        for file in day_group['files']:
            df = pd.read_csv(file, encoding='utf-8')
            userrank = {}
            for _, row in df.iterrows():
                if row.isnull().all():
                    continue
                if 'Unofficial' in row and (row['Unofficial'] != 'N' and row['Unofficial'] != False):
                    continue
                    
                # Skip zero solves
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
                
                # Check members
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

            newrating = calculateRating(userrank, curratings)
            cur_diff = {u: newrating[u] - curratings.get(u, 1400) for u in newrating}
            curratings.update(newrating)

            if skip:
                for k, v in cur_diff.items():
                    pending_diff[k] = pending_diff.get(k, 0) + v
            else:
                if pending_diff:
                    for k, v in pending_diff.items():
                        cur_diff[k] = cur_diff.get(k, 0) + v
                    pending_diff = {}
                diff = cur_diff
        
        # After finishing all files on this date
        if skip:
            if pending_diff:
                for k, v in pending_diff.items():
                    cur_diff[k] = cur_diff.get(k, 0) + v
                pending_diff = {}
            diff = cur_diff
            
        ratings_history.append(curratings.copy())

    # Form dataframe
    datas = []
    users = curratings.keys()
    for school, member in users:
        data = {'学校': school, '姓名': member}
        for i in range(len(ratings_history)):
            rating = ratings_history[i].get((school, member), None)
            data[tags[i]] = rating
        if (school, member) in diff:
            data['Δ'] = diff[(school, member)]
        datas.append(data)

    df = pd.DataFrame(datas)
    if not df.empty:
        df = df.sort_values(by=[tags[-1], '学校'], ascending=[False, True])

    os.makedirs('data/rating', exist_ok=True)
    df.to_csv('data/rating/rating_member.csv', index=False, encoding='utf-8')

    if not df.empty:
        df = df.style.map(rating_color, subset=tags)
        df = df.map(lambda v:'color:red;' if pd.notnull(v) and float(v)>=0 else 'color:gray;', subset=['Δ'])
        # Handle NaN formatting
        def format_delta(v):
            if pd.isnull(v): return ''
            return f'{int(v):+d}'
        df = df.format(format_delta, subset=['Δ'])
        df.to_excel('data/rating/rating_member.xlsx', index=False)
    print("Member Rating exported to data/rating/rating_member.csv & .xlsx")

def generate_school_rating(rating_type="school"):
    schedule = build_contest_schedule(rating_type)
    if not schedule:
        return
        
    tags = [s['tag'] for s in schedule]
    
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
        if school in diff:
            data['Δ'] = diff[school]
        datas.append(data)

    df = pd.DataFrame(datas)
    if not df.empty:
        df = df.sort_values(by=[tags[-1], '学校'], ascending=[False, True])

    os.makedirs('data/rating', exist_ok=True)
    df.to_csv('data/rating/rating_school.csv', index=False, encoding='utf-8')

    if not df.empty:
        df = df.style.map(rating_color, subset=tags)
        df = df.map(lambda v:'color:red;' if pd.notnull(v) and float(v)>=0 else 'color:gray;', subset=['Δ'])
        def format_delta(v):
            if pd.isnull(v): return ''
            return f'{int(v):+d}'
        df = df.format(format_delta, subset=['Δ'])
        df.to_excel('data/rating/rating_school.xlsx', index=False)
    print("School Rating exported to data/rating/rating_school.csv & .xlsx")

def main(rating_type: str):
    if rating_type in ['member', 'all']:
        generate_member_rating("member")
    if rating_type in ['school', 'all']:
        generate_school_rating("school")
