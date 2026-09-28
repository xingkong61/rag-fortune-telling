"""/api/info：城市 → 经纬度（内置常用城市表，供前端自动填坐标）。"""
from fastapi import APIRouter

router = APIRouter()

_CITIES = {
    "北京": (116.41, 39.90),
    "上海": (121.47, 31.23),
    "广州": (113.26, 23.13),
    "深圳": (114.06, 22.55),
    "杭州": (120.16, 30.29),
    "南京": (118.80, 32.06),
    "武汉": (114.31, 30.59),
    "成都": (104.07, 30.67),
    "西安": (108.94, 34.34),
    "郑州": (113.63, 34.75),
    "沈阳": (123.43, 41.80),
    "昆明": (102.71, 25.04),
    "拉萨": (91.14, 29.65),
    "乌鲁木齐": (87.62, 43.83),
    "哈尔滨": (126.64, 45.76),
    "海口": (110.20, 20.04),
}


@router.get("/cities")
def list_cities():
    return {"cities": sorted(_CITIES.keys())}


@router.get("/info")
def city_info(city: str):
    coord = _CITIES.get(city)
    if not coord:
        return {"longitude": None, "latitude": None}
    return {"longitude": coord[0], "latitude": coord[1]}