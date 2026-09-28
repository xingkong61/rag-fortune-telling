"""古籍入库脚本：扫描 data/books/*.txt → 按“卷”切分 → 固定窗口切块 → 向量化 → 写入 Chroma。

用法：python scripts/ingest_books.py
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings  # noqa: E402
from app.rag.embed import embed_texts  # noqa: E402
from app.rag.store import VectorStore  # noqa: E402

CHUNK_SIZE = 800   # 每块字符数
OVERLAP = 100      # 相邻块重叠
BATCH = 10         # text-embedding-v3 单次请求输入上限

# 匹配“卷X”“卷X”开头行（全角数字支持）
_VOLUME_RE = re.compile(r"^\s*(卷[一二三四五六七八九十百〇零两]+.*)$", re.M)
# 次一级：匹配“论……”“X曰”等，MVP 先只按卷切，其余并入上一卷
_CLEAN_RE = re.compile(r"[ \t\u3000]+")


def split_by_volume(text: str) -> list[tuple[str, str]]:
    """按‘卷’标题切分，无卷标题则整本视为一卷。"""
    marks = [(m.start(), _CLEAN_RE.sub("", m.group(1))) for m in _VOLUME_RE.finditer(text)]
    if not marks:
        return [("", _CLEAN_RE.sub(" ", text))]
    out = []
    for i, (pos, title) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out.append((title, text[pos:end]))
    return out


def chunk_text(chapter_title: str, content: str, book: str, base_idx: int) -> list[tuple[str, str, str, int]]:
    title = chapter_title or "全书"
    chunks = []
    start, idx = 0, 0
    n = len(content)
    while start < n:
        piece = content[start:start + CHUNK_SIZE].strip()
        if piece:
            chunks.append((book, title if idx == 0 else f"{title}·{idx + 1}", piece, base_idx))
        start += CHUNK_SIZE - OVERLAP
        idx += 1
    return chunks


def main() -> None:
    books_dir = os.path.join("data", "books")
    files = sorted(glob.glob(os.path.join(books_dir, "*.txt")))
    if not files:
        print(f"未找到古籍文本，请将 .txt 放入 {books_dir}/ （UTF-8 编码）")
        return

    store = VectorStore(settings.chroma_dir)
    all_chunks: list[tuple[str, str, str, int]] = []
    for fp in files:
        book = os.path.splitext(os.path.basename(fp))[0]
        with open(fp, encoding="utf-8", errors="replace") as f:
            text = f.read()
        chapters = split_by_volume(text)
        for ci, (title, content) in enumerate(chapters):
            all_chunks.extend(chunk_text(title, content, book, ci * 10000 + 0))
        print(f"《{book}》：{len(chapters)} 卷")

    print(f"共切分 {len(all_chunks)} 块，开始向量化入库（Batch={BATCH}）…")
    ids, docs, metas = [], [], []
    for i, (book, chap, piece, _idx) in enumerate(all_chunks):
        uid = f"{book}::{i}"
        ids.append(uid)
        docs.append(piece)
        metas.append({"book": book, "chapter": chap, "idx": i})

    for b in range(0, len(ids), BATCH):
        seg = slice(b, b + BATCH)
        embs = embed_texts(docs[seg])
        store.upsert(ids[seg], embs, docs[seg], metas[seg])
        print(f"  {min(b + BATCH, len(ids))}/{len(ids)}")

    print(f"完成，库内共 {store.count()} 块。集合：{store.collection.name}")


if __name__ == "__main__":
    main()