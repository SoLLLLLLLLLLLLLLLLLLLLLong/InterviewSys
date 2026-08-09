# AI创作工坊面试速查手册

> 这个项目是一个基于大模型的 AI 创作 Agent 平台，主要面向 AI 图片生成和数字人口播内容创作场景，核心是把文案、配音、上传照片、数字人视频和导出做成多阶段任务流。 前端使用 Vue 3、JavaScript、Pinia 和 uni-app H5 搭建网页端创作工作台；后端使用 FastAPI 提供统一 API，并通过 avatar-worker 封装 SadTalker/MuseTalk 数字人推理适配。核心实现是把文案、配音、上传照片、数字人视频、导出抽象成多阶段 Agent Workflow，前端通过 Pinia 管理创作状态，通过 uni.request 轮询任务进度，后端负责大模型调用、图片生成、任务编排、上传校验和密钥管理。

```text
AI 创作平台  前端：Vue3 页面 + Pinia 状态 + uni.request 联调 ； 后端：FastAPI 代理模型 + 任务编排
            Agent：文案 -> 配音 -> 上传照片 -> 数字人 -> 导出 ； 安全：Key 不进前端，放服务端环境变量
```

## 0.1 项目实现细节地图

| 模块 | 怎么实现 | 涉及知识点 | 面试结果说法 |
| --- | --- | :-- | --- |
| 登录注册 | FastAPI 注册/登录返回 session token，前端 Pinia + uni storage 保存，启动时 `/api/auth/me` 校验 | HTTP、鉴权、PBKDF2、session、401 | 实现登录态恢复和用户维度任务隔离 |
| 请求封装 | 统一封装 `uni.request` 和 `uni.uploadFile`，自动携带 Bearer token，401 自动退出 | uni-app、HTTP、错误处理、上传 | 前端请求逻辑集中管理，便于维护 |
| AI 图片生成 | 前端创建 image task，后端调用 SiliconFlow/Kolors 或 fallback，前端轮询 taskId | 大模型 API、任务状态、轮询 | 跑通文生图任务和结果回显 |
| 数字人口播 | 文案、配音、上传照片、数字人、导出拆成多阶段 workflow | Agent Workflow、状态机、长任务 | 用户能按步骤完成视频生成流程 |
| 上传照片 | `uni.chooseImage` 选择，`uni.uploadFile` 上传，后端校验格式/大小/宽高并返回评分 | multipart、文件校验、素材质量 | 支持单人正脸照片作为数字人输入 |
| 数字人 worker | API 提交 job，worker 根据 `AVATAR_PROVIDER` 调 SadTalker/MuseTalk，输出 mp4 | worker、GPU 推理、进程调用、静态文件 | 推理服务和业务 API 解耦，可替换模型 |
| 作品中心 | 成功/失败任务写入 works，前端分批展示和刷新 | 列表渲染、分页、失败态 | 用户能查看历史作品和错误原因 |

速记：页面触发 -> Pinia action -> uni.request -> FastAPI task -> worker/model -> task polling -> 结果回显。

### 1.1 第一条：前端页面开发

> 基于 Vue 3 + JavaScript + uni-app H5 完成 AI 创作工作台、AI 图片生成、数字人口播、作品中心等页面开发，实现页面模块拆分、视频预览与导出交互。【主要负责前端页面和交互部分。首页工作台展示 AI 图片、数字人口播、作品中心等入口；AI 图片页负责输入提示词、选择比例、创建图片任务并展示结果；数字人口播页负责文案输入、音色选择、上传数字人照片、查看适配评分、生成视频预览和导出；作品中心用于展示生成记录、任务状态和预览链接。页面开发时我把通用 UI 抽成卡片、状态面板、按钮、步骤区等组件，避免页面代码过长。】

### 1.2 第二条：Pinia + uni.request + Agent 流程【 速记：Pinia 管状态，uni.request 调接口，taskId 串流程，polling 查进度。】

> 基于 Pinia + uni.request 实现文案、配音、数字人视频、导出等多阶段 Agent 创作流程，支持任务状态轮询、失败提示与结果回显。【用 Pinia 管理创作流程中的共享状态，比如当前文案、图片提示词、选中的音色、选中的数字人、当前任务 ID、任务状态、进度、图片结果、视频预览地址和导出结果。前端不会直接等一个长接口返回，而是先创建任务，后端返回 taskId，前端再定时请求 `/api/tasks/{taskId}`。这样可以处理图片生成、视频生成这类耗时任务，并且可以展示排队中、生成中、成功、失败等状态。】

