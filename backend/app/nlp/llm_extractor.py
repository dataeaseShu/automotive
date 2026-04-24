"""
LLM 辅助字段提取（阿里云百炼 OpenAI 兼容）
"""
import json
from typing import Optional, Dict, Any

from openai import AsyncOpenAI

from app.config import get_settings
from app.models.slots import PlanSlots


class LLMFieldExtractor:
    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[AsyncOpenAI] = None
        self.model = self.settings.DASHSCOPE_MODEL

        if self.settings.DASHSCOPE_API_KEY:
            try:
                self.client = AsyncOpenAI(
                    api_key=self.settings.DASHSCOPE_API_KEY,
                    base_url=self.settings.DASHSCOPE_BASE_URL,
                )
            except Exception:
                self.client = None

    def _extract_json(self, content: str) -> Dict[str, Any]:
        text = content.strip()

        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

        try:
            return json.loads(text)
        except Exception:
            # 容错：截取首个 JSON 对象
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise

    def extract_intent_and_fields(self, user_input: str, existing_slots: Optional[PlanSlots] = None) -> Dict[str, Any]:
        raise NotImplementedError("Use extract_intent_and_fields_async instead")

    async def extract_intent_and_fields_async(self, user_input: str, existing_slots: Optional[PlanSlots] = None) -> Dict[str, Any]:
        if not self.client:
            return {"intent": "isCreate", "confidence": 0, "fields": {}, "error": "LLM not available"}

        existing_info = "无"
        if existing_slots:
            existing_info = (
                f"车型={existing_slots.vehicle.value if existing_slots.vehicle else '未设置'}; "
                f"场景={existing_slots.scene.value if existing_slots.scene else '未设置'}; "
                f"目标={existing_slots.goal.value if existing_slots.goal else '未设置'}; "
                f"地域={existing_slots.location.value if existing_slots.location else '未设置'}; "
                f"预算={existing_slots.budget.value if existing_slots.budget else '未设置'}; "
                f"出价={existing_slots.bid_strategy.value if existing_slots.bid_strategy else '未设置'}; "
                f"排期={existing_slots.schedule.value if existing_slots.schedule else '未设置'}; "
                f"定向={existing_slots.audience.value if existing_slots.audience else '未设置'}"
            )

        prompt = f"""
你是汽车投放助手。请从用户输入中提取建计划字段，并返回严格 JSON（不要 markdown）。

已有槽位：{existing_info}
用户输入：{user_input}

返回 JSON：
{{
  "intent": "isCreate|isModify|isQuery|isConfirm",
  "vehicle": "string|null",
  "scene": "short_video|live|null",
  "goal": "store_traffic|test_drive|lead_collection|null",
  "location": {{"type": "radius|city|nationwide", "km": number|null}} | null,
  "budget": number|null,
  "bid_strategy": {{"type": "manual|auto", "amount": number|null}} | null,
  "schedule": {{"days": number|null, "start_date": "YYYY-MM-DD|null"}} | null,
  "audience": {{"gender": "male|female|both|null", "age_range": "string|null"}} | null,
  "confidence": 0-1,
  "reasoning": "string"
}}
""".strip()

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是汽车营销投放专家，输出必须是可解析 JSON。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                top_p=0.8,
            )
            content = (response.choices[0].message.content or "").strip()
            result = self._extract_json(content)
            if "confidence" not in result:
                result["confidence"] = 0.6
            return result
        except Exception as e:
            return {
                "intent": "isCreate",
                "fields": {},
                "confidence": 0,
                "error": str(e),
            }


_extractor: Optional[LLMFieldExtractor] = None


def get_llm_extractor() -> LLMFieldExtractor:
    global _extractor
    if _extractor is None:
        _extractor = LLMFieldExtractor()
    return _extractor
