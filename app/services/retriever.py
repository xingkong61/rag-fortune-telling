"""检索引擎：MVP 以向量单路召回，接口预留多路融合（阶段 1 加 BM25）。"""
from config import settings
from app.rag.embed import embed_texts
from app.rag.store import VectorStore


class Retriever:
    def __init__(self):
        self.store = VectorStore(settings.chroma_dir)
        self.top_k = settings.rag_top_k
        self.min_score = settings.rag_min_score

    def retrieve(self, query: str, top_k: int | None = None,
                 books: list[str] | None = None) -> list[dict]:
        """检索古籍片段；books 用于按术数方法限定书目（如梅花只查《梅花易数》）。"""
        k = top_k or self.top_k
        if self.store.count() == 0:
            return []
        emb = embed_texts([query])[0]
        hits = []
        for item in self.store.query(emb, k, books):
            score = 1.0 - item["distance"]  # cosine distance → 相似度
            if score < self.min_score:
                continue
            hits.append({
                "book": item["metadata"].get("book", ""),
                "chapter": item["metadata"].get("chapter", ""),
                "text": item["document"],
                "score": round(score, 4),
            })
        return hits


_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever