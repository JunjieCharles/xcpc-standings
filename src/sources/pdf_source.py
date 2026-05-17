import os
import re
from typing import Any, Dict, List, Optional

from src.models import ContestStandings, TeamStanding


PDF_SOURCE_SPECS = [
    {
        "series": "ICPC",
        "year": "2026",
        "category": "Invitational",
        "name": "xian",
        "file": "2026年ICPC全国邀请赛（陕西）参赛手册.pdf",
        "parser": "icpc_2026_xian_invitational_roster",
    }
]


def find_pdf_identifier(row: Dict[str, Any]) -> str:
    for spec in PDF_SOURCE_SPECS:
        if all(str(row.get(key, "")) == spec[key] for key in ("series", "year", "category", "name")):
            path = os.path.join("data", "raw", "cache", "pdf", spec["file"])
            if os.path.exists(path):
                return spec["file"]
    return ""


def get_pdf_spec(identifier: str) -> Optional[Dict[str, str]]:
    basename = os.path.basename(identifier)
    for spec in PDF_SOURCE_SPECS:
        if spec["file"] == basename:
            return spec
    return None


def clean_cell(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


class PDFDataSource:
    def fetch_contest_data(self, identifier: str) -> Dict[str, Any]:
        spec = get_pdf_spec(identifier)
        if not spec:
            raise ValueError(f"No PDF parser registered for {identifier}")

        pdf_path = os.path.join("data", "raw", "cache", "pdf", spec["file"])
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(pdf_path)

        if spec["parser"] == "icpc_2026_xian_invitational_roster":
            return self.parse_icpc_2026_xian_invitational_roster(pdf_path, spec)

        raise ValueError(f"Unsupported PDF parser: {spec['parser']}")

    def parse_icpc_2026_xian_invitational_roster(self, pdf_path: str, spec: Dict[str, str]) -> Dict[str, Any]:
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError("pdfplumber is required to parse PDF roster sources") from exc

        teams = []
        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                for table in page.extract_tables() or []:
                    if not self.is_xian_roster_table(table):
                        continue
                    page_added = False
                    for row in table[1:]:
                        parsed = self.parse_xian_roster_row(row)
                        if parsed:
                            teams.append(parsed)
                            page_added = True
                    if page_added:
                        pages.append(page_index)

        return {
            "contest_name": f"{spec['series']}_{spec['year']}_{spec['category']}_{spec['name']}",
            "source_file": os.path.basename(pdf_path),
            "pages": pages,
            "teams": teams,
        }

    def is_xian_roster_table(self, table: List[List[Any]]) -> bool:
        if not table:
            return False
        header = " ".join(clean_cell(cell) for cell in table[0])
        return "编号" in header and "学校" in header and "队伍名称" in header and "队员" in header

    def parse_xian_roster_row(self, row: List[Any]) -> Optional[Dict[str, Any]]:
        if len(row) < 14 or not clean_cell(row[0]).isdigit():
            return None

        school = clean_cell(row[3])
        team_name = clean_cell(row[8]) or clean_cell(row[6])
        members = [clean_cell(row[index]) for index in (10, 12, 13) if index < len(row) and clean_cell(row[index])]

        if not school or not team_name:
            return None

        return {
            "no": int(clean_cell(row[0])),
            "school": school,
            "team_name": team_name,
            "english_team_name": clean_cell(row[6]),
            "members": members[:3],
            "venue": clean_cell(row[15]) if len(row) > 15 else "",
            "seat": clean_cell(row[18]) if len(row) > 18 else "",
        }


class PDFStandingsGenerator:
    def __init__(self, data: Dict[str, Any], contest_name: str = ""):
        self.data = data
        self.contest_name = contest_name or data.get("contest_name", "")

    def generate(self) -> Dict[str, Any]:
        standings = []
        for item in self.data.get("teams", []):
            members = item.get("members", [])
            standings.append(TeamStanding(
                school=item.get("school", ""),
                team_name=item.get("team_name", ""),
                member1=members[0] if len(members) > 0 else None,
                member2=members[1] if len(members) > 1 else None,
                member3=members[2] if len(members) > 2 else None,
                score=0,
                penalty=0,
                is_official=True,
            ))

        return ContestStandings(
            contest_name=self.contest_name,
            problem_ids=[],
            standings=standings,
        ).to_dict()