关键流程：点击生成 -> POST 创建任务 -> 返回 taskId -> Pinia 保存 taskId -> 轮询 GET /api/tasks/{taskId} -> 更新 progress/status/result -> 成功后展示图片或视频，失败后展示错误原因

### 1.3 第三条：FastAPI + Worker + 模型调用

> 基于 FastAPI 搭建后端 API 与数字人 Worker，完成大模型服务代理、图片生成任务、数字人口播任务编排、上传校验与作品结果管理，并通过环境变量隔离模型密钥。【后端用 FastAPI 做统一网关，前端只请求自己的后端，不直接请求大模型平台。后端负责文案生成、图片生成任务、配音任务、上传照片、数字人任务、导出任务、任务查询和作品查询。数字人部分单独拆了 avatar-worker，业务 API 只负责提交任务和查状态，worker 内部支持 SadTalker/MuseTalk 二选一真实推理适配，后续也可以继续扩展 Wav2Lip。模型 Key 都放在服务端环境变量里，避免泄露到前端。】

## 2. 前端重点：页面、组件、布局、状态、联调

### 2.1 前端页面有哪些

当前 uni-app H5 版主要页面：前端整体是 uni-app H5 页面应用，页面入口由 pages.json 管理。登录页和工作台通过 Pinia 登录态切换，工作台内部用局部状态切换功能面板，让用户在同一个创作后台里完成图片生成、数字人口播和作品查看。

- `pages/index/index.vue`：H5 页面入口，根据登录态展示登录页或工作台。
- `LoginView.vue`：注册登录页                `WorkspaceView.vue`：H5 创作工作台。
- 工作台内的功能面板：系统概览、AI 图片生成、数字人口播、作品中心。

### 2.2 组件拆分怎么说

当前 H5 版没有拆很多小组件，而是集中在 `WorkspaceView.vue` 做工作台，但面试可以讲设计思路：按复用频率拆组件，比如导航侧栏、功能卡片、任务状态条、结果预览卡片、选项卡片、作品卡片。当前项目为了演示速度先集中在一个工作台页里，后续重构时可以把这些区块拆到 `components` 目录。

没有拆得很细：首版更关注主流程跑通和部署演示，页面规模还可控；但我已经按区块写了清晰结构和 class，后续可以自然拆成组件，不会影响状态和接口层。

### 2.3 PC 布局怎么讲

当前布局特点：PC 端和移动端不一样，PC 屏幕更宽，所以我没有继续用纵向步骤表单，而是改成左侧导航和双栏工作区。这样用户一边配置文案、音色、数字人，一边看任务状态和视频预览，操作路径更短，也更适合后台类产品。 左侧深色导航。 右侧主工作区。 顶部显示后端状态。 中间使用卡片式工作台。 AI 图片是双栏：输入区 + 预览区。 数字人口播是双栏：编辑配置区 + 流程/视频预览区。

### 2.4 状态管理为什么用 Pinia

因为这个项目有很多跨区域共享状态，比如登录用户、token、当前文案、选中的音色、任务 ID、任务进度、结果 URL。如果只放在组件内部，切换面板或刷新后会比较乱。Pinia 可以把这些状态集中管理，页面只负责展示和触发 action。

项目里 Pinia 管了什么：

- `auth store`（专门管用户登录态的地方）：token、用户信息、登录、注册、退出。【比如登录成功后，后端会返回 token，把 token 和用户信息存到 Pinia 里，同时也同步到本地缓存。之后请求接口时统一带上 token，页面刷新后也可以从缓存恢复登录状态。退出登录时，就清掉 token、用户信息和缓存。】
- `creation store`：文案、图片提示词、音色、数字人、BGM、任务 ID、任务状态、作品列表。【主要管创作流程里的业务状态，比如用户输入的文案、图片提示词、选择的音色、数字人、BGM，还有后端返回的任务 ID、任务进度和作品列表。因为这些状态会跨多个页面和步骤使用，所以放到 Pinia 里统一管理，避免每个组件之间层层传参。】

### 2.5 uni.request、Fetch 和 Axios 怎么回答

