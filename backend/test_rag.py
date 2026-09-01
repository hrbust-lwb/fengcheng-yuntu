from app.rag.hybrid import taizhou_retriever

def run_tests():
    test_queries = [
        "泰州有哪些好吃的早茶店？推荐必点什么？",
        "我想看水上森林和芦苇迷宫，有什么景区推荐？",
        "晚上的凤城河有什么特色演出活动？"
    ]

    print("=" * 60)
    print(" 凤城云图 - 泰州 RAG 检索模块测试 ")
    print("=" * 60)

    for q in test_queries:
        print(f"\n👉 查询问题: {q}")
        results = taizhou_retriever.retrieve(query=q, top_k=2)
        for idx, r in enumerate(results, 1):
            print(f"\n--- [召回知识片段 {idx}] ---")
            print(r.strip())
        print("-" * 60)

if __name__ == "__main__":
    run_tests()