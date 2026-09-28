# 基于 RAG 的算命程序

输入出生信息或所占之事，系统排盘/起卦，从古籍知识库（RAG）检索相关内容，由大模型组织成解读返回，支持多轮追问与流式输出。

**三种术数：**

- **八字命理** — 输入出生日期时间（精确到分钟）与出生地 → 真太阳时校正 → 四柱、十神、纳音、五行分布 → 检索《三命通会》→ 命理解读
- **梅花易数** — 所占之事 + 时间起卦（农历年月日时取数）或报数起卦 → 本卦/互卦/变卦、体用生克 → 检索《梅花易数》→ 断卦
- **六爻纳甲** — 所占之事 + 逐爻录入或一键摇卦 → 纳甲装卦（京房八宫定世应、六亲、六神、旬空月破、伏神、动爻变卦）→ 检索《增删卜易》→ 断卦

## 工作原理

```
用户输入（出生信息 / 所占之事）
   ↓
① 排盘 / 起卦（lunar-python + 真太阳时校正，纯本地计算）
   ↓
② 检索（Chroma 向量召回，按术数方法限定书目，多轮场景先做问句改写）
   ↓
③ 生成（命局/卦象摘要 + 古籍片段 + 出处约束 → Qwen，白话结论与详解分段输出）
   ↓
④ 输出（SSE 逐字上屏，含折叠的引用来源，支持会话内追问）
```

- **流式输出**：首包 `meta`（命盘/卦象卡片）毫秒级下发，正文 `delta` 逐字推送，`done` 收尾带出处，`error` 给出中文兜底提示——避免反代 100 秒超时和长时间白屏。
- **演示模式**：未配置 API Key 时自动降级（哈希向量 + 拼接文本），免 Key 跑通全管线，便于联调。

## 快速开始

要求 Python 3.11+。

```bash
pip install -r requirements.txt

# 配置 DashScope API Key（https://dashscope.console.aliyun.com/）
# 不配置也能跑，但检索与生成均为演示数据
export DASHSCOPE_API_KEY=sk-xxx        # Windows: set DASHSCOPE_API_KEY=sk-xxx

# 古籍入库（首次运行一次；books/*.txt 已内置公版古籍三册）
python scripts/ingest_books.py

# 启动
python main.py                         # http://127.0.0.1:8300
```

浏览器打开 <http://127.0.0.1:8300>，顶部 Tab 选术数方法即可开始。

## 配置项

复制 `.env.example` 为 `.env` 按需修改：

| 变量 | 默认 | 说明 |
|---|---|---|
| `DASHSCOPE_API_KEY` | 空 | 阿里云 DashScope Key，空则进入演示模式 |
| `LLM_MODEL_FLASH` | `qwen3.8-flash` | 默认生成模型 |
| `LLM_MODEL_MAX` | `qwen3.8-max` | 复杂命局 /「详细版」按钮切换 |
| `EMBED_MODEL` | `text-embedding-v3` | 向量模型 |
| `LLM_TIMEOUT` | `60` | 单次 LLM 超时（秒），须小于反代 100 秒源站超时 |
| `LLM_ENABLE_THINKING` | `false` | 思考模式开关（开启后首字延迟可达近百秒） |
| `RAG_TOP_K` | `8` | 检索片段数 |
| `RAG_MIN_SCORE` | `0.35` | 相似度阈值，低于则视为无命中 |
| `CHROMA_DIR` | `data/chroma` | 向量库持久化目录 |

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/fate` | 八字：出生信息 + 经纬度 → 命盘 + 解读（可 `stream: true`） |
| POST | `/api/meihua` | 梅花：所占之事 + 起卦方式 → 卦象 + 断卦 |
| POST | `/api/liuyao` | 六爻：所占之事 + 爻值（缺省自动摇卦）→ 装卦 + 断卦 |
| POST | `/api/chat` | 追问：`{session_id, question}`，按会话记录的方法分流 |
| GET | `/api/info?city=北京` | 城市名 → 经纬度（内置常用城市表） |
| GET | `/healthz` | 健康检查 |

业务端点均支持 `stream` 开关：`false` 返回完整 JSON（便于 curl 调试），`true` 返回 `text/event-stream`，事件为 `meta` / `delta` / `done` / `error`。

示例：

```bash
curl -X POST http://127.0.0.1:8300/api/meihua \
  -H "Content-Type: application/json" \
  -d '{"question": "近期换工作是否顺利", "kind": "number", "numbers": [7, 3]}'
```

## 目录结构

```
├── main.py                 # FastAPI 入口
├── config.py               # 配置（读 .env）
├── app/
│   ├── api/                # 路由：fate / meihua / liuyao / chat / info + SSE 流式层
│   ├── services/           # 业务：bazi / meihua / liuyao / gua / methods / retriever / generator / dialog
│   ├── rag/                # embed（DashScope）/ store（Chroma）
│   └── schemas/            # Pydantic 请求/响应模型
├── static/index.html       # 单页前端（原生 JS，fetch + SSE）
├── data/
│   ├── books/              # 古籍原文（公版）：三命通会 / 梅花易数 / 增删卜易
│   └── chroma/             # 向量库持久化（ingest 脚本生成，不入库）
└── scripts/
    ├── fetch_books.py      # 古籍抓取脚本
    ├── ingest_books.py     # 切卷 → 切块 → 向量化 → 入库
    └── start_public.cmd    # 启动 + cloudflared 临时隧道（公网 HTTPS）
```

## 公网访问

`scripts/start_public.cmd` 会以 `127.0.0.1` 启动服务并开一条 cloudflared 临时隧道（每次 URL 随机）。详细说明与 named tunnel 方案见 [cloudflared快速隧道操作手册.md](cloudflared快速隧道操作手册.md)。

> 注意：隧道暴露后任何拿到 URL 的人都可以调用（消耗你的模型配额），建议仅临时使用，长期对外需自行加鉴权。

## 免责声明

本项目仅用于中国传统术数文化的学习与娱乐，输出内容由 AI 依据古籍文本生成，不构成任何现实决策依据，请勿用于医疗、投资、法律等场景。
