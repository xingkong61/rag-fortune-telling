"""文本向量化：DashScope text-embedding-v3。

未配置 API Key 时降级为确定性哈希向量（仅用于无 Key 联调管线，
不保证语义质量，且向量库用独立集合避免与真实向量混用）。
"""
import hashlib
import math

from openai import OpenAI

from config import settings

_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_client: OpenAI | None = None
_DEMO_DIM = 256


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.dashscope_api_key, base_url=_BASE_URL)
    return _client


def _demo_embed(text: str) -> list[float]:
    v = [0.0] * _DEMO_DIM
    for ch in text:
        h = int.from_bytes(hashlib.md5(ch.encode("utf-8")).digest()[:4], "little")
        v[h % _DEMO_DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if settings.is_demo:
        return [_demo_embed(t) for t in texts]
    resp = _get_client().embeddings.create(model=settings.embed_model, input=texts)
    return [d.embedding for d in resp.data]