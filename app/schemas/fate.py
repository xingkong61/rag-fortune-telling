"""/api/fate 请求与响应模型。"""
from datetime import datetime
from pydantic import BaseModel, Field


class FateRequest(BaseModel):
    # 出生时间（北京时间，ISO 格式，如 1995-08-24T14:30:00）
    datetime: datetime
    # 出生地经纬度（用于真太阳时校正，缺省视为东经120度）
    longitude: float | None = None
    latitude: float | None = None
    # 是否做真太阳时（平太阳时近似）校正
    use_true_solar_time: bool = True
    gender: str | None = Field(default=None, description="male/female")
    # true 时返回 SSE 事件流（meta/delta/done），false 时返回完整 JSON
    stream: bool = False


class BaziInfo(BaseModel):
    year: str
    month: str
    day: str
    hour: str
    year_na_yin: str
    month_na_yin: str
    day_na_yin: str
    hour_na_yin: str
    # 四柱天干十神：年/月/时（日干为日主）
    ten_gods: dict[str, str]
    day_master: str  # 日主五行
    wuxing: dict[str, int]  # 五行出现次数统计
    lunar_date: str  # 农历日期
    true_solar_time: str | None = None  # 校正后时间（做了校正时非空）


class SourceRef(BaseModel):
    book: str
    chapter: str
    snippet: str
    score: float


class FateResponse(BaseModel):
    session_id: str
    bazi: BaziInfo
    verdict: str = ""  # 白话结论（由解读文本分段得到）
    reading: str
    sources: list[SourceRef]
    demo: bool = False  # 演示模式标记（未配置 API Key）