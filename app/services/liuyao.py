"""六爻（纳甲筮法）：摇卦 → 装卦。

摇卦：三枚铜钱掷六次，自初爻至上爻。以「背」为阳：
  三背 → 老阳（重○，动）、两背 → 少阳（单）、一背 → 少阴（拆）、三字 → 老阴（交×，动）。
装卦：八宫归属定世应、纳甲取地支、卦宫五行为我定六亲、日干起六神，
      并标出月建、日辰、旬空、月破、日冲与伏神。
"""
import random
from datetime import datetime

from lunar_python import Solar

from app.services import gua

# 八卦纳甲（自下而上六爻）
NAJIA = {
    "乾": ("甲子", "甲寅", "甲辰", "壬午", "壬申", "壬戌"),
    "坎": ("戊寅", "戊辰", "戊午", "戊申", "戊戌", "戊子"),
    "艮": ("丙辰", "丙午", "丙申", "丙戌", "丙子", "丙寅"),
    "震": ("庚子", "庚寅", "庚辰", "庚午", "庚申", "庚戌"),
    "巽": ("辛丑", "辛亥", "辛酉", "辛未", "辛巳", "辛卯"),
    "离": ("己卯", "己丑", "己亥", "己酉", "己未", "己巳"),
    "坤": ("乙未", "乙巳", "乙卯", "癸丑", "癸亥", "癸酉"),
    "兑": ("丁巳", "丁卯", "丁丑", "丁亥", "丁酉", "丁未"),
}

# 京房八宫：各世卦相对本宫八纯卦的变爻集合（爻位 1~6）与世爻位置
_FLIPS = {"一世": {1}, "二世": {1, 2}, "三世": {1, 2, 3}, "四世": {1, 2, 3, 4},
          "五世": {1, 2, 3, 4, 5}, "游魂": {1, 2, 3, 5}, "归魂": {5}}
_SHI_POS = {"本宫": 6, "一世": 1, "二世": 2, "三世": 3, "四世": 4, "五世": 5,
            "游魂": 4, "归魂": 3}

# 六神起例：甲乙起青龙、丙丁起朱雀、戊起勾陈、己起螣蛇、庚辛起白虎、壬癸起玄武
_LIUSHEN = ["青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武"]
_LIUSHEN_START = {"甲": 0, "乙": 0, "丙": 1, "丁": 1, "戊": 2,
                  "己": 3, "庚": 4, "辛": 4, "壬": 5, "癸": 5}

# 四象：爻值 → (阴阳, 是否动爻, 名称)
_YAO_KIND = {
    6: ("阴", True, "老阴（交×）"),
    7: ("阳", False, "少阳（单）"),
    8: ("阴", False, "少阴（拆）"),
    9: ("阳", True, "老阳（重○）"),
}

_CHONG = {"子": "午", "午": "子", "丑": "未", "未": "丑", "寅": "申", "申": "寅",
          "卯": "酉", "酉": "卯", "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳"}


def _build_gong_table() -> dict[str, tuple[str, int]]:
    """六十四卦 → (所属宫, 世爻位置)，由京房八宫变卦规则生成。"""
    table: dict[str, tuple[str, int]] = {}
    for gong in gua.XIANTIAN_NUM:
        base = list(gua.GUA_LINES[gong]) + list(gua.GUA_LINES[gong])
        table[gua.hexagram_name(gong, gong)] = (gong, _SHI_POS["本宫"])
        for kind, flips in _FLIPS.items():
            lines = [1 - v if (i + 1) in flips else v for i, v in enumerate(base)]
            up, down = gua.gua_of_lines(lines)
            table[gua.hexagram_name(up, down)] = (gong, _SHI_POS[kind])
    return table


GUA_GONG = _build_gong_table()


def _liuqin(gong_wx: str, zhi_wx: str) -> str:
    """以卦宫五行为我取六亲。"""
    return {"比和": "兄弟", "生我": "父母", "我生": "子孙",
            "克我": "官鬼", "我克": "妻财"}[gua.relation(gong_wx, zhi_wx)]


def _ying_of(shi: int) -> int:
    """应爻与世爻相隔三位。"""
    return shi + 3 if shi <= 3 else shi - 3


def _najia_lines(up: str, down: str) -> list[str]:
    """六爻纳甲干支（自下而上）。"""
    return list(NAJIA[down][:3]) + list(NAJIA[up][3:])


