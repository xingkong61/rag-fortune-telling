"""梅花易数：时间起卦、报数起卦 → 本卦/互卦/变卦与体用生克。

起卦法（《梅花易数·象数易理篇》）：
  时间起卦：上卦 =（年支数 + 农历月 + 农历日）÷ 8 取余；
            下卦 =（年支数 + 农历月 + 农历日 + 时支数）÷ 8 取余；
            动爻 = 同（年+月+日+时）÷ 6 取余。余 0 者取 8（卦）或 6（爻）。
  报数起卦：两数分别定上下卦，和数定动爻；给三数则第三数直取动爻。
体用：动爻所在之卦为用，另一卦为体（动者为用，静者为体）。
"""
from datetime import datetime

from lunar_python import Solar

from app.services import gua
from app.services.bazi import apply_true_solar_time


def _mod(v: int, m: int) -> int:
    """取余，余 0 记为 m（卦数 8、爻数 6 的传统取法）。"""
    r = v % m
    return r if r else m


def _cast(shang: str, xia: str, dong: int) -> dict:
    """由上下卦与动爻推本卦、互卦、变卦、体用。"""
    ben_lines = gua.lines6(shang, xia)

    # 互卦：二三四爻为下卦，三四五爻为上卦
    hu_xia = gua.LINES_TO_GUA[tuple(ben_lines[1:4])]
    hu_shang = gua.LINES_TO_GUA[tuple(ben_lines[2:5])]

    # 变卦：动爻阴阳互换
    bian_lines = list(ben_lines)
    bian_lines[dong - 1] = 1 - bian_lines[dong - 1]
    bian_shang, bian_xia = gua.gua_of_lines(bian_lines)

    # 体用：动爻在下卦则下卦为用，在上卦则上卦为用
    if dong <= 3:
        ti, yong = shang, xia
    else:
        ti, yong = xia, shang
    rel = gua.relation(gua.GUA_WUXING[ti], gua.GUA_WUXING[yong])

    return {
        "shang_gua": shang, "xia_gua": xia,
        "shang_symbol": gua.GUA_SYMBOL[shang], "xia_symbol": gua.GUA_SYMBOL[xia],
        "ben_gua": gua.hexagram_name(shang, xia),
        "ben_lines": ben_lines,
        "dong_yao": dong, "dong_yao_name": gua.yao_name(dong),
        "ti_gua": ti, "yong_gua": yong,
        "ti_wuxing": gua.GUA_WUXING[ti], "yong_wuxing": gua.GUA_WUXING[yong],
        "relation": rel,
        "relation_text": {"我生": "体生用", "生我": "用生体", "我克": "体克用", "克我": "用克体"}[rel]
        if rel != "比和" else "体用比和",
        "relation_note": gua.TIYONG_NOTE[rel],
        "hu_gua": gua.hexagram_name(hu_shang, hu_xia),
        "hu_shang": hu_shang, "hu_xia": hu_xia,
        "bian_gua": gua.hexagram_name(bian_shang, bian_xia),
        "bian_shang": bian_shang, "bian_xia": bian_xia,
        "bian_lines": bian_lines,
        "gua_xiang": f"体卦{ti}（{gua.GUA_WUXING[ti]}）：{gua.GUA_XIANG[ti]}；"
                     f"用卦{yong}（{gua.GUA_WUXING[yong]}）：{gua.GUA_XIANG[yong]}",
    }


