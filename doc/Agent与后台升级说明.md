# Agent 与全栈后台升级说明

## 一句话架构

前端使用 Vue 3 + Pinia 展示候选人工作台、角色后台和 Agent 执行过程；后端使用 FastAPI 提供接口，LangGraph 编排面试 Agent，Chroma + BM25 提供混合检索，MySQL 保存业务数据，Redis 保存短期运行状态。

## 多 Agent 链路

```text
用户回答
  -> Router Agent 判断回答、求提示或结束
  -> Evaluation Agent 评分并提取薄弱点
  -> 面试状态机决定追问、提示、切题或结束
  -> Chroma + BM25 双路召回
  -> RRF 融合 + Rerank 重排
  -> Evidence Judge 检查证据，不足时最多补查一次
  -> Interview Agent 生成下一题
  -> Report Agent 汇总评分、证据和完整记录
```

LangGraph 管“节点按什么顺序执行”，状态机管“业务规则允许走哪条分支”。这样既有模型灵活性，又不会让模型无限追问或自行决定面试永不结束。

## 前后端流式链路

1. 前端发送回答并立即插入用户气泡和助手占位消息。
2. 后端创建 `run_id`，返回 `run_started` 事件。
3. LangGraph 每完成一个节点就写入 Redis/内存 Run Store。
4. FastAPI 流式接口持续读取事件并发送给浏览器。
5. 前端通过 `fetch + getReader()` 解析每行 JSON。
6. 节点事件写入 Pinia 的 `agentEvents`，文本 `token` 追加到助手气泡。
7. 完成事件返回最终候选人状态、引用证据和 `run_id`。
8. 用户主动停止时，前端先调用 `/api/platform/agent-runs/{run_id}/cancel` 写入取消标记，再终止当前 `fetch`。
9. 网络意外断开时不取消后台任务；前端使用 `/api/interview/runs/{run_id}/recover` 轮询并恢复最终回复、面试状态和引用证据。

## 数据模式

开发者默认模式不依赖额外服务：认证和报告使用 SQLite，工作区使用 JSON，Agent Run 使用内存。

正式模式设置 `ENABLE_PLATFORM_DB=true` 后，用户、组织、工作区、项目、会话、消息、简历、面试任务、报告、知识文档、Agent Run 和评测结果进入 MySQL；Redis 保存运行进度、取消标记和短期事件。数据库不可用时不会悄悄写入错误数据，应切回开发模式排查。

## 管理后台

- 候选人：只能访问自己的项目、会话、简历、面试和报告。
- 企业面试官：查看所属组织候选人，管理面试模板、题库和组织知识库，观察 Agent Runs。
- 企业面试官：还可查看所属组织的面试任务、逐轮得分和报告列表。
- 平台管理员：管理组织、角色、用户、Prompt 版本、非敏感模型信息、全平台运行和评测指标。

权限在前端用于控制入口和页面跳转，后端 RBAC 才是最终安全边界。不能只靠 Vue 隐藏按钮。

## 前后台联动和可视化

可以直接记这 5 步：

1. 面试官在后台新增岗位模板、题库和评分维度。
2. 前端进入模拟面试或点击开始面试前，请求 `/api/roles` 刷新岗位选项。
3. 后端开始面试时，根据岗位读取最新模板 profile。
4. 后端把模板维度和题库参考注入面试状态与 Interview Agent Prompt。
5. 前端通过 `candidate.interview_state.multi_agent.interview_plan` 展示本轮面试计划。

标准回答：

“这个项目不是前台写死岗位配置。后台新增岗位模板和题库后，前台会通过 `/api/roles` 拉取最新岗位列表。用户开始面试时，FastAPI 会读取对应岗位的模板 profile，把能力维度、题量和题库参考写入 `interview_state`，再注册到运行时 RoleManager。Interview Agent 生成问题时会把后台题库作为参考方向，但不会机械照抄，这样既能保证岗位配置生效，又能保持提问自然。”

后台看板使用 ECharts 封装 `ChartCard` 组件，展示 Agent 运行状态、运行耗时、候选人得分趋势、岗位任务分布、模板分布和题库维度覆盖。普通接口仍然走 `axios`，图表数据来自 `/api/platform/charts`。

数字面试官是轻量增强版：前端用组件显示面试官形象和 Agent 当前阶段，语音输出使用浏览器 SpeechSynthesis，语音输入使用浏览器 SpeechRecognition。开启数字面试官后，AI 普通气泡会隐藏，由数字人区域承载面试官表达；如果 Live2D 服务不可用，则使用 CSS 兜底形象。

## 为什么开发阶段不强制 Docker

Docker Compose 的作用是用一个配置统一启动 FastAPI、Vue 构建环境、MySQL 和 Redis。它能提高环境一致性，但本项目的学习与开发不强制使用 Docker：

- 默认模式只需 Vue 3 前端、FastAPI 后端、SQLite、JSON 和内存 Run Store。
- 需要展示正式数据架构时，再单独启动 MySQL 和 Redis，并设置 `ENABLE_PLATFORM_DB=true`。
- 后台是标准 Web 系统，技术栈为 Python/FastAPI + Vue 3，不需要 uni-app。

## 自动评测

运行 `python -m evaluation.run_evaluation` 可检查路由准确率、工具选择准确率、问题覆盖率和重复率。运行 `pytest -q tests` 可执行基础单元测试。配置 LangSmith Key 后可追加 `--sync-langsmith`，把固定样例同步为 LangSmith Dataset。

## 两种简历定位

**Agent / AI 应用岗位：** 基于 LangGraph 构建 Router、Resume Analyst、Planner、Interview、Evaluation、Evidence Judge、Report 多 Agent 状态图，结合 Tool Calling、混合检索、规则状态机、断线恢复、LangSmith Tracing 与离线评测提升流程可控性和可观测性。

**前端 / Web 全栈岗位：** 基于 Vue 3、Pinia、Vue Router、Axios 与 FastAPI 实现候选人工作台和角色化管理后台，完成 RBAC、MySQL 数据持久化、Redis 运行状态、HTTP 真流式交互、文件上传、会话管理、报告列表和异常恢复链路。
