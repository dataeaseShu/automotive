"""
主NLP解析流水线
- 规则解析 + LLM 提取融合
- 自动填充默认值（不追问）
"""
import re
from datetime import date
from typing import Optional, Any

from app.models.slots import (
    PlanSlots,
    SlotField,
    MarketingScene,
    MarketingGoal,
    LocationType,
    LocationValue,
    AudienceValue,
    ScheduleValue,
    CLARIFICATION_PROMPTS,
)
from app.nlp.budget_parser import parse_budget, parse_bid_strategy, default_bid_strategy
from app.nlp.location_parser import parse_location
from app.nlp.date_parser import parse_schedule
from app.nlp.vehicle_lexicon import VehicleLexicon
from app.nlp.llm_extractor import get_llm_extractor

_vehicle_lexicon = VehicleLexicon()

# ─── 营销场景 ──────────────────────────────────────────────────────────────
_SCENE_SHORT_VIDEO = re.compile(r"短视频|视频投放|信息流|抖音|短片")
_SCENE_LIVE = re.compile(r"直播|直播间|live")


def _parse_scene(text: str) -> Optional[SlotField]:
    if _SCENE_SHORT_VIDEO.search(text):
        m = _SCENE_SHORT_VIDEO.search(text)
        return SlotField(value=MarketingScene.SHORT_VIDEO, confidence=0.95, source=m.group(0))  # type: ignore[union-attr]
    if _SCENE_LIVE.search(text):
        m = _SCENE_LIVE.search(text)
        return SlotField(value=MarketingScene.LIVE, confidence=0.95, source=m.group(0))  # type: ignore[union-attr]
    return None


# ─── 营销目标 ──────────────────────────────────────────────────────────────
_GOAL_STORE = re.compile(r"门店|引流|到店|进店")
_GOAL_TEST_DRIVE = re.compile(r"试驾|试乘|体验驾驶|预约试驾")
_GOAL_LEAD = re.compile(r"线索|留资|留电|表单|预约|获客")


def _parse_goal(text: str) -> Optional[SlotField]:
    if _GOAL_TEST_DRIVE.search(text):
        m = _GOAL_TEST_DRIVE.search(text)
        return SlotField(value=MarketingGoal.TEST_DRIVE, confidence=0.95, source=m.group(0))  # type: ignore[union-attr]
    if _GOAL_STORE.search(text):
        m = _GOAL_STORE.search(text)
        return SlotField(value=MarketingGoal.STORE_TRAFFIC, confidence=0.9, source=m.group(0))  # type: ignore[union-attr]
    if _GOAL_LEAD.search(text):
        m = _GOAL_LEAD.search(text)
        return SlotField(value=MarketingGoal.LEAD_COLLECTION, confidence=0.85, source=m.group(0))  # type: ignore[union-attr]
    return None


# ─── 定向人群 ──────────────────────────────────────────────────────────────
_GENDER_MALE = re.compile(r"男性|男人|男士|男生|(?<![女])男(?!性女)")
_GENDER_FEMALE = re.compile(r"女性|女人|女士|女生|(?<![男])女(?!性男)")
_AUDIENCE_HINT = re.compile(r"人群|受众|定向|年龄|岁")
_AGE_MAP = [
    (re.compile(r"00后|零零后|Z世代"), "18-25"),
    (re.compile(r"90后|九零后|年轻人|年轻"), "18-35"),
    (re.compile(r"80后|八零后"), "35-45"),
    (re.compile(r"70后|七零后"), "45-55"),
    (re.compile(r"中年|中年人"), "35-50"),
    # 任意起始年龄区间：25-40、25到40岁、25~40 等
    (re.compile(r"(\d{1,2})\s*[-~到至]\s*(\d{2})\s*岁?"), None),
    # 单点年龄：30岁、35岁
    (re.compile(r"(\d{1,2})\s*岁"), None),
]


def _parse_audience(text: str, pending_audience: bool = False) -> Optional[SlotField]:
    """解析人群定向槽位。

    pending_audience=True 时允许把裸数字识别为年龄（适用于槽位追问上下文）。
    """
    gender = "both"
    has_male = bool(_GENDER_MALE.search(text))
    has_female = bool(_GENDER_FEMALE.search(text))
    if has_male and not has_female:
        gender = "male"
    elif has_female and not has_male:
        gender = "female"

    age_range = None
    age_source = ""
    for pattern, mapped in _AGE_MAP:
        m = pattern.search(text)
        if m:
            if mapped:
                # 固定映射（世代标签等）
                age_range = mapped
                age_source = m.group(0)
            elif m.lastindex == 2:
                # 任意区间 (\d{1,2})-(\d{2})
                age_range = f"{m.group(1)}-{m.group(2)}"
                age_source = m.group(0)
            else:
                # 单点年龄 (\d{1,2})岁
                age_range = m.group(1)
                age_source = m.group(0)
            break

    # 上下文追问或明确人群语义时：数字可视为年龄
    if age_range is None and (pending_audience or _AUDIENCE_HINT.search(text)):
        # 先尝试整句就是数字（如 "30"）
        bare = re.fullmatch(r"\s*(\d{1,2})\s*", text)
        if bare:
            val = int(bare.group(1))
            if 10 <= val <= 80:
                age_range = str(val)
                age_source = bare.group(1)
        else:
            # 再尝试语义短句中的单个年龄（如 "投放人群30"、"年龄30"）
            embedded = re.search(r"(?<!\d)(\d{1,2})(?!\d)", text)
            if embedded:
                val = int(embedded.group(1))
                if 10 <= val <= 80:
                    age_range = str(val)
                    age_source = embedded.group(1)

    if gender == "both" and age_range is None:
        return None

    aud = AudienceValue(gender=gender, age_range=age_range)  # type: ignore[arg-type]
    return SlotField(
        value=aud.model_dump(),
        confidence=0.85,
        source=age_source or text[:12],
    )


