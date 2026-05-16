import requests
import json
import yaml
import csv
from datetime import datetime
import re
import os

SERIES_YEAR_BASE = {
    'ICPC': 1975,
    'CCPC': 2014,
}

def parse_int(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def chinese_number_to_int(text):
    text = str(text or '').strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)

    digit_map = {
        '零': 0,
        '〇': 0,
        '一': 1,
        '二': 2,
        '两': 2,
        '三': 3,
        '四': 4,
        '五': 5,
        '六': 6,
        '七': 7,
        '八': 8,
        '九': 9,
    }
    unit_map = {
        '十': 10,
        '百': 100,
        '千': 1000,
    }
    section_unit_map = {
        '万': 10000,
    }

    total = 0
    section = 0
    number = 0
    for char in text:
        if char in digit_map:
            number = digit_map[char]
        elif char in unit_map:
            unit = unit_map[char]
            section += (number or 1) * unit
            number = 0
        elif char in section_unit_map:
            section += number
            total += (section or 1) * section_unit_map[char]
            section = 0
            number = 0
        else:
            return None

    return total + section + number

def parse_ordinal_from_name(name):
    text = str(name or '')
    match = re.search(r'第([0-9零〇一二两三四五六七八九十百千万]+)届', text)
    if match:
        return chinese_number_to_int(match.group(1))

    match = re.search(r'\b([0-9]+)(?:st|nd|rd|th)\b', text, re.IGNORECASE)
    return int(match.group(1)) if match else None

def parse_year_from_name(name):
    match = re.search(r'20\d{2}', str(name or ''))
    return int(match.group(0)) if match else None

def parse_year_from_date(date_str):
    text = str(date_str or '').strip()
    if re.match(r'^\d{4}', text):
        return int(text[:4])
    return None

def is_strict_series_category(series, category):
    return series in SERIES_YEAR_BASE and category in ('Regional', 'Final')

def normalize_year_ordinal(series, category, year, ordinal, date_str, name):
    year = parse_int(year)
    ordinal = parse_int(ordinal)
    name_year = parse_year_from_name(name)
    name_ordinal = parse_ordinal_from_name(name)
    date_year = parse_year_from_date(date_str)

    if is_strict_series_category(series, category):
        if category == 'Final' and name_ordinal is not None and 'world final' in str(name or '').lower():
            ordinal = name_ordinal
        if ordinal is None:
            ordinal = name_ordinal
        if year is None:
            year = name_year
        if ordinal is not None:
            year = SERIES_YEAR_BASE[series] + ordinal
        elif year is not None:
            ordinal = year - SERIES_YEAR_BASE[series]
        return year, ordinal

    if ordinal is None:
        ordinal = name_ordinal
    if year is None:
        year = name_year
    if year is None:
        year = date_year
    return year, ordinal

def parse_xcpcio():
    contests = []
    try:
        data = requests.get('https://board.xcpcio.com/data/index/contest_list.json').json()
    except Exception as e:
        print(f"Error fetching XCPCIO: {e}")
        return []

    for series, series_data in data.items():
        if series not in ['icpc', 'ccpc', 'provincial-contest', 'camp']:
            continue
        
        for group, group_data in series_data.items():
            if type(group_data) is not dict:
                continue
                
            ordinal = None
            year = None
            
            # Determine Year and Ordinal
            if series == 'icpc':
                if group.isdigit():
                    year = int(group)
                    ordinal = year - 1975
                elif group.endswith('st') or group.endswith('nd') or group.endswith('rd') or group.endswith('th'):
                    try:
                        ordinal = int(re.search(r'\d+', group).group())
                        year = ordinal + 1975
                    except:
                        pass
            elif series == 'ccpc':
                if group.isdigit():
                    year = int(group)
                    ordinal = year - 2014
                elif group.endswith('st') or group.endswith('nd') or group.endswith('rd') or group.endswith('th'):
                    try:
                        ordinal = int(re.search(r'\d+', group).group())
                        year = ordinal + 2014
                    except:
                        pass
            
            std_series = 'ICPC' if series == 'icpc' else 'CCPC' if series == 'ccpc' else 'Other'
            
            for contest_id, contest_info in group_data.items():
                if type(contest_info) is not dict or 'config' not in contest_info:
                    continue
                
                name = contest_info['config'].get('contest_name', '')
                start_time = contest_info['config'].get('start_time')
                date_str = ''
                if start_time:
                    try:
                        if start_time > 10000000000:
                            start_time /= 1000
                        date_str = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d')
                    except Exception:
                        pass
                
                contests.append({
                    'source': 'xcpcio',
                    'source_category': series,
                    'series': std_series,
                    'year': year,
                    'ordinal': ordinal,
                    'date': date_str,
                    'name': name,
                    'id': contest_info.get('board_link', '').lstrip('/')
                })
    return contests

