import json
import yaml
import os
from typing import List, Dict, Any
from src.models import ContestStandings, TeamStanding, ProblemStatus
from src.utils.http import fetch_text_with_retry, fetch_json_with_retry

class RanklandDataSource:
    BASE_URL = "https://raw.githubusercontent.com/algoux/srk-collection/master/official"

    def get_contest_list(self) -> Dict[str, Any]:
        """
        获取 Rankland official 的配置列表 config.yaml
        """
        list_url = f"{self.BASE_URL}/config.yaml"
        content = fetch_text_with_retry(list_url)
        if content:
            return yaml.safe_load(content)
        return {}

    def fetch_contest_data(self, category: str, year: str, contest_id: str) -> Dict[str, Any]:
        """
        获取单个比赛的数据 (SRK 格式)
        因为 Rankland 存放路径是按 {category}/{year}/{contest_id}.srk.json
        例如: category="icpc", year="icpc2025", contest_id="icpc2025ecfinal"
        """
        cache_dir = "data/raw/cache/rankland"
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{contest_id}.json")
        
        if os.path.exists(cache_file):
            
            print(f"  [CACHE] Loading Rankland from {cache_file}")
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        url = f"{self.BASE_URL}/{category}/{year}/{contest_id}.srk.json"
        
        data = fetch_json_with_retry(url)
        if data:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            return data
            
        return {}

class SRKStandingsGenerator:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.problems = data.get("problems", [])
        self.problem_ids = [p.get("alias", p.get("title", str(i))) for i, p in enumerate(self.problems)]
        
    def generate(self) -> Dict[str, Any]:
        final_standings = []
        
        rows = self.data.get("rows", [])
        for i, row in enumerate(rows):
            user = row.get("user", {})
            score = row.get("score", {})
            statuses = row.get("statuses", [])
            
            team_id = user.get("id", str(i))
            team_name = user.get("name", "")
            school = user.get("organization", "")
            is_official = user.get("official", False)
            
            members = user.get("teamMembers", [])
            
            # SRK 中教练可能在名字里带 (教练)
            member_names = []
            coach_names = []
            for m in members:
                name = m.get("name", "")
                if name:
                    if "(教练)" in name or "（教练）" in name:
                        coach_names.append(name.replace("(教练)", "").replace("（教练）", "").strip())
                    else:
                        # 某些队伍（尤其是没有正确填写三个对象的情况）会把三个人的名字用空格连在一起
                        if len(members) == 1 and name.count(' ') >= 2:
                            member_names.extend([n.strip() for n in name.split() if n.strip()])
                        else:
                            member_names.append(name)
            
            # 修复包含逗号导致四名成员的情况
            if len(member_names) > 3 and "AWADALLA" in member_names:
                # 找到并合并 "AWADALLA" 和 "bdelrahman HossamEldin A. A."
                try:
                    idx = member_names.index("AWADALLA")
                    member_names[idx] = member_names[idx] + ", " + member_names[idx+1]
                    member_names.pop(idx+1)
                except Exception:
                    pass
            
            # 女队标签可能存在于 extra 中或者名字里
            is_girl = None
            
            # 读取总题数和罚时
            solved = score.get("value", 0)
            penalty_time = score.get("time", [0, "s"])
            penalty_mins = int(penalty_time[0]) // 60 if penalty_time[1] == "s" else int(penalty_time[0])
            
            problems_dict = {}
            for p_idx, status in enumerate(statuses):
                res = status.get("result")
                # tries 在 SRK 是包含了通过的那发提交的总提交数 (如果是 AC 的话)
                tries = status.get("tries", 0)
                ptime = status.get("time", [0, "s"])
                pmins = int(ptime[0]) // 60 if ptime[1] == "s" else int(ptime[0])
                
                if res in ["AC", "FB"]: # First Blood or Accepted
                    problems_dict[str(p_idx)] = ProblemStatus(
                        solved=True,
                        tries=tries - 1 if tries > 0 else 0, # Standard JSON 需要未通过次数
                        time_mins=pmins
                    )
                elif res in ["RJ", "WA", "TLE", "MLE", "RTE", "PE", "CE", "UKE"] or res is not None:
                    # 尚未 AC
                    if tries > 0:
                        problems_dict[str(p_idx)] = ProblemStatus(
                            solved=False,
                            tries=tries,
                            time_mins=0
                        )
            
            # Rankland 榜单自身已经排好序并带有 rank 信息（在原数据里的顺序就是终榜顺）
            # 或者我们可以重新算一遍以保持公式一致，这里我们保留 Rankland 计算好的数据结构
            # 此外，Rankland 奖牌信息有时存在于 mark 中，但在 SRK 目前未直接携带。
            medal = "" 
            # (如果有特定的标记会在 row['awards'] 里，我们先略过)
            if "awards" in row and isinstance(row["awards"], list) and len(row["awards"]) > 0:
                raw_medal = row["awards"][0] # maybe e.g. "Gold Medal"
                if "Gold" in raw_medal or "金" in raw_medal: medal = "Gold"
                elif "Silver" in raw_medal or "银" in raw_medal: medal = "Silver"
                elif "Bronze" in raw_medal or "铜" in raw_medal: medal = "Bronze"
                elif "Honor" in raw_medal or "优胜" in raw_medal: medal = "Honorable"
                else: medal = raw_medal
            
            final_standings.append(TeamStanding(
                rank=i + 1 if is_official else 0, # Note: using 0 to represent '*' or unofficial
                team_name=team_name,
                school=school,
                member1=member_names[0] if len(member_names) > 0 else None,
                member2=member_names[1] if len(member_names) > 1 else None,
                member3=member_names[2] if len(member_names) > 2 else None,
                coach="、".join(coach_names) if coach_names else None,
                is_girl=is_girl,
                is_official=is_official,
                score=solved,
                penalty=penalty_mins,
                medal=medal if medal else None,
                problem_scores=problems_dict
            ))
            
        contest_name = self.data.get("contest", {}).get("title", "Unknown Contest")
            
        result = ContestStandings(
            contest_name=contest_name,
            problem_ids=self.problem_ids,
            standings=final_standings
        )
        return result.to_dict()

