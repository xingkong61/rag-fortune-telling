"""多轮对话会话存储（进程内内存）。

MVP 用内存 dict，服务重启即丢失；阶段 4 可替换为 Redis/SQLite。
"""
import threading

MAX_TURNS = 20  # 每个会话保留的最近消息条数

_lock = threading.Lock()
_sessions: dict[str, dict] = {}


def create(session_id: str, method: str, chart: dict,
           gender: str | None = None) -> None:
    """建立会话。chart 为八字命盘或卦象（与 method 对应）。"""
    with _lock:
        _sessions[session_id] = {"method": method, "chart": chart,
                                 "gender": gender, "messages": []}


def get(session_id: str) -> dict | None:
    return _sessions.get(session_id)


def append(session_id: str, role: str, content: str) -> None:
    with _lock:
        s = _sessions.get(session_id)
        if not s:
            return
        s["messages"].append({"role": role, "content": content})
        s["messages"] = s["messages"][-MAX_TURNS:]


def recent(session_id: str, n: int = 4) -> list[dict]:
    s = _sessions.get(session_id)
    return list(s["messages"][-n:]) if s else []