def parse_rankland():
    try:
        config_text = requests.get('https://raw.githubusercontent.com/algoux/srk-collection/master/official/config.yaml').text
        data = yaml.safe_load(config_text)
    except Exception as e:
        print(f"Error fetching Rankland: {e}")
        return []

    return parse_rankland_config(data)

def parse_rankland_config(data):
    contests = []

    def update_context(node, series, source_category, year, ordinal, has_children):
        name = str(node.get('name', '') or '')
        path = str(node.get('path', '') or '')
        candidates = [path.lower(), name.lower()]

        for value in candidates:
            if value == 'icpc':
                series = 'ICPC'
                source_category = 'icpc'
            elif value == 'ccpc':
                series = 'CCPC'
                source_category = 'ccpc'
            else:
                normalized = normalize_source_category(value)
                if normalized in ('provincial', 'school', 'camp'):
                    source_category = normalized

        if has_children:
            match = re.search(r'\d{4}', name) or re.search(r'\d{4}', path)
            if match:
                year = int(match.group())
                if series == 'ICPC':
                    ordinal = year - 1975
                elif series == 'CCPC':
                    ordinal = year - 2014

        return series, source_category, year, ordinal

    def walk(node, series='Other', source_category='', year=None, ordinal=None):
        if not isinstance(node, dict):
            return

        children = node.get('children', [])
        has_children = isinstance(children, list) and bool(children)
        series, source_category, year, ordinal = update_context(node, series, source_category, year, ordinal, has_children)
        if has_children:
            for child in children:
                walk(child, series, source_category, year, ordinal)
            return

        path = node.get('path', '')
        if not path:
            return

        name = node.get('name', '')
        date_str = ''
        date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', str(name))
        if date_match:
            date_str = date_match.group(1)
            name = str(name)[len(date_str):].strip()

        contests.append({
            'source': 'rankland',
            'source_category': source_category,
            'series': series,
            'year': year,
            'ordinal': ordinal,
            'date': date_str,
            'name': name,
            'id': path
        })

    root = data.get('root', {}) if isinstance(data, dict) else {}
    for top_level in root.get('children', []):
        walk(top_level)

    return contests

