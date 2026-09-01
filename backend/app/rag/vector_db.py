import os
import re
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# 路径配置：定位知识库文档与向量库持久化目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "../../data"))
GUIDES_DIR = os.path.join(DATA_DIR, "guides")
CHROMA_PERSIST_DIR = os.path.join(DATA_DIR, "chroma_db")

COLLECTION_NAME = "taizhou_travel_guides"


def split_markdown_with_titles(content: str, source_name: str, max_chunk_size: int = 400) -> List[Dict[str, Any]]:
    """
    分块标题上下文增强切分算法（加固版）：
    支持 h1/h2/h3 标题路径继承，并自动过滤过短的标点/空白碎片。
    """
    lines = content.split("\n")
    chunks = []

    current_h1 = ""
    current_h2 = ""
    current_h3 = ""
    current_buffer = []

    def flush_buffer():
        if not current_buffer:
            return

        text_block = "\n".join(current_buffer).strip()
        current_buffer.clear()

        # 过滤纯标点或无意义超短块
        if len(text_block) < 15 and not any(c.isalnum() for c in text_block):
            return

        headers = [h for h in [current_h1, current_h2, current_h3] if h]
        header_path = " > ".join(headers) if headers else source_name

        if len(text_block) > max_chunk_size:
            paragraphs = text_block.split("\n- ")
            temp_sub = ""
            for p in paragraphs:
                item = p if p.startswith("- ") else f"- {p}"
                if len(temp_sub) + len(item) > max_chunk_size and len(temp_sub) > 20:
                    chunks.append({
                        "text": f"【{header_path}】\n{temp_sub.strip()}",
                        "source": source_name,
                        "header": header_path
                    })
                    temp_sub = item
                else:
                    temp_sub = f"{temp_sub}\n{item}" if temp_sub else item
            if len(temp_sub.strip()) > 15:
                chunks.append({
                    "text": f"【{header_path}】\n{temp_sub.strip()}",
                    "source": source_name,
                    "header": header_path
                })
        else:
            chunks.append({
                "text": f"【{header_path}】\n{text_block}",
                "source": source_name,
                "header": header_path
            })

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            flush_buffer()
            current_h1 = stripped[2:].strip()
            current_h2 = ""
            current_h3 = ""
        elif stripped.startswith("## "):
            flush_buffer()
            current_h2 = stripped[3:].strip()
            current_h3 = ""
        elif stripped.startswith("### "):
            flush_buffer()
            current_h3 = stripped[4:].strip()
        else:
            if stripped:
                current_buffer.append(stripped)

    flush_buffer()
    return chunks


class VectorDBManager:
    """ChromaDB 向量数据库管理器"""

    def __init__(self, persist_dir: str = CHROMA_PERSIST_DIR):
        self.persist_dir = persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)

        # 初始化持久化 Chroma 客户端
        self.client = chromadb.PersistentClient(path=self.persist_dir)

        # 默认使用通用中文/多语言 Embedding 模型，若本地无 GPU 则自动使用内置 CPU 特征提取器
        try:
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="paraphrase-multilingual-MiniLM-L12-v2"
            )
        except Exception:
            # 兜底使用 Chroma 默认 Embedding
            self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"description": "Taizhou Travel Guides Knowledge Base"}
        )

    def load_markdown_documents(self, guides_dir: str = GUIDES_DIR) -> List[Dict[str, Any]]:
        """从 guides 目录加载并切分所有 Markdown 攻略文件"""
        if not os.path.exists(guides_dir):
            return []

        all_chunks = []
        for filename in os.listdir(guides_dir):
            if filename.endswith(".md"):
                file_path = os.path.join(guides_dir, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                chunks = split_markdown_with_titles(content, source_name=filename)
                all_chunks.extend(chunks)
        return all_chunks

    def init_vector_db(self, force_rebuild: bool = False):
        """初始化向量库，将切分后的知识块存入 ChromaDB"""
        # 如果库中已有数据且不强制重建，则直接跳过
        if self.collection.count() > 0 and not force_rebuild:
            print(f"[VectorDB] 向量库已存在 {self.collection.count()} 条切片索引，跳过初始化。")
            return

        if force_rebuild:
            self.client.delete_collection(COLLECTION_NAME)
            self.collection = self.client.create_collection(
                name=COLLECTION_NAME,
                embedding_function=self.embedding_fn
            )

        chunks = self.load_markdown_documents()
        if not chunks:
            print(f"[VectorDB] 未在 {GUIDES_DIR} 找到可加载的 Markdown 文件。")
            return

        documents = []
        metadatas = []
        ids = []

        for idx, chunk in enumerate(chunks):
            documents.append(chunk["text"])
            metadatas.append({
                "source": chunk["source"],
                "header": chunk["header"]
            })
            ids.append(f"doc_{idx}")

        # 批量写入 Chroma
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"[VectorDB] 成功向量化并索引 {len(documents)} 条文档切片至 ChromaDB。")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """执行向量语义相似度检索"""
        if self.collection.count() == 0:
            self.init_vector_db()

        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, max(1, self.collection.count()))
        )

        formatted_results = []
        if results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results["metadatas"] else [{}] * len(docs)
            distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metas, distances):
                # 距离转换为相似度得分 (距离越小，相似度越高)
                score = round(1.0 / (1.0 + dist), 4)
                formatted_results.append({
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "header": meta.get("header", ""),
                    "score": score
                })

        return formatted_results

    def get_all_chunks(self) -> List[Dict[str, Any]]:
        """获取全部文档切片（供 BM25 建立倒排索引使用）"""
        chunks = self.load_markdown_documents()
        if not chunks and self.collection.count() > 0:
            all_data = self.collection.get()
            for doc, meta in zip(all_data["documents"], all_data["metadatas"]):
                chunks.append({
                    "text": doc,
                    "source": meta.get("source", ""),
                    "header": meta.get("header", "")
                })
        return chunks


# 单例实例供全局调用
vector_db_manager = VectorDBManager()

if __name__ == "__main__":
    # 本地快速测试验证
    print("正在构建/检查向量数据库...")
    vector_db_manager.init_vector_db(force_rebuild=True)
    test_query = "海陵区皮包水早茶哪家最正宗？"
    search_res = vector_db_manager.search(test_query, top_k=3)
    print(f"\n测试查询: '{test_query}'")
    for r in search_res:
        print(f"[{r['score']}] {r['header']} -> {r['text'][:60]}...")