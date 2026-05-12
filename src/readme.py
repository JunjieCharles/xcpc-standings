import csv
import os
import re
import json
from datetime import datetime
from src.utils.text import contains_chinese

def main():

    en_to_zh = {}
    json_path = 'data/config/zh_to_en.json'
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            zh_to_en = json.load(f)
            en_to_zh = {v: k for k, v in zh_to_en.items()}

    data = []

    csv_dir = 'data/merged/csv'
    contests_file = 'data/contests/contests.csv'

    if not os.path.exists(contests_file):
        print(f"File not found: {contests_file}")
        exit(1)

    with open(contests_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            series = row.get('series', '')
            year = row.get('year', '')
            ordinal = row.get('ordinal', '')
            date_str = row.get('date', '')
            sub = row.get('category', '')
            name = row.get('name', '')
        
            xcpcio = bool(row.get('xcpcio_id', '').strip())
            rankland = bool(row.get('rankland_id', '').strip())
            pta = bool(row.get('pta_id', '').strip())
            archive = bool(row.get('archive_id', '').strip())
        
            contest_name = f"{series}_{year}_{sub}_{name}"
        
            date_val = None
            if date_str:
                try:
                    date_val = datetime.strptime(date_str, '%Y-%m-%d')
                except:
                    pass
                
            filepath = os.path.join(csv_dir, f"{contest_name}.csv")
        
            if not os.path.exists(filepath):
                continue
            
            with open(filepath, 'r', encoding='utf-8-sig') as cf:
                creader = csv.reader(cf)
                try:
                    headers = next(creader)
                except:
                    continue
                
                has_rank = 'Rank' in headers
                has_school = 'School' in headers
                has_team = 'Team Name' in headers
                has_solved = 'Solved' in headers
                has_penalty = 'Penalty' in headers
                has_medal = 'Medal' in headers
                has_problem = len(headers) > 13
                has_members = 'Member1' in headers
            
                school_col_index = headers.index('School') if has_school else -1
                members_col_index = headers.index('Member1') if has_members else -1
            
                school_has_chinese = False
                members_has_chinese = False
            
                row_count = 0
                for r in creader:
                    if has_school and school_col_index < len(r):
                        if contains_chinese(r[school_col_index]):
                            school_has_chinese = True
                    if has_members and members_col_index < len(r):
                        if contains_chinese(r[members_col_index]):
                            members_has_chinese = True
                    row_count += 1
                    if row_count >= 50:
                        break
        
            data.append({
                'series': series,
                'year': int(float(year)) if year.replace('.', '', 1).isdigit() else 0,
                'ordinal': ordinal,
                'date': date_val,
                'category': sub,
                'name': en_to_zh.get(name, name),
                'contest_name': contest_name,
                'has_xcpcio': xcpcio,
                'has_rankland': rankland,
                'has_pta': pta,
                'has_rank': has_rank,
                'has_school': has_school,
                'has_team': has_team,
                'has_solved': has_solved,
                'has_penalty': has_penalty,
                'has_medal': has_medal,
                'has_problem': has_problem,
                'has_members': has_members,
                'school_has_chinese': school_has_chinese,
                'members_has_chinese': members_has_chinese
            })

    def contest_sort_key(item):
        date_val = item['date'] or datetime.min
        return date_val

    data.sort(key=contest_sort_key, reverse=True)

    markdown_lines = [
        "|Series|Year|Ordinal|Category|Name|Date|XCPCIO|Rankland|PTA|Rank|School|Team|Solved|Penalty|Medal|Problems|Members|",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    ]

    def check_symbol(condition):
        return '✅' if condition else ''

    def check_school_symbol(has_column, has_chinese):
        if not has_column: return ''
        return '✅' if has_chinese else '🔤'

    for item in data:
        date_str = item['date'].strftime('%Y/%m/%d') if item['date'] else ''
        line = (
            f"|{item['series']}"
            f"|{item['year']}"
            f"|{item['ordinal']}"
            f"|{item['category']}"
            f"|{item['name']}"
            f"|{date_str}"
            f"|{check_symbol(item['has_xcpcio'])}"
            f"|{check_symbol(item['has_rankland'])}"
            f"|{check_symbol(item['has_pta'])}"
            f"|{check_symbol(item['has_rank'])}"
            f"|{check_school_symbol(item['has_school'], item['school_has_chinese'])}"
            f"|{check_symbol(item['has_team'])}"
            f"|{check_symbol(item['has_solved'])}"
            f"|{check_symbol(item['has_penalty'])}"
            f"|{check_symbol(item['has_medal'])}"
            f"|{check_symbol(item['has_problem'])}"
            f"|{check_school_symbol(item['has_members'], item['members_has_chinese'])}|"
        )
        markdown_lines.append(line)

    with open('README.md', 'w', encoding='utf-8') as f:
        intro = """# ICPC/CCPC 区域赛终榜汇总

## 使用说明

本项目使用 `main.py` 作为统一入口，提供以下命令行功能：

- **更新比赛列表数据**
  ```bash
  python main.py update
  ```
- **合并比赛榜单并生成 CSV** (支持批量处理特定年份)
  ```bash
  python main.py merge --batch --years 2025
  # 处理多范围或全量： python main.py merge --batch --years 2021-2025 
  # （也可设为 all 获取全部年份）
  ```
- **生成/更迭 Rating 双榜单**
  ```bash
  python main.py rating --type all  # --type 选项：member, school, all
  ```
- **更新 README 状态**
  ```bash
  python main.py readme
  ```

- 原始文件在 `data/raw/cache` 文件夹下，解析并合并后的文件在 `data/merged/csv` 文件夹下
- 特别鸣谢：[xcpcio](https://github.com/xcpcio/xcpcio)、[RankLand](https://rl.algoux.org/collection/official)

## 数据完整性

"""
        f.write(intro)
        f.write('\n'.join(markdown_lines) + '\n')
    
    print(f"README.md generated successfully! {len(data)} contests added.")

if __name__ == '__main__':
    main()
