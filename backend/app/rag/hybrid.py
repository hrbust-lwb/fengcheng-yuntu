import os
import jieba
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
import chromadb
from app.config import settings

class TaizhouHybridRetriever:
    """泰州文旅专用混合检索器 (BM25 + ChromaDB + RRF 融合)"""

    def __init__(self, doc_dir: str = "./data/guides"):
        self.doc_dir = doc_dir
        self.chunks: List[Dict[str, Any]] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: BM25Okapi = None

        # 初始化 ChromaDB 客户端与 Collection
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)

        # 集合名称：taizhou_travel_guides
        self.collection = self.chroma_client.get_or_create_collection(
            name="taizhou_travel_guides",
            metadata={"hnsw:space": "cosine"}
        )

        # 加载与初始化本地 Markdown
        self._load_and_index_documents()

    def _load_and_index_documents(self):
        """解析 Markdown 文档并同步建立 BM25 索引与 ChromaDB 向量库 (优化版)"""
        if not os.path.exists(self.doc_dir):
            return

        documents = []
        metadatas = []
        ids = []
        chunk_idx = 0

        for file_name in sorted(os.listdir(self.doc_dir)):
            if not file_name.endswith(".md"):
                continue

            file_path = os.path.join(self.doc_dir, file_name)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 提取文档主标题 (H1)
            lines = content.splitlines()
            h1_title = "泰州旅游攻略"
            for line in lines:
                if line.startswith("# "):
                    h1_title = line.replace("#", "").strip()
                    break

            # 按二级标题分块
            raw_sections = content.split("\n## ")
            for section in raw_sections:
                section_str = section.strip()
                # 过滤掉仅有主标题的无意义短块
                if not section_str or (section_str.startswith("# ") and len(section_str.splitlines()) <= 2):
                    continue

                # 为每个分块注入主标题上下文，极大提升 BM25 与向量相似度命中率
                clean_text = section_str if section_str.startswith("## ") else f"## {section_str}"
                full_chunk_text = f"【{h1_title}】\n{clean_text}"

                chunk_id = f"tz_doc_{chunk_idx}"
                self.chunks.append({
                    "id": chunk_id,
                    "source": file_name,
                    "doc_title": h1_title,
                    "text": full_chunk_text
                })

                # 中文分词
                tokens = list(jieba.cut_for_search(full_chunk_text))
                self.tokenized_corpus.append(tokens)

                documents.append(full_chunk_text)
                metadatas.append({"source": file_name, "doc_title": h1_title})
                ids.append(chunk_id)
                chunk_idx += 1

        if self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)

        if ids:
            existing_data = self.collection.get()
            if existing_data and existing_data.get("ids"):
                self.collection.delete(ids=existing_data["ids"])

            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"[RAG] 优化后成功索引 {len(ids)} 个高质量泰州文旅知识分块。")

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """
        混合检索核心逻辑：
        1. BM25 精确关键词打分
        2. Chroma 语义向量检索打分
        3. RRF (Reciprocal Rank Fusion) 倒数排名融合算法
        """
        if not self.chunks:
            return []

        # 1. BM25 关键词检索召回候选
        query_tokens = list(jieba.cut_for_search(query))
        bm25_scores = self.bm25.get_scores(query_tokens) if self.bm25 else []
        bm25_ranked_indices = sorted(
            range(len(bm25_scores)),
            key=lambda i: bm25_scores[i],
            reverse=True
        )[:top_k * 2]

        # 2. ChromaDB 向量语义检索召回候选
        chroma_results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k * 2, len(self.chunks))
        )
        retrieved_ids = chroma_results.get("ids", [[]])[0]

        # 3. RRF 融合打分 (k=60 为学术与工程通用平滑常数)
        rrf_scores: Dict[int, float] = {}
        k_const = 60

        for rank, idx in enumerate(bm25_ranked_indices):
            rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (k_const + rank + 1)

        id_to_idx = {c["id"]: i for i, c in enumerate(self.chunks)}
        for rank, cid in enumerate(retrieved_ids):
            if cid in id_to_idx:
                idx = id_to_idx[cid]
                rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (k_const + rank + 1)

        # 4. 排序输出 Top-K 文本
        sorted_indices = sorted(rrf_scores.keys(), key=lambda i: rrf_scores[i], reverse=True)[:top_k]
        return [self.chunks[i]["text"] for i in sorted_indices]

# 全局单例实例化
taizhou_retriever = TaizhouHybridRetriever()