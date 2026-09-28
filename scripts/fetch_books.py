"""一次性数据准备脚本：从 guoxuehuicui.com 抓取《三命通会》全文并按卷落盘。

《三命通会》（明·万民英）为公有领域古籍。每章一个页面，正文在 <p> 标签中。
用法：python scripts/fetch_books.py
输出：data/books/三命通会.txt（格式：卷一/卷二…分段 + 章节标题行 + 正文）
"""
import os
import re
import sys
import time
import urllib.request

INDEX_URL = "https://www.guoxuehuicui.com/dianji/sanmingtonghui/"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

_ITEM_RE = re.compile(
    r'<li class="small-title"><h2>\s*(卷[一二三四五六七八九十百]*)\s*</h2></li>'
    r'|<a href="(/dianji/sanmingtonghui/(\d+)\.html)">([^<]+)</a>'
)
_P_RE = re.compile(r"<p>(.*?)</p>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_SITE = "https://www.guoxuehuicui.com"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_index(html: str) -> list[tuple[str, str, str]]:
    """返回 [(卷名, URL, 章节名)]，按目录顺序。"""
    chapters: list[tuple[str, str, str]] = []
    vol = ""
    for m in _ITEM_RE.finditer(html):
        if m.group(1):  # 卷标题
            vol = m.group(1)
            continue
        # 章节链接（相对路径）
        url = _SITE + m.group(2)
        name = m.group(4).strip().rstrip("（")
        chapters.append((vol, url, name))
    return chapters


def extract_body(html: str) -> str:
    paras = []
    for p in _P_RE.findall(html):
        txt = _TAG_RE.sub("", p)
        for a, b in [("&nbsp;", " "), ("&ldquo;", "“"), ("&rdquo;", "”"),
                     ("&hellip;", "…"), ("&mdash;", "—"), ("&amp;", "&")]:
            txt = txt.replace(a, b)
        txt = re.sub(r"\s+", "", txt.strip())
        if txt:
            paras.append(txt)
    return "".join(paras)


def main() -> None:
    print("抓取目录页…")
    index_html = fetch(INDEX_URL)
    chapters = parse_index(index_html)
    # 去重（保留首次出现的书内链接）
    seen: set[str] = set()
    unique = []
    for vol, url, name in chapters:
        if url not in seen:
            seen.add(url)
            unique.append((vol, url, name))
    print(f"共发现 {len(unique)} 个章节")

    out_dir = os.path.join("data", "books")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "三命通会.txt")

    prev_vol = ""
    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for vol, url, name in unique:
            if vol != prev_vol:
                f.write(f"\n{vol}\n\n")
                prev_vol = vol
            try:
                body = extract_body(fetch(url))
            except Exception as e:
                print(f"\n跳过 {name}：{e}")
                continue
            if not body:
                continue
            f.write(f"{name}\n{body}\n\n")
            count += 1
            print(".", end="", flush=True)
            time.sleep(0.15)
    print(f"\n完成：{count} 章写入 {out_path}")


if __name__ == "__main__":
    main()