def _ganzhi_index(ganzhi: str) -> int:
    """干支（如「丁酉」）在六十甲子中的序号，0 为甲子。"""
    g, z = gua.TIANGAN.index(ganzhi[0]), gua.DIZHI.index(ganzhi[1])
    for i in range(60):
        if i % 10 == g and i % 12 == z:
            return i
    return 0  # 理论上不可达


def _xun_kong(day_ganzhi: str) -> list[str]:
    """日辰旬空（空亡两支）。"""
    n = _ganzhi_index(day_ganzhi)
    xun_start = (n - n % 10) % 12  # 旬首地支序号
    return [gua.DIZHI[(xun_start + 10) % 12], gua.DIZHI[(xun_start + 11) % 12]]


def toss_yao() -> int:
    """掷三枚铜钱得一爻：背数 0/1/2/3 → 老阴/少阴/少阳/老阳。"""
    backs = sum(random.randint(0, 1) for _ in range(3))
    return {0: 6, 1: 8, 2: 7, 3: 9}[backs]


def divine(yao_values: list[int] | None, question: str,
           when: datetime | None = None, longitude: float | None = None,
           use_true_solar_time: bool = True) -> dict:
    """装卦。yao_values 为 6 个爻值（6/7/8/9，自下而上）；缺省则自动摇卦。"""
    from app.services.bazi import apply_true_solar_time

    cast_dt = when or datetime.now()
    if use_true_solar_time:
        cast_dt, note = apply_true_solar_time(cast_dt, longitude)
    else:
        note = None

    auto = not yao_values
    if auto:
        yao_values = [toss_yao() for _ in range(6)]
    if len(yao_values) != 6 or any(v not in _YAO_KIND for v in yao_values):
        raise ValueError("需给出 6 个爻值，取值只能是 6（老阴）/7（少阳）/8（少阴）/9（老阳）")

    lunar = Solar.fromDate(cast_dt).getLunar()
    ec = lunar.getEightChar()
    day_ganzhi = ec.getDay()
    month_zhi = ec.getMonth()[-1]        # 月建取节气月支
    day_gan = day_ganzhi[0]
    kong = _xun_kong(day_ganzhi)

    lines = [1 if v in (7, 9) else 0 for v in yao_values]
    up, down = gua.gua_of_lines(lines)
    ben_name = gua.hexagram_name(up, down)
    gong, shi = GUA_GONG[ben_name]
    gong_wx = gua.GUA_WUXING[gong]
    najia = _najia_lines(up, down)
    dong_yaos = [i + 1 for i, v in enumerate(yao_values) if _YAO_KIND[v][1]]

    # 变卦（无动爻则不变）
    bian_name = bian_najia = None
    bian_gong_wx = None
    if dong_yaos:
        bian_lines = [1 - lines[i - 1] if i in dong_yaos else lines[i - 1]
                      for i in range(1, 7)]
        b_up, b_down = gua.gua_of_lines(bian_lines)
        bian_name = gua.hexagram_name(b_up, b_down)
        bian_najia = _najia_lines(b_up, b_down)
        bian_gong_wx = gua.GUA_WUXING[GUA_GONG[bian_name][0]]

    # 伏神：本卦缺某六亲时，取本宫八纯卦中该六亲所在爻
    ben_qin = {_liuqin(gong_wx, gua.ZHI_WUXING[n[1]]) for n in najia}
    fu_yaos: dict[int, str] = {}
    for pos, n in enumerate(NAJIA[gong], start=1):
        qin = _liuqin(gong_wx, gua.ZHI_WUXING[n[1]])
        if qin not in ben_qin:
            fu_yaos.setdefault(pos, f"{n}（{qin}）")
    missing_qin = [q for q in ["父母", "兄弟", "子孙", "妻财", "官鬼"] if q not in ben_qin]

    yaos = []
    for pos in range(1, 7):
        v = yao_values[pos - 1]
        yin_yang, is_dong, label = _YAO_KIND[v]
        zhi = najia[pos - 1][1]
        item = {
            "pos": pos,
            "name": gua.yao_name(pos),
            "value": v,
            "kind": label,
            "yin_yang": yin_yang,
            "dong": is_dong,
            "najia": najia[pos - 1],
            "zhi": zhi,
            "wuxing": gua.ZHI_WUXING[zhi],
            "liuqin": _liuqin(gong_wx, gua.ZHI_WUXING[zhi]),
            "liushen": _LIUSHEN[(_LIUSHEN_START[day_gan] + pos - 1) % 6],
            "shi": pos == shi,
            "ying": pos == _ying_of(shi),
            "kong": zhi in kong,
            "yue_po": _CHONG[zhi] == month_zhi,
            "ri_chong": _CHONG[zhi] == day_ganzhi[1],
            "fu": fu_yaos.get(pos),
            "bian_najia": bian_najia[pos - 1] if bian_najia and is_dong else None,
            "bian_liuqin": _liuqin(bian_gong_wx, gua.ZHI_WUXING[bian_najia[pos - 1][1]])
            if bian_najia and is_dong else None,
        }
        yaos.append(item)

    cat = gua.classify_question(question)
    return {
        "kind": "auto" if auto else "manual",
        "cast_time": cast_dt.strftime("%Y-%m-%d %H:%M"),
        "true_solar_time": cast_dt.strftime("%Y-%m-%d %H:%M") if note else None,
        "lunar_text": f"{lunar.getYearInGanZhi()}年{abs(lunar.getMonth())}月"
                      f"{lunar.getDay()}日{lunar.getTimeZhi()}时",
        "month_jian": f"{month_zhi}（{gua.ZHI_WUXING[month_zhi]}）",
        "day_ganzhi": day_ganzhi,
        "xun_kong": kong,
        "ben_gua": ben_name,
        "ben_lines": lines,
        "gong": gong,
        "gong_wuxing": gong_wx,
        "shi_yao": shi,
        "ying_yao": _ying_of(shi),
        "dong_yaos": dong_yaos,
        "bian_gua": bian_name,
        "bian_lines": bian_lines if dong_yaos else None,
        "yaos": yaos,
        "missing_liuqin": missing_qin,
        "fushen_text": "、".join(f"{gua.yao_name(p)}{t}" for p, t in sorted(fu_yaos.items())) or None,
        "question": question,
        "category": cat,
    }