def parse_archive():
    contests = []
    archive_dir = os.path.join('data', 'raw', 'cache', 'archive')
    csv_dir = os.path.join(archive_dir, 'csv')
    date_file = os.path.join(archive_dir, 'date.csv')
    
    if not os.path.exists(csv_dir) or not os.path.exists(date_file):
        print("Archive not found.")
        return []
        
    date_map = {}
    try:
        with open(date_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = row.get('date', '').strip()
                if d:
                    # convert YYYY/MM/DD to YYYY-MM-DD
                    parts = d.split('/')
                    if len(parts) == 3:
                        d = f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
                date_map[row['contest']] = d
    except Exception as e:
        print(f"Error reading archive date.csv: {e}")
        
    try:
        for fname in os.listdir(csv_dir):
            if not fname.endswith('.csv'):
                continue
            contest_id = fname[:-4] # remove .csv
            parts = contest_id.split('_')
            if len(parts) >= 3:
                ordinal_str = parts[0]
                series = parts[1].upper() # ICPC or CCPC
                name = '_'.join(parts[2:]) # e.g. 沈阳, ECFinal
                
                ordinal = None
                year = None
                if ordinal_str.isdigit():
                    ordinal = int(ordinal_str)
                    if series == 'ICPC':
                        year = ordinal + 1975
                    elif series == 'CCPC':
                        year = ordinal + 2014
                        
                date_str = date_map.get(contest_id, '')
                
                contests.append({
                    'source': 'archive',
                    'source_category': '',
                    'series': series,
                    'year': year,
                    'ordinal': ordinal,
                    'date': date_str,
                    'name': name,
                    'id': contest_id
                })
    except Exception as e:
        print(f"Error reading archive csv folder: {e}")
        
    return contests

def parse_pintia():
    try:
        from src.sources.pta_source import PtaDataSource
        data = PtaDataSource().get_contest_list()
    except Exception as e:
        print(f"Error fetching Pintia: {e}")
        return []
    
    contests = []
    for c in data:
        name = c.get('name', '')
        if '热身赛' in name or '测试' in name:
            continue
            
        c_id = c.get('id')
        start_at = c.get('start', '') 
        if not start_at: start_at = c.get('startAt', '')
        date_str = start_at[:10] if start_at else ''
        year = None
            
        series = 'Other'
        if 'CCPC' in name.upper() or '中国大学生程序设计竞赛' in name:
            series = 'CCPC'
        elif 'ICPC' in name.upper() or '国际大学生程序设计竞赛' in name:
            series = 'ICPC'
            
        year = parse_year_from_name(name)
        ordinal = parse_ordinal_from_name(name)
            
        contests.append({
            'source': 'pta',
            'source_category': '',
            'series': series,
            'year': year,
            'ordinal': ordinal,
            'date': date_str,
            'name': name,
            'id': c_id
        })
    return contests

def normalize_source_category(source_category):
    text = str(source_category or '').strip().lower()
    text = text.replace('_', '-').replace(' ', '-')
    if text in ('provincial-contest', 'provincial', 'province', '省赛'):
        return 'provincial'
    if text in ('school-contest', 'school', 'campus', '校赛'):
        return 'school'
    return text

def get_category(series, idx, name, source_category=''):
    lb = str(idx).lower()
    ln = str(name).lower()
    source_category = normalize_source_category(source_category)

    def has_any(keywords):
        return any(keyword in lb or keyword in ln for keyword in keywords)
    
    if has_any(['warmup', '热身', 'dressrehearsal', 'dress rehearsal', '测试']):
        return "Warmup"

    if source_category == 'camp':
        return "Camp"
    if source_category == 'provincial':
        return "Provincial"
    if source_category == 'school':
        return "School"
        
    if has_any(['girl', 'lad', '女生']):
        return "Girls"
    if has_any(['vocational', '高职']) or lb == 'hv' or lb.endswith('hv'):
        return "Vocational"
    if has_any(['online', '网络', 'internet']):
        return "Online"
    if has_any(['invitational', '邀请']):
        return "Invitational"
    
    if has_any(['final', '决赛']):
        return "Final"
    if has_any(['provincial', '省', '市', '自治区', '特别行政区']):
        return "Provincial"
    if has_any(['camp', '训练', '令营']):
        return "Camp"
    
    if series == 'CCPC' or series == 'ICPC':
        return "Regional"
    return "Regular"

def get_chinese_to_eng():
    try:
        import json
        with open('data/config/zh_to_en.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def sanitize_full_name(name):
    return re.sub(r'[/\\:*?"<>|]', '', str(name or '')).strip()

def get_name_id(source, series, idx, name):
    if source in ('pta', 'archive') or str(idx).isdigit():
        idx_cleaned = str(name).lower()
    else:
        idx_cleaned = str(idx).lower()
    
    if "第一场" in idx_cleaned:
        idx_cleaned = idx_cleaned.replace("第一场", "1")
    if "第二场" in idx_cleaned:
        idx_cleaned = idx_cleaned.replace("第二场", "2")
        
    for ch, en in get_chinese_to_eng().items():
        if ch.lower() in idx_cleaned:
            idx_cleaned = idx_cleaned.replace(ch.lower(), en)
            
    idx_cleaned = re.sub(r'[^a-zA-Z0-9一-龥]', '', idx_cleaned)
    if series != 'Other':
        idx_cleaned = re.sub(r'(icpc|ccpc)', '', idx_cleaned)
        
    idx_cleaned = re.sub(r'\d{4}', '', idx_cleaned)
    idx_cleaned = re.sub(r'\d+(th|st|nd|rd|届)', '', idx_cleaned)
    
    idx_cleaned = idx_cleaned.replace("网络预选赛", "online")
    idx_cleaned = idx_cleaned.replace("网络赛", "online")
    idx_cleaned = idx_cleaned.replace("网络", "online")
    idx_cleaned = idx_cleaned.replace("asiaec", "")
    idx_cleaned = idx_cleaned.replace("年", "")
    
    if source == 'pta' and series == 'Other':
        # 直接使用全名，去除可能导致文件系统问题的非法字符
        return sanitize_full_name(name)
    
    for w in ['总决赛', '预选赛', '邀请赛', '省赛', '特训营', '夏令营', '热身赛', '系统测试赛', '程序设计竞赛', '计算机技能竞赛', '高职专场', '女生专场', '混合组', '组', '锦标赛', '第十一届', '第十二届', '第十届', '届', '大学生', '中国']:
        idx_cleaned = idx_cleaned.replace(w, '')
        
    for w in ['invitational', 'onsite', 'warmup', 'camp', 'provincial', 'contest', 'internet', 'girls', 'girl', 'ladies', 'lady', 'women', 'dressrehearsal']:
        idx_cleaned = idx_cleaned.replace(w, '')
        
    return idx_cleaned.strip()

def get_default_name_id(category, name_id):
    if str(name_id or '').strip():
        return name_id
    defaults = {
        'Girls': 'girls',
        'Vocational': 'vocational',
    }
    return defaults.get(category, name_id)

def merge_contests(records):
    merged_dict = {}
    pta_full_names = {}
    for r in records:
        source = r['source']
        source_category = r.get('source_category', '')
        series = r['series']
        year = r['year'] if r['year'] is not None else ''
        ordinal = r['ordinal'] if r['ordinal'] is not None else ''
        date = r['date'] if r['date'] is not None else ''
        name = r['name']
        cid = r['id']
        
        sub = get_category(series, cid, name, source_category)
        year, ordinal = normalize_year_ordinal(series, sub, year, ordinal, date, name)
        year = year if year is not None else ''
        ordinal = ordinal if ordinal is not None else ''
        name_id = get_name_id(source, series, cid, name)
        name_id = get_default_name_id(sub, name_id)
        
        # Merge by year, series, sub, name_id to avoid missing dates causing duplicates
        key = (str(year), str(series), str(sub), str(name_id))
        
        if key not in merged_dict:
            merged_dict[key] = {
                'series': series, 
                'year': year, 
                'ordinal': ordinal,
                'date': date,
                'category': sub, 
                'name': name_id,
                'xcpcio_id': '', 
                'rankland_id': '',
                'archive_id': '',
                'pta_id': ''
            }
        else:
            if not merged_dict[key]['date'] and date:
                merged_dict[key]['date'] = date
            if not merged_dict[key]['ordinal'] and ordinal:
                merged_dict[key]['ordinal'] = ordinal
        
        if source == 'xcpcio':
            merged_dict[key]['xcpcio_id'] = cid
        elif source == 'rankland':
            merged_dict[key]['rankland_id'] = cid
        elif source == 'archive':
            merged_dict[key]['archive_id'] = cid
        elif source == 'pta':
            merged_dict[key]['pta_id'] = cid
            pta_full_names[key] = sanitize_full_name(name)

    for key, row in merged_dict.items():
        has_only_pta = row.get('pta_id') and not row.get('xcpcio_id') and not row.get('rankland_id') and not row.get('archive_id')
        if has_only_pta and pta_full_names.get(key):
            row['name'] = pta_full_names[key]
            
    return merged_dict

def main():
    print("Fetching XCPCIO...")
    xcpcio_list = parse_xcpcio()
    print("Fetching Rankland...")
    rankland_list = parse_rankland()
    print("Fetching Archive...")
    archive_list = parse_archive()
    print("Fetching PTA...")
    pta_list = parse_pintia()
    
    all_contests = xcpcio_list + rankland_list + archive_list + pta_list
    print(f"Total raw records: {len(all_contests)}")
    
    merged_dict = merge_contests(all_contests)
    print(f"Merged into unique events: {len(merged_dict)}")
    
    os.makedirs('data/contests', exist_ok=True)
    out_path = 'data/contests/contests.csv'
    
    out_fields = ['series', 'year', 'ordinal', 'date', 'category', 'name', 'xcpcio_id', 'rankland_id', 'pta_id', 'archive_id']
    try:
        with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=out_fields)
            writer.writeheader()
            sorted_keys = sorted(merged_dict.keys(), key=lambda x: (merged_dict[x]['date'] if merged_dict[x]['date'] else '0000-00-00', merged_dict[x]['year'] if merged_dict[x]['year'] else 0), reverse=True)
            for k in sorted_keys:
                writer.writerow(merged_dict[k])
        print(f"Saved merged contests to {out_path}")
    except PermissionError:
        out_path = 'data/contests/contests_new.csv'
        with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=out_fields)
            writer.writeheader()
            sorted_keys = sorted(merged_dict.keys(), key=lambda x: (merged_dict[x]['date'] if merged_dict[x]['date'] else '0000-00-00', merged_dict[x]['year'] if merged_dict[x]['year'] else 0), reverse=True)
            for k in sorted_keys:
                writer.writerow(merged_dict[k])
        print(f"Saved merged contests to {out_path} (original was blocked)")

if __name__ == '__main__':
    main()