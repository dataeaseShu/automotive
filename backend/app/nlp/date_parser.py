"""
排期与时段解析器
- 周期：一周/7天/一个月/30天 等 -> days
- 时段：晚间/早间/全天
- 默认 7 天
"""
import re
from datetime import date, timedelta
from typing import Optional, List

from app.models.slots import SlotField, ScheduleValue, TimeSlot
from app.nlp.cn_number import cn_to_int


_DAY_PATTERNS = [
    (re.compile(r"(\d+)\s*天"), lambda m: int(m.group(1))),
    (re.compile(r"([零一二两三四五六七八九十百千]+)\s*天"), lambda m: cn_to_int(m.group(1))),
    (re.compile(r"一周|7天"), lambda m: 7),
    (re.compile(r"两周|14天"), lambda m: 14),
    (re.compile(r"一个月|30天|一月"), lambda m: 30),
    (re.compile(r"(\d+)\s*周"), lambda m: int(m.group(1)) * 7),
    (re.compile(r"(\d+)\s*个月"), lambda m: int(m.group(1)) * 30),
]

_EVENING_KW = re.compile(r"晚间|晚上|夜间|夜晚|傍晚|下午|黄金时段")
_MORNING_KW = re.compile(r"早间|早上|上午|清晨|早晨")
_ALLDAY_KW = re.compile(r"全天|全时段|不限时段|24小时")


def parse_schedule(text: str) -> Optional[SlotField]:
    """解析排期意图，返回 SlotField(ScheduleValue)"""
    days: int = 7
    confidence: float = 0.6  # 默认值时较低，有命中则提升
    source_parts: List[str] = []

    # 周期
    matched_days = False
    for pattern, extractor in _DAY_PATTERNS:
        m = pattern.search(text)
        if m:
            extracted = extractor(m)
            if extracted:
                days = extracted
                matched_days = True
                confidence = 0.95
                source_parts.append(m.group(0))
                break

    # 时段
    time_slots: List[TimeSlot] = []
    if _ALLDAY_KW.search(text):
        time_slots = [TimeSlot.ALL_DAY]
        m2 = _ALLDAY_KW.search(text)
        source_parts.append(m2.group(0))  # type: ignore[union-attr]
    else:
        if _MORNING_KW.search(text):
            time_slots.append(TimeSlot.MORNING)
            m3 = _MORNING_KW.search(text)
            source_parts.append(m3.group(0))  # type: ignore[union-attr]
        if _EVENING_KW.search(text):
            time_slots.append(TimeSlot.EVENING)
            m4 = _EVENING_KW.search(text)
            source_parts.append(m4.group(0))  # type: ignore[union-attr]

    if not matched_days and not time_slots:
        return None  # 文本中完全没有排期信息

    start_date = date.today().isoformat()
    sched = ScheduleValue(days=days, start_date=start_date, time_slots=time_slots or None)
    return SlotField(
        value=sched.model_dump(),
        confidence=confidence,
        source="、".join(source_parts) if source_parts else "默认7天",
    )
