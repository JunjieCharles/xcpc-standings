import requests
import json
import yaml
import csv
from datetime import datetime
import re
import os

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
                    'series': std_series,
                    'year': year,
                    'ordinal': ordinal,
                    'date': date_str,
                    'name': name,
                    'id': contest_info.get('board_link', '').lstrip('/')
                })
    return contests

def parse_rankland():
    contests = []
    try:
        config_text = requests.get('https://raw.githubusercontent.com/algoux/srk-collection/master/official/config.yaml').text
        data = yaml.safe_load(config_text)
    except Exception as e:
        print(f"Error fetching Rankland: {e}")
        return []

    for top_level in data.get('root', {}).get('children', []):
        cat_name = top_level.get('name', '')
        
        std_series = 'Other'
        if cat_name.upper() == 'ICPC':
            std_series = 'ICPC'
        elif cat_name.upper() == 'CCPC':
            std_series = 'CCPC'
            
        for group in top_level.get('children', []):
            group_name = group.get('name', '')
            
            year = None
            ordinal = None
            match = re.search(r'\d{4}', group_name)
            if match:
                year = int(match.group())
                if std_series == 'ICPC':
                    ordinal = year - 1975
                elif std_series == 'CCPC':
                    ordinal = year - 2014
            
            for child in group.get('children', []):
                name = child.get('name', '')
                path = child.get('path', '')
                
                date_str = ''
                child_year = year
                date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', name)
                if date_match:
                    date_str = date_match.group(1)
                    name = name[len(date_str):].strip()
                    if not child_year:
                        child_year = int(date_str[:4])
                    
                contests.append({
                    'source': 'rankland',
                    'series': std_series,
                    'year': child_year,
                    'ordinal': ordinal,
                    'date': date_str,
                    'name': name,
                    'id': path
                })
                
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
    ord_map = {'一':1, '二':2, '三':3, '四':4, '五':5, '六':6, '七':7, '八':8, '九':9, '十':10}
    for c in data:
        name = c.get('name', '')
        if '热身赛' in name or '测试' in name:
            continue
            
        c_id = c.get('id')
        start_at = c.get('start', '') 
        if not start_at: start_at = c.get('startAt', '')
        date_str = start_at[:10] if start_at else ''
        year = None
        if date_str:
            year = int(date_str[:4])
            
        series = 'Other'
        if 'CCPC' in name.upper() or '中国大学生程序设计竞赛' in name:
            series = 'CCPC'
        elif 'ICPC' in name.upper() or '国际大学生程序设计竞赛' in name:
            series = 'ICPC'
            
        m = re.search(r'20\d{2}', name)
        if m:
            year = int(m.group(0))
            
        ordinal = None
        m_ord = re.search(r'第([一二三四五六七八九十]+)届', name)
        if m_ord:
            cn_num = m_ord.group(1)
            val = 0
            if cn_num == '十': val = 10
            elif len(cn_num) == 1: val = ord_map.get(cn_num, 0)
            elif len(cn_num) == 2 and cn_num.startswith('十'): val = 10 + ord_map.get(cn_num[1:], 0)
            elif len(cn_num) == 2 and cn_num.endswith('十'): val = ord_map.get(cn_num[0], 0) * 10
            elif len(cn_num) == 3 and cn_num[1] == '十': val = ord_map.get(cn_num[0], 0) * 10 + ord_map.get(cn_num[2], 0)
            
            if val > 0:
                ordinal = val
                
        if series == 'CCPC' and ordinal:
            year = 2014 + ordinal
        elif series == 'ICPC' and ordinal:
            year = 1975 + ordinal
            
        contests.append({
            'source': 'pta',
            'series': series,
            'year': year,
            'ordinal': ordinal,
            'date': date_str,
            'name': name,
            'id': c_id
        })
    return contests

def get_category(series, idx, name):
    lb = str(idx).lower()
    ln = str(name).lower()
    
    if "warmup" in lb or "热身" in ln or "dressrehearsal" in lb or "dress rehearsal" in ln or "测试" in ln:
        return "Warmup"
    
    if series == "Other":
        if "vocational" in lb or "高职" in ln:
            return "Vocational"
        return "Regular"
        
    if "girl" in lb or "girl" in ln or "lad" in lb or "lad" in ln or "女生" in ln:
        return "Girls"
    if "vocational" in lb or "高职" in ln:
        return "Vocational"
    if "online" in lb or "网络" in ln or "internet" in lb:
        return "Online"
    if "invitational" in lb or "邀请" in ln:
        return "Invitational"
    
    if "final" in lb or "总决赛" in ln:
        return "Final"
    if "provincial" in lb or "省" in ln:
        return "Provincial"
    if "camp" in lb or "训练" in ln or "夏令营" in ln:
        return "Camp"
    
    return "Regional"

def get_chinese_to_eng():
    try:
        import json
        with open('data/config/zh_to_en.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

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
        clean_full = re.sub(r'[/\\:*?"<>|]', '', str(name))
        return clean_full.strip()
    
    for w in ['总决赛', '预选赛', '邀请赛', '省赛', '特训营', '夏令营', '热身赛', '系统测试赛', '程序设计竞赛', '计算机技能竞赛', '高职专场', '女生专场', '混合组', '组', '锦标赛', '第十一届', '第十二届', '第十届', '届', '大学生', '中国']:
        idx_cleaned = idx_cleaned.replace(w, '')
        
    for w in ['invitational', 'onsite', 'warmup', 'camp', 'provincial', 'contest', 'internet', 'girls', 'girl', 'ladies', 'lady', 'women', 'dressrehearsal']:
        idx_cleaned = idx_cleaned.replace(w, '')
        
    return idx_cleaned.strip()

def merge_contests(records):
    merged_dict = {}
    for r in records:
        source = r['source']
        series = r['series']
        year = r['year'] if r['year'] is not None else ''
        ordinal = r['ordinal'] if r['ordinal'] is not None else ''
        date = r['date'] if r['date'] is not None else ''
        name = r['name']
        cid = r['id']
        
        sub = get_category(series, cid, name)
        name_id = get_name_id(source, series, cid, name)
        
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