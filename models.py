from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class ProblemStatus:
    solved: bool
    tries: int  # Number of failed attempts before AC (or total tries if rejected)
    time_mins: int  # Submission time in minutes for AC

    def to_dict(self) -> Dict[str, Any]:
        return {
            "solved": self.solved,
            "tries": self.tries,
            "time_mins": self.time_mins
        }
        
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            solved=bool(data.get("solved", False)),
            tries=int(data.get("tries", 0) or 0),
            time_mins=int(data.get("time_mins", 0) or 0)
        )

@dataclass
class TeamStanding:
    team_name: str
    school: str
    member1: Optional[str] = None
    member2: Optional[str] = None
    member3: Optional[str] = None
    rank: Optional[int] = None
    school_rank: Optional[int] = None
    score: int = 0
    penalty: int = 0
    is_official: bool = True
    is_girl: Optional[bool] = None
    medal: Optional[str] = None
    coach: Optional[str] = None
    _unofficial_rank: Optional[int] = None
    problem_scores: Dict[str, ProblemStatus] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_name": self.team_name,
            "school": self.school,
            "member1": self.member1,
            "member2": self.member2,
            "member3": self.member3,
            "rank": self.rank,
            "school_rank": self.school_rank,
            "_unofficial_rank": self._unofficial_rank,
            "score": self.score,
            "penalty": self.penalty,
            "is_official": self.is_official,
            "is_girl": self.is_girl,
            "medal": self.medal,
            "coach": self.coach,
            "problem_scores": {k: v.to_dict() for k, v in self.problem_scores.items()}
        }

    @classmethod
    def from_dict(cls, data: dict):
        probs = data.get("problem_scores", {})
        if not probs:
            probs = data.get("problems", {})
            
        return cls(
            team_name=data.get("team_name") or "",
            school=data.get("school") or "",
            member1=data.get("member1"),
            member2=data.get("member2"),
            member3=data.get("member3"),
            rank=data.get("rank"),
            school_rank=data.get("school_rank"),
            score=int(data.get("score", 0) if data.get("score") is not None else data.get("solved", 0) or 0),
            penalty=int(data.get("penalty", 0) or 0),
            is_official=data.get("is_official", True),
            is_girl=data.get("is_girl"),
            _unofficial_rank=data.get("_unofficial_rank"),
            medal=data.get("medal"),
            coach=data.get("coach"),
            problem_scores={k: ProblemStatus.from_dict(v) for k, v in probs.items() if isinstance(v, dict)}
        )
        
    def get_sort_key(self):
        ac_times = [v.time_mins for v in self.problem_scores.values() if v.solved]
        ac_times.sort(reverse=True)
        return (
            -self.score,
            self.penalty,
            ac_times,
            str(self.school or ""),
            str(self.team_name or ""),
            str(self.member1 or ""),
            str(self.member2 or ""),
            str(self.member3 or "")
        )

@dataclass
class ContestStandings:
    contest_name: str
    problem_ids: List[str]
    standings: List[TeamStanding]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contest_name": self.contest_name,
            "problem_ids": self.problem_ids,
            "standings": [t.to_dict() for t in self.standings]
        }
        
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            contest_name=data.get("contest_name", ""),
            problem_ids=data.get("problem_ids", []),
            standings=[TeamStanding.from_dict(t) for t in data.get("standings", [])]
        )

def calculate_canonical_ranks(standings: List[TeamStanding]):
    standings.sort(key=lambda t: t.get_sort_key())
    
    official_rank = 1
    unofficial_rank = 1
    school_rank_counter = 1
    seen_schools = set()
    
    for t in standings:
        if not t.is_official:
            t.rank = None
            t.school_rank = None
            # Store unofficial rank for merging keys
            t._unofficial_rank = unofficial_rank
            unofficial_rank += 1
            continue
            
        t.rank = official_rank
        t._unofficial_rank = None
        official_rank += 1
        
        norm_school = t.school.strip().lower()
        if norm_school and norm_school not in seen_schools:
            t.school_rank = school_rank_counter
            school_rank_counter += 1
            seen_schools.add(norm_school)
        else:
            t.school_rank = None
