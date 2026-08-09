# 智能面试辅导场景的前后端完整 Web 系统

一个面向计算机与软件相关岗位面试准备场景的智能辅导项目，采用 `Vue 3 + Vite + Pinia + FastAPI + LangGraph + LangChain + Chroma` 架构，支持技术问答、岗位模拟面试、简历定制化提问、多 Agent 执行可视化、项目/会话管理、面试评分、报告导出、ECharts 数据看板、角色化管理后台和 LangSmith 调试。

## 功能概览

- 正式登录体系与 RBAC
  支持邮箱 + 密码注册登录，以及候选人、企业面试官、平台管理员三类角色。默认开发模式使用 SQLite/JSON；启用平台数据库后统一使用 MySQL。

- 技术问答模式  
  支持围绕技术知识点、面试题和岗位准备进行多轮问答；问答模式下具备 Tool Calling 能力，可根据问题自动决定是否调用天气或知识库工具。

- 模拟面试模式  
  支持按岗位进行模拟面试，并结合回答质量动态追问、提示、切题或结束。

- 简历定制化提问  
  支持上传简历，系统会结合岗位要求和简历内容生成更贴近真实面试场景的问题。

- 知识库导入与 RAG 检索  
  支持导入 `pdf / txt / md / docx` 文档，完成解析、切分、向量化与检索增强生成。

- 面试评分与报告生成  
  面试结束后可生成分数、结构化报告，并将报告保存为本地 Markdown 文件，同时沉淀到历史记录列表。

- 历史面试记录列表  
  支持查看过往面试记录、分数、报告详情，并可恢复到当前工作台继续复盘。

- 首页引导与项目/会话管理  
  提供首页落地页、首次使用引导、主题模式切换，以及项目文件夹、会话的新建、重命名、删除、置顶和切换。

- 真流式输出与中断兜底  
  基于 HTTP 流式响应实现实时输出，支持手动停止、继续生成、重试本轮回答和中断恢复。

- LangSmith 调试  
  支持按需开启 LangSmith tracing，用于观测问答、知识库导入、模拟面试和报告生成链路。

- LangGraph 多 Agent 工作流
  使用 Router、Resume Analyst、Interview Planner、Interview、Evaluation、Evidence Judge 和 Report 节点编排面试流程，并由规则状态机控制追问、切题和结束。

- 混合检索与引用
  使用 Chroma 向量召回与 BM25 关键词召回，通过 RRF 融合和 Rerank 重排，返回文档来源和分片编号。

- 角色化管理后台
  企业面试官可查看组织内候选人、面试任务和报告，并管理模板与题库；平台管理员还可管理用户、组织、角色、Prompt 版本、Agent Runs 和自动评测指标。

- 前后台配置联动与数据看板
  后台新增岗位模板、题库和评分维度后，前台模拟面试会读取最新岗位配置；后台使用 ECharts 展示 Agent 运行状态、延迟趋势、候选人得分趋势、岗位任务分布和题库覆盖情况。

## 前后端实现

### 前端

- 技术栈：`Vue 3 + Vite + Vue Router + Pinia + JavaScript + CSS + ECharts`
- 主要职责：
  - 组织登录页、首页落地页、问答页、模拟面试页、历史记录页
  - 使用 Vue Router 管理首页、工作台和不同模式页面跳转
  - 管理响应式状态、文件上传、模式切换和错误提示
  - 支持项目/会话树、首次引导弹窗、主题模式和空状态提示
  - 普通请求使用 `axios`
  - 流式请求使用 `fetch + ReadableStream + getReader()`
  - 实现长列表渐进渲染、自动滚动、骨架屏、懒加载和移动端适配
  - 展示 Agent 节点执行过程、检索状态、运行结果和引用证据
  - 提供企业面试官与平台管理员管理页面，并执行前后端双重权限校验
  - 使用 ECharts 封装图表卡片，展示 Agent 观测和面试业务统计数据

### 后端

- 技术栈：`FastAPI + Python`
- 主要职责：
  - 提供注册登录、问答、模拟面试、文件上传、历史记录和报告下载接口
  - 本地开发可使用 SQLite + JSON；正式数据模式使用 MySQL + SQLAlchemy + Alembic
  - Redis 保存 Agent Run 进度、取消状态和断线恢复所需的短期事件
  - 使用 LangGraph 编排多 Agent，并结合 LangChain、DeepSeek、Tool Calling 和规则状态机
  - 托管前端构建产物

## 面试场景专项设计

- 面试状态机  
  将模拟面试拆成提问、追问、提示、切题、结束等状态，用状态机控制流程，而不是完全交给模型自由发挥。