​	Axios 和 Fetch 是 Web 浏览器里常见的请求方式，uni.request 是 uni-app 提供的跨端请求 API。这个项目为了保持 uni-app H5 和后续跨端兼容，统一封装 uni.request，集中处理请求地址、JSON 数据、Authorization token 和错误提示。如果是纯 Vue Web 项目，也可以换成 Axios 或 Fetch。

### 2.6 pages.json 和 Vue Router 怎么讲

​	uni-app 也是有路由的，只是它的页面路由主要通过 `pages.json` 注册管理，然后用 `uni.navigateTo`、`uni.redirectTo`、`uni.switchTab` 这些 API 跳转。和普通 Vue Web 项目不同，它不依赖 Vue Router，因为 uni-app 要同时适配 H5、小程序、App 等多端。：

> ```
> uni.navigateTo({
>   url: '/pages/home/index'
> })
> ```
>
> 普通 Vue Web 项目通常用 Vue Router 做路由守卫和页面跳转；uni-app 更强调跨端页面配置。
>
> 【`Vue Web` 用 `Vue Router` 管路由，`uni-app` 用 `pages.json + uni.navigateTo` 管跨端页面跳转】

关键词：pages.json、navigationBarTitleText、H5 router mode、跨端页面配置

### 2.7 登录态怎么恢复

> 登录成功后，后端返回服务端 session token 和 user。前端通过 uni.setStorageSync 保存 token 和用户信息，同时 Pinia 保存运行时状态。刷新页面时 auth store 会先读取本地 token，再请求 `/api/auth/me` 校验 token 是否仍有效；如果有效就恢复登录态，如果 401 就清空本地状态并回到登录页。之后每次业务请求都会带上 `Authorization: Bearer token`。

注意： 当前版本已经有 PBKDF2 密码哈希、session 过期时间、退出登录清理 session 和 401 统一处理。生产环境还可以继续升级 JWT/Refresh Token、验证码、设备管理、审计日志和更完整的 RBAC 权限。

### 2.8 接口联调怎么讲

> 我先用 Postman 或浏览器直接测 `/api/health`，确认后端可用；再测登录接口拿 token；然后在前端请求封装里统一加 Authorization。长任务接口会先测创建任务，再测轮询状态，最后看前端能不能按 status 更新 UI。

```text
调试顺序： /api/health
-> /api/auth/login
-> /api/image/tasks
-> /api/tasks/{taskId}
-> /api/works
```

### 2.9 上传数字人照片怎么实现

> 前端使用 `uni.chooseImage` 选择本地图片，再通过 `uni.uploadFile` 上传到 FastAPI 的 `/api/uploads/avatar-image`。后端会校验文件类型、大小和宽高，保存到 runtime uploads 目录，并返回 assetId、previewUrl 和 qualityScore。前端把这个 asset 保存到 Pinia，创建数字人任务时只传 imageAssetId，避免重复上传。

```text
速记：chooseImage 选图 -> uploadFile 上传 -> 后端校验图片是否合法 -> 后端保存图片 -> 返回 assetId -> 创建数字人任务时带上 assetId ->  后端根据 assetId 找到图片并生成视频
【用户上传了一张照片，后端保存后，会给这张照片生成一个编号，这个编号就是 assetId。后面创建数字人任务时，前端不用再重复传整张图片，后续数字人任务只引用这个 ID，不需要前端重复上传图片，这样也方便做权限校验、素材复用和任务追踪。“我要用 assetId = xxx 这张照片来生成数字人视频。”】
```

### 2.10 loading、禁用按钮和长列表怎么处理

> 我在 Pinia 里把 loading 拆成初始化、上传、业务动作和作品刷新等状态。请求开始时设置 loading（比如用户点“生成图片”，接口还没返回时，我们要让页面知道：现在正在生成中），接口结束后，不管成功还是失败，都恢复页面显示“生成中...”。。按钮根据 loading 和任务状态禁用（把按钮置灰，防止用户重复提交），finally 里恢复。作品中心用分批展示和“加载更多”，避免一次性渲染长列表，减少首屏压力。长任务不能一直傻等，要通过 taskId 轮询状态，并设置轮询上限，避免任务异常时前端一直等。如果还没完成，就提示用户：任务还在处理中，可以稍后到作品中心查看

涉及知识点：

