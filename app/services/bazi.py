"""排盘服务：基于 lunar-python 计算四柱干支、纳音、十神、五行统计。

真太阳时：MVP 采用平太阳时近似 真太阳时 ≈ 北京时间 + (经度−120°)×4分钟，
均时差（EoT）校正留待阶段 1 精化。
"""
from datetime import datetime, timedelta

from lunar_python import Solar

# 八字天干地支的五行属性
_WX = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土",
    "巳": "火", "午": "火", "未": "土", "申": "金", "酉": "金",
    "戌": "土", "亥": "水",
}
# 五行排序顺序（中文美观）
_WX_ORDER = ["木", "火", "土", "金", "水"]


def apply_true_solar_time(dt: datetime, longitude: float | None) -> tuple[datetime, str | None]:
    """平太阳时近似校正。返回 (校正后时间, 展示文案)。"""
    if longitude is None:
        return dt, None
    offset_min = (longitude - 120.0) * 4.0
    adjusted = dt + timedelta(minutes=offset_min)
    note = f"经度校正 {offset_min:+.1f} 分钟"
    if abs(offset_min) < 0.5:
        return dt, None
    return adjusted, note


def compute(dt: datetime, longitude: float | None, latitude: float | None,
            use_true_solar_time: bool) -> dict:
    solar_dt, note = dt, None
    if use_true_solar_time:
        solar_dt, note = apply_true_solar_time(dt, longitude)

    solar = Solar.fromDate(solar_dt)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()

    pillars = {
        "year": ec.getYear(),
        "month": ec.getMonth(),
        "day": ec.getDay(),
        "hour": ec.getTime(),
    }
    na_yin = {
        "year": ec.getYearNaYin(),
        "month": ec.getMonthNaYin(),
        "day": ec.getDayNaYin(),
        "hour": ec.getTimeNaYin(),
    }
    ten_gods = {
        "year": ec.getYearShiShenGan(),
        "month": ec.getMonthShiShenGan(),
        "hour": ec.getTimeShiShenGan(),
    }
    lunar_date = (f"{lunar.getYearInChinese()}年"
                  f"{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}")

    # 五行统计：统计四柱 8 个字的五行
    wuxing_counts: dict[str, int] = {}
    for p in pillars.values():
        for ch in p:
            w = _WX.get(ch)
            if w:
                wuxing_counts[w] = wuxing_counts.get(w, 0) + 1
    wuxing = {k: wuxing_counts.get(k, 0) for k in _WX_ORDER}

    return {
        "year": pillars["year"],
        "month": pillars["month"],
        "day": pillars["day"],
        "hour": pillars["hour"],
        "year_na_yin": na_yin["year"],
        "month_na_yin": na_yin["month"],
        "day_na_yin": na_yin["day"],
        "hour_na_yin": na_yin["hour"],
        "ten_gods": ten_gods,
        "day_master": _WX.get(pillars["day"][0], ""),
        "wuxing": wuxing,
        "lunar_date": lunar_date.lstrip("农历"),
        "true_solar_time": solar_dt.strftime("%Y-%m-%d %H:%M") if note else None,
    }


def summary_lines(bazi: dict, gender: str | None) -> list[str]:
    """命局摘要（供生成层拼 prompt）。"""
    return [
        f"四柱：{bazi['year']}年、{bazi['month']}月、{bazi['day']}日、{bazi['hour']}时",
        f"纳音：{bazi['year_na_yin']} / {bazi['month_na_yin']} / {bazi['day_na_yin']} / {bazi['hour_na_yin']}",
        f"日主五行：{bazi['day_master']}",
        f"十神：年柱{bazi['ten_gods']['year']}、月柱{bazi['ten_gods']['month']}、时柱{bazi['ten_gods']['hour']}",
        f"五行分布：{bazi['wuxing']}",
        (f"性别：{'男' if gender == 'male' else '女'}" if gender else ""),
    ]


def build_query(bazi: dict, gender: str | None) -> str:
    """将命局转成检索问题：日主 + 四柱 + 十神为关键词。"""
    parts = [
        f"日主五行{bazi['day_master']}",
        f"四柱八字 {bazi['year']}年 {bazi['month']}月 {bazi['day']}日 {bazi['hour']}时",
        f"年柱十神{bazi['ten_gods']['year']} 月柱十神{bazi['ten_gods']['month']} 时柱十神{bazi['ten_gods']['hour']}",
    ]
    if gender:
        parts.append("男命" if gender == "male" else "女命")
    parts.append("日主强弱 喜用神 性格 事业财运 婚姻 健康 命局分析")
    return " ".join(parts)