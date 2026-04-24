"""
预算与出价策略解析器
- 预算：中文数字 / 阿拉伯数字 / 混合，统一换算为元（整数）
- 出价策略：
    命中"手动"或"出价X元" -> 手动出价 + 可选金额
    否则默认智能出价
"""
import re
from typing import Optional, Tuple

from app.nlp.cn_number import extract_number
from app.models.slots import SlotField, BidStrategyValue, BidStrategyType


# ─── 预算解析 ──────────────────────────────────────────────────────────────

_BUDGET_TRIGGERS = re.compile(
    r"(?:预算|budget)[^\d零一二两三四五六七八九十百千万亿]*"
    r"([零一二两三四五六七八九十百千万亿\d\.]+\s*[wW万千百亿]?)"
    r"|([零一二两三四五六七八九十百千万亿\d\.]+(?:\s*[wW万千百亿])?)\s*(?:元|块|rmb|人民币|预算)"
    r"|(\d[\d,\.]*)\s*(?:元|块|rmb)",
    re.IGNORECASE,
)


def parse_budget(text: str, pending_budget: bool = False) -> Optional[SlotField]:
    """
    从文本中抽取总预算（元，整数）。
    成功返回 SlotField(value=int, confidence=float, source=str)，否则返回 None。
    """
    # 尝试 "预算X万" 或 "X万预算" 等模式
    m = _BUDGET_TRIGGERS.search(text)
    if m:
        raw = (m.group(1) or m.group(2) or m.group(3) or "").strip().replace(",", "")
        val, src = extract_number(raw)
        if val is not None:
            return SlotField(value=int(val), confidence=0.95, source=m.group(0).strip())

    if pending_budget:
        bare = re.fullmatch(r"\s*([零一二两三四五六七八九十百千万亿\d\.]+\s*[wW万千百亿]?)\s*(?:元|块|rmb|人民币)?\s*", text)
        if bare:
            val, src = extract_number(bare.group(1).strip())
            if val is not None and val > 0:
                return SlotField(value=int(val), confidence=0.9, source=src or bare.group(0).strip())

    # 宽松：直接提取文中任意金额
    val, src = extract_number(text)
    if val and val >= 100:  # 过滤噪音小数字
        return SlotField(value=int(val), confidence=0.75, source=src)

    return None


# ─── 出价策略解析 ──────────────────────────────────────────────────────────

_MANUAL_PATTERN = re.compile(
    r"手动(?:出价)?(?:[^\d零一二两三四五六七八九十百千万亿]*"
    r"([零一二两三四五六七八九十百千万亿\d\.]+)\s*[元块])?",
)
_BID_AMOUNT_PATTERN = re.compile(
    r"出价\s*([零一二两三四五六七八九十百千万亿\d\.]+)\s*[元块]",
)
_AUTO_PATTERN = re.compile(r"智能(?:出价)?|自动(?:出价)?")


def parse_bid_strategy(text: str, pending_bid: bool = False) -> Optional[SlotField]:
    """
    解析出价策略。
    - 命中"智能/自动" -> 智能出价（source 非"默认"，不会再次追问）
    - 命中"手动"或"出价X元" -> 手动出价
    - pending_bid=True 时：裸数字视为手动出价金额
    - 否则返回 None（调用方默认智能出价）
    """
    if _AUTO_PATTERN.search(text):
        m = _AUTO_PATTERN.search(text)
        val = BidStrategyValue(type=BidStrategyType.AUTO)
        return SlotField(value=val.model_dump(), confidence=0.95, source=m.group(0).strip())  # type: ignore[union-attr]

    m = _MANUAL_PATTERN.search(text)
    if m:
        amount: Optional[float] = None
        if m.group(1):
            v, _ = extract_number(m.group(1))
            amount = float(v) if v else None
        val = BidStrategyValue(type=BidStrategyType.MANUAL, amount=amount)
        return SlotField(value=val.model_dump(), confidence=0.95, source=m.group(0).strip())

    m = _BID_AMOUNT_PATTERN.search(text)
    if m:
        v, _ = extract_number(m.group(1))
        amount = float(v) if v else None
        val = BidStrategyValue(type=BidStrategyType.MANUAL, amount=amount)
        return SlotField(value=val.model_dump(), confidence=0.95, source=m.group(0).strip())

    # 上下文追问时：裸数字（可选带元）视为手动出价金额
    if pending_bid:
        bare = re.fullmatch(r"\s*([零一二两三四五六七八九十百千万亿\d\.]+)\s*[元块]?\s*", text)
        if bare:
            v, _ = extract_number(bare.group(1))
            if v is not None and v > 0:
                bid_val = BidStrategyValue(type=BidStrategyType.MANUAL, amount=float(v))
                return SlotField(value=bid_val.model_dump(), confidence=0.85, source=bare.group(0).strip())

    return None


def default_bid_strategy() -> SlotField:
    """当文本未指定出价策略时，默认智能出价"""
    return SlotField(
        value=BidStrategyValue(type=BidStrategyType.AUTO).model_dump(),
        confidence=1.0,
        source="默认智能出价",
    )
