import json

import urllib.request
from typing import List, Dict, Any
import csv
from src.models import ContestStandings, TeamStanding, ProblemStatus
from src.utils.http import fetch_json_with_retry

def get_xcpcio_name(obj) -> str:
    """Helper to extract localized name from XCPCIO format."""
    if isinstance(obj, str):
        return obj.strip()
    if not isinstance(obj, dict):
        return str(obj)
    
    # If it is { "name": "something" }
    if "name" in obj:
        return get_xcpcio_name(obj["name"])
        
    if "texts" in obj:
        if "zh-CN" in obj["texts"]:
            return obj["texts"]["zh-CN"]
        if "en" in obj["texts"]:
            return obj["texts"]["en"]
    return obj.get("fallback", "") or obj.get("fallback_lang", "") or str(obj)

class ICPCStandingsGenerator:
    def __init__(self, data: Dict[str, Any]):
        self.config = data.get("config", {}) or {}
        self.teams_data = data.get("team", []) or []
        self.runs_data = data.get("run", []) or []
        self.organizations_data = data.get("organizations", []) or []
        
        self.penalty_time = self.config.get("penalty", 20 * 60) # Default 20 mins to seconds
        self.problem_ids = self.config.get("problem_id", [])
        self.options = self.config.get("options", {}) or {}
        self.penalty_mode = self.options.get("calculation_of_penalty", "")
        
        # Process organizations
        # In XCPCIO, orgs can be a list or a dict
        self.org_map = {}
        if isinstance(self.organizations_data, list):
            for org in self.organizations_data:
                self._parse_org(org, org.get("id"))
        elif isinstance(self.organizations_data, dict):
            for oid, org in self.organizations_data.items():
                self._parse_org(org, oid)

    def _parse_org(self, org: Dict, org_id: str):
        if not org_id:
            return
        name_obj = org.get("name", {})
        
        name = ""
        if isinstance(name_obj, str):
            name = name_obj
        else:
            name = name_obj.get("fallback", "") or name_obj.get("fallback_lang", "")
            if "texts" in name_obj:
                name = name_obj["texts"].get("zh-CN", name_obj["texts"].get("en", name))
            if not name:
                name = name_obj.get("fallback", "Unknown")
            
        self.org_map[org_id] = name

    def _get_team_name(self, team_obj: Dict) -> str:
        name_obj = team_obj.get("name", {})
        
        if isinstance(name_obj, str):
            return name_obj
            
        if "texts" in name_obj and "zh-CN" in name_obj["texts"]:
            return name_obj["texts"]["zh-CN"]
        if "texts" in name_obj and "en" in name_obj["texts"]:
            return name_obj["texts"]["en"]
        return name_obj.get("fallback", str(name_obj))

    def _timestamp_to_seconds(self, timestamp: Any) -> float:
        try:
            value = float(timestamp or 0)
        except (TypeError, ValueError):
            return 0.0

        unit = str(self.options.get("submission_timestamp_unit", "")).lower()
        if unit in {"millisecond", "milliseconds", "ms"}:
            return value / 1000.0
        if unit in {"second", "seconds", "s"}:
            return value

        start_time = self.config.get("start_time")
        end_time = self.config.get("end_time")
        try:
            duration_seconds = float(end_time) - float(start_time)
        except (TypeError, ValueError):
            duration_seconds = 0

        if duration_seconds > 0 and value > duration_seconds * 10:
            return value / 1000.0
        if value > 24 * 60 * 60:
            return value / 1000.0
        return value

    def _accumulates_penalty_in_seconds(self) -> bool:
        return self.penalty_mode == "accumulate_in_seconds_and_finally_to_the_minute"
    
    def generate(self) -> List[Dict]:
        teams = {}
        # Init teams
        for t in (list(self.teams_data.values()) if isinstance(self.teams_data, dict) else self.teams_data):
            # XCPCIO team list might be a dict mapped by keys or array, handle both if necessary
            # Assuming array based on test output
            if not isinstance(t, dict): continue
            tid = t.get("id") or t.get("team_id")
            if not tid:
                continue
            org_id = t.get("organization_id", "")
            org_name = self.org_map.get(org_id, org_id) # default to id if not found
            if not org_name and "organization" in t:
                org_name = t["organization"]
            
            # Process members
            members_list = []
            for m in t.get("members", []):
                name = get_xcpcio_name(m)
                if name:
                    members_list.append(name)
                    
            coaches_list = []
            coaches = t.get("coaches", [])
            if not coaches and t.get("coach"):
                coaches = [t.get("coach")]
            for c in coaches:
                name = get_xcpcio_name(c)
                if name:
                    coaches_list.append(name)
            
            team_groups = t.get("group", [])
            
            is_girl_flag = None
            if "girl" in team_groups or "girls" in team_groups or "women" in team_groups:
                is_girl_flag = True

            teams[tid] = {
                "team_id": tid,
                "team_name": self._get_team_name(t),
                "school": org_name,
                "member1": members_list[0] if len(members_list) > 0 else "",
                "member2": members_list[1] if len(members_list) > 1 else "",
                "member3": members_list[2] if len(members_list) > 2 else "",
                "coach": "、".join(coaches_list),
                "is_girl": is_girl_flag,
                "is_official": "official" in team_groups,
                "solved": 0,
                "penalty_mins": 0,
                "penalty_seconds": 0.0,
                "problems": {}, # pk -> { 'solved': bool, 'tries': int, 'time': int }
            }
        
        # Sort runs by timestamp to process chronologically
        sorted_runs = sorted(self.runs_data, key=lambda x: x.get("timestamp", 0))
        
        for run in sorted_runs:
            tid = run.get("team_id")
            if tid not in teams:
                continue
            
            p_id = run.get("problem_id")
            status = run.get("status")
            timestamp = run.get("timestamp", 0)
            
            team_probs = teams[tid]["problems"]
            if p_id not in team_probs:
                team_probs[p_id] = {"solved": False, "tries": 0, "time": 0}
            
            prob = team_probs[p_id]
            
            if prob["solved"]:
                continue # Ignore runs after solved
                
            if status == "CORRECT" or status == "ACCEPTED":
                prob["solved"] = True
                
                timestamp_seconds = self._timestamp_to_seconds(timestamp)
                time_mins = int(timestamp_seconds // 60)
                
                prob["time_mins"] = time_mins
                teams[tid]["solved"] += 1
                
                if self._accumulates_penalty_in_seconds():
                    teams[tid]["penalty_seconds"] += timestamp_seconds + (prob["tries"] * self.penalty_time)
                else:
                    teams[tid]["penalty_mins"] += time_mins + (prob["tries"] * (self.penalty_time // 60))
            elif status not in ["PENDING", "COMPILING", "JUDGING", "CE", "COMPILATION_ERROR", "UKE"]:
                 prob["tries"] += 1
                 
        # convert to list
        standings = list(teams.values())
        
        # Calculate final accumulated penalty in minutes
        for t in standings:
            if self._accumulates_penalty_in_seconds():
                t["penalty"] = int(t.get("penalty_seconds", 0) // 60)
            else:
                t["penalty"] = t.get("penalty_mins", 0)
        
        # Filter official teams if needed, but normally keep all, just rank official for medals
        official_standings = [t for t in standings if t["is_official"]]
        unofficial_standings = [t for t in standings if not t["is_official"]]
        
        # Sort
        # Primary: solved (desc), Secondary: penalty (asc)
        def sort_key(t):
            return (-t["solved"], t["penalty"])
            
        official_standings.sort(key=sort_key)
        unofficial_standings.sort(key=sort_key)
        
        # Assign rank and medal for official teams
        medal_cfg_raw = self.config.get("medal", {})
        if isinstance(medal_cfg_raw, dict):
            medal_cfg = medal_cfg_raw.get("official", {})
            if not isinstance(medal_cfg, dict):
                medal_cfg = {}
        else:
            medal_cfg = {}
            
        gold_count = medal_cfg.get("gold", 0)
        silver_count = medal_cfg.get("silver", 0)
        bronze_count = medal_cfg.get("bronze", 0)
        
        for i, t in enumerate(official_standings):
            t["rank"] = i + 1
            if t["solved"] > 0:
                if gold_count == 0 and silver_count == 0 and bronze_count == 0:
                    t["medal"] = ""
                elif t["rank"] <= gold_count:
                    t["medal"] = "Gold"
                elif t["rank"] <= gold_count + silver_count:
                    t["medal"] = "Silver"
                elif t["rank"] <= gold_count + silver_count + bronze_count:
                    t["medal"] = "Bronze"
                else:
                    t["medal"] = "Honorable"
            else:
                t["medal"] = ""

        # Unofficial rank relative to official (commonly done) or separated
        for i, t in enumerate(unofficial_standings):
             t["rank"] = "*"
             t["medal"] = ""
             
        # Combine
        final_standings = official_standings + unofficial_standings
        final_standings.sort(key=sort_key) # overall sort
        
        # Build Standard JSON
        standing_objects = []
        for t in final_standings:
            problem_scores = {}
            for pid, pdata in t["problems"].items():
                try:
                    p_idx = int(pid)
                    label = self.problem_ids[p_idx] if p_idx < len(self.problem_ids) else str(pid)
                except (ValueError, TypeError):
                    label = str(pid)
                    
                problem_scores[label] = ProblemStatus(
                    solved=pdata.get("solved", False),
                    tries=pdata.get("tries", 0),
                    time_mins=pdata.get("time_mins", 0)
                )
                
            standing_objects.append(TeamStanding(
                team_name=t["team_name"],
                school=t["school"],
                member1=t.get("member1") or None,
                member2=t.get("member2") or None,
                member3=t.get("member3") or None,
                rank=t.get("rank") if isinstance(t.get("rank"), int) else 0,
                score=t.get("solved", 0),
                penalty=t.get("penalty", 0),
                is_official=t.get("is_official", True),
                  is_girl=t.get("is_girl"),
                medal=t.get("medal") or None,
                coach=t.get("coach") or None,
                problem_scores=problem_scores
            ))
            
        result = ContestStandings(
            contest_name=self.config.get("contest_name", "Unknown Contest"),
            problem_ids=[str(pid) for pid in self.problem_ids],
            standings=standing_objects
        )
        return result.to_dict()
        
    @staticmethod
    def export_csv(filename: str, standard_json: Dict[str, Any]):
        problem_ids = standard_json.get("problem_ids", [])
        standings = standard_json.get("standings", [])
        
        headers = ["Rank", "School Rank", "School", "Team Name", "Member1", "Member2", "Member3", "Coach", "Girl", "Official", "Solved", "Penalty", "Medal"] + problem_ids
        with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for t in standings:
                row = [
                    t.get("rank", ""),
                    t.get("school_rank", ""),
                    t.get("school", ""),
                    t.get("team_name", ""),
                    t.get("member1", ""),
                    t.get("member2", ""),
                    t.get("member3", ""),
                    t.get("coach", ""),
                    str(t.get("is_girl")) if t.get("is_girl") is not None else "",
                    "True" if t.get("is_official", True) else "False",
                    t.get("score", t.get("solved", 0)),
                    t.get("penalty", 0),
                    t.get("medal", "")
                ]
                # Problem columns
                # The dictionary key is now 'problem_scores'
                p_scores = t.get("problem_scores", {})
                for p_idx in range(len(problem_ids)):
                    prob_label = problem_ids[p_idx]
                    p_data = p_scores.get(str(prob_label)) or p_scores.get(str(p_idx))
                    
                    if not p_data:
                        row.append("")
                    else:
                        solved = p_data.get("solved", False)
                        tries = p_data.get("tries", 0)
                        time_mins = p_data.get("time_mins", 0)
                        
                        if solved:
                            if tries == 0:
                                row.append(f"+({time_mins})")
                            else:
                                row.append(f"+{tries}({time_mins})")
                        else:
                            if tries > 0:
                                row.append(f"-{tries}")
                            else:
                                row.append("")
                
                writer.writerow(row)


class XCPCIODataSource:
    BASE_URL = "https://board.xcpcio.com/data"

    def get_contest_list(self) -> Dict[str, Any]:
        """
        获取首页的比赛列表数据。
        数据结构通常为嵌套字典: { "icpc": { "2024": { "ecfinal": { "board_link": "/icpc/2024/ecfinal", "config": ... } } } }
        """
        list_url = f"{self.BASE_URL}/index/contest_list.json"
        
        req = urllib.request.Request(list_url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"Failed to fetch contest list: {e}")
            return {}

    def fetch_contest_data(self, contest_path: str) -> Dict[str, Any]:
        """
        传入比赛路径，如 "icpc/50th/ecfinal"
        获取 config.json, team.json, run.json 并合并
        """
        import os
        cache_dir = "data/raw/cache/xcpcio"
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{contest_path.replace('/', '_')}.json")
        
        if os.path.exists(cache_file):
            
            print(f"  [CACHE] Loading XCPCIO from {cache_file}")
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        config_url = f"{self.BASE_URL}/{contest_path}/config.json"
        team_url = f"{self.BASE_URL}/{contest_path}/team.json"
        run_url = f"{self.BASE_URL}/{contest_path}/run.json"
        
        data = {}
        data["config"] = fetch_json_with_retry(config_url)
        data["team"] = fetch_json_with_retry(team_url)
        data["run"] = fetch_json_with_retry(run_url)
        
        org_url = f"{self.BASE_URL}/{contest_path}/organizations.json"
        data["organizations"] = fetch_json_with_retry(org_url) or []
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
            
        return data

if __name__ == "__main__":
    spider = XCPCIODataSource()
    
    print("Fetching Contest List from XCPCIO...")
    contest_list = spider.get_contest_list()
    # 比赛数据是嵌套的，提取一条展示，例如 ICPC 50th ECFinal 或其他
    if contest_list:
        # 取出一个比赛示例展示结构
        print(f"Got {len(contest_list)} main categories (e.g. icpc, ccpc...)")
        
    print("\nFetching specific contest data (ICPC 50th ECFinal)...")
    data = spider.fetch_contest_data("icpc/50th/ecfinal")
    if data and data.get("config"):
        print("Config Title:", data["config"].get("contest_name", ""))
        print("Team count:", len(data.get("team", [])))
        print("Run count:", len(data.get("run", [])))
        
        print("Data fetched. Processing standings...")
        generator = ICPCStandingsGenerator(data)
        standard_json = generator.generate()
        
        # Save Standard JSON
        import os
        out_dir = "data/raw/json/xcpcio"
        os.makedirs(out_dir, exist_ok=True)
        
        json_file = f"{out_dir}/icpc_50th_ecfinal.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(standard_json, f, ensure_ascii=False, indent=2)
        print(f"Standard JSON successfully saved to {json_file}")
        
        # print top 5 official teams
        print("\nTop 5 Official Teams:")
        standings = standard_json.get("standings", [])
        official_t = [t for t in standings if t.get("is_official")]
        for i in range(min(5, len(official_t))):
            t = official_t[i]
            print(f"Rank {t['rank']}: {t['team_name']} ({t['school']}) - {t['solved']} solved, {t['penalty']} penalty - {t['medal']}")
