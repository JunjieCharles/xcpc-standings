import json
import os
from typing import Dict, Set

from src.utils.text import normalize_text

_school_mapping: Dict[str, str] = {}
_display_school_mapping: Dict[str, str] = {}
_ambiguous_school_mappings: Set[str] = set()
_initialized: bool = False

def init_school_mapping(json_path: str = "data/config/school.json") -> None:
    global _school_mapping, _display_school_mapping, _ambiguous_school_mappings, _initialized
    if _initialized:
        return
    
    if not os.path.exists(json_path):
        _initialized = True
        return

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        alias_to_zhs: Dict[str, Set[str]] = {}

        for zh, aliases in data.items():
            norm_zh = normalize_text(zh)
            _display_school_mapping[norm_zh] = zh
            
            if norm_zh not in alias_to_zhs:
                alias_to_zhs[norm_zh] = set()
            alias_to_zhs[norm_zh].add(zh)
            
            for alias in aliases:
                alt = str(alias).strip()
                if alt:
                    norm_alt = normalize_text(alt)
                    if norm_alt:
                        if norm_alt not in alias_to_zhs:
                            alias_to_zhs[norm_alt] = set()
                        alias_to_zhs[norm_alt].add(zh)
                        
        for norm_name, zhs in alias_to_zhs.items():
            if len(zhs) > 1:
                _ambiguous_school_mappings.add(norm_name)
            else:
                zh = list(zhs)[0]
                _school_mapping[norm_name] = zh
                _display_school_mapping[norm_name] = zh
                
        _initialized = True
    except Exception as e:
        if isinstance(e, AssertionError):
            raise
        pass

def get_canonical_school_name(school: str) -> str:
    """Return canonical display name if available, else original."""
    init_school_mapping()
    norm = normalize_text(school)
    return _display_school_mapping.get(norm, school)

def normalize_school_name(school: str) -> str:
    """Return normalized short mapping if available, else normalized form."""
    init_school_mapping()
    norm_school = normalize_text(school)
    return _school_mapping.get(norm_school, norm_school)
