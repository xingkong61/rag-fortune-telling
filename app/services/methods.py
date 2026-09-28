"""术数方法注册表：三种方法（八字 / 梅花易数 / 六爻）的摘要、检索问题与语料范围。

API 层与生成层只依赖本模块，新增术数时在此登记即可。
"""
from app.services import bazi, liuyao, meihua

METHOD_NAMES = {"bazi": "八字命理", "meihua": "梅花易数", "liuyao": "六爻纳甲"}

# 各法检索的古籍范围（须与 data/books/*.txt 的书名一致）
BOOKS: dict[str, list[str]] = {
    "bazi": ["三命通会"],
    "meihua": ["梅花易数"],
    "liuyao": ["增删卜易", "卜筮正宗"],
}

# 各法首轮提问（八字为整体解读，梅花/六爻由前端传入所占之事）
DEFAULT_QUESTIONS = {
    "bazi": "请为我整体解读这个命局",
    "meihua": "请依卦象为我断此事的吉凶",
    "liuyao": "请依卦象为我断此事的吉凶",
}


def is_valid(method: str) -> bool:
    return method in METHOD_NAMES


def summary_lines(method: str, chart: dict, gender: str | None = None) -> list[str]:
    """卦象/命局摘要，供生成层拼 prompt。"""
    if method == "bazi":
        return bazi.summary_lines(chart, gender)
    if method == "meihua":
        return meihua.summary_lines(chart)
    return liuyao.summary_lines(chart)


def build_query(method: str, chart: dict, question: str | None = None,
                gender: str | None = None) -> str:
    """构造该方法的古籍检索问题。"""
    if method == "bazi":
        query = bazi.build_query(chart, gender)
        return f"{query} {question}".strip() if question else query
    if method == "meihua":
        return meihua.build_query(chart, question)
    return liuyao.build_query(chart, question)


def books(method: str) -> list[str] | None:
    """该法限定的书目；返回 None 表示不限。"""
    return BOOKS.get(method)


def question_of(method: str, chart: dict) -> str:
    """首轮所问：梅花/六爻卦象内已存问事，八字为固定话术。"""
    return chart.get("question") or DEFAULT_QUESTIONS.get(method, "请为我解读")