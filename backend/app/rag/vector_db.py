"""向量库兼容导出层。"""

from app.rag.chunking import split_markdown_with_titles
from app.rag.vector_store import FAISSVectorStore, vector_db_manager

VectorDBManager = FAISSVectorStore

__all__ = [
    "FAISSVectorStore",
    "VectorDBManager",
    "split_markdown_with_titles",
    "vector_db_manager",
]
