import json
import os
from typing import List, Dict, Any

from src.models import ContestStandings, TeamStanding, ProblemStatus
from src.utils.http import fetch_json_with_retry

class PtaDataSource:
    BASE_URL = "https://pintia.cn/api/competitions"

    def get_contest_list(self) -> List[Dict[str, Any]]:
        """
        Fetch public contest list from PTA.
        """
        url = f"{self.BASE_URL}/public?page=0&limit=100"
        headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
        data = fetch_json_with_retry(url, headers=headers)
        if data and "competitions" in data:
            return data["competitions"]
        return []

    def fetch_contest_data(self, contest_id: str) -> Dict[str, Any]:
        """
        Fetch standings for a specific PTA contest.
        """
        cache_dir = "data/raw/cache/pta"
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{contest_id}.json")
        
        if os.path.exists(cache_file):
            print(f"  [CACHE] Loading PTA from {cache_file}")
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        url = f"{self.BASE_URL}/{contest_id}/xcpc-rankings/public"
        headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
        data = fetch_json_with_retry(url, headers=headers)
        if data:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            return data
            
        return {}

class PTAStandingsGenerator:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.xcpc_rankings = data.get("xcpcRankings", {})
        self.problem_info = self.xcpc_rankings.get("problemInfoByProblemSetProblemId", {})
        self.rankings = self.xcpc_rankings.get("rankings", [])
        
        sorted_probs = sorted(self.problem_info.items(), key=lambda x: x[1].get('label', ''))
        self.problem_ids = [k for k, v in sorted_probs]
        self.problem_labels = {k: v.get('label', str(i)) for i, (k, v) in enumerate(sorted_probs)}
        
    def generate(self) -> ContestStandings:
        final_standings = []
        for row in self.rankings:
            team_info = row.get("teamInfo", {})
            members = team_info.get("memberNames", [])
            m1 = members[0] if len(members) > 0 else ""
            m2 = members[1] if len(members) > 1 else ""
            m3 = members[2] if len(members) > 2 else ""
            
            is_official = not team_info.get("excluded", False)
            is_girl = team_info.get("girlMajor", False)
            
            team_standing = TeamStanding(
                rank=row.get("rank"),
                school=team_info.get("schoolName", ""),
                team_name=team_info.get("teamName", ""),
                member1=m1,
                member2=m2,
                member3=m3,
                coach="",
                is_official=is_official,
                is_girl=is_girl,
                score=row.get("solvedCount", 0),
                penalty=row.get("solvingTime", 0)
            )
            
            problem_details = row.get("detailsByProblemSetProblemId", {})
            for pid in self.problem_ids:
                prob = problem_details.get(pid, {})
                accept_time = prob.get("acceptTime", -1)
                is_solved = accept_time >= 0
                valid_submit_count = prob.get("validSubmitCount", 0)
                tries = max(0, valid_submit_count - 1) if is_solved else valid_submit_count
                time_mins = accept_time if is_solved else 0
                status = "accepted" if is_solved else ("failed" if tries > 0 else "unattempted")
                
                ps = ProblemStatus(
                    solved=is_solved,
                    tries=tries,
                    time_mins=time_mins
                )
                team_standing.problem_scores[self.problem_labels[pid]] = ps
                
            final_standings.append(team_standing)
            
        return ContestStandings(
            contest_name=self.data.get("competition", {}).get("name", ""),
            problem_ids=list(self.problem_labels.values()),
            standings=final_standings
        )
