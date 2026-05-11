import re

import pypinyin


def normalize_text(s: str) -> str:
    """Normalize text by removing non-alphanumeric/Chinese characters and lowercasing."""
    s = str(s or "")
    s = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', s)
    s = s.lower()
    return s


def contains_chinese(text: str) -> bool:
    """Check if the string contains any Chinese characters."""
    if not text:
        return False
    return bool(re.search(r'[\u4e00-\u9fa5]', str(text)))


def get_name_pinyin_set(name: str) -> set:
    """Convert a name to a set of pinyin strings or normalized strings for matching."""
    if not name:
        return set()
    py_list = pypinyin.pinyin(name, style=pypinyin.NORMAL)
    flat = [item[0].lower() for item in py_list]
    parts = "".join(flat).split()
    if not parts:
        parts = [normalize_text(name)]
    return set(parts)
