import unittest

from src.merge_standings import merge_standings
from src.models import TeamStanding, calculate_canonical_ranks
from src.sources.pta_source import PTAStandingsGenerator
from src.update_contests import chinese_number_to_int, get_category, merge_contests, parse_ordinal_from_name, parse_rankland_config


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
    def test_rankland_nested_provincial_group_is_preserved(self):
        config = {
            "root": {
                "children": [
                    {
                        "name": "省赛",
                        "children": [
                            {
                                "name": "北京市赛",
                                "children": [
                                    {"name": "2026-05-10 BJCPC", "path": "bjcpc2026"},
                                ],
                            },
                            {
                                "name": "浙江省赛",
                                "children": [
                                    {"name": "2026-04-25 ZJCPC", "path": "zjcpc23rd"},
                                ],
                            },
                        ],
                    }
                ]
            }
        }

        merged = merge_contests(parse_rankland_config(config))

        self.assertIn(("2026", "Other", "Provincial", "bjcpc"), merged)
        self.assertIn(("2026", "Other", "Provincial", "zjcpc"), merged)

    def test_rankland_leaf_date_does_not_override_parent_season_year(self):
        config = {
            "root": {
                "children": [
                    {
                        "name": "ICPC",
                        "path": "icpc",
                        "children": [
                            {
                                "name": "ICPC 2025",
                                "path": "icpc2025",
                                "children": [
                                    {"name": "2026-02-02 EC Final", "path": "icpc2025ecfinal"},
                                ],
                            }
                        ],
                    },
                    {
                        "name": "CCPC",
                        "path": "ccpc",
                        "children": [
                            {
                                "name": "CCPC 2025",
                                "path": "ccpc2025",
                                "children": [
                                    {"name": "2026-04-26 Final", "path": "ccpc2025final"},
                                ],
                            }
                        ],
                    },
                ]
            }
        }

        merged = merge_contests(parse_rankland_config(config))

        self.assertIn(("2025", "ICPC", "Final", "ecfinal"), merged)
        self.assertIn(("2025", "CCPC", "Final", "final"), merged)
        self.assertNotIn(("2026", "ICPC", "Final", "ecfinal"), merged)
        self.assertNotIn(("2026", "CCPC", "Final", "final"), merged)

    def test_chinese_ordinal_parser_handles_large_values(self):
        self.assertEqual(chinese_number_to_int("十"), 10)
        self.assertEqual(chinese_number_to_int("二十一"), 21)
        self.assertEqual(chinese_number_to_int("一百零三"), 103)
        self.assertEqual(parse_ordinal_from_name("World Finals (49th)"), 49)

    def test_world_finals_title_ordinal_prevents_adjacent_season_merge(self):
        merged = merge_contests([
            {
                "source": "rankland",
                "source_category": "icpc",
                "series": "ICPC",
                "year": 2024,
                "ordinal": 49,
                "date": "2024-09-19",
                "name": "World Finals (48th)",
                "id": "icpc48th2024worldfinals",
            },
            {
                "source": "xcpcio",
                "source_category": "icpc",
                "series": "ICPC",
                "year": 2024,
                "ordinal": 49,
                "date": "2025-09-04",
                "name": "World Finals",
                "id": "icpc/49th/world-finals",
            },
        ])

        self.assertIn(("2023", "ICPC", "Final", "worldfinals"), merged)
        self.assertIn(("2024", "ICPC", "Final", "worldfinals"), merged)
        self.assertEqual(merged[("2023", "ICPC", "Final", "worldfinals")]["rankland_id"], "icpc48th2024worldfinals")
        self.assertEqual(merged[("2024", "ICPC", "Final", "worldfinals")]["xcpcio_id"], "icpc/49th/world-finals")

    def test_regional_and_final_year_ordinal_do_not_use_date_year(self):
        merged = merge_contests([
            {
                "source": "rankland",
                "source_category": "icpc",
                "series": "ICPC",
                "year": "",
                "ordinal": "",
                "date": "2026-02-02",
                "name": "第50届 ICPC 亚洲区域赛 EC Final",
                "id": "ecfinal",
            },
            {
                "source": "rankland",
                "source_category": "ccpc",
                "series": "CCPC",
                "year": 2025,
                "ordinal": "",
                "date": "2026-04-26",
                "name": "Final",
                "id": "final",
            },
        ])

        icpc = merged[("2025", "ICPC", "Final", "ecfinal")]
        ccpc = merged[("2025", "CCPC", "Final", "final")]
        self.assertEqual(icpc["ordinal"], 50)
        self.assertEqual(ccpc["ordinal"], 11)

    def test_non_strict_categories_prefer_name_year_before_date_year(self):
        merged = merge_contests([
            {
                "source": "rankland",
                "source_category": "school",
                "series": "Other",
                "year": "",
                "ordinal": "",
                "date": "2026-05-01",
                "name": "2025 第二十一届校赛",
                "id": "school-21",
            },
        ])

        row = merged[("2025", "Other", "School", "school21")]
        self.assertEqual(row["ordinal"], 21)

    def test_source_category_is_used_before_generic_keyword_fallback(self):
        merged = merge_contests([
            {
                "source": "rankland",
                "source_category": "provincial",
                "series": "Other",
                "year": 2025,
                "ordinal": "",
                "date": "2025-04-01",
                "name": "Spring Contest",
                "id": "zhejiang",
            },
            {
                "source": "rankland",
                "source_category": "school",
                "series": "Other",
                "year": 2025,
                "ordinal": "",
                "date": "2025-05-01",
                "name": "Campus Contest",
                "id": "school-a",
            },
            {
                "source": "xcpcio",
                "source_category": "provincial-contest",
                "series": "Other",
                "year": 2025,
                "ordinal": "",
                "date": "2025-06-01",
                "name": "Standalone",
                "id": "standalone",
            },
        ])

        self.assertIn(("2025", "Other", "Provincial", "zhejiang"), merged)
        self.assertIn(("2025", "Other", "School", "schoola"), merged)
        self.assertIn(("2025", "Other", "Provincial", "standalone"), merged)

    def test_warmup_overrides_source_category_and_keywords_check_id_and_name(self):
        self.assertEqual(get_category("Other", "camp-warmup", "", "camp"), "Warmup")
        self.assertEqual(get_category("CCPC", "ccpc2025ladies", "", "ccpc"), "Girls")
        self.assertEqual(get_category("CCPC", "contest", "高职专场", "ccpc"), "Vocational")
        self.assertEqual(get_category("CCPC", "ccpc2025hv", "", "ccpc"), "Vocational")

    def test_pta_only_record_keeps_full_contest_name(self):
        full_name = "第十二届CCPC中国大学生程序设计竞赛福建省赛暨福建省大学生程序设计竞赛正式赛"
        merged = merge_contests([
            {
                "source": "pta",
                "series": "CCPC",
                "year": 2025,
                "ordinal": 12,
                "date": "2025-06-21",
                "name": full_name,
                "id": "1934898936967766016",
            },
        ])

        self.assertEqual(next(iter(merged.values()))["name"], full_name)

    def test_girls_and_vocational_empty_names_get_default_name_id(self):
        merged = merge_contests([
            {
                "source": "rankland",
                "series": "CCPC",
                "year": 2025,
                "ordinal": 11,
                "date": "2025-10-26",
                "name": "",
                "id": "ccpc2025ladies",
            },
            {
                "source": "archive",
                "series": "CCPC",
                "year": 2025,
                "ordinal": 11,
                "date": "2025-10-26",
                "name": "高职专场",
                "id": "11_CCPC_高职专场",
            },
        ])

        self.assertEqual(merged[("2025", "CCPC", "Girls", "girls")]["name"], "girls")
        self.assertEqual(merged[("2025", "CCPC", "Vocational", "vocational")]["name"], "vocational")

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