# ─── 预处理 ────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    result = []
    for ch in text:
        cp = ord(ch)
        if 0xFF01 <= cp <= 0xFF5E:
            ch = chr(cp - 0xFEE0)
        result.append(ch)
    return re.sub(r"\s+", " ", "".join(result)).strip()


# ─── 规则解析 ──────────────────────────────────────────────────────────────

def _parse_slots_rule(text: str, pending_slot: Optional[str] = None) -> PlanSlots:
    slots = PlanSlots()

    vehicle_result = _vehicle_lexicon.match(text)
    if vehicle_result:
        std_name, confidence, source = vehicle_result
        slots.vehicle = SlotField(value=std_name, confidence=confidence, source=source)

    slots.scene = _parse_scene(text)
    slots.goal = _parse_goal(text)
    slots.location = parse_location(text)
    slots.audience = _parse_audience(text, pending_audience=(pending_slot == "audience"))
    slots.budget = parse_budget(text, pending_budget=(pending_slot == "budget"))
    slots.bid_strategy = parse_bid_strategy(text, pending_bid=(pending_slot == "bid_strategy"))
    slots.schedule = parse_schedule(text, pending_schedule=(pending_slot == "schedule"))
    return slots


# ─── LLM 映射 ───────────────────────────────────────────────────────────────

def _llm_to_slots(llm_result: dict[str, Any], allow_location: bool = True) -> PlanSlots:
    slots = PlanSlots()
    conf = float(llm_result.get("confidence", 0.7) or 0.7)

    if llm_result.get("vehicle"):
        slots.vehicle = SlotField(value=llm_result["vehicle"], confidence=conf, source="llm")

    if llm_result.get("scene") in {"short_video", "live"}:
        slots.scene = SlotField(value=llm_result["scene"], confidence=conf, source="llm")

    if llm_result.get("goal") in {"store_traffic", "test_drive", "lead_collection"}:
        slots.goal = SlotField(value=llm_result["goal"], confidence=conf, source="llm")

    if allow_location and isinstance(llm_result.get("location"), dict):
        loc = llm_result["location"]
        loc_type = loc.get("type")
        if loc_type in {"radius", "city", "nationwide"}:
            km = loc.get("km") or loc.get("radius_km")
            slots.location = SlotField(
                value=LocationValue(type=LocationType(loc_type), km=km).model_dump(),
                confidence=conf,
                source="llm",
            )

    budget = llm_result.get("budget")
    if isinstance(budget, (int, float)) and budget > 0:
        slots.budget = SlotField(value=int(budget), confidence=conf, source="llm")

    # bid_strategy：需要 type 字段合法才接受
    bs = llm_result.get("bid_strategy")
    if isinstance(bs, dict) and bs.get("type") in {"manual", "auto"}:
        slots.bid_strategy = SlotField(value=bs, confidence=conf, source="llm")

    # schedule：需要 days 为正整数才接受，避免 {"days": null} 覆盖规则结果
    sc = llm_result.get("schedule")
    if isinstance(sc, dict) and isinstance(sc.get("days"), (int, float)) and sc["days"] > 0:
        slots.schedule = SlotField(value=sc, confidence=conf, source="llm")

    # audience：需要 gender 或 age_range 有实际内容才接受
    aud = llm_result.get("audience")
    if isinstance(aud, dict) and (
        aud.get("gender") in {"male", "female", "both"}
        or (aud.get("age_range") and str(aud["age_range"]).strip())
    ):
        slots.audience = SlotField(value=aud, confidence=conf, source="llm")

    return slots


# ─── 默认值填充 ─────────────────────────────────────────────────────────────

