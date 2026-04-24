from __future__ import annotations
from typing import Optional, List, Literal, Any
from pydantic import BaseModel
from enum import Enum


class MarketingScene(str, Enum):
    SHORT_VIDEO = "short_video"
    LIVE = "live"


class MarketingGoal(str, Enum):
    STORE_TRAFFIC = "store_traffic"
    TEST_DRIVE = "test_drive"
    LEAD_COLLECTION = "lead_collection"


class LocationType(str, Enum):
    RADIUS = "radius"
    CITY = "city"
    NATIONWIDE = "nationwide"


class BidStrategyType(str, Enum):
    MANUAL = "manual"
    AUTO = "auto"


class TimeSlot(str, Enum):
    MORNING = "morning"
    EVENING = "evening"
    ALL_DAY = "all_day"


# ──────────────────────────────────────────────
# 单个槽位值（带置信度与来源片段）
# ──────────────────────────────────────────────

class SlotField(BaseModel):
    value: Any
    confidence: float = 1.0        # 0.0 ~ 1.0
    source: Optional[str] = None   # 触发该槽位的原文片段


class LocationValue(BaseModel):
    type: LocationType
    km: Optional[int] = None       # radius 时填写公里数


class AudienceValue(BaseModel):
    gender: Literal["male", "female", "both"] = "both"
    age_range: Optional[str] = None   # 如 "18-35"


class BidStrategyValue(BaseModel):
    type: BidStrategyType = BidStrategyType.AUTO
    amount: Optional[float] = None    # 手动出价金额（元）


class ScheduleValue(BaseModel):
    days: int = 7
    start_date: Optional[str] = None   # ISO 日期 YYYY-MM-DD
    time_slots: Optional[List[TimeSlot]] = None


# ──────────────────────────────────────────────
# 完整槽位集合
# ──────────────────────────────────────────────

class PlanSlots(BaseModel):
    vehicle: Optional[SlotField] = None        # 推广车型
    scene: Optional[SlotField] = None          # 营销场景
    goal: Optional[SlotField] = None           # 营销目标
    location: Optional[SlotField] = None       # 投放地域
    audience: Optional[SlotField] = None       # 定向人群
    budget: Optional[SlotField] = None         # 总预算（元）
    bid_strategy: Optional[SlotField] = None   # 出价策略
    schedule: Optional[SlotField] = None       # 排期

    # 必填槽位列表（未填时需追问）
    REQUIRED: List[str] = ["vehicle", "scene", "goal", "location", "budget"]

    def missing_required(self) -> List[str]:
        """返回缺失的必填槽位名"""
        return [f for f in self.REQUIRED if getattr(self, f) is None]

    def low_confidence_fields(self, threshold: float = 0.7) -> List[str]:
        """返回置信度低于阈值的已填槽位名"""
        result = []
        for field_name in ["vehicle", "scene", "goal", "location", "audience",
                           "budget", "bid_strategy", "schedule"]:
            slot = getattr(self, field_name)
            if slot and slot.confidence < threshold:
                result.append(field_name)
        return result

    def merge(self, other: "PlanSlots") -> "PlanSlots":
        """后出现覆盖前出现（对已有槽位，新值优先）"""
        data = self.model_dump()
        other_data = other.model_dump(exclude={"REQUIRED"})
        for key, val in other_data.items():
            if val is not None:
                data[key] = val
        data["REQUIRED"] = self.REQUIRED
        return PlanSlots(**data)


# ──────────────────────────────────────────────
# 追问消息
# ──────────────────────────────────────────────

CLARIFICATION_PROMPTS: dict[str, str] = {
    "vehicle": "请问您希望推广哪款车型？（例如：比亚迪汉EV、特斯拉Model 3）",
    "scene": "请问您的营销场景是「短视频」还是「直播」？",
    "goal": "请问您的营销目标是「门店引流」、「试驾预约」还是「线索收集」？",
    "location": "请问投放地域是「周边X公里」、「同城」还是「全国」？",
    "audience": "请问您的目标人群是哪些？（如：男性、90后、年轻人等）",
    "budget": "请问您的总预算是多少？（如：两万、50000元）",
    "bid_strategy": "请问出价策略选「智能出价」还是「手动出价」？如手动请告诉我出价金额。",
    "schedule": "请问投放周期是多久？（如：一周、30天；是否有特定时段：早间/晚间）",
}
