🍵 凤城云图 (Fengcheng-Yuntu) · 泰州智能文旅规划系统
凤城云图 是一套专为江苏泰州深度定制的 AI 智能文旅规划与地理可视化系统。系统融合了 DeepSeek-Chat 大语言模型、Hybrid RAG 混合知识检索（BM25 + ChromaDB + RRF）、高德地图 Web/JS API 空间富化以及实时天气感知引擎，彻底解决了通用大模型在旅行规划中常见的“路线跨区折返、POI 同名漂移、虚假门票与脱离空间坐标”等幻觉问题。

🌟 核心特性与创新亮点
垂直文旅领域建模（泰州特色数据域）：深度构建覆盖海陵早茶（皮包水文化/烫干丝/蟹黄汤包/鱼汤面）、海陵古建园林、姜堰溱湖湿地、兴化水上森林与垛田花海的结构化 Markdown 知识库。
物理空间防折返与 POI 坐标纠偏机制：
结构化空间聚类：Prompt 强约束每日行程收敛于同一行政区。
地名噪声正则清洗：自动剥离“早茶/午餐/打卡/自由活动”等动作后缀与括号干扰。
高德中心城区坐标偏置（Location Bias）：注入泰州核心地理坐标锚点与距离排序算法，杜绝“主城区早茶误漂移至 25km 外郊区同名分店”的跨区飞线缺陷。
高质量 Hybrid RAG 检索引擎：
采用 分块标题上下文增强 机制，消除空分块与断裂分块。
结合 jieba 分词 + BM25 关键词匹配 与 ChromaDB 向量相似度，经 RRF (Reciprocal Rank Fusion) 算法融合重排，精准召回地道文旅要点。
环境与时令动态感知：
集成高德实时天气接口，根据降雨/气温自适应调整游览建议（如室内早茶/展馆替补方案）。
具备时令感知能力（如 9 月出行自动调度兴化千垛万寿菊花海而非春季油菜花）。
沉浸式双向交互大屏：
左侧时间轴卡片与右侧高德地图 3D 轨迹深度联动。
支持点击行程节点平滑飞行（map.setZoomAndCenter）聚焦并弹出带真实景图的定制 InfoWindow。
完整工程闭环与持久化：基于 Pydantic v2 严苛契约定义，集成 SQLAlchemy ORM + SQLite，提供历史行程持久化与完整 RESTful CRUD 接口。

🏗️ 系统架构图
![系统架构图](./框架图.jpg)

📂 项目工程目录结构
fengcheng-yuntu/
├── backend/                         # 后端工程 (FastAPI)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # 服务入口、全局 CORS 与数据表初始化
│   │   ├── config.py                # Pydantic Settings 配置与环境变量读取
│   │   ├── database.py              # SQLite 数据库引擎与 Session 工厂
│   │   ├── schemas/                 # Pydantic 数据传输协议
│   │   │   └── trip.py              # 行程请求、响应、地点、天气契约定义
│   │   ├── models/                  # SQLAlchemy ORM 数据库实体
│   │   │   └── trip.py              # 行程记录持久化表模型
│   │   ├── services/                # 外部三方服务
│   │   │   ├── map_service.py       # 高德 POI 坐标偏置与清洗解析服务
│   │   │   └── weather_service.py   # 泰州天气查询与动态提示服务
│   │   ├── rag/                     # RAG 检索模块
│   │   │   └── hybrid.py            # BM25 + ChromaDB + RRF 混合检索引擎
│   │   ├── agent/                   # LLM 决策与规划
│   │   │   ├── prompt_templates.py  # 泰州文旅专属结构化 Prompt 模板
│   │   │   └── planner.py           # 行程规划 Agent 核心编排器
│   │   └── routes/                  # API 控制器
│   │       └── trip.py              # 行程生成、详情查询与历史记录路由
│   ├── data/
│   │   ├── guides/                  # 泰州垂直高质量 Markdown 攻略库
│   │   │   ├── morning_tea_and_culture.md
│   │   │   ├── wetland_and_ecology.md
│   │   │   └── taizhou_food_and_routes.md
│   │   └── chroma_db/               # Chroma 向量数据库本地持久化目录
│   ├── requirements.txt             # Python 依赖清单
│   └── .env.example                 # 环境变量模板
│
├── frontend/                        # 前端工程 (Vue 3 + Vite)
│   ├── src/
│   │   ├── api/
│   │   │   └── trip.js              # Axios 后端 API 请求封装
│   │   ├── components/
│   │   │   └── MapView.vue          # 高德 JS API 2.0 地图渲染与轨迹连线组件
│   │   ├── App.vue                  # 全屏可视化大屏交互主页
│   │   ├── style.css                # TailwindCSS 全局样式
│   │   └── main.js                  # Vue 入口
│   ├── tailwind.config.js           # Tailwind 配置文件
│   ├── postcss.config.js            # PostCSS 配置文件
│   ├── vite.config.js               # Vite 基础配置
│   └── package.json                 # Node.js 依赖清单
│
└── README.md


🚀 快速启动指南
1. 环境准备
   Python: 3.11（推荐）或 3.10
    Node.js: 18.x 或更高版本

    后端部署与启动
    进入后端目录并创建虚拟环境：
    cd backend
    python -m venv venv
    # 激活虚拟环境 (Windows PowerShell)
    .\venv\Scripts\Activate.ps1
    # 或 Windows CMD: .\venv\Scripts\activate.bat

    安装依赖：
    pip install -r requirements.txt

    配置环境变量：
    在 backend/ 目录下新建 .env 文件，填入你的密钥信息：

    PROJECT_NAME="凤城云图 (Fengcheng-Yuntu)"
    # DeepSeek API 配置
    DEEPSEEK_API_KEY="sk-your-deepseek-api-key"
    DEEPSEEK_BASE_URL="https://api.deepseek.com"
    LLM_MODEL_NAME="deepseek-chat"

    # 高德开放平台 Web 服务 Key (用于后端 POI 检索与天气)
    AMAP_WEB_KEY="your-amap-web-key"
    ENABLE_AMAP_ENRICHMENT=true

    # 数据库配置
    DATABASE_URL="sqlite:///./fengcheng.db"
    启动后端服务：
    uvicorn app.main:app --reload --port 8000