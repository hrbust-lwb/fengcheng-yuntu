# 凤城云图 · 泰州智能文旅规划系统

基于 LangChain + LangGraph 构建的泰州文旅规划 Agent。系统将用户需求解析、本地知识检索、LLM 行程规划、地图路线计算、天气感知和结果校验拆成明确节点，最终生成包含时间、景点、交通、耗时、费用、酒店和次日衔接信息的可执行路书。

## 1. 解决的问题

通用大模型直接生成旅游攻略时，常见问题包括：

- 路线跨区折返，单日行程在多个区县之间反复跳转。
- 景点或酒店出现同名漂移，模型生成了不存在的门店。
- 门票、营业时间、游玩时长和交通耗时缺少可靠依据。
- 天气、距离和路线等实时事实完全依赖模型参数记忆。
- 多日行程的住宿与次日出发地点不连续。
- 多节点 Agent 难以定位是检索、规划、工具调用还是校验环节出错。

凤城云图通过「本地知识库 Hybrid RAG + LangGraph 多节点协同 + Langfuse 全链路追踪 + Docker Tool 沙箱」解决上述问题。

## 2. 核心方案

### LangGraph 多节点工作流

```text
用户需求
   │
   ▼
analyze_requirements   需求解析、日期与天数归一化
   │
   ▼
retrieve_knowledge     FAISS + BM25 + BGE-Reranker + 天气 Tool
   │
   ▼
generate_itinerary     DeepSeek 生成结构化 JSON 行程
   │
   ▼
enrich_routes          POI 坐标纠偏 + 驾车路线计算
   │
   ▼
validate_plan          日期、预算、住宿、时长、坐标与路线校验
   │            │
   │ 校验失败   │ 校验通过
   └──────┐     ▼
          │  build_response
          └─► generate_itinerary（带约束反馈重试）
```

### Hybrid RAG

- Markdown 标题路径增强切分，保留知识块所属章节。
- SentenceTransformer 生成本地向量。
- FAISS 执行向量语义召回。
- jieba + BM25 执行景点、酒店、茶社等实体精确召回。
- RRF 融合 BM25 与 FAISS 排名。
- BGE-Reranker 对候选知识进行二次排序；模型不可用时自动退化为 RRF 排序。

### Tool Calling 与 Docker 沙箱

外部事实通过 Tool 获取，减少模型直接生成路线和天气信息：

- `Amap_Weather_Tool`：实时天气与出行建议。
- `Amap_POI_Search_Tool`：景点、酒店和餐饮坐标富化。
- `Amap_Driving_Route_Tool`：站点间驾车距离与耗时。
- `Tool_Sandbox`：可选的 Docker 隔离执行器，通过只读文件系统、内存、CPU、进程数和超时限制降低异常工具调用影响。

默认 `ENABLE_DOCKER_SANDBOX=false`，保持本地直接调用；启用后使用受限容器执行 Tool。

### 结果校验与自我修正

`validate_plan` 会检查：

- 行程天数与用户日期区间是否一致。
- 每日编号、日期和活动数量是否完整。
- 最后一天之前的最后一个活动是否为明确住宿点。
- 总预算是否超过用户预算 5%。
- 活动时间格式、游玩时长和坐标是否有效。
- 路线距离与驾车耗时是否已补充。

校验失败时，错误信息会回传给 `generate_itinerary`，最多执行两轮约束修正。

### LangFuse 全链路追踪

通过 LangFuse 记录：

- 根 Agent Trace 和每个 LangGraph 节点。
- LLM 输入、输出、模型、Token 与重试次数。
- Retriever、BM25、FAISS 和 Reranker 检索结果。
- 天气、POI、路线等 Tool 调用。
- 最终响应、校验错误、警告和重试次数。

## 3. 工程结构

```text
backend/
├── app/
│   ├── agent/
│   │   ├── graph.py                  # LangGraph 编排
│   │   ├── state.py                  # 图状态定义
│   │   ├── llm.py                    # LLM 与 Prompt 构建
│   │   ├── planner.py                # 兼容入口
│   │   ├── nodes/                    # 需求、检索、规划、路线、校验、响应节点
│   │   └── tools/                    # Tool 调用与 Docker 沙箱
│   ├── rag/
│   │   ├── chunking.py               # Markdown 标题增强切分
│   │   ├── vector_store.py           # FAISS 索引
│   │   ├── reranker.py               # BGE-Reranker
│   │   └── hybrid.py                 # BM25 + FAISS + RRF + Reranker
│   ├── repositories/                 # 行程持久化
│   ├── routes/                       # 生成与历史接口
│   ├── services/                     # 业务服务、地图、天气
│   ├── schemas/                      # Pydantic 契约
│   └── utils/                        # 日期等通用工具
├── docker/tool_sandbox/Dockerfile    # Tool 沙箱镜像
├── data/guides/                      # 泰州文旅 Markdown 知识库
├── test_rag.py
└── test_planner.py

frontend/
└── src/
    ├── App.vue                       # 页面组合
    ├── composables/useTripPlanner.js # 表单与请求状态
    ├── components/                   # 表单、结果、天气、时间轴、预算、地图
    ├── constants/tripOptions.js
    └── api/trip.js
```

## 4. 快速启动

### 后端

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

关键环境变量：

```ini
DEEPSEEK_API_KEY=your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
AMAP_WEB_KEY=your-amap-web-key
FAISS_INDEX_DIR=./data/faiss_index
EMBEDDING_MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2
RERANKER_MODEL_NAME=BAAI/bge-reranker-base
ENABLE_RERANKER=true
ENABLE_DOCKER_SANDBOX=false
```

### 前端

```powershell
cd frontend
npm install
npm run dev
```

### Docker Tool 沙箱（可选）

```powershell
cd backend
docker build -f docker/tool_sandbox/Dockerfile -t fengcheng-tool-sandbox:latest .
```

构建后将 `ENABLE_DOCKER_SANDBOX` 设置为 `true`。

## 5. API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/trip/generate` | 生成并保存完整行程 |
| POST | `/api/v1/trip/generate-stream` | SSE 分阶段返回生成状态 |
| GET | `/api/v1/trip/history/list` | 查询历史行程 |
| GET | `/api/v1/trip/{trip_id}` | 查询行程详情 |
| DELETE | `/api/v1/trip/{trip_id}` | 删除历史行程 |
| GET | `/health` | 健康检查 |

## 6. 验证

```powershell
$env:PYTHONIOENCODING='utf-8'
python test_rag.py
python test_planner.py
```

前端生产构建：

```powershell
cd frontend
npm run build
```

