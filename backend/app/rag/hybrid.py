import jieba
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
from app.rag.vector_db import vector_db_manager


class TaizhouHybridRetriever:
    """泰州文旅专用混合检索器 (BM25 + ChromaDB + RRF 融合)"""

    def __init__(self):
        # 1. 初始化底层向量库 (自动完成 Markdown 多级标题切分与 Chroma 索引)
        vector_db_manager.init_vector_db()

        # 2. 复用 vector_db 切好的高质量语料构建 BM25 倒排索引
        self.chunks: List[Dict[str, Any]] = vector_db_manager.get_all_chunks()
        self.tokenized_corpus: List[List[str]] = []

        for chunk in self.chunks:
            tokens = list(jieba.cut_for_search(chunk["text"]))
            self.tokenized_corpus.append(tokens)

        self.bm25: BM25Okapi = BM25Okapi(self.tokenized_corpus) if self.tokenized_corpus else None

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """
        混合检索核心逻辑：
        1. BM25 精确专有名词召回
        2. Chroma 向量语义相似度召回 (调用 vector_db_manager)
        3. RRF (Reciprocal Rank Fusion) 倒数排名融合算法
        """
        if not self.chunks:
            return []

        candidate_k = top_k * 2

        # 1. BM25 关键词候选召回
        query_tokens = list(jieba.cut_for_search(query))
        bm25_ranked_indices = []
        if self.bm25:
            bm25_scores = self.bm25.get_scores(query_tokens)
            bm25_ranked_indices = sorted(
                range(len(bm25_scores)),
                key=lambda i: bm25_scores[i],
                reverse=True
            )[:candidate_k]

        # 2. ChromaDB 向量语义候选召回 (直接复用 vector_db_manager)
        vector_results = vector_db_manager.search(query=query, top_k=candidate_k)
        text_to_idx = {c["text"]: idx for idx, c in enumerate(self.chunks)}

        # 3. RRF 融合打分 (k=60 为经典平滑常数)
        rrf_scores: Dict[int, float] = {}
        k_const = 60

        # 融合 BM25 排名
        for rank, idx in enumerate(bm25_ranked_indices):
            rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (k_const + rank + 1)

        # 融合 向量相似度 排名
        for rank, item in enumerate(vector_results):
            item_text = item.get("text", "")
            if item_text in text_to_idx:
                idx = text_to_idx[item_text]
                rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (k_const + rank + 1)

        # 4. 按 RRF 综合得分排序输出 Top-K 文本
        sorted_indices = sorted(
            rrf_scores.keys(),
            key=lambda i: rrf_scores[i],
            reverse=True
        )[:top_k]

        return [self.chunks[i]["text"] for i in sorted_indices]


# 全局单例实例化，供 planner.py 导入使用
taizhou_retriever = TaizhouHybridRetriever()