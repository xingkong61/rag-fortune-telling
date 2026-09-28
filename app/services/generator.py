"""生成服务：OpenAI 兼容接口调用 Qwen，把卦象/命局 + 古籍片段组织成解读。

未配置 Key 时返回演示文本（拼接检索结果），便于端到端联调。
各术数方法的系统提示词按 method 区分：bazi（子平）/ meihua（梅花易数）/ liuyao（六爻纳甲）。
"""
from collections.abc import Iterator

from openai import APIConnectionError, APITimeoutError, OpenAI

from config import settings

_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 问句改写是短任务，单独给更短超时，避免拖长首字节前的静默时间
_REWRITE_TIMEOUT = 20.0

# DashScope 兼容模式：思考模式开关（各请求共用）
_THINKING = {"extra_body": {"enable_thinking": settings.llm_enable_thinking}}

# 卦象/命局摘要在 prompt 中的标题
_HEADERS = {"bazi": "命局信息", "meihua": "起卦信息", "liuyao": "卦象信息"}

SYSTEM_PROMPTS = {
    "bazi": (
        "你是一位精通子平命理（八字学）、文笔雅致温润的命理顾问。"
        "你会收到用户的命局摘要和从古籍中检索到的命理内容片段。"
        "输出必须严格分成两段，每段以自己的标记起头，标记前后不要添加任何其它文字："
        "【结论】用 3~5 句白话直说结果：这造命局总体如何、最大的长处与短板、宜进取还是宜守成；"
        "不用古文、不使用未经解释的命理术语、不引经据典、不与下文重复。"
        "【详解】再写 200~400 字的正式解读，条理分明、通俗中有古意。"
        "必须遵守："
        "1) 只依据给定的命局与古籍片段展开，不得编造未给出的结论或吉凶；"
        "2) 引用古籍观点时用 [来源：书名·章节] 标注；"
        "3) 若检索到的古籍内容与命局关联有限，须明说「古籍对您这一造的直接记载有限，以下为一般性提示」。"
    ),
    "meihua": (
        "你是一位精通《梅花易数》的易学顾问，文笔简净而有古意。"
        "你会收到起卦信息（起卦方式、本卦、动爻、体用生克、互卦、变卦、卦象类象）、所占之事，"
        "以及从《梅花易数》《周易》等古籍中检索到的片段。"
        "输出必须严格分成两段，每段以自己的标记起头，标记前后不要添加任何其它文字："
        "【结论】用 3~5 句白话直说结果：此事成与不成、凭何而吉或因何受阻、宜进还是宜守；"
        "不用古文、不使用未经解释的术数术语、不引经据典、不与下文重复。"
        "【详解】再写 200~400 字的正式断卦解读，先明卦象与体用关系，再断吉凶与事势趋向，最后给出建议。"
        "必须遵守："
        "1) 以体用生克为断卦纲领，只依据给定卦象展开，不得编造未给出的吉凶；"
        "2) 引用古籍观点时用 [来源：书名·章节] 标注；"
        "3) 若检索片段与所占之事关联有限，须明说「古籍对此的直接记载有限，以下为依卦象常理的提示」。"
    ),
    "liuyao": (
        "你是一位精通六爻纳甲（《增删卜易》《卜筮正宗》一路）的卜筮专家，文笔简净而有古意。"
        "你会收到装卦结果（本卦及其卦宫、世应、六亲、六神、动爻与变卦、月建日辰、旬空、参考用神），"
        "以及检索到的古籍片段。"
        "输出必须严格分成两段，每段以自己的标记起头，标记前后不要添加任何其它文字："
        "【结论】用 3~5 句白话直说结果：此事成与不成、何时见分晓、宜进还是宜守；"
        "不用古文、不使用未经解释的术数术语、不引经据典、不与下文重复。"
        "【详解】再写 200~400 字的正式断卦解读，先取用神并论其旺衰生克，"
        "再看世应与动爻、变爻的生克吉凶，最后给出应期与建议。"
        "必须遵守："
        "1) 以所给卦象、月建日辰为依据，只依据给定信息断卦，不得编造未给出的吉凶；"
        "2) 引用古籍观点时用 [来源：书名·章节] 标注；"
        "3) 若检索片段与所占之事关联有限，须明说「古籍对此的直接记载有限，以下为依六爻常法的提示」。"
    ),
}

