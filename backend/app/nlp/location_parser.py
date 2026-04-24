"""
投放地域解析器
支持：
  周边X公里  -> {"type": "radius", "km": X}
  同城/本市/本地  -> {"type": "city"}
  全国/全量   -> {"type": "nationwide"}
"""
import re
from typing import Optional

from app.models.slots import SlotField, LocationValue, LocationType
from app.nlp.cn_number import extract_number


_RADIUS_PATTERN = re.compile(
    r"(?:周边|附近|周围|半径)?\s*([零一二两三四五六七八九十百千\d]+)\s*(?:公里|km|KM)(?:内|范围内)?"
)
_CITY_KEYWORDS = re.compile(r"同城|本市|本地|本城|全城|市内|周边(?!\s*\d)")
_NATIONWIDE_KEYWORDS = re.compile(r"全国|全量|全域|不限地域|全部地区")


def parse_location(text: str) -> Optional[SlotField]:
    """
    从文本中抽取投放地域。
    - 后出现覆盖前出现由调用方（slots.merge）保证
    """
    # 按特异性从高到低匹配（radius > city > nationwide）
    m = _RADIUS_PATTERN.search(text)
    if m:
        v, _ = extract_number(m.group(1))
        km = int(v) if v else 5  # 解析失败给默认5公里
        loc = LocationValue(type=LocationType.RADIUS, km=km)
        return SlotField(value=loc.model_dump(), confidence=0.95, source=m.group(0))

    if _NATIONWIDE_KEYWORDS.search(text):
        loc = LocationValue(type=LocationType.NATIONWIDE)
        m3 = _NATIONWIDE_KEYWORDS.search(text)
        return SlotField(value=loc.model_dump(), confidence=0.9, source=m3.group(0))  # type: ignore[union-attr]

    if _CITY_KEYWORDS.search(text):
        loc = LocationValue(type=LocationType.CITY)
        m2 = _CITY_KEYWORDS.search(text)
        return SlotField(value=loc.model_dump(), confidence=0.9, source=m2.group(0))  # type: ignore[union-attr]

    return None
