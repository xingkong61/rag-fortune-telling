"""一次性数据准备脚本：从中文维基文库（zh.wikisource.org）抓取术数古籍全文。

《梅花易數》《增刪卜易》为公有领域古籍，按子页面（卷/序/篇）分别抓取后合并落盘。
用法：python scripts/fetch_divination_books.py
输出：data/books/梅花易数.txt、data/books/增删卜易.txt（可选：卜筮正宗.txt）
格式：每页先写“卷X / 序 / 篇名”标题行，再写正文，便于 ingest_books.py 按“卷”切分。
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

API = "https://zh.wikisource.org/w/api.php"
RAW = "https://zh.wikisource.org/w/index.php"
UA = {
    "User-Agent": "RAG-fate-books/1.0 (local data prep; contact: local)",
    "Accept": "application/json",
}
SLEEP = 0.3          # 页间休眠
RETRIES = 3          # 单个请求重试次数
TIMEOUT = 20         # 单次请求超时（秒）

# (输出文件名, 维基文库根标题, 是否必须, 最小字符数阈值)
BOOKS = [
    ("梅花易数", "梅花易數", True, 10000),
    ("增删卜易", "增刪卜易", True, 10000),
    ("卜筮正宗", "卜筮正宗（河潞武子龄校本）", False, 10000),
]

_SECTION_RE = re.compile(r"\|\s*section\s*=\s*([^\n|}]+)")
_HEADING_RE = re.compile(r"^\s*=+\s*(.*?)\s*=+\s*$")


def fetch(url: str) -> str:
    """带重试的 GET，返回文本。"""
    last: Exception | None = None
    for _ in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:  # 网络抖动：重试
            last = e
            time.sleep(1.0)
    raise last if last else RuntimeError("unknown error")


def api(params: dict) -> dict:
    params = dict(params)
    params["format"] = "json"
    url = API + "?" + urllib.parse.urlencode(params)
    return json.loads(fetch(url))


def list_subpages(root: str, must: bool) -> list[str]:
    """列出根页面及其全部子页面标题（prefixsearch ∪ 根页链接）。"""
    titles: set[str] = {root}
    prefix = root + "/"

    # 1) prefixsearch
    try:
        d = api({"action": "query", "list": "prefixsearch",
                 "pssearch": prefix, "pslimit": "200"})
        for p in d.get("query", {}).get("prefixsearch", []):
            t = p.get("title", "")
            if t == root or t.startswith(prefix):
                titles.add(t)
    except Exception as e:
        print(f"  子页面检索失败（prefixsearch）：{e}")

    # 2) 根页面内链（补充 prefixsearch 可能遗漏的条目）
    try:
        d = api({"action": "parse", "page": root, "prop": "links", "redirects": "1"})
        for l in d.get("parse", {}).get("links", []):
            t = l.get("*", "")
            if t.startswith(prefix) and ":" not in t:
                titles.add(t)
    except Exception as e:
        print(f"  子页面检索失败（links）：{e}")

    return _order(root, titles)


def _order(root: str, titles: set[str]) -> list[str]:
    """排序：根页 → 序 → 数字篇（自然序）→ 其它。"""
    def key(t: str):
        sub = t[len(root):].lstrip("/")
        if sub == "":
            return (0, 0, "")
        if sub.startswith("序"):
            return (1, 0, sub)
        m = re.match(r"(\d+)", sub)
        if m:
            return (2, int(m.group(1)), sub)
        return (3, 0, sub)

    return sorted(titles, key=key)


def get_extract(title: str) -> str:
    """取纯文本正文（explaintext）。"""
    d = api({"action": "query", "prop": "extracts", "explaintext": "1",
             "redirects": "1", "titles": title})
    for v in d.get("query", {}).get("pages", {}).values():
        if "missing" in v:
            return ""
        return v.get("extract", "") or ""
    return ""


def get_raw(title: str) -> str:
    """取 wiki 源码（用于提取篇名，并作为纯文本的兜底）。"""
    url = RAW + "?" + urllib.parse.urlencode({"title": title, "action": "raw"})
    return fetch(url)


_TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}")
_LINK_PIPE_RE = re.compile(r"\[\[[^\]|]*\|([^\]]*)\]\]")
_LINK_RE = re.compile(r"\[\[([^\]]*)\]\]")
_TAG_RE = re.compile(r"<[^>]+>")
_TABLE_RE = re.compile(r"\{\|.*?\|\}", re.S)
_FILE_RE = re.compile(r"\[\[(?:File|Image|文件|檔案|图像|圖像):[^\]]*\]\]", re.I)


def clean_wikitext(raw: str) -> str:
    """清理 wiki 源码：模板、链接、表格、HTML 标签、ref 等。"""
    raw = re.sub(r"<onlyinclude>|</onlyinclude>|<noinclude>|</noinclude>|"
                 r"<includeonly>|</includeonly>", "", raw)
    raw = _FILE_RE.sub("", raw)
    raw = _TABLE_RE.sub("", raw)
    for _ in range(4):  # 逐层剥离嵌套模板
        new = _TEMPLATE_RE.sub("", raw)
        if new == raw:
            break
        raw = new
    raw = _LINK_PIPE_RE.sub(r"\1", raw)
    raw = _LINK_RE.sub(r"\1", raw)
    raw = re.sub(r"<ref[^>]*?/>|<ref[^>]*?>.*?</ref>", "", raw, flags=re.S)
    raw = _TAG_RE.sub("", raw)
    raw = raw.replace("'''", "").replace("''", "")
    raw = re.sub(r"^\s*[|!{].*$", "", raw, flags=re.M)  # 表格/参数残留行
    return raw


def tidy(text: str) -> str:
    """逐行清理：去标题等号标记、去行内空白，压缩空行。"""
    lines = []
    for ln in text.replace("\r", "\n").split("\n"):
        m = _HEADING_RE.match(ln)
        if m:
            ln = m.group(1)
        ln = re.sub(r"[ \t\u3000]+", "", ln.strip())
        if ln:
            lines.append(ln)
    return "\n".join(lines)


def section_title(raw: str) -> str:
    m = _SECTION_RE.search(raw)
    return m.group(1).strip() if m else ""


def _dedupe(pages: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], list[str]]:
    """剔除正文已被先前（更大）页面完整包含的页面，返回 (保留页, 被跳过的标题)。"""
    kept: list[tuple[str, str]] = []
    kept_norm: list[str] = []
    dup: list[str] = []
    for title, body in pages:
        nb = re.sub(r"\s+", "", body)
        if nb and any(nb in k for k in kept_norm):
            dup.append(title)
            continue
        kept.append((title, body))
        kept_norm.append(nb)
    return kept, dup


def fetch_book(name: str, root: str, must: bool, min_len: int) -> tuple[bool, int, list[str]]:
    """抓取一本书，返回 (是否成功, 总字符数, 失败页面列表)。"""
    print(f"\n《{name}》：根标题 {root}", flush=True)
    titles = list_subpages(root, must)
    print(f"  发现 {len(titles)} 个页面（含根页）", flush=True)

    pages: list[tuple[str, str]] = []  # (标题, 正文)
    failed: list[str] = []
    for t in titles:
        sub = t[len(root):].lstrip("/") or "序"
        try:
            body = get_extract(t)
            raw = ""
            if not body:  # extracts 不可用时兜底：抓源码并清理
                raw = get_raw(t)
                body = clean_wikitext(raw)
            if not raw:
                try:
                    raw = get_raw(t)
                except Exception:
                    raw = ""
            # 根页用书名作标题（其正文已自带“序”等内部标题）
            title = section_title(raw) or (name if t == root else sub)
            body = tidy(body)
            if not body:
                failed.append(t)
                print(f"  · 跳过（空内容）：{t}", flush=True)
                continue
            pages.append((title, body))
            print(f"  · {t}  ✓ {len(body)} 字", flush=True)
        except Exception as e:
            failed.append(t)
            print(f"  · 跳过 {t}：{e}", flush=True)
        time.sleep(SLEEP)

    # 根页常通过模板嵌入（transclusion）已包含各子页面正文，避免重复入库
    pages, dup = _dedupe(pages)
    if dup:
        print(f"  去重：跳过 {len(dup)} 个与已收页面重复的子页 {dup}", flush=True)

    total = sum(len(b) for _, b in pages)
    if total < min_len:
        print(f"  ! 《{name}》正文仅 {total} 字（< {min_len}），判定为残缺/仅目录，跳过落盘", flush=True)
        return (False, total, failed)

    out_dir = os.path.join("data", "books")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{name}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        for title, body in pages:
            f.write(f"\n{title}\n\n{body}\n\n")
    print(f"  完成：{len(pages)} 页 / {total} 字 → {out_path}")
    return (True, total, failed)


def main() -> None:
    results = []
    for name, root, must, min_len in BOOKS:
        try:
            ok, total, failed = fetch_book(name, root, must, min_len)
        except Exception as e:
            print(f"\n《{name}》抓取失败：{e}")
            ok, total, failed = False, 0, [root]
        results.append((name, ok, total, failed))

    print("\n===== 汇总 =====")
    for name, ok, total, failed in results:
        status = "成功" if ok else "失败/跳过"
        print(f"《{name}》：{status}，{total} 字"
              + (f"，失败 {len(failed)} 页 {failed}" if failed else ""))


if __name__ == "__main__":
    main()