CHAT_SYSTEM_PROMPTS = {
    "bazi": (
        "你是一位精通子平命理（八字学）、文笔雅致温润的命理顾问。"
        "用户已获得命局的基础解读，现提出追问。你会收到命局摘要、近期对话和与该追问相关的古籍片段。"
        "请针对追问作答，150–300 字，条理分明。必须遵守："
        "1) 只依据命局与古籍片段展开，不得编造未给出的结论或吉凶；"
        "2) 引用古籍观点时用 [来源：书名·章节] 标注；"
        "3) 若检索到的古籍内容与追问关联有限，须明说「古籍对此的直接记载有限，以下为一般性提示」。"
    ),
    "meihua": (
        "你是一位精通《梅花易数》的易学顾问，文笔简净而有古意。"
        "用户已获得断卦解读，现提出追问。你会收到卦象摘要、近期对话和与该追问相关的古籍片段。"
        "请针对追问作答，150–300 字。必须遵守："
        "1) 仍以体用生克为纲，只依据给定卦象与古籍片段展开，不得编造吉凶；"
        "2) 引用古籍观点时用 [来源：书名·章节] 标注；"
        "3) 若检索片段与追问关联有限，须明说「古籍对此的直接记载有限，以下为依卦象常理的提示」。"
    ),
    "liuyao": (
        "你是一位精通六爻纳甲的卜筮专家，文笔简净而有古意。"
        "用户已获得断卦解读，现提出追问。你会收到卦象摘要、近期对话和与该追问相关的古籍片段。"
        "请针对追问作答，150–300 字。必须遵守："
        "1) 仍以用神、世应、月建日辰为断，不得编造吉凶；"
        "2) 引用古籍观点时用 [来源：书名·章节] 标注；"
        "3) 若检索片段与追问关联有限，须明说「古籍对此的直接记载有限，以下为依六爻常法的提示」。"
    ),
}

REWRITE_PROMPT = (
    "你是术数问答系统的检索助手。用户会给出卦象/命局摘要、此前的追问，以及一个新的追问。"
    "新追问可能省略主语或指代前文（如「那婚姻呢」）。"
    "请把它改写成一句自包含、可用于古籍检索的完整问题，保留原意。"
    "只输出改写后的问题本身，不要作答，不要解释。"
)


# 解读正文的分段标记：白话结论在前，正式详解在后
VERDICT_MARK = "【结论】"
DETAIL_MARK = "【详解】"
_MARKS = {VERDICT_MARK: "verdict", DETAIL_MARK: "reading"}
_HOLD = max(len(m) for m in _MARKS) - 1  # 分片末尾可能被截断的标记长度


def split_sections(chunks: Iterator[str]) -> Iterator[tuple[str, str]]:
    """把流式文本按分段标记切成 (section, text) 增量。

    标记可能被网络分片截断（如上一片结尾是「【结」），故每次保留末尾若干字符待定，
    等下一片到达再判断，流结束时冲刷剩余内容。标记出现前的文字归入 reading，
    这样模型万一没按格式输出，就退化成改造前「只有详解」的样子。
    """
    section = "reading"
    buf = ""
    for chunk in chunks:
        buf += chunk
        while True:
            hit = None
            for mark, sec in _MARKS.items():
                pos = buf.find(mark)
                if pos >= 0 and (hit is None or pos < hit[0]):
                    hit = (pos, mark, sec)
            if hit is None:
                break
            pos, mark, sec = hit
            if pos > 0:
                yield section, buf[:pos]
            section = sec
            buf = buf[pos + len(mark):]
        if len(buf) > _HOLD:
            yield section, buf[:-_HOLD]
            buf = buf[-_HOLD:]
    if buf:
        yield section, buf


def split_verdict(text: str) -> tuple[str, str]:
    """把完整文本拆成 (白话结论, 正式详解)。"""
    parts: dict[str, list[str]] = {"verdict": [], "reading": []}
    for sec, piece in split_sections([text]):
        parts[sec].append(piece)
    return "".join(parts["verdict"]).strip(), "".join(parts["reading"]).strip()


def _get_client() -> OpenAI:
    # 显式超时：避免上游挂起时请求无限等待（流式下为「分片之间」的最大静默时长）
    return OpenAI(api_key=settings.dashscope_api_key, base_url=_BASE_URL,
                  timeout=settings.llm_timeout)


def friendly_error(e: Exception) -> str:
    """把上游异常转成给用户看的中文提示，避免直接抛 524/堆栈。"""
    if isinstance(e, APITimeoutError):
        return (f"模型响应超时（超过 {settings.llm_timeout:.0f} 秒未返回），"
                f"请稍后重试，或把问题问得更具体一些")
    if isinstance(e, APIConnectionError):
        return "无法连接模型服务，请检查网络或 DASHSCOPE_API_KEY 配置"
    return f"生成失败：{e}"


def error_status(e: Exception) -> int:
    """上游异常对应的 HTTP 状态码：超时 504，其余上游故障 502。"""
    return 504 if isinstance(e, APITimeoutError) else 502


def _delta_text(chunk) -> str:
    """从流式分片中取出正文增量（忽略思维链字段）。"""
    choices = getattr(chunk, "choices", None)
    if not choices:
        return ""
    return getattr(choices[0].delta, "content", None) or ""


def _hits_lines(hits: list[dict], limit: int = 220) -> list[str]:
    if not hits:
        return ["（未检索到相关古籍片段）"]
    lines = []
    for i, h in enumerate(hits, 1):
        snippet = h["text"].replace("\n", " ")[:limit]
        lines.append(f"[{i}]《{h['book']}·{h['chapter']}》：{snippet}")
    return lines


