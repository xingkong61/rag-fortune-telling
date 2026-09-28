"""全局配置：读取 .env，未配置 Key 时进入演示模式（免 API 跑通管线）。"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # 阿里云 DashScope API Key（https://dashscope.console.aliyun.com/）
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    # Qwen 模型 ID
    llm_model_flash: str = os.getenv("LLM_MODEL_FLASH", "qwen3.8-flash")
    llm_model_max: str = os.getenv("LLM_MODEL_MAX", "qwen3.8-max")
    # 向量模型
    embed_model: str = os.getenv("EMBED_MODEL", "text-embedding-v3")
    # 单次 LLM 请求超时（秒）。需明显小于 Cloudflare 等反代的 100 秒源站超时，
    # 否则超时会被反代拦成 524，用户看不到明确原因。
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "60"))
    # 是否启用模型思考模式。命理解读不需要长思维链，而开启后模型会先长时间输出
    # reasoning_content（实测首字延迟近 97 秒），既拖慢体验又易触发反代超时，故默认关闭。
    llm_enable_thinking: bool = os.getenv(
        "LLM_ENABLE_THINKING", "false"
    ).strip().lower() in ("1", "true", "yes", "on")
    # 检索参数
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "8"))
    rag_min_score: float = float(os.getenv("RAG_MIN_SCORE", "0.35"))
    chroma_dir: str = os.getenv("CHROMA_DIR", "data/chroma")

    @property
    def is_demo(self) -> bool:
        """未配置 Key 时走演示嵌入/生成，便于无 Key 联调管线。"""
        return not self.dashscope_api_key


settings = Settings()