def fill_defaults(slots: PlanSlots) -> PlanSlots:
    if slots.scene is None:
        slots.scene = SlotField(value=MarketingScene.SHORT_VIDEO, confidence=1.0, source="默认短视频")

    if slots.goal is None:
        slots.goal = SlotField(value=MarketingGoal.STORE_TRAFFIC, confidence=1.0, source="默认门店引流")

    if slots.location is None:
        slots.location = SlotField(
            value=LocationValue(type=LocationType.CITY).model_dump(),
            confidence=1.0,
            source="默认同城",
        )

    if slots.budget is None:
        slots.budget = SlotField(value=50000, confidence=1.0, source="默认预算50000")

    if slots.bid_strategy is None:
        slots.bid_strategy = default_bid_strategy()

    if slots.schedule is None:
        slots.schedule = SlotField(
            value=ScheduleValue(days=7, start_date=date.today().isoformat()).model_dump(),
            confidence=1.0,
            source="默认7天",
        )

    if slots.vehicle is None:
        slots.vehicle = SlotField(value="通用车型", confidence=0.6, source="默认车型")

    return slots


# ─── 主流水线 ──────────────────────────────────────────────────────────────

async def parse_slots(text: str, existing: Optional[PlanSlots] = None, pending_slot: Optional[str] = None) -> PlanSlots:
    """
    解析用户输入并融合槽位：LLM > 规则 > existing。
    pending_slot 传入当前正在追问的槽位名（如 "audience"），提升纯文本回复的解析精度。
    注意：不自动填充默认值，由调用方在进入 preview 前统一调用 fill_defaults。
    """
    normalized = _normalize(text)
    base = existing or PlanSlots()

    rule_slots = _parse_slots_rule(normalized, pending_slot=pending_slot)
    merged = base.merge(rule_slots)

    try:
        extractor = get_llm_extractor()
        llm_result = await extractor.extract_intent_and_fields_async(normalized, merged, pending_slot=pending_slot)
        if llm_result and float(llm_result.get("confidence", 0) or 0) >= 0.35:
            allow_location = pending_slot == "location" or rule_slots.location is not None
            llm_slots = _llm_to_slots(llm_result, allow_location=allow_location)
            merged = merged.merge(llm_slots)
    except Exception:
        # LLM 非阻断能力：失败时保留规则结果
        pass

    return merged


async def parse_slots_with_intent(text: str, existing: Optional[PlanSlots] = None, pending_slot: Optional[str] = None) -> tuple[PlanSlots, str]:
    """
    一次 LLM 调用同时返回解析后的槽位和意图，避免重复调用。
    注意：不自动填充默认值，由调用方在进入 preview 前统一调用 fill_defaults。
    """
    normalized = _normalize(text)
    base = existing or PlanSlots()

    rule_slots = _parse_slots_rule(normalized, pending_slot=pending_slot)
    merged = base.merge(rule_slots)
    intent = "isCreate"  # 默认意图

    try:
        extractor = get_llm_extractor()
        llm_result = await extractor.extract_intent_and_fields_async(normalized, merged, pending_slot=pending_slot)
        if llm_result:
            # 提取意图
            raw_intent = llm_result.get("intent")
            if raw_intent in {"isCreate", "isModify", "isQuery", "isConfirm"}:
                intent = raw_intent
            # 融合槽位
            if float(llm_result.get("confidence", 0) or 0) >= 0.35:
                allow_location = pending_slot == "location" or rule_slots.location is not None
                llm_slots = _llm_to_slots(llm_result, allow_location=allow_location)
                merged = merged.merge(llm_slots)
    except Exception:
        # LLM 非阻断能力：失败时保留规则结果，意图用规则推断
        intent = _detect_intent_by_rule(normalized)

    return merged, intent


def get_next_clarification(slots: PlanSlots, threshold: float = 0.7) -> Optional[str]:
    missing = slots.missing_required()
    if missing:
        return missing[0]

    low_conf = slots.low_confidence_fields(threshold)
    if low_conf:
        return low_conf[0]

    return None


def get_clarification_prompt(field: str) -> str:
    return CLARIFICATION_PROMPTS.get(field, f"请补充「{field}」相关信息。")


def _detect_intent_by_rule(normalized: str) -> str:
    """规则兜底意图识别（LLM 不可用时使用）。"""
    create_kw = ["建计划", "创建计划", "新建计划", "投放", "推广", "推"]
    modify_kw = ["修改", "调整", "改成", "改为", "更换"]
    query_kw = ["查看", "查询", "看看", "多少", "什么"]
    confirm_kw = ["确认", "提交", "推送", "同意", "可以"]

    if any(k in normalized for k in confirm_kw):
        return "isConfirm"
    if any(k in normalized for k in modify_kw):
        return "isModify"
    if any(k in normalized for k in query_kw):
        return "isQuery"
    if any(k in normalized for k in create_kw):
        return "isCreate"
    return "isCreate"


async def detect_intent(text: str, slots: Optional[PlanSlots] = None) -> str:
    """
    识别意图：isCreate | isModify | isQuery | isConfirm
    优先使用 LLM，失败时回退规则。
    """
    normalized = _normalize(text)

    try:
        extractor = get_llm_extractor()
        llm_result = await extractor.extract_intent_and_fields_async(normalized, slots)
        intent = llm_result.get("intent") if isinstance(llm_result, dict) else None
        if intent in {"isCreate", "isModify", "isQuery", "isConfirm"}:
            return intent
    except Exception:
        pass

    return _detect_intent_by_rule(normalized)
