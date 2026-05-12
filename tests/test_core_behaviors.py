import unittest

from src.merge_standings import merge_standings
from src.models import TeamStanding, calculate_canonical_ranks
from src.sources.pta_source import PTAStandingsGenerator


def standing(team_name, school, score, penalty, members=None, problem_scores=None):
    members = members or []
    return {
        "team_name": team_name,
        "school": school,
        "member1": members[0] if len(members) > 0 else None,
        "member2": members[1] if len(members) > 1 else None,
        "member3": members[2] if len(members) > 2 else None,
        "score": score,
        "penalty": penalty,
        "is_official": True,
        "problem_scores": problem_scores or {},
    }


def problem(solved, tries=0, time_mins=0):
    return {"solved": solved, "tries": tries, "time_mins": time_mins}


class CoreBehaviorTests(unittest.TestCase):
    def test_canonical_sort_uses_team_name_before_school(self):
        teams = [
            TeamStanding(team_name="b-team", school="A School"),
            TeamStanding(team_name="a-team", school="Z School"),
        ]

        calculate_canonical_ranks(teams)

        self.assertEqual([team.team_name for team in teams], ["a-team", "b-team"])

    def test_merge_matches_strictly_by_rank_not_member_fallback(self):
        base = {
            "contest_name": "test",
            "problem_ids": [],
            "standings": [
                standing("Alpha", "School A", 2, 10, ["Alice"]),
                standing("Beta", "School B", 1, 10, ["Bob"]),
            ],
        }
        complement = {
            "contest_name": "test",
            "problem_ids": [],
            "standings": [
                standing("Gamma", "School C", 2, 10, ["Bob"]),
                standing("Beta", "School B", 1, 10, ["Bob"]),
            ],
        }

        _merged, warnings = merge_standings(base, complement, contest_name="test")

        self.assertTrue(any(w["Rank"] == "1" and w["Field"] == "team_name" for w in warnings))
        self.assertFalse(any(w["Rank"] == "2" and w["Field"] == "team_name" for w in warnings))

    def test_team_name_marker_difference_is_not_a_conflict(self):
        base = {
            "contest_name": "test",
            "problem_ids": [],
            "standings": [standing("*Daida", "Peking University", 1, 10)],
        }
        complement = {
            "contest_name": "test",
            "problem_ids": [],
            "standings": [standing("Daida", "Peking University", 1, 10)],
        }

        merged, warnings = merge_standings(base, complement, contest_name="test")

        self.assertEqual(warnings, [])
        self.assertEqual(merged["standings"][0]["team_name"], "Daida")

    def test_pta_valid_submit_count_excludes_accept_from_tries(self):
        raw = {
            "competition": {"name": "test"},
            "xcpcRankings": {
                "problemInfoByProblemSetProblemId": {
                    "p1": {"label": "A"},
                    "p2": {"label": "B"},
                },
                "rankings": [
                    {
                        "rank": 1,
                        "teamInfo": {
                            "schoolName": "School",
                            "teamName": "Team",
                            "memberNames": [],
                        },
                        "solvedCount": 1,
                        "solvingTime": 35,
                        "detailsByProblemSetProblemId": {
                            "p1": {"acceptTime": 35, "validSubmitCount": 2},
                            "p2": {"acceptTime": -1, "validSubmitCount": 3},
                        },
                    }
                ],
            },
        }

        standings = PTAStandingsGenerator(raw).generate()
        team = standings.standings[0]

        self.assertEqual(team.problem_scores["A"].tries, 1)
        self.assertEqual(team.problem_scores["B"].tries, 3)

    def test_problem_time_conflict_is_reported(self):
        base = {
            "contest_name": "test",
            "problem_ids": ["A"],
            "standings": [standing("Team", "School", 1, 30, problem_scores={"A": problem(True, 0, 30)})],
        }
        complement = {
            "contest_name": "test",
            "problem_ids": ["A"],
            "standings": [standing("Team", "School", 1, 30, problem_scores={"A": problem(True, 0, 31)})],
        }

        merged, warnings = merge_standings(base, complement, contest_name="test")

        self.assertTrue(any(w["Field"] == "problem:A:time_mins" for w in warnings))
        self.assertEqual(merged["standings"][0]["problem_scores"]["A"]["time_mins"], 30)

    def test_problem_resolution_can_apply_full_cell_value(self):
        base = {
            "contest_name": "test",
            "problem_ids": ["A"],
            "standings": [standing("Team", "School", 1, 30, problem_scores={"A": problem(True, 0, 30)})],
        }
        complement = {
            "contest_name": "test",
            "problem_ids": ["A"],
            "standings": [standing("Team", "School", 1, 30, problem_scores={"A": problem(True, 1, 31)})],
        }
        resolutions = {("test", "1", "problem:A:time_mins"): "+1(31)"}

        merged, warnings = merge_standings(base, complement, contest_name="test", resolutions=resolutions)
        status = merged["standings"][0]["problem_scores"]["A"]

        self.assertEqual(status, {"solved": True, "tries": 1, "time_mins": 31})
        self.assertTrue(any(w["Field"] == "problem:A:time_mins" and w["Resolution"] == "+1(31)" for w in warnings))

    def test_problem_solved_conflict_prefers_ac_without_resolution(self):
        base = {
            "contest_name": "test",
            "problem_ids": ["A"],
            "standings": [standing("Team", "School", 1, 50, problem_scores={"A": problem(False, 2, 0)})],
        }
        complement = {
            "contest_name": "test",
            "problem_ids": ["A"],
            "standings": [standing("Team", "School", 1, 50, problem_scores={"A": problem(True, 1, 50)})],
        }

        merged, warnings = merge_standings(base, complement, contest_name="test")

        self.assertTrue(any(w["Field"] == "problem:A:solved" for w in warnings))
        self.assertEqual(merged["standings"][0]["problem_scores"]["A"], {"solved": True, "tries": 1, "time_mins": 50})

    def test_unsolved_problem_tries_conflict_is_reported(self):
        base = {
            "contest_name": "test",
            "problem_ids": ["A"],
            "standings": [standing("Team", "School", 0, 0, problem_scores={"A": problem(False, 2, 0)})],
        }
        complement = {
            "contest_name": "test",
            "problem_ids": ["A"],
            "standings": [standing("Team", "School", 0, 0, problem_scores={"A": problem(False, 3, 0)})],
        }

        _merged, warnings = merge_standings(base, complement, contest_name="test")

        self.assertTrue(any(w["Field"] == "problem:A:tries" for w in warnings))

    def test_complement_problem_ids_are_appended(self):
        base = {
            "contest_name": "test",
            "problem_ids": ["A"],
            "standings": [standing("Team", "School", 1, 10, problem_scores={"A": problem(True, 0, 10)})],
        }
        complement = {
            "contest_name": "test",
            "problem_ids": ["A", "B"],
            "standings": [standing("Team", "School", 1, 10, problem_scores={"B": problem(False, 1, 0)})],
        }

        merged, _warnings = merge_standings(base, complement, contest_name="test")

        self.assertEqual(merged["problem_ids"], ["A", "B"])
        self.assertEqual(merged["standings"][0]["problem_scores"]["B"], {"solved": False, "tries": 1, "time_mins": 0})


if __name__ == "__main__":
    unittest.main()