- 追问 / 切题策略  
  为单题设置追问上限，并结合回答质量判断是否继续深挖、先给提示，还是切换到下一题，避免模型一直围绕同一问题反复追问。

- 简历驱动的定制化面试  
  上传简历后，系统会优先围绕简历中的项目、职责和技术选型提问；未上传简历时，则按岗位通用能力推进。

- 后台配置驱动面试流程
  企业面试官可在后台维护岗位模板、题库和能力维度；开始面试时后端读取对应模板，将维度计划和题库参考注入面试 Agent，使提问更贴合岗位配置。

- 流式输出 + 中断恢复  
  支持消息占位、流式输出、手动停止、继续生成和重试本轮回答；刷新页面时会把未完成回复标记为 `interrupted`，避免长时间卡在“生成中”。

- 历史面试复盘  
  每次生成报告后都会写入 SQLite，并保存独立报告文件；前端可查看历史记录、下载报告或恢复历史面试到当前工作台。

## 技术栈

- 前端：Vue 3、Vite、Vue Router、Pinia、JavaScript、CSS、ECharts
- 后端：FastAPI、Python
- AI 应用：LangGraph、LangChain、DeepSeek API、Prompt Engineering、Tool Calling
- 检索增强：RAG、Chroma、BM25、RRF、Rerank、Embedding、多格式文档解析
- 持久化：MySQL、SQLAlchemy、Alembic、Redis；SQLite/JSON 本地降级
- 调试观测：LangSmith

## 项目结构

```text
.
├─ frontend/
│  ├─ index.html
│  ├─ package.json
│  ├─ vite.config.js
│  └─ src/
│     ├─ App.vue
│     ├─ main.js
│     ├─ styles.css
│     ├─ api/
│     ├─ components/
│     ├─ composables/
│     ├─ constants/
│     ├─ router/
│     ├─ stores/
│     ├─ types/
│     ├─ views/
│     ├─ constants.js
│     └─ utils/
├─ main.py
├─ agent/
├─ rag/
├─ routers/
├─ services/
├─ infrastructure/
├─ evaluation/
├─ migrations/
├─ scripts/
├─ tests/
├─ utils/
│  ├─ auth_store.py
│  ├─ user_history_store.py
│  └─ langsmith_handler.py
├─ config/
├─ prompts/
├─ data/
│  ├─ app.db
│  ├─ interview_reports/
│  ├─ uploaded_knowledge/
│  ├─ uploaded_resumes/
│  └─ user_histories/
└─ requirements.txt
```

## 环境与启动

### 1. 激活虚拟环境

当前服务器默认使用 Conda 环境：

```bash
conda activate interviewEnv
```

如果是第一次在新服务器上创建环境，可以执行：

```bash
conda create -n interviewEnv python=3.12
conda activate interviewEnv
```

### 2. 安装后端依赖

```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

如果使用 MySQL 正式数据模式，并且登录时出现 `cryptography package is required`，补装：

```bash
pip install cryptography
```

### 3. 配置环境变量

建议通过 `.env` 或系统环境变量配置：

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.siliconflow.cn/v1
DEEPSEEK_MODEL=deepseek-ai/DeepSeek-V4-Flash

EMBEDDING_API_KEY=your_api_key
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B

WEATHER_API_KEY=your_weather_api_key
LANGCHAIN_API_KEY=your_langsmith_api_key

# 可选：启用正式数据与运行状态层
ENABLE_PLATFORM_DB=true
DATABASE_URL=mysql+pymysql://interview:interview@127.0.0.1:3306/interviewSys?charset=utf8mb4
REDIS_URL=redis://127.0.0.1:6379/0
ADMIN_EMAILS=admin@qq.com
INTERVIEWER_EMAILS=interviewer@qq.com
```

不准备 MySQL/Redis 时，将 `ENABLE_PLATFORM_DB=false` 并留空 `REDIS_URL`，系统会继续使用原有 SQLite、JSON 和内存运行状态，适合普通开发调试。

### 4. MySQL 安装、启动与初始化

MySQL 是正式模式下的业务数据库，用来保存用户、组织、角色、项目、会话、面试任务、题库、报告和 Agent Run 等结构化数据。账号注册成功不代表数据库服务一直在运行；每次重启服务器后，需要先确认 MySQL 服务已启动。

如果没有 sudo 权限，可以在 Conda 环境里安装 MySQL：

```bash
conda activate interviewEnv
conda install -c conda-forge mysql
```

确认命令存在：

```bash
which mysqld
which mysql
which mysqladmin
```

首次初始化本地 MySQL 数据目录，只在 `$MYSQL_DATA` 为空时执行一次：