- `loading`：提升用户反馈，防止重复点击。          `disabled`：避免重复提交。                finally`：请求完成后统一恢复状态。
- `分页/加载更多`：减少长列表渲染压力。                `轮询上限`：避免异常任务无限轮询。

## 3. UniApp 和跨端相关问题

### 3.1 UniApp 是基于 Vue 语法的跨端开发框架，可以把一套代码编译到微信小程序、H5、App 等平台。它适合业务逻辑相似、需要多端覆盖的项目。

### 3.2 UniApp 和 Vue Web 的区别

- Vue Web 运行在浏览器里，路由通常用 Vue Router。
- UniApp 可以编译成 H5、小程序和 App，页面配置通常在 `pages.json`。
- Vue Web 请求常用 Fetch/Axios。
- UniApp 为了跨端兼容通常使用 `uni.request`。
- Vue Web 使用 HTML 标签，如 `div`、`input`。
- UniApp 常用跨端组件，如 `view`、`text`、`scroll-view`。

```text
速记：Vue Web 面向浏览器，UniApp 面向跨端运行环境。
```

### 3.3 如果问 uni-app H5 怎么请求服务器

> uni-app H5 端也不能直接放大模型 Key，正确做法是 H5 页面通过 uni.request 请求自己的 FastAPI 后端，后端再代理调用大模型。开发阶段可以用本地代理或后端 CORS，服务器部署时可以让 FastAPI 同时托管 H5 静态资源，减少跨域问题。“CORS 是浏览器的跨域安全机制。因为我的前端和 FastAPI 后端可能运行在不同端口，比如前端是 5173，后端是 3000，所以后端需要配置 CORS，明确允许前端域名访问接口，否则浏览器会拦截请求。”
>
> 【`CORS` 叫**跨域资源共享**，简单说就是：**浏览器为了安全，不允许一个网页随便请求另一个域名/端口的后端接口，除非后端明确允许。**两个地址的**协议、域名/IP、端口**只要有一个不同，就算跨域。浏览器会先检查后端有没有允许跨域，如果后端没配置，前端请求就会被浏览器拦截。】

### 3.4 如果问你 UniApp 做过哪些

> 我做过首页工作台、AI 图片生成、数字人口播流程页和作品页这些页面。主要涉及卡片布局、scroll-view 滚动区域、uni.request 接口请求、H5 网页端部署和本地状态维护。当前项目用 uni-app H5 运行，后续如果要扩展小程序端，可以复用后端接口和主要业务流程。

## 4. AI 创作 Agent 主流程

### 4.1 图片生成流程

```text
用户输入 Prompt → 前端 POST /api/image/tasks → 后端创建图片任务 Image Task → 调用 SiliconFlow/Kolors 或 fallback 生成→ 前端轮询任务状态 /api/tasks/{taskId} → 成功后返回 previewUrl → 展示图片→ 作品中心记录结果
```

### 4.2 数字人口播流程

```text
输入或生成文案 → 选择音色 → 创建配音任务 → 选择数字人 → 上传单人正脸照片并完成质量校验 → 创建数字人预览任务 → avatar-worker 调 SadTalker/MuseTalk 生成视频 → worker 返回下载地址 previewUrl/downloadUrl → 创建导出任务 → 作品中心查看结果
```

### 4.3 为什么叫 Agent Workflow

> 它不是单次模型调用，而是围绕用户目标自动编排多个工具：LLM 生成文案、图片模型生成图、TTS 或当前演示配音链路生成音频、avatar-worker 调 SadTalker/MuseTalk 生成视频、导出模块生成作品。每一步有任务状态和结果，整体形成一个工作流型 Agent。

```text
Agent = 目标 + 工具 + 编排 + 状态 + 结果闭环。
```

## 5. 后端和安全相关问题

### 5.1 为什么用 FastAPI

> FastAPI 写接口效率高，支持异步，自动生成接口文档，而且和 Python AI 生态结合方便。后续如果接 MuseTalk、SadTalker、PyTorch 推理服务，Python 后端会更自然。

### 5.2 为什么模型 Key 不能放前端

> 前端代码会被浏览器看到，构建产物和网络请求也可能被抓包。如果把 Key 放前端，就等于公开密钥。所以把 Key 放在服务端环境变量，前端只请求自己的 FastAPI 后端。（前端不可信，Key 放后端。）

### 5.3 登录注册怎么做

当前项目：

- 注册时，前端把用户名、密码提交到：`POST /api/auth/register` ，后端不会直接保存明文密码，而是先用 `PBKDF2` 对密码做哈希处理，再保存哈希结果，不保存明文密码。这样即使数据泄露，也不会直接暴露用户原始密码。

- 登录时，前端调用：`POST /api/auth/login` ，后端校验用户名和密码，校验成功后生成一个 `token` 返回给前端。

- 前端把 token 保存起来，之后请求需要登录的接口时，在请求头里带上：Authorization: Bearer token值 

- 后端收到请求后，会根据这个 Bearer token 找到对应用户，从而判断“当前是谁在操作”。            

- session 有过期时间，退出登录会清理当前 session。演示数据存在 JSON runtime store。

  【当前项目实现了基础登录注册，密码用 PBKDF2 哈希保存，登录后通过 Bearer token 维护登录态。因为现在是演示项目，用户和 session 暂时放在 JSON runtime store 里。生产环境要会换成数据库，比如 SQLite、MySQL 或 PostgreSQL，并使用 JWT + Refresh Token 做登录态管理，同时加入验证码、登录失败次数限制、接口权限校验和 token 黑名单，提升安全性。】

> 当前已经具备基础服务端登录校验，生产环境会把 JSON runtime store 换成数据库，并进一步加入 JWT/Refresh Token、bcrypt 或 argon2、验证码、登录频控和权限控制。
>
> （1）`JWT` 全称是 `JSON Web Token`，可以理解成一种带签名的登录凭证。普通 token 可能只是一个随机字符串，后端需要去数据库或缓存里查它对应哪个用户。而 JWT 本身可以携带一些用户信息，比如：
>
> ```
> {
>   "userId": "u001",
>   "username": "test",
>   "exp": "过期时间"
> }
> ```
>
> 但是它不是随便写的，后端会用密钥给它签名。前端不能伪造，后端可以验证签名是否合法。
>
> 用户登录后，后端发给前端 JWT，前端之后每次请求都带上它，后端验证签名和过期时间，就知道这个请求属于哪个用户。
>
> （2）`Access Token` 一般有效期比较短，比如 2 小时，用来访问接口。
>
> （3）`Refresh Token` 有效期更长，比如 7 天或 30 天，用来换新的 Access Token。
>
> ```
> Access Token 短期有效，泄露风险更低
> Refresh Token 负责续期，用户不用频繁登录
> ```

### 5.4 数据存在哪里

> 目前为了演示轻量，用户、任务、作品和 session 存在 `services/api/runtime/data.json`。生产环境我会换成 SQLite 或 PostgreSQL；如果任务量变大，还会加 Redis 和消息队列处理长任务。
>
> SQLite / PostgreSQL：负责长期保存数据（数据库）;  Redis：负责快速临时存取数据（缓存/状态管理）
>
> （1）SQLite 是一种**轻量级关系型数据库**。特点：不需要单独启动数据库服务器; 数据直接保存成一个文件（例如 `.db`） ;  适合小型项目/小型网站、单机应用
>
> 简单、不需要配置服务器、部署方便
> 缺点：高并发能力有限、 多人同时大量写入不适合
>
> （2）PostgreSQL（简称 PG）是一个**大型关系型数据库** 它需要单独部署：应用服务器 → PostgreSQL数据库服务器；适合企业系统、大型网站、多用户平台、AI SaaS平台；  优点：支持大量数据、支持高并发、事务可靠、数据查询能力强          缺点：部署复杂一些、需要维护
>
> （3） Redis 不是传统数据库，它主要是内存中的高速 Key-Value 存储
> 例如：你的 AI 图片生成任务：用户点击：生成图片 → 后端：创建任务：task_id = 12345 → 任务状态：running。
>
> 这个状态放 Redis，几毫秒就能查询：
> key:
> task:12345
> value:
> { status:"running", progress:50}
>
> （4） 消息队列负责：排队执行耗时任务：用户请求 → 创建任务 → 消息队列 → GPU Worker → 生成图片 → 更新状态
>
> | 组件       | 作用       | 类比         |
> | ---------- | ---------- | ------------ |
> | SQLite     | 小型数据库 | 个人记账本   |
> | PostgreSQL | 大型数据库 | 公司财务系统 |
> | Redis      | 高速缓存   | 桌面上的便签 |
> | 消息队列   | 任务排队   | 取号排队系统 |

### 5.5 为什么拆 avatar-worker

> 数字人推理依赖 GPU、模型权重和复杂环境，不适合直接塞进业务 API。拆成 worker 后，业务后端只负责提交任务和查询结果，底层可以灵活替换 MuseTalk、SadTalker 或 Wav2Lip。这里的 **worker** 可以理解成：专门负责执行耗时任务的后台程序（不直接面对用户，而是在后台执行任务的程序）。
>
> avatar-worker 就是一个独立的后台推理服务，专门占用 GPU 执行数字人生成任务；API 只负责业务逻辑和任务管理。这样可以避免 AI 模型推理阻塞业务服务，也方便以后替换模型。

### 5.6 当前数字人是不是真实生成

> 当前已经不是固定返回演示视频了。项目里的 avatar-worker 已经支持 SadTalker 和 MuseTalk 两种 provider 适配，可以根据 `AVATAR_PROVIDER` 切换；如果服务器配置了对应仓库、模型权重、Python 环境和 GPU，就会调用真实推理命令生成 mp4，并通过 `/worker/files/...` 返回预览和下载地址。如果没有配置真实推理环境，worker 会返回明确失败原因，例如缺少 `SADTALKER_REPO_DIR`，不会假装生成成功。

### 5.7 SadTalker 和 MuseTalk 怎么选

> 如果需求是“上传一张单人正脸照片 + 配音音频 -> 数字人口播视频”，我优先选 SadTalker，因为它更贴合静态人像驱动。MuseTalk 更偏向口型驱动和视频模板素材，适合已有模板人物视频或更复杂的口型同步场景。项目通过 worker provider 隔离具体模型，前端和业务 API 不需要关心底层选哪个仓库。

```text
SadTalker：照片驱动，适合单人正脸口播。    MuseTalk：口型驱动，适合模板视频/更强唇形同步。       共同点：都放在 worker，不直接进前端或业务 API。
```

### 5.8 avatar-worker 内部怎么实现

> API 创建数字人任务后，会把用户 ID、文案、配音音频地址、照片 asset 和分辨率参数传给 avatar-worker。worker 先准备图片和音频文件，再根据 `AVATAR_PROVIDER` 调用 SadTalker 或 MuseTalk 的推理命令。命令执行完成后，worker 扫描输出目录里的 mp4，把结果复制到公开目录，并返回 previewUrl、downloadUrl、provider、failureStage 等字段。API 再把这些结果同步到任务和作品中心。

## 6. 和个人技能对应怎么讲

### 6.1 前端技能

```text
Vue 3、JavaScript、HTML、CSS、Vue Router、Pinia、Axios、uni-app、HTTP、前后端交互、UI 还原、组件封装
```

项目对应：

- Vue 3：页面和状态组合式开发。  JavaScript：所有前端逻辑用 JS 实现。   HTML/CSS：H5 工作台布局、卡片、按钮、预览区。
- Vue Router：普通 Web 项目可用，当前 uni-app H5 主要通过 pages.json 管页面。   Pinia：登录态和创作流程状态管理。
- Axios：项目当前用 uni.request，但可说明复杂纯 Web 项目会换 Axios。   HTTP：前端调用 FastAPI REST API。
- UI 还原：根据参考图做工作台、卡片、预览和流程布局。   组件封装：可拆导航、卡片、状态条、作品卡片等。

### 6.2 AI 应用技能

```text
LangChain、LangGraph、RAG、Prompt Engineering、大模型接口调用、知识检索、业务链路联调
```

- Prompt Engineering：文案生成 prompt 设计。 大模型接口调用：DeepSeek/SiliconFlow 后端代理。
- Agent Workflow：多阶段任务编排。 RAG/Embedding：项目预留 Embedding，可用于模板召回和脚本分类。
- LangGraph 拓展：后续可用状态图管理文案、配音、数字人、导出节点。

> 这个项目没有强依赖 LangChain，因为当前流程比较清晰，用普通服务层和任务状态就能实现。后续如果流程更复杂，比如多工具选择、条件分支、失败回退，就可以用 LangGraph 把节点和状态转移显式建模。

### 6.4 工程化与工具

- Linux：服务器运行 FastAPI 和 worker。  Git：项目版本管理。   Conda：Python 环境管理。  Postman：接口测试。  FastAPI：后端服务。
- 部署：构建 uni-app H5 后由 FastAPI 托管静态资源。 问题排查：端口不通、接口 502、跨域、token、任务状态等。

### 6.5 深度学习技能

- 数字人链路已经通过 avatar-worker 适配 SadTalker/MuseTalk，真实运行需要 GPU、模型权重和对应 Python 环境。
- 图片生成和视频生成属于多模态生成任务。
- PyTorch 经验有助于理解模型部署、GPU 推理、显存、输入预处理和结果后处理。

> YOLO 属于视觉检测任务，这个项目是生成式 AI 应用，两者方向不同。但视觉项目经验让我更熟悉数据处理、模型推理、指标评估和部署调试。后续数字人上传照片质量校验，也可以扩展人脸检测、清晰度检测、遮挡检测等视觉能力。

## 7. 岗位 JD 可能问的问题

### 7.1 你为什么想做前端

> 我喜欢前端是因为它离用户最近，能把业务逻辑、交互体验和工程实现结合起来。我也对 AI 应用很感兴趣，所以希望做的不只是静态页面，而是能把大模型能力真正落到可用产品里，比如这个 AI 创作工作台。

### 7.2 你做 Vue 最大的收获是什么

> 最大收获是状态和组件边界要设计清楚。简单页面可以直接写，但流程一复杂，比如有登录态、任务状态、结果预览，就必须把请求封装、Pinia 状态和页面展示分开，否则后期很难维护。

### 7.3 你怎么做模块设计

> 我会先按业务流程拆模块，比如登录、创作、任务、作品模块。前端部分我会再按照职责拆分， 页面主要负责页面布局和交互展示，store （管理公共状态）用来统一管理跨页面需要共享的数据和状态，比如用户信息、当前任务状态、作品列表这些；services 层主要负责封装后端接口请求，把接口调用统一管理起来，页面不用直接写请求逻辑，只需要调用对应的方法获取数据，组件负责复用展示。

### 7.4 如何排查线上问题

> 我会先判断是前端、网络还是后端问题。前端看控制台报错和 Network；网络看接口状态码、请求地址、跨域、token；后端看服务日志、接口返回和任务状态。如果是 502 或连接失败，会先确认服务端口是否监听、服务器防火墙和反向代理配置。

### 7.5 怎么做系统测试与优化

> 前端会测主流程、边界输入、失败态和刷新恢复；性能上会减少无意义请求，长任务用轮询间隔控制，图片和视频结果按需加载；UI 上会保证按钮禁用态、loading、错误提示和空状态明确。

### 7.6 如果给你一个 Figma 设计稿怎么还原

> 如果拿到一个 Figma 设计稿，我一般不会直接开始写页面，而是先整体分析设计稿的结构，比如页面有哪些区域、布局方式是什么、哪些部分是公共组件。     然后我会整理设计规范，包括颜色、字体、间距、圆角、阴影这些，把一些通用样式抽出来。        接着按照页面结构拆组件，比如导航栏、按钮、卡片、表单等公共组件先实现，再基于这些组件开发具体页面。       开发过程中我会先保证整体布局和视觉效果和设计稿一致，然后再补充交互，比如点击状态、加载状态、错误提示以及响应式适配。最后会通过 Figma 对比检查细节，不断调整间距和样式。

### 7.7 你怎么看 GEO 或生成式引擎优化

> 我的理解是，GEO（Generative Engine Optimization，生成式引擎优化）可以看作是面向 AI 搜索和生成式问答场景的内容优化。传统 SEO 主要关注网页在搜索引擎中的排名，而 GEO 更关注内容能不能被 AI 模型理解、检索到，并作为答案的一部分进行引用和推荐。
>
> 从技术角度来说，GEO 不只是优化关键词，而是需要让内容结构更加清晰，比如使用结构化数据、明确的信息层级、高质量内容组织方式，让 AI 更容易提取和理解。
>
> 如果从前端和 AI 应用角度看，前端可以通过合理的信息架构、语义化 HTML、结构化展示提升内容可解析性；AI 应用侧可以结合 Prompt 设计、RAG 检索增强、知识库管理等方式，让生成内容更加稳定和准确。同时也可以通过数据分析和 A/B 测试持续优化内容效果。
>
> 【GEO 是针对生成式 AI 搜索的一种内容优化方式。以前 SEO 主要是让网页获得搜索排名，**GEO 的目标是让内容更容易被生成式 AI 理解、检索和引用，而不是单纯提高搜索排名。前端侧主要关注内容结构和可解析性，AI 应用侧主要通过 Prompt、RAG 和知识管理提高生成结果质量。**】

### 7.8 你能长期实习一年吗

> 稳定实习时间也希望在一个项目里持续迭代，不只是完成短期任务。这个岗位既有 Vue/UniApp 开发，也有 AI 方向项目，我比较感兴趣，愿意长期投入。我希望通过长期实习先把业务和技术基础打扎实，如果有机会也愿意参与更国际化的项目。实习是一个成长机会。
>
> 我现在真实生产级项目经验还不算多，所以要学会重视代码规范、文档和复盘。遇到不熟悉的问题，我会先查官方文档和项目代码，再用小 demo 验证，尽量避免凭感觉改。

## 9. 项目可能被深问的点

### 9.1 为什么任务要轮询，不直接等结果

生成图片、生成视频可能耗时很久，直接等待会导致请求超时、用户体验差。任务化以后，后端先返回 taskId，前端持续查状态，页面可以展示进度和失败原因。

### 9.2 如果用户刷新页面怎么办

当前登录态通过 uni storage 恢复，作品和任务记录在后端存储。更完整的做法是把当前进行中的任务 ID 也持久化，刷新后重新查询任务状态。

### 9.3 如果任务失败怎么办

后端返回 `failed`、`errorMessage`、`failureStage`、`retryable`。前端展示失败原因，并根据 retryable 决定是否允许重试。

### 9.5 如何保证用户 A 看不到用户 B 的作品

每个请求根据 token 解析 userId，查询任务和作品时带 userId 过滤。生产环境还要加权限校验和数据库索引。

### 9.6 为什么用 fallback

AI 服务可能因为 Key、额度、网络或模型不可用失败。fallback 能保证演示链路不断，同时前端仍能测试任务状态、结果展示和作品中心。

### 9.7 如何接真实 TTS

把 `/api/voice/tasks` 的后台逻辑替换成真实 TTS 服务调用，返回音频 URL。前端不需要改很多，只要继续读 `result.voiceUrl`。

### 9.8 如何接真实数字人

当前已经通过 `avatar-worker` 适配 SadTalker/MuseTalk：输入人像图、音频、文本元数据，输出视频 URL。业务 API 仍然只调用 worker 的创建任务和查询任务接口。真实运行时需要配置模型仓库路径、权重、Python 环境和 GPU。

### 9.9 如何接 RAG

把脚本模板、行业知识、产品资料做成向量库。用户输入主题后，先用 Embedding 召回相关模板和知识，再把召回内容拼进 prompt，让生成文案更贴近业务。

### 9.10 如果改成 LangGraph 怎么做

可以把流程拆成节点：ScriptNode -> VoiceNode -> AvatarNode -> ExportNode

每个节点有输入、输出和失败处理。LangGraph 负责状态转移和条件分支。

### 9.11 为什么前端不直接调用 SadTalker/MuseTalk

> SadTalker/MuseTalk 是 Python 深度学习推理项目，需要 GPU、模型权重和后端文件系统，浏览器前端不能直接运行。前端只负责上传素材、展示状态和结果；推理放在 worker，既安全也更符合工程部署。

### 9.12 为什么 API 和 worker 还要加内部 token

> worker 是内部推理服务，不应该被任意外部请求直接调用。API 调 worker 时带 `AVATAR_WORKER_TOKEN`，worker 校验 `x-worker-token`，这样即使 worker 端口暴露，也能降低被滥用的风险。生产环境还应该配合内网访问、防火墙和 Nginx 限制。

### 9.13 如果真实数字人生成失败怎么定位（排查顺序）

```text
前端任务状态和 errorMessage -> API 日志，看是否成功创建 worker job -> worker /worker/health，看 provider 是否 configured
-> worker 日志，看命令是否执行失败 -> 检查仓库路径、Python 环境、权重、CUDA、输入图片和音频
```

## 12. 项目一句话：AI 创作 Agent 平台

```text
前端三件事：页面、状态、联调。                   页面三模块：工作台、生成页、作品中心。
状态三类：登录态、创作态、任务态。               后端三件事：模型代理、任务编排、密钥安全。
Agent 五步：文案、配音、上传照片、视频、导出。    问题排查四步：控制台、Network、后端日志、端口连通。
```



