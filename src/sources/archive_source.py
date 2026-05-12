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
            import re
            for p in problem_ids:
                p_text = row.get(p, '').strip()
                if not p_text:
                    continue
                
                is_solved = False
                tries = 0
                time_mins = 0
                
                if p_text == '-':
                    tries = 0
                elif p_text.startswith('-'):
                    try:
                        tries = int(p_text[1:])
                    except ValueError:
                        pass
                else:
                    match = re.match(r'^\+?(\d*)\((\d+)\)$', p_text)
                    if match:
                        is_solved = True
                        tries_str = match.group(1)
                        tries = max(0, int(tries_str) - 1) if tries_str else 0
                        time_mins = int(match.group(2))
                    else:
                        match2 = re.match(r'^(\d+)$', p_text)
                        if match2:
                            is_solved = True
                            tries = 0
                            time_mins = int(match2.group(1))

                if is_solved or tries > 0:
                    problem_scores[p] = ProblemStatus(solved=is_solved, tries=tries, time_mins=time_mins)
            
            team_data.problem_scores = problem_scores
            standings.append(team_data)
            
        result = ContestStandings(
            contest_name=self.contest_name,
            problem_ids=problem_ids,
            standings=standings
        )
        return result.to_dict()
