"""泰州文旅 Hybrid RAG 检索器。"""

from typing import Any

import jieba
from langfuse.decorators import observe
from rank_bm25 import BM25Okapi

from app.rag.reranker import bge_reranker
from app.rag.vector_store import vector_db_manager


class TaizhouHybridRetriever:
    """融合 BM25、FAISS 候选并使用 BGE Reranker 二次排序。"""

    def __init__(self) -> None:
        vector_db_manager.init_vector_db()
        self.chunks: list[dict[str, Any]] = vector_db_manager.get_all_chunks()
        self.text_to_index = {
            chunk["text"]: index for index, chunk in enumerate(self.chunks)
        }
        tokenized_corpus = [
            list(jieba.cut_for_search(chunk["text"])) for chunk in self.chunks
        ]
        self.bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None

    def _bm25_candidates(self, query: str, limit: int) -> list[int]:
        if self.bm25 is None:
            return []
        query_tokens = list(jieba.cut_for_search(query))
        scores = self.bm25.get_scores(query_tokens)
        return sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )[:limit]

    @staticmethod
    def _rrf_fuse(
        bm25_indices: list[int],
        vector_results: list[dict[str, Any]],
        text_to_index: dict[str, int],
        k_const: int = 60,
    ) -> list[int]:
        scores: dict[int, float] = {}
        for rank, index in enumerate(bm25_indices):
            scores[index] = scores.get(index, 0.0) + 1.0 / (k_const + rank + 1)
        for rank, item in enumerate(vector_results):
            index = text_to_index.get(item.get("text", ""))
            if index is not None:
                scores[index] = scores.get(index, 0.0) + 1.0 / (
                    k_const + rank + 1
                )
        return sorted(scores, key=lambda index: scores[index], reverse=True)

    @observe(name="Hybrid_RAG_Retrieval")
    def retrieve(self, query: str, top_k: int = 3) -> list[str]:
        if not self.chunks:
            return []

        candidate_k = max(top_k * 4, top_k)
        bm25_indices = self._bm25_candidates(query, candidate_k)
        vector_results = vector_db_manager.search(query, top_k=candidate_k)
        fused_indices = self._rrf_fuse(
            bm25_indices,
            vector_results,
            self.text_to_index,
        )

        candidates = []
        for index in fused_indices[:candidate_k]:
            chunk = dict(self.chunks[index])
            chunk["rrf_rank"] = len(candidates) + 1
            candidates.append(chunk)

        reranked = bge_reranker.rerank(query, candidates, top_k=top_k)
        return [item["text"] for item in reranked]


taizhou_retriever = TaizhouHybridRetriever()