```bash
export MYSQL_DATA="$HOME/.local/mysql-data"
export MYSQL_RUN="$HOME/.local/mysql-run"

mkdir -p "$MYSQL_DATA" "$MYSQL_RUN"
chmod 700 "$MYSQL_DATA" "$MYSQL_RUN"

mysqld --no-defaults \
  --initialize-insecure \
  --basedir="$CONDA_PREFIX" \
  --datadir="$MYSQL_DATA"
```

每次启动 MySQL：

```bash
export MYSQL_DATA="$HOME/.local/mysql-data"
export MYSQL_RUN="$HOME/.local/mysql-run"

mkdir -p "$MYSQL_DATA" "$MYSQL_RUN"

mysqld --no-defaults \
  --basedir="$CONDA_PREFIX" \
  --datadir="$MYSQL_DATA" \
  --socket="$MYSQL_RUN/mysql.sock" \
  --pid-file="$MYSQL_RUN/mysql.pid" \
  --log-error="$MYSQL_RUN/mysql.err" \
  --bind-address=127.0.0.1 \
  --port=3306 &
```

确认 MySQL 是否启动成功：

```bash
mysqladmin --socket="$MYSQL_RUN/mysql.sock" -u root --skip-password ping
```

如果已经给 root 设置过密码，则改用：

```bash
mysqladmin --socket="$MYSQL_RUN/mysql.sock" -u root -p ping
```

首次创建项目数据库和项目账号：

```bash
mysql --socket="$MYSQL_RUN/mysql.sock" -u root --skip-password
```

进入 MySQL 后执行：

```sql
ALTER USER 'root'@'localhost' IDENTIFIED BY 'root';

CREATE DATABASE IF NOT EXISTS interviewSys
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'interview'@'127.0.0.1'
IDENTIFIED BY 'interview';

GRANT ALL PRIVILEGES ON interviewSys.*
TO 'interview'@'127.0.0.1';

FLUSH PRIVILEGES;
EXIT;
```

如果 root 已经设置过密码，后续登录改用：

```bash
mysql --socket="$MYSQL_RUN/mysql.sock" -u root -p
```

创建数据库后，初始化项目表结构：

```bash
alembic upgrade head
```

如果需要把旧的 SQLite/JSON 数据迁移到正式数据库，再执行：

```bash
python scripts/migrate_local_to_platform.py
```

停止 MySQL：

```bash
mysqladmin --socket="$MYSQL_RUN/mysql.sock" -u root -p shutdown
```

### 5. Redis 启动

Redis 用于保存 Agent Run 运行进度、取消标记和短期事件。没有 Redis 时可以临时把 `.env` 里的 `REDIS_URL` 留空，系统会使用内存状态，但正式模式建议启动 Redis。

无 sudo 权限时可以通过 Conda 安装：

```bash
conda activate interviewEnv
conda install -c conda-forge redis
```

启动 Redis：

```bash
mkdir -p "$HOME/.local/redis"

redis-server \
  --bind 127.0.0.1 \
  --port 6379 \
  --daemonize yes \
  --dir "$HOME/.local/redis" \
  --logfile "$HOME/.local/redis/redis.log"
```

检查 Redis：

```bash
redis-cli -h 127.0.0.1 -p 6379 ping
```

相关配置文件：

- `config/rag.yml`
- `config/agent.yml`
- `config/chroma.yml`

### 6. 构建前端

本项目最终由 FastAPI 托管前端构建产物，所以服务器部署时推荐先构建前端：

```bash
cd frontend
npm install
npm run build
cd ..
```

如果本地开发想单独启动 Vite 前端：

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### 7. 启动后端

```bash
conda activate interviewEnv
uvicorn main:app --host 0.0.0.0 --port 8080
```

启动后访问：

