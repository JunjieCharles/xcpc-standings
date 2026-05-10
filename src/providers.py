import os
import json
import traceback
from typing import Dict, Any, Optional, Tuple

class BaseProvider:
    """Base class for data providers (XCPCIO, Rankland, Archive)."""
    source_name = "Base"

    def __init__(self, identifier: str, contest_name: str):
        self.identifier = identifier
        self.contest_name = contest_name

    def is_valid(self) -> bool:
        return bool(self.identifier)

    def fetch_raw(self) -> Any:
        raise NotImplementedError

    def parse_standard(self, raw_data: Any) -> Dict[str, Any]:
        raise NotImplementedError

    def get_standings(self) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


class JSONCacheProvider(BaseProvider):
    """Provider that caches raw fetched data as JSON and outputs standardize JSON."""

    def __init__(self, identifier: str, contest_name: str, cache_dir: str, json_dir: str):
        super().__init__(identifier, contest_name)
        self.cache_dir = cache_dir
        self.json_dir = json_dir

    def fetch_raw(self) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def parse_standard(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def _get_json_path(self) -> str:
        safe_id = self.identifier.replace('/', '_')
        return os.path.join(self.json_dir, f"{safe_id}.json")

    def get_standings(self) -> Optional[Dict[str, Any]]:
        if not self.is_valid():
            return None
            
        try:
            raw = self.fetch_raw()
        except Exception as e:
            print(f"  [ERROR] {self.source_name} fetch/load failed: {e}")
            import traceback
            traceback.print_exc()
            return None
            
        if not raw:
            return None

        try:
            std = self.parse_standard(raw)
            if not std:
                return None
            json_path = self._get_json_path()
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            with open(json_path, "w", encoding="utf-8") as f:
                import json
                json.dump(std, f, ensure_ascii=False, indent=2)
            return std
        except Exception as e:
            print(f"  [ERROR] {self.source_name} parsing failed: {e}")
            import traceback
            traceback.print_exc()
            return None

class XCPCIOProvider(JSONCacheProvider):
    source_name = "XCPCIO"

    def __init__(self, identifier: str, contest_name: str):
        super().__init__(identifier, contest_name, "data/raw/cache/xcpcio", "data/raw/json/xcpcio")

    def fetch_raw(self):
        from src.xcpcio_source import XCPCIODataSource
        return XCPCIODataSource().fetch_contest_data(self.identifier)

    def parse_standard(self, raw_data):
        from src.xcpcio_source import ICPCStandingsGenerator
        std = ICPCStandingsGenerator(raw_data).generate()
        if "problem_ids" not in std:
            std["problem_ids"] = []
        if "contest_name" not in std or not std["contest_name"]:
            std["contest_name"] = self.contest_name
        return std


class RanklandProvider(JSONCacheProvider):
    source_name = "Rankland"

    def __init__(self, identifier: str, contest_name: str, cat_year: Optional[Tuple[str, str]]):
        super().__init__(identifier, contest_name, "data/raw/cache/rankland", "data/raw/json/rankland")
        self.cat_year = cat_year

    def is_valid(self) -> bool:
        return bool(self.identifier and self.cat_year)

    def fetch_raw(self):
        from src.rankland_source import RanklandDataSource
        cat, year = self.cat_year
        return RanklandDataSource().fetch_contest_data(cat, year, self.identifier)

    def parse_standard(self, raw_data):
        from src.rankland_source import SRKStandingsGenerator
        std = SRKStandingsGenerator(raw_data).generate()
        if "contest_name" not in std or not std["contest_name"]:
            std["contest_name"] = self.contest_name
        return std


class ArchiveProvider(JSONCacheProvider):
    source_name = "Archive"

    def __init__(self, identifier: str, contest_name: str):
        super().__init__(identifier, contest_name, "data/raw/cache/archive", "data/raw/json/archive")
        self.csv_path = f"{self.cache_dir}/csv/{self.identifier}.csv"

    def is_valid(self) -> bool:
        return bool(self.identifier) and os.path.exists(self.csv_path)

    def fetch_raw(self):
        from src.archive_source import ArchiveDataSource
        print(f"  [{self.source_name}] Loading local CSV: {self.csv_path}")
        return ArchiveDataSource().fetch_contest_data(self.csv_path)

    def parse_standard(self, raw_data):
        from src.archive_source import ArchiveStandingsGenerator
        std = ArchiveStandingsGenerator(raw_data, self.contest_name).generate()
        if "contest_name" not in std or not std["contest_name"]:
            std["contest_name"] = self.contest_name
        return std