def divine_by_time(when: datetime | None, question: str, longitude: float | None = None,
                   use_true_solar_time: bool = True) -> dict:
    """时间起卦（when 缺省取起卦当下）。"""
    cast_dt, note = (when or datetime.now()), None
    if use_true_solar_time:
        cast_dt, note = apply_true_solar_time(cast_dt, longitude)

    lunar = Solar.fromDate(cast_dt).getLunar()
    year_num = gua.DIZHI.index(lunar.getYearZhi()) + 1
    month_num = abs(lunar.getMonth())
    day_num = lunar.getDay()
    hour_num = gua.DIZHI.index(lunar.getTimeZhi()) + 1

    upper_sum = year_num + month_num + day_num
    total = upper_sum + hour_num
    chart = _cast(gua.NUM_TO_GUA[_mod(upper_sum, 8)], gua.NUM_TO_GUA[_mod(total, 8)],
                  _mod(total, 6))
    chart.update({
        "kind": "time",
        "cast_time": cast_dt.strftime("%Y-%m-%d %H:%M"),
        "true_solar_time": cast_dt.strftime("%Y-%m-%d %H:%M") if note else None,
        "lunar_text": f"{lunar.getYearInGanZhi()}年{abs(lunar.getMonth())}月"
                      f"{lunar.getDay()}日{lunar.getTimeZhi()}时",
        "seed_text": f"年支{year_num}＋月{month_num}＋日{day_num}＝{upper_sum}（定上卦），"
                     f"再加时支{hour_num}＝{total}（定下卦、动爻）",
        "note": note,
    })
    chart["question"] = question
    chart["category"] = gua.classify_question(question)
    return chart


def divine_by_numbers(numbers: list[int], question: str) -> dict:
    """报数起卦：两数（和数取动爻）或三数（第三数直取动爻）。"""
    n1, n2 = numbers[0], numbers[1]
    total = n1 + n2
    dong_seed = numbers[2] if len(numbers) >= 3 else total
    chart = _cast(gua.NUM_TO_GUA[_mod(n1, 8)], gua.NUM_TO_GUA[_mod(n2, 8)],
                  _mod(dong_seed, 6))
    chart.update({
        "kind": "number",
        "cast_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "numbers": numbers,
        "lunar_text": None,
        "seed_text": f"报数 {n1}（定上卦）、{n2}（定下卦）"
                     + (f"、{numbers[2]}（直取动爻）" if len(numbers) >= 3 else f"，和{total}取动爻"),
        "note": None,
    })
    chart["question"] = question
    chart["category"] = gua.classify_question(question)
    return chart


def summary_lines(chart: dict) -> list[str]:
    """卦象摘要（供生成层拼 prompt）。"""
    lines = [
        f"起卦方式：{'时间起卦' if chart['kind'] == 'time' else '报数起卦'}"
        + (f"（{chart['lunar_text']}）" if chart.get("lunar_text") else ""),
        f"起卦依据：{chart['seed_text']}",
        f"本卦：{chart['ben_gua']}（上{chart['shang_gua']}{chart['shang_symbol']}、"
        f"下{chart['xia_gua']}{chart['xia_symbol']}）",
        f"动爻：{chart['dong_yao_name']}",
        f"体用：体卦{chart['ti_gua']}（{chart['ti_wuxing']}）、用卦{chart['yong_gua']}（{chart['yong_wuxing']}），"
        f"{chart['relation_text']} —— {chart['relation_note']}",
        f"互卦：{chart['hu_gua']}（上{chart['hu_shang']}、下{chart['hu_xia']}）",
        f"变卦：{chart['bian_gua']}（上{chart['bian_shang']}、下{chart['bian_xia']}）",
        f"卦象类象：{chart['gua_xiang']}",
        f"所问之事：{chart['question']}（属{chart['category']['category']}，"
        f"《梅花易数》对应「{chart['category']['meihua_zhan']}」）",
    ]
    return lines


def build_query(chart: dict, question: str | None = None) -> str:
    """构造古籍检索问题：《梅花易数》以体用、互变、占类为纲。"""
    cat = chart["category"]
    parts = [
        f"梅花易数 {chart['ben_gua']} 互卦{chart['hu_gua']} 变卦{chart['bian_gua']}",
        f"体卦{chart['ti_gua']} 用卦{chart['yong_gua']} {chart['relation_text']} 体用生克",
        f"{cat['meihua_zhan']} 断法",
    ]
    q = (question or chart.get("question") or "").strip()
    if q:
        parts.append(q)
    return " ".join(parts)