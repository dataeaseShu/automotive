"""
车型词库服务
- 从 data/vehicle_lexicon.json 加载别名 -> 标准名映射
- 支持模糊匹配（别名包含用户片段 或 用户片段包含别名）
"""
import json
import os
import re
from typing import Optional


_LEXICON_PATH = os.path.join(
    os.path.dirname(__file__), "../../data/vehicle_lexicon.json"
)


class VehicleLexicon:
    def __init__(self, path: str = _LEXICON_PATH):
        with open(os.path.abspath(path), "r", encoding="utf-8") as f:
            raw: dict[str, list[str]] = json.load(f)

        # alias_lower -> (standard_name, alias_original)
        self._alias_map: dict[str, tuple[str, str]] = {}
        for std_name, aliases in raw.items():
            # 标准名本身也可以匹配
            self._alias_map[std_name.lower()] = (std_name, std_name)
            for alias in aliases:
                self._alias_map[alias.lower()] = (std_name, alias)

        # 按长度降序排列，优先匹配更长的别名（避免"汉"比"比亚迪汉EV"先命中）
        self._sorted_aliases = sorted(self._alias_map.keys(), key=len, reverse=True)

        # 品牌级兜底映射：只提品牌未提具体车型时，映射到主推车型
        self._brand_defaults: list[tuple[re.Pattern[str], str]] = [
            (re.compile(r"比亚迪|BYD", re.IGNORECASE), "比亚迪汉EV"),
            (re.compile(r"特斯拉|Tesla", re.IGNORECASE), "特斯拉Model Y"),
            (re.compile(r"宝马|BMW", re.IGNORECASE), "宝马5系"),
            (re.compile(r"奔驰|Mercedes", re.IGNORECASE), "奔驰C级"),
            (re.compile(r"奥迪|Audi", re.IGNORECASE), "奥迪A4L"),
        ]

    def match(self, text: str) -> Optional[tuple[str, float, str]]:
        """
        在 text 中查找车型别名。
        返回 (标准名, 置信度, 原文片段) 或 None。
        置信度规则：
          - 完整别名命中 -> 0.95
          - 部分包含（text 含 alias 或 alias 含 text 中某词）-> 0.75
        """
        text_lower = text.lower()

        # 精确包含
        for alias_lower in self._sorted_aliases:
            if alias_lower in text_lower:
                std_name, orig_alias = self._alias_map[alias_lower]
                return std_name, 0.95, orig_alias

        # 品牌兜底命中
        for pattern, fallback in self._brand_defaults:
            m = pattern.search(text)
            if m:
                return fallback, 0.82, m.group(0)

        # 无命中
        return None

    def search(self, keyword: str) -> list[str]:
        """
        根据关键字搜索匹配的标准车型名列表（用于商品搜索候选）。
        """
        kw = keyword.lower()
        matched: set[str] = set()
        for alias_lower, (std_name, _) in self._alias_map.items():
            if kw in alias_lower or alias_lower in kw:
                matched.add(std_name)
        return list(matched)
