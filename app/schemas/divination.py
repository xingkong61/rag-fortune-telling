"""/api/meihua、/api/liuyao 请求与响应模型（卦象类术数）。"""
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.fate import SourceRef


class QuestionCategory(BaseModel):
    """问事归类：梅花取占类、六爻取参考用神。"""
    category: str
    meihua_zhan: str
    yongshen: str


class MeihuaRequest(BaseModel):
    question: str = Field(min_length=1, max_length=200, description="所占之事")
    kind: str = Field(default="time", description="time=时间起卦 / number=报数起卦")
    numbers: list[int] | None = Field(default=None, description="报数起卦的 2~3 个数")
    when: datetime | None = Field(default=None, description="起卦时间，缺省取当前")
    longitude: float | None = None
    latitude: float | None = None
    use_true_solar_time: bool = True
    # true 时返回 SSE 事件流（meta/delta/done），false 时返回完整 JSON
    stream: bool = False

    @model_validator(mode="after")
    def _check(self):
        if self.kind not in ("time", "number"):
            raise ValueError("kind 只能是 time 或 number")
        if self.kind == "number":
            nums = self.numbers or []
            if len(nums) not in (2, 3):
                raise ValueError("报数起卦需给出 2 个或 3 个数字")
            if any(n < 1 for n in nums):
                raise ValueError("报数需为正整数")
        return self


class MeihuaChart(BaseModel):
    kind: str
    cast_time: str
    lunar_text: str | None = None
    seed_text: str
    numbers: list[int] | None = None
    note: str | None = None
    true_solar_time: str | None = None
    shang_gua: str
    xia_gua: str
    shang_symbol: str
    xia_symbol: str
    ben_gua: str
    ben_lines: list[int]
    dong_yao: int
    dong_yao_name: str
    ti_gua: str
    yong_gua: str
    ti_wuxing: str
    yong_wuxing: str
    relation: str
    relation_text: str
    relation_note: str
    hu_gua: str
    hu_shang: str
    hu_xia: str
    bian_gua: str
    bian_shang: str
    bian_xia: str
    bian_lines: list[int]
    gua_xiang: str
    question: str
    category: QuestionCategory


class MeihuaResponse(BaseModel):
    session_id: str
    chart: MeihuaChart
    verdict: str = ""  # 白话结论（由断卦文本分段得到）
    reading: str
    sources: list[SourceRef]
    demo: bool = False


class LiuyaoRequest(BaseModel):
    question: str = Field(min_length=1, max_length=200, description="所占之事")
    yaos: list[int] | None = Field(
        default=None,
        description="六爻爻值（6=老阴 7=少阳 8=少阴 9=老阳），自初爻至上爻；缺省由服务端摇卦",
    )
    when: datetime | None = Field(default=None, description="起卦时间，缺省取当前")
    longitude: float | None = None
    latitude: float | None = None
    use_true_solar_time: bool = True
    # true 时返回 SSE 事件流（meta/delta/done），false 时返回完整 JSON
    stream: bool = False


class YaoInfo(BaseModel):
    pos: int
    name: str
    value: int
    kind: str          # 老阴（交×）/ 少阳（单）/ 少阴（拆）/ 老阳（重○）
    yin_yang: str
    dong: bool
    najia: str
    zhi: str
    wuxing: str
    liuqin: str
    liushen: str
    shi: bool
    ying: bool
    kong: bool         # 旬空
    yue_po: bool       # 月破
    ri_chong: bool     # 日冲
    fu: str | None = None          # 伏神
    bian_najia: str | None = None  # 动爻所化
    bian_liuqin: str | None = None


class LiuyaoChart(BaseModel):
    kind: str
    cast_time: str
    lunar_text: str
    note: str | None = None
    true_solar_time: str | None = None
    month_jian: str
    day_ganzhi: str
    xun_kong: list[str]
    ben_gua: str
    ben_lines: list[int]
    gong: str
    gong_wuxing: str
    shi_yao: int
    ying_yao: int
    dong_yaos: list[int]
    bian_gua: str | None = None
    bian_lines: list[int] | None = None
    yaos: list[YaoInfo]
    missing_liuqin: list[str]
    fushen_text: str | None = None
    question: str
    category: QuestionCategory


class LiuyaoResponse(BaseModel):
    session_id: str
    chart: LiuyaoChart
    verdict: str = ""  # 白话结论（由断卦文本分段得到）
    reading: str
    sources: list[SourceRef]
    demo: bool = False