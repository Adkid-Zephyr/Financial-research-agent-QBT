# 前端研究入口重构交付摘要

## 本轮目标
- 在不引入新前端框架的前提下，把现有 FastAPI 静态页从“验收控制台”升级成可直接测试的产品化网页入口。
- 支持以下交互闭环：
  - 选择品种、合约、研究周期
  - 输入一句话研究诉求
  - AI 先梳理关键关注点与写作导向
  - 选择身份视角/口吻
  - 触发生成研报
  - 通过 WebSocket 观察运行状态
  - 下载 Markdown / PDF

## 新增与调整的后端能力

### 研究偏好模型
- `futures_research.models.research.ResearchProfile`
- `futures_research.models.research.ResearchPreview`
- `futures_research.models.research.ResearchOptionsCatalog`
- `futures_research.research_profile`
  - 维护研究周期与身份视角选项
  - 构造前端元数据
  - 构造 `request_context`
  - 生成 preview fallback

### 新增 API
- `GET /research/options`
  - 返回：
    - `varieties`
    - `horizons`
    - `personas`
- `POST /research/preview`
  - 请求：
    - `symbol`
    - `research_profile`
  - 返回：
    - `resolved_symbol`
    - `variety_code`
    - `variety`
    - `summary`
    - `key_points`
    - `writing_directives`
    - `recommended_template`

### 调整 API
- `POST /runs`
  - 新增请求字段：
    - `research_profile`
  - 新增响应字段：
    - `run_id`
    - `resolved_symbol`

## 工作流透传方式
- `run_research()` 现在支持：
  - `research_profile`
  - `run_id`
- 自定义研究偏好会写入：
  - `WorkflowState.raw_data.request_context`
- `aggregate_node`
  - 读取 `request_context`
  - 让 Mock 数据摘要体现研究周期 / 身份视角 / 用户关注点
- `analyze_node`
  - 把 `request_context` 传给分析 prompt 和 LLM context
- `write_node`
  - 把 `request_context` 传给写作 prompt 和 LLM context

## 前端页面结构
- 入口：
  - `GET /`
- 静态资源：
  - `/Users/ann/Documents/投研agent/futures_research/api/static/index.html`
  - `/Users/ann/Documents/投研agent/futures_research/api/static/app.js`
  - `/Users/ann/Documents/投研agent/futures_research/api/static/styles.css`

### 页面模块
- 顶部 Hero：
  - 产品定位说明
  - 文档 / 输出目录入口
- 参数条：
  - 品种
  - 合约
  - 研究周期
  - 日期
- 大输入区：
  - 一句话描述研究诉求
  - 引导 suggestion pills
- 身份卡片区：
  - 散户短线高胜率交易者
  - 期货大户交易者
  - 大宗产品供应商
  - 金融公司期货部门
  - 投机者
- AI 需求梳理区：
  - 摘要
  - 关键关注点
  - 写作导向
  - 模板提示
- 状态侧栏：
  - 健康状态
  - 存储状态
  - 当前模型
  - WebSocket 状态
  - 运行事件日志
- 最近一次生成结果：
  - 合约
  - 评分
  - 情绪
  - 状态
  - Markdown / PDF 下载链接
- 保留区：
  - 历史报告查询
  - 批量运行调试入口

## 本轮验收结果
- 单测：
  - `.venv/bin/python -m unittest tests.test_api tests.test_workflow tests.test_websocket`
  - 18 个用例通过
- 前端语法：
  - `node --check futures_research/api/static/app.js`
  - 通过
- 本地 API 烟测：
  - `GET /healthz`
  - `GET /research/options`
  - `POST /research/preview`
  - `GET /`
  - 全部通过
- 真实生成烟测：
  - `POST /runs` 返回 `run_id`
  - WebSocket 收到完整事件链
  - `/reports/{run_id}` 可查询
  - Markdown / PDF 下载链接可访问

## 继续工作建议
- 若继续做网页打磨：
  - 增加“预览后确认再生成”的更明显双阶段交互
  - 增加最近一次任务的状态时间线和滚动自动定位
  - 增加报告正文的富文本预览，而不只是 `pre`
- 若继续做公司客户端接入：
  - 抽象前端所需的契约为 4 个核心接口：
    - `/research/options`
    - `/research/preview`
    - `/runs`
    - `/reports/{run_id}`
  - 再决定客户端侧是否自己维护 WebSocket 事件面板
- 若继续做模型效果：
  - 让真实 LLM 的 preview 输出和正式 report 模板联动得更深
  - 把 `recommended_template` 真正映射到细化 prompt 模板，而不仅是提示标签