def summary_lines(chart: dict) -> list[str]:
    """卦象摘要（供生成层拼 prompt）。"""
    lines = [
        f"起卦时间：{chart['cast_time']}（{chart['lunar_text']}），"
        f"{'系统自动摇卦' if chart['kind'] == 'auto' else '手动录入爻象'}",
        f"月建：{chart['month_jian']}　日辰：{chart['day_ganzhi']}　"
        f"旬空：{'、'.join(chart['xun_kong'])}",
        f"本卦：{chart['ben_gua']}（{chart['gong']}宫，{chart['gong']}属{chart['gong_wuxing']}），"
        f"世爻{chart['shi_yao']}爻、应爻{chart['ying_yao']}爻",
        f"动爻：{'、'.join(gua.yao_name(p) for p in chart['dong_yaos']) or '六爻安静'}",
        f"变卦：{chart['bian_gua'] or '无（静卦）'}",
    ]
    if chart["missing_liuqin"]:
        lines.append(f"卦中缺{('、'.join(chart['missing_liuqin']))}，"
                     f"伏神：{chart['fushen_text']}")
    lines.append("六爻装卦（自初爻至上爻）：")
    for y in chart["yaos"]:
        flags = []
        if y["shi"]:
            flags.append("世")
        if y["ying"]:
            flags.append("应")
        if y["dong"]:
            flags.append("动")
        if y["kong"]:
            flags.append("旬空")
        if y["yue_po"]:
            flags.append("月破")
        if y["ri_chong"]:
            flags.append("日冲")
        row = (f"  {y['name']}：{y['liuqin']}{y['najia']}（{y['wuxing']}）"
               f"{y['yin_yang']}，六神{y['liushen']}")
        if y["fu"]:
            row += f"，伏神{y['fu']}"
        if flags:
            row += f"，{'/'.join(flags)}"
        if y["bian_najia"]:
            row += f"，动化{y['bian_najia']}（{y['bian_liuqin']}）"
        lines.append(row)
    lines.append(f"所问之事：{chart['question']}（属{chart['category']['category']}，"
                 f"参考用神：{chart['category']['yongshen']}）")
    return lines


def build_query(chart: dict, question: str | None = None) -> str:
    """构造古籍检索问题：六爻以六亲、世应、动变、月建日辰为纲。"""
    cat = chart["category"]
    yong = chart["category"]["yongshen"].split("（")[0]
    parts = [
        f"六爻纳甲 {chart['ben_gua']} 世应 用神{yong} 六亲 生克",
        f"月建{chart['month_jian']} 日辰{chart['day_ganzhi']} 旬空 动爻 变卦"
        + (f" {chart['bian_gua']}" if chart["bian_gua"] else " 静卦"),
        f"{cat['category']} 章 断法",
    ]
    q = (question or chart.get("question") or "").strip()
    if q:
        parts.append(q)
    return " ".join(parts)