- [http://127.0.0.1:8080/](http://127.0.0.1:8080/)

如果在服务器上运行，需要访问服务器地址和端口，例如：

- `http://服务器IP:8080/`

### 8. 一次完整启动顺序

每次重新运行项目时，可以按这个顺序检查：

```bash
cd "/home/yeyuxin/NBN/agent/Intelligent Interview Coaching System"
conda activate interviewEnv

# 1. 启动 MySQL
export MYSQL_DATA="$HOME/.local/mysql-data"
export MYSQL_RUN="$HOME/.local/mysql-run"
mysqld --no-defaults \
  --basedir="$CONDA_PREFIX" \
  --datadir="$MYSQL_DATA" \
  --socket="$MYSQL_RUN/mysql.sock" \
  --pid-file="$MYSQL_RUN/mysql.pid" \
  --log-error="$MYSQL_RUN/mysql.err" \
  --bind-address=127.0.0.1 \
  --port=3306 &

# 2. 可选：启动 Redis
redis-server --bind 127.0.0.1 --port 6379 --daemonize yes \
  --dir "$HOME/.local/redis" \
  --logfile "$HOME/.local/redis/redis.log"

# 3. 初始化或更新数据库表结构
alembic upgrade head

# 4. 构建前端
cd frontend
npm install
npm run build
cd ..

# 5. 启动后端
uvicorn main:app --host 0.0.0.0 --port 8080
```

本项目不要求 Docker。前端、FastAPI、MySQL 和 Redis 都可以按开发者模式分别启动。

管理后台仍然是浏览器 Web 应用：后端使用 `Python + FastAPI`，前端使用 `Vue 3 + JavaScript`。本项目不需要 uni-app；uni-app 更适合同时发布微信小程序和移动 App，并不是桌面浏览器管理后台的必要技术。

## 核心接口

### 认证与用户

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/bootstrap`

### 问答与面试

- `POST /api/qa/chat`
- `POST /api/qa/chat/stream`
- `POST /api/qa/clear`
- `POST /api/interview/start`
- `POST /api/interview/message`
- `POST /api/interview/message/stream`
- `POST /api/interview/runs/{run_id}/recover`
- `POST /api/interview/end`
- `POST /api/interview/report`

### 文件与知识库

- `POST /api/knowledge/import`
- `POST /api/resume/upload`
- `POST /api/resume/clear`

### 历史记录与报告

- `GET /api/history/interviews`
- `GET /api/history/interviews/{record_id}`
- `POST /api/history/interviews/{record_id}/restore`
- `GET /api/history/interviews/{record_id}/download`
- `GET /api/interview/report/download`

### 工作区与会话

- `POST /api/workspace/onboarding`
- `POST /api/workspace/projects`
- `PATCH /api/workspace/projects/{project_id}`
- `POST /api/workspace/projects/{project_id}/activate`
- `POST /api/workspace/projects/{project_id}/pin`
- `DELETE /api/workspace/projects/{project_id}`
- `POST /api/workspace/projects/{project_id}/conversations`
- `PATCH /api/workspace/conversations/{conversation_id}`
- `POST /api/workspace/conversations/{conversation_id}/activate`
- `POST /api/workspace/conversations/{conversation_id}/pin`
- `POST /api/workspace/conversations/{conversation_id}/mode`
- `DELETE /api/workspace/conversations/{conversation_id}`

### 管理后台与 Agent 观测

- `GET /api/platform/dashboard`
- `GET /api/platform/users`
- `PATCH /api/platform/users/{user_id}/role`
- `GET/POST /api/platform/organizations`
- `GET /api/platform/agent-runs`
- `GET /api/platform/agent-runs/{run_id}`
- `POST /api/platform/agent-runs/{run_id}/cancel`
- `GET /api/platform/evaluations`
- `GET /api/platform/interview-tasks`
- `GET /api/platform/reports`
- `GET /api/platform/configuration`
- `POST /api/platform/templates`
- `POST /api/platform/questions`
- `POST /api/platform/prompts`

## 使用说明

### 登录

- 先注册或登录
- 登录成功后，后端会通过 Cookie 维持会话
- 不同用户的当前工作态和历史面试记录相互隔离

### 首页与工作区

- 登录后先进入首页，可选择技术问答、模拟面试或历史复盘
- 左侧边栏支持创建项目文件夹，并在项目内管理多个会话
- 每个会话可保存自己的模式、聊天记录、面试状态和上传内容

### 问答模式

- 适合围绕某个技术知识点提问
- 普通请求走 `axios`
- 流式回复走 `fetch + ReadableStream`
- 支持手动停止、继续生成和重试本轮回答

### 模拟面试模式

- 先选择目标岗位
- 可选上传简历
- 系统会按岗位能力维度推进面试
- 回答较弱时会提示或切换题目
- 面试结束后可生成分数和报告

### 历史记录

- 生成报告后会自动写入历史记录
- 可查看过往报告、下载报告文件
- 可将某条历史记录恢复到当前工作台继续复盘

## 项目亮点

- 基于 `DeepSeek + RAG` 的智能问答与模拟面试系统
- 支持正式登录体系、用户隔离和历史记录列表
- 支持首页落地页、首次引导、主题切换和项目/会话管理
- 支持 `岗位 + 简历` 定制化提问
- 设计了面试状态机、追问 / 切题策略与评分机制
- 支持真流式输出、手动停止、继续生成和重试本轮回答
- 支持报告文件导出、本地留存与 LangSmith tracing
- 支持 LangGraph 多 Agent 编排、混合检索、Evidence Judge 与自动评测
- 支持 MySQL/Redis 正式数据模式和候选人/面试官/管理员 RBAC 后台
