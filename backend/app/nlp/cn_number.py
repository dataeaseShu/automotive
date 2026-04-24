"""
中文数字到整数/浮点数的转换工具
支持：两万、十五万、一千三百、2.5万、20000 等混合形式
"""
import re

_DIGIT_MAP = {
    "零": 0, "〇": 0,
    "一": 1, "壹": 1,
    "二": 2, "贰": 2, "两": 2,
    "三": 3, "叁": 3,
    "四": 4, "肆": 4,
    "五": 5, "伍": 5,
    "六": 6, "陆": 6,
    "七": 7, "柒": 7,
    "八": 8, "捌": 8,
    "九": 9, "玖": 9,
}

_UNIT_MAP = {
    "十": 10, "拾": 10,
    "百": 100, "佰": 100,
    "千": 1000, "仟": 1000,
    "万": 10_000,
    "亿": 100_000_000,
}

_MONEY_UNIT = {
    "万": 10_000,
    "千": 1_000,
    "百": 100,
    "亿": 100_000_000,
}


def cn_to_int(text: str) -> int | None:
    """
    将中文数字字符串转为整数。
    支持：'两万'->20000, '十五万'->150000, '一千三百'->1300
    返回 None 表示无法解析。
    """
    text = text.strip()
    if not text:
        return None

    # 纯阿拉伯数字
    if re.fullmatch(r"\d+", text):
        return int(text)

    # 数字+中文单位，如 "2万"、"1.5万"
    m = re.fullmatch(r"(\d+\.?\d*)\s*([万千百亿])", text)
    if m:
        num, unit = float(m.group(1)), _MONEY_UNIT.get(m.group(2), 1)
        return int(num * unit)

    # 纯中文
    result = _parse_cn(text)
    return result


def _parse_cn(s: str) -> int | None:
    """解析纯中文数字串"""
    # 处理以"十"开头的简写，如"十万"=100000
    if s and s[0] in ("十", "拾"):
        s = "一" + s

    total = 0
    section = 0   # 当前节（万以下）
    cur = 0       # 当前待乘的数字

    for ch in s:
        if ch in _DIGIT_MAP:
            cur = _DIGIT_MAP[ch]
        elif ch in ("万", "亿"):
            section += cur
            cur = 0
            unit = _UNIT_MAP[ch]
            total += section * unit
            section = 0
        elif ch in _UNIT_MAP:
            if cur == 0:
                cur = 1  # 十 → 1*10
            section += cur * _UNIT_MAP[ch]
            cur = 0
        else:
            return None  # 非法字符

    section += cur
    total += section
    return total if total > 0 else None


def extract_number(text: str) -> tuple[float | None, str]:
    """
    从文本中抽取第一个数字（支持阿拉伯数字和中文数字+单位）。
    返回 (数值, 原文片段)
    """
    # 先尝试 "数字+中文单位"，如 "2万"
    m = re.search(r"(\d+\.?\d*)\s*([万千百亿])", text)
    if m:
        num = float(m.group(1)) * _MONEY_UNIT.get(m.group(2), 1)
        return int(num), m.group(0)

    # 纯中文数字 + 单位
    cn_pattern = r"[零一二两三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟]+"
    m = re.search(cn_pattern, text)
    if m:
        val = cn_to_int(m.group(0))
        if val:
            return val, m.group(0)

    # 纯阿拉伯
    m = re.search(r"\d+\.?\d*", text)
    if m:
        return float(m.group(0)), m.group(0)

    return None, ""
