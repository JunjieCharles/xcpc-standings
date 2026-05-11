import csv
from typing import Dict, Any, List
from src.models import ContestStandings, TeamStanding, ProblemStatus

class ArchiveDataSource:
    def fetch_contest_data(self, csv_path: str) -> List[Dict]:
        data = []
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        return data

class ArchiveStandingsGenerator:
    def __init__(self, data: List[Dict], contest_name: str = ""):
        self.data = data
        self.contest_name = contest_name

    def generate(self) -> Dict[str, Any]:
        standings = []
        problem_ids = []
        if self.data:
            # extract problem IDs from first row (keys that are single uppercase letters)
            first_row = self.data[0]
            for key in first_row.keys():
                if len(key) == 1 and key.isupper():
                    problem_ids.append(key)
        
        for row in self.data:
            try:
                solved = int(row.get('Solved', 0) or 0)
            except:
                solved = 0
                
            try:
                penalty = int(row.get('Penalty', 0) or 0)
            except:
                penalty = 0
                
            is_official = row.get('Unofficial', 'N') != 'Y' # Unofficial=Y means non-official. Or None/N means official
            if not row.get('Unofficial'):
                is_official = True
            
            is_girl_str = str(row.get('Girl', '')).strip().upper()
            is_girl = True if is_girl_str == 'Y' else (False if is_girl_str == 'N' else None)
            
            team_data = TeamStanding(
                school=row.get('School', '').strip(),
                team_name=row.get('Team', '').strip(),
                member1=row.get('Member1', '').strip() or None,
                member2=row.get('Member2', '').strip() or None,
                member3=row.get('Member3', '').strip() or None,
                coach=row.get('Coaches', '').strip() or None,
                score=solved,
                penalty=penalty,
                is_official=is_official,
                is_girl=is_girl,
                medal=row.get('Medal', '').strip() or None
            )
            
            # problem status is roughly the column
            problem_scores = {}
            for p in problem_ids:
                p_text = row.get(p, '').strip()
                if not p_text:
                    continue
                # Parsing standard XCPC string like "100" (time) or "+1" (unsolved) or "-2"
                # A bit complex because archive CSV might be: AC time (if solved), negative tries (if unsolved). 
                # Let's just do a naive check: if it's purely digits and > 0 without sign? 
                # Actually, standard format requires a proper conversion if we want to parse it into ProblemStatus.
                # For now just passing dummy ProblemStatus for archive since it wasn't standardized before, 
                # or we just skip this for archive as it wasn't fully processed anyway.
                # Here we just want the class structure.
                pass
                
            standings.append(team_data)
            
        result = ContestStandings(
            contest_name=self.contest_name,
            problem_ids=problem_ids,
            standings=standings
        )
        return result.to_dict()
