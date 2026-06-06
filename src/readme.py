import csv
import os
import re
import json
from datetime import datetime
from src.utils.text import contains_chinese

def translate_contest_name(name, en_to_zh):
    if name in en_to_zh:
        return en_to_zh[name]
    match = re.match(r'^([a-z]+)(\d+)$', str(name or ''))
    if match and match.group(1) in en_to_zh:
        return f"{en_to_zh[match.group(1)]}{match.group(2)}"
    return name

def display_contest_name(category, name, en_to_zh):
    display_name = translate_contest_name(name, en_to_zh)
    if category == 'Invitational':
        return f"{display_name}邀请赛"
    return display_name

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
                'name': display_contest_name(sub, name, en_to_zh),
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

    def check_members_symbol(has_column, has_chinese):
        if not has_column: return ''
        return '✅' if has_chinese else ''

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
            f"|{check_members_symbol(item['has_members'], item['members_has_chinese'])}|"
        )
        markdown_lines.append(line)

    with open('README.md', 'w', encoding='utf-8', newline='\n') as f:
        intro = """# XCPC Standings

## 使用说明

本项目汇总 ICPC/CCPC 等 XCPC 赛事终榜，并生成统一 CSV/JSON 与个人、学校 Rating。`main.py` 是统一入口；年份支持完整写法和短写，例如 `2025`、`25`、`25-26`。半年度范围按比赛日期筛选，可写作 `25下半年-26上半年` 或 `25H2-26H1`。

```bash
# 更新比赛列表
python main.py update

# 批量合并榜单，输出到 data/merged/json 和 data/merged/csv
python main.py merge --batch --years 25下半年-26上半年

# 生成个人和学校 Rating，输出到 data/rating/csv 和 data/rating/xlsx
python main.py rating --type all --years 25下半年-26上半年

# 生成当前赛季 Rating，或从 24H2 起生成历史 Rating
python main.py rating --type all --current
python main.py rating --type all --history --history-start 24H2

# 重新生成本说明和下方数据完整性表
python main.py readme
```

常用输出位置：

- 原始缓存：`data/raw/cache`
- 比赛索引：`data/contests/contests.csv`、`data/contests/rated_contests.csv`
- 合并榜单：`data/merged/csv`、`data/merged/json`
- PDF 参赛手册：`data/raw/cache/pdf`（作为名单补充源）
- Rating CSV：`data/rating/csv`
- Rating XLSX：`data/rating/xlsx`

特别鸣谢：[xcpcio](https://github.com/xcpcio/xcpcio)、[RankLand](https://rl.algoux.org/collection/official)

## 数据完整性

"""
        f.write(intro)
        f.write('\n'.join(markdown_lines) + '\n')

    print(f"README.md generated successfully! {len(data)} contests added.")

if __name__ == '__main__':
    main()
