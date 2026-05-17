import os
import csv
import json
import tempfile
import unittest

from src.merge_standings import merge_pdf_roster, merge_standings
from src.models import TeamStanding, calculate_canonical_ranks
from src.rating.calculator import build_contest_schedule, build_contest_tag, collect_member_userrank, collect_school_userrank
from src.sources.pdf_source import PDFDataSource, find_pdf_identifier
from src.sources.pta_source import PTAStandingsGenerator
from src.update_contests import chinese_number_to_int, get_category, merge_contests, parse_ordinal_from_name, parse_rankland_config
from src.utils.years import contest_matches_year_arg, normalize_year_arg, years_in_arg


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
    def test_rating_counts_zero_solved_teams_with_submissions(self):
        headers = [
            "Rank", "School Rank", "School", "Team Name", "Member1", "Member2", "Member3",
            "Coach", "Girl", "Official", "Solved", "Penalty", "Medal", "A", "B"
        ]
        rows = [
            [1, 1, "提交大学", "ZeroSolvedSubmitted", "甲", "乙", "丙", "", "", "True", 0, 0, "", "-1", ""],
            [2, 2, "空交大学", "ZeroSolvedNoSubmit", "丁", "戊", "己", "", "", "True", 0, 0, "", "", ""],
            [3, 3, "通过大学", "Solved", "庚", "辛", "壬", "", "", "True", 1, 10, "", "+(10)", ""],
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "rating.csv")
            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, lineterminator="\n")
                writer.writerow(headers)
                writer.writerows(rows)

            member_userrank = collect_member_userrank(path)
            school_userrank = collect_school_userrank(path)

        self.assertEqual(member_userrank[("提交大学", "甲")], 1)
        self.assertEqual(member_userrank[("提交大学", "乙")], 1)
        self.assertEqual(member_userrank[("提交大学", "丙")], 1)
        self.assertEqual(member_userrank[("通过大学", "庚")], 3)
        self.assertNotIn(("空交大学", "丁"), member_userrank)

        self.assertEqual(school_userrank["提交大学"], 1)
        self.assertEqual(school_userrank["通过大学"], 3)
        self.assertNotIn("空交大学", school_userrank)

    def test_json_rating_counts_zero_solved_teams_with_submissions(self):
        standings = {
            "contest_name": "rating fixture",
            "problem_ids": ["A", "B"],
            "standings": [
                {
                    "team_name": "ZeroSolvedSubmitted",
                    "school": "提交大学",
                    "member1": "甲",
                    "member2": "乙",
                    "member3": "丙",
                    "rank": 1,
                    "school_rank": 1,
                    "score": 0,
                    "penalty": 0,
                    "is_official": True,
                    "problem_scores": {"A": {"solved": False, "tries": 1, "time_mins": 0}},
                },
                {
                    "team_name": "ZeroSolvedNoSubmit",
                    "school": "空交大学",
                    "member1": "丁",
                    "member2": "戊",
                    "member3": "己",
                    "rank": 2,
                    "school_rank": 2,
                    "score": 0,
                    "penalty": 0,
                    "is_official": True,
                    "problem_scores": {},
                },
                {
                    "team_name": "Solved",
                    "school": "通过大学",
                    "member1": "庚",
                    "member2": "辛",
                    "member3": "壬",
                    "rank": 3,
                    "school_rank": 3,
                    "score": 1,
                    "penalty": 10,
                    "is_official": True,
                    "problem_scores": {"A": {"solved": True, "tries": 0, "time_mins": 10}},
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "rating.json")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(standings, f, ensure_ascii=False)

            member_userrank = collect_member_userrank(path)
            school_userrank = collect_school_userrank(path)

        self.assertEqual(member_userrank[("提交大学", "甲")], 1)
        self.assertEqual(member_userrank[("提交大学", "乙")], 1)
        self.assertEqual(member_userrank[("提交大学", "丙")], 1)
        self.assertEqual(member_userrank[("通过大学", "庚")], 3)
        self.assertNotIn(("空交大学", "丁"), member_userrank)

        self.assertEqual(school_userrank["提交大学"], 1)
        self.assertEqual(school_userrank["通过大学"], 3)
        self.assertNotIn("空交大学", school_userrank)

    def test_short_year_arguments_are_expanded(self):
        self.assertEqual(normalize_year_arg("25"), "2025")
        self.assertEqual(normalize_year_arg("25-26"), "2025-2026")
        self.assertEqual(normalize_year_arg("2025-26"), "2025-2026")
        self.assertEqual(years_in_arg("25-26"), {"2025", "2026"})

    def test_half_year_arguments_are_expanded_and_match_dates(self):
        self.assertEqual(normalize_year_arg("25下半年-26上半年"), "2025H2-2026H1")
        self.assertEqual(normalize_year_arg("25H2-26H1"), "2025H2-2026H1")
        self.assertEqual(normalize_year_arg("25下-26上"), "2025H2-2026H1")
        self.assertTrue(contest_matches_year_arg({"year": "2025", "date": "2025-11-01"}, "25下半年-26上半年"))
        self.assertTrue(contest_matches_year_arg({"year": "2026", "date": "2026-05-01"}, "25下半年-26上半年"))
        self.assertFalse(contest_matches_year_arg({"year": "2025", "date": "2025-05-01"}, "25下半年-26上半年"))
        self.assertFalse(contest_matches_year_arg({"year": "2026", "date": "2026-07-01"}, "25下半年-26上半年"))

    def test_invalid_year_range_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_year_arg("26-25")

    def test_srni_is_excluded_from_rating_schedule(self):
        schedule = build_contest_schedule("member", "25下半年-26上半年", combine_same_day=False)
        self.assertFalse(any("srni" in file.lower() for day in schedule for file in day["files"]))

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

        self.assertIn(("2026", "Other", "Provincial", "beijing", "2026-05-10"), merged)
        self.assertIn(("2026", "Other", "Provincial", "zhejiang", "2026-04-25"), merged)

    def test_recent_provincial_names_prefer_chinese_location_keyword(self):
        merged = merge_contests([
            {
                "source": "pta",
                "series": "Other",
                "year": 2025,
                "ordinal": 19,
                "date": "2025-11-30",
                "name": "2025年绍兴市第十九届大学生计算机技能竞赛（程序设计）",
                "id": "1992863483790479360",
            },
            {
                "source": "rankland",
                "source_category": "provincial",
                "source_context": "省赛 内蒙古自治区赛",
                "series": "Other",
                "year": 2025,
                "ordinal": 18,
                "date": "2025-06-22",
                "name": "NMCPC",
                "id": "nmcpc18th",
            },
            {
                "source": "rankland",
                "source_category": "provincial",
                "source_context": "省赛 四川省赛",
                "series": "Other",
                "year": 2025,
                "ordinal": 17,
                "date": "2025-06-08",
                "name": "第十七届",
                "id": "sccpc17th",
            },
            {
                "source": "rankland",
                "source_category": "provincial",
                "source_context": "省赛 东北地区赛",
                "series": "Other",
                "year": 2025,
                "ordinal": 19,
                "date": "2025-05-25",
                "name": "第十九届",
                "id": "northeastcpc19th",
            },
        ])

        self.assertIn(("2025", "Other", "Provincial", "shaoxing", "2025-11-30"), merged)
        self.assertIn(("2025", "Other", "Provincial", "neimenggu", "2025-06-22"), merged)
        self.assertIn(("2025", "Other", "Provincial", "sichuan", "2025-06-08"), merged)
        self.assertIn(("2025", "Other", "Provincial", "northeast", "2025-05-25"), merged)

    def test_recent_provincial_same_location_variants_use_date_not_name_suffix(self):
        merged = merge_contests([
            {
                "source": "rankland",
                "source_category": "provincial",
                "source_context": "省赛 河南省赛",
                "series": "Other",
                "year": 2025,
                "ordinal": 16,
                "date": "2025-05-11",
                "name": "第十六届 ICPC",
                "id": "haicpc16th",
            },
            {
                "source": "rankland",
                "source_category": "provincial",
                "source_context": "省赛 河南 省赛",
                "series": "Other",
                "year": 2025,
                "ordinal": 7,
                "date": "2025-06-02",
                "name": "第七届 CCPC",
                "id": "haccpc7th",
            },
        ])

        self.assertIn(("2025", "Other", "Provincial", "henan", "2025-05-11"), merged)
        self.assertIn(("2025", "Other", "Provincial", "henan", "2025-06-02"), merged)
        self.assertEqual(merged[("2025", "Other", "Provincial", "henan", "2025-05-11")]["name"], "henan")
        self.assertEqual(merged[("2025", "Other", "Provincial", "henan", "2025-06-02")]["name"], "henan")

    def test_older_provincial_short_names_are_not_rewritten(self):
        merged = merge_contests([
            {
                "source": "rankland",
                "source_category": "provincial",
                "source_context": "省赛 浙江省赛",
                "series": "Other",
                "year": 2024,
                "ordinal": 21,
                "date": "2024-04-13",
                "name": "ZJCPC",
                "id": "zjcpc21st",
            },
        ])

        self.assertIn(("2024", "Other", "Provincial", "zjcpc"), merged)

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

        self.assertIn(("2025", "Other", "Provincial", "zhejiang", "2025-04-01"), merged)
        self.assertIn(("2025", "Other", "School", "schoola"), merged)
        self.assertIn(("2025", "Other", "Provincial", "standalone", "2025-06-01"), merged)

    def test_warmup_overrides_source_category_and_keywords_check_id_and_name(self):
        self.assertEqual(get_category("Other", "camp-warmup", "", "camp"), "Warmup")
        self.assertEqual(get_category("CCPC", "ccpc2025ladies", "", "ccpc"), "Girls")
        self.assertEqual(get_category("CCPC", "contest", "高职专场", "ccpc"), "Vocational")
        self.assertEqual(get_category("CCPC", "ccpc2025hv", "", "ccpc"), "Vocational")

    def test_pta_only_unrequested_record_keeps_full_contest_name(self):
        full_name = "2025年高校程序设计能力提升活动"
        merged = merge_contests([
            {
                "source": "pta",
                "series": "Other",
                "year": 2025,
                "ordinal": "",
                "date": "2025-12-01",
                "name": full_name,
                "id": "pta-regular",
            },
        ])

        self.assertEqual(next(iter(merged.values()))["name"], full_name)

    def test_pta_preliminary_uses_english_name_without_preliminary_suffix(self):
        full_name = "2025 年（第二十二届）广东省大学生程序设计竞赛 暨“汇丰科技（中国）”中国大学生程序设计竞赛邀请赛（广东）预赛 - 正式赛"
        merged = merge_contests([
            {
                "source": "pta",
                "series": "CCPC",
                "year": 2025,
                "ordinal": 22,
                "date": "2025-06-02",
                "name": full_name,
                "id": "1925946171279802368",
            },
        ])

        self.assertIn(("2025", "CCPC", "Preliminary", "guangdong"), merged)
        self.assertEqual(next(iter(merged.values()))["name"], "guangdong")

    def test_northeastern_and_northeast_invitational_merge(self):
        merged = merge_contests([
            {
                "source": "xcpcio",
                "source_category": "ccpc",
                "series": "CCPC",
                "year": 2025,
                "ordinal": 11,
                "date": "2025-05-25",
                "name": "Northeastern Invitational",
                "id": "ccpc/11th/northeastern",
            },
            {
                "source": "rankland",
                "source_category": "ccpc",
                "series": "CCPC",
                "year": 2025,
                "ordinal": 11,
                "date": "2025-05-25",
                "name": "Northeast Invitational",
                "id": "ccpc2025invitational-northeast",
            },
            {
                "source": "rankland",
                "source_category": "provincial",
                "source_context": "省赛 东北地区赛",
                "series": "Other",
                "year": 2025,
                "ordinal": 19,
                "date": "2025-05-25",
                "name": "第十九届",
                "id": "northeastcpc19th",
            },
        ])

        invite = merged[("2025", "CCPC", "Invitational", "northeast")]
        provincial = merged[("2025", "Other", "Provincial", "northeast", "2025-05-25")]
        self.assertEqual(invite["xcpcio_id"], "ccpc/11th/northeastern")
        self.assertEqual(invite["rankland_id"], "ccpc2025invitational-northeast")
        self.assertEqual(provincial["rankland_id"], "northeastcpc19th")

    def test_reverse_translation_handles_numbered_online_names(self):
        tag = build_contest_tag({"series": "ICPC", "name": "online1", "sub": "Online"}, {"online": "网络赛"})

        self.assertEqual(tag, "ICPC网络赛1")

    def test_invitational_tag_uses_invitation_suffix(self):
        tag = build_contest_tag({"series": "ICPC", "name": "xian", "sub": "Invitational"}, {"xian": "西安"})

        self.assertEqual(tag, "ICPC西安邀请赛")

    def test_pdf_identifier_matches_xian_invitational(self):
        identifier = find_pdf_identifier({"series": "ICPC", "year": "2026", "category": "Invitational", "name": "xian"})

        self.assertEqual(identifier, "2026年ICPC全国邀请赛（陕西）参赛手册.pdf")

    def test_pdf_roster_merge_fills_members_by_school_and_team(self):
        base = {
            "contest_name": "test",
            "problem_ids": [],
            "standings": [standing("南蛮入侵", "阿坝师范学院", 4, 697)],
        }
        pdf = {
            "contest_name": "test",
            "problem_ids": [],
            "standings": [standing("南蛮入侵", "阿坝师范学院", 0, 0, ["刘付焮", "冯浩", "唐杰"])],
        }

        merged, matched, unmatched = merge_pdf_roster(base, pdf)

        self.assertEqual(matched, 1)
        self.assertEqual(unmatched, 0)
        self.assertEqual(merged["standings"][0]["member1"], "刘付焮")
        self.assertEqual(merged["standings"][0]["member2"], "冯浩")
        self.assertEqual(merged["standings"][0]["member3"], "唐杰")

    @unittest.skipUnless(os.path.exists("data/raw/cache/pdf/2026年ICPC全国邀请赛（陕西）参赛手册.pdf"), "PDF fixture not available")
    def test_xian_invitational_pdf_roster_parser(self):
        data = PDFDataSource().fetch_contest_data("2026年ICPC全国邀请赛（陕西）参赛手册.pdf")

        self.assertGreaterEqual(len(data["teams"]), 300)
        self.assertEqual(data["teams"][0]["school"], "阿坝师范学院")
        self.assertEqual(data["teams"][0]["team_name"], "南蛮入侵")
        self.assertEqual(data["teams"][0]["members"], ["刘付焮", "冯浩", "唐杰"])

    def test_online_qualification_rounds_merge_as_online_numbers(self):
        merged = merge_contests([
            {
                "source": "xcpcio",
                "source_category": "icpc",
                "series": "ICPC",
                "year": 2025,
                "ordinal": 50,
                "date": "2025-09-07",
                "name": "Online Qualification 1",
                "id": "icpc/50th/online-qualification-1",
            },
            {
                "source": "pta",
                "series": "ICPC",
                "year": 2025,
                "ordinal": 50,
                "date": "2025-09-07",
                "name": "2025 ICPC Asia EC网络预选赛（第一场）",
                "id": "1962439589388427264",
            },
        ])

        row = merged[("2025", "ICPC", "Online", "online1")]
        self.assertEqual(row["xcpcio_id"], "icpc/50th/online-qualification-1")
        self.assertEqual(row["pta_id"], "1962439589388427264")

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

    def test_vocational_name_is_always_vocational(self):
        merged = merge_contests([
            {
                "source": "pta",
                "series": "CCPC",
                "year": 2025,
                "ordinal": 11,
                "date": "2025-10-26",
                "name": "第十一届中国大学生程序设计竞赛（高职专场）",
                "id": "1978768358019448832",
            },
        ])

        self.assertIn(("2025", "CCPC", "Vocational", "vocational"), merged)
        self.assertEqual(next(iter(merged.values()))["name"], "vocational")

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
