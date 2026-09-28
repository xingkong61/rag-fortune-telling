"""Chroma 向量库封装（本地持久化）。"""
import chromadb


class VectorStore:
    def __init__(self, persist_dir: str):
        self.client = chromadb.PersistentClient(path=persist_dir)
        # 演示模式与真实模式分开集合，避免向量混用
        suffix = "_demo" if _demo_mode() else ""
        self.collection = self.client.get_or_create_collection(
            f"fate_books{suffix}",
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, ids: list[str], embeddings: list[list[float]],
               documents: list[str], metadatas: list[dict]):
        self.collection.upsert(ids=ids, embeddings=embeddings,
                               documents=documents, metadatas=metadatas)

    def query(self, embedding: list[float], top_k: int,
              books: list[str] | None = None) -> list[dict]:
        where = {"book": {"$in": books}} if books else None
        res = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        out = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            out.append({"document": doc, "metadata": meta, "distance": dist})
        return out

    def count(self) -> int:
        return self.collection.count()


# 避免循环导入：延迟读取 config
def _demo_mode() -> bool:
    from config import settings
    return settings.is_demo