def _chart_block(method: str, lines: list[str]) -> list[str]:
    return [f"【{_HEADERS.get(method, '卦象信息')}】", *lines]


def _reading_prompt(method: str, lines: list[str], hits: list[dict],
                    question: str | None) -> str:
    prompt = _chart_block(method, lines)
    prompt += ["", "【古籍检索片段】", *_hits_lines(hits)]
    if question:
        prompt.append(f"\n【本次所问】{question}\n请据此写出解读。")
    return "\n".join(prompt)


def _chat_prompt(method: str, lines: list[str], hits: list[dict],
                 history: list[dict], question: str) -> str:
    prompt = _chart_block(method, lines)
    if history:
        prompt += ["", "【近期对话】"]
        prompt += [f"{'用户' if m['role'] == 'user' else '顾问'}：{m['content'][:200]}"
                   for m in history]
    prompt += ["", "【古籍检索片段】", *_hits_lines(hits)]
    prompt.append(f"\n【本次追问】{question}\n请针对该追问作答。")
    return "\n".join(prompt)


def generate_reading(method: str, lines: list[str], hits: list[dict],
                     question: str | None = None,
                     want_max: bool = False) -> tuple[str, bool]:
    """首轮解读。lines 为卦象/命局摘要（各服务模块的 summary_lines）。"""
    if settings.is_demo:
        return _demo_text(lines, hits, question), True

    model = settings.llm_model_max if want_max else settings.llm_model_flash
    resp = _get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPTS[method]},
            {"role": "user", "content": _reading_prompt(method, lines, hits, question)},
        ],
        temperature=0.4,
        **_THINKING,
    )
    return resp.choices[0].message.content or "", False


def rewrite_query(question: str, lines: list[str], history: list[dict]) -> str:
    """把省略式追问改写成自包含的检索问题。失败或演示模式时回退为原问题。"""
    if settings.is_demo:
        return question
    past = [m["content"][:120] for m in history if m["role"] == "user"][-3:]
    context = ["【卦象/命局摘要】", *lines]
    if past:
        context += ["", "【此前的追问】", *past]
    context += ["", f"【新的追问】{question}"]
    try:
        resp = _get_client().chat.completions.create(
            model=settings.llm_model_flash,
            messages=[
                {"role": "system", "content": REWRITE_PROMPT},
                {"role": "user", "content": "\n".join(context)},
            ],
            temperature=0.0,
            timeout=_REWRITE_TIMEOUT,
            **_THINKING,
        )
        return (resp.choices[0].message.content or "").strip() or question
    except Exception:
        # 改写失败不应中断追问，退回原问题即可
        return question


def generate_chat_answer(method: str, lines: list[str], hits: list[dict],
                         history: list[dict], question: str,
                         want_max: bool = False) -> tuple[str, bool]:
    if settings.is_demo:
        return _demo_text(lines, hits, question), True

    model = settings.llm_model_max if want_max else settings.llm_model_flash
    resp = _get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CHAT_SYSTEM_PROMPTS[method]},
            {"role": "user", "content": _chat_prompt(method, lines, hits, history, question)},
        ],
        temperature=0.4,
        **_THINKING,
    )
    return resp.choices[0].message.content or "", False


def _stream(system_prompt: str, user_prompt: str, want_max: bool):
    """流式调用 LLM，逐段产出正文增量。"""
    model = settings.llm_model_max if want_max else settings.llm_model_flash
    stream = _get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        stream=True,
        **_THINKING,
    )
    for chunk in stream:
        text = _delta_text(chunk)
        if text:
            yield text


def stream_reading(method: str, lines: list[str], hits: list[dict],
                   question: str | None = None, want_max: bool = False):
    """首轮解读的流式版本；演示模式一次性产出全部文本。"""
    if settings.is_demo:
        yield _demo_text(lines, hits, question)
        return
    yield from _stream(SYSTEM_PROMPTS[method],
                       _reading_prompt(method, lines, hits, question), want_max)


def stream_chat_answer(method: str, lines: list[str], hits: list[dict],
                       history: list[dict], question: str,
                       want_max: bool = False):
    """追问回答的流式版本；演示模式一次性产出全部文本。"""
    if settings.is_demo:
        yield _demo_text(lines, hits, question)
        return
    yield from _stream(CHAT_SYSTEM_PROMPTS[method],
                       _chat_prompt(method, lines, hits, history, question), want_max)


def _demo_text(lines: list[str], hits: list[dict], question: str | None) -> str:
    """演示模式文本：同样带分段标记，保证前端分流逻辑被覆盖到。"""
    parts = [VERDICT_MARK, "〔演示模式〕未配置 DASHSCOPE_API_KEY，无实义结论。", DETAIL_MARK,
             "〔演示模式〕以下为管线拼接输出，非实义解读。", *lines]
    if question:
        parts.append(f"所问：{question}")
    parts.append("检索到的古籍片段：")
    for i, h in enumerate(hits, 1):
        parts.append(f"{i}. 《{h['book']}·{h['chapter']}》（相关度 {h['score']}）：{h['text'][:80]}…")
    return "\n".join(parts)