if __name__ == "__main__":
    spider = RanklandDataSource()
    
    print("Fetching Contest List from Rankland...")
    try:
        config_yaml = spider.get_contest_list()
        print(f"Got Rankland configuration roots: {list(config_yaml.keys())}")
    except ImportError:
        print("Please install PyYAML explicitly using pip to parse config.yaml")

    print("\nFetching specific contest data (ICPC 2025 ECFinal)...")
    # path in config.yaml is usually icpc/icpc2025/icpc2025ecfinal
    data = spider.fetch_contest_data("icpc", "icpc2025", "icpc2025ecfinal")
    
    if data and "problems" in data:
        print(f"Data fetched. Processing standings for {data.get('contest', {}).get('title')}...")
        generator = SRKStandingsGenerator(data)
        standard_json = generator.generate()
        
        # Save Standard JSON
        import os
        
        out_dir = "data/raw/json/rankland"
        os.makedirs(out_dir, exist_ok=True)
        
        json_file = f"{out_dir}/icpc_50th_ecfinal.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(standard_json, f, ensure_ascii=False, indent=2)
        print(f"Standard JSON successfully saved to {json_file}")
        
        print("\nTop 5 Official Teams from Rankland:")
        standings = standard_json.get("standings", [])
        official_t = [t for t in standings if t.get("is_official")]
        for i in range(min(5, len(official_t))):
            t = official_t[i]
            print(f"Rank {t['rank']}: {t['team_name']} ({t['school']}) - {t['solved']} solved, {t['penalty']} penalty - {t['medal']}")