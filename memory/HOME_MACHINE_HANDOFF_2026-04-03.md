# 家庭电脑续接说明

## 当前代码基线
- GitHub 分支：`ui-redesign-plusIDENTITY`
- 最新提交：`cab47d7`
- 提交说明：`Add research studio UI redesign`

## 当前完成状态
- 已完成“期货研报工作台”网页入口重构。
- 前端已支持：
  - 选择品种、合约、研究周期、日期
  - 输入一句话研究诉求
  - AI 先梳理需求摘要、关键点、写作导向
  - 选择身份视角
  - 触发单次生成
  - WebSocket 观察运行状态
  - 查看历史报告
  - 下载 Markdown / PDF
- 后端新增接口：
  - `GET /research/options`
  - `POST /research/preview`
  - `POST /runs` 已支持 `research_profile`
- 研究偏好已打通到工作流 `aggregate -> analyze -> write`。

## 已完成验证
- 单测：
  - `.venv/bin/python -m unittest tests.test_api tests.test_workflow tests.test_websocket`
  - 18 个用例通过
- 真实阿里百炼兼容接口测试：
  - `ANTHROPIC_BASE_URL=https://coding.dashscope.aliyuncs.com/apps/anthropic`
  - `LLM_MODEL=kimi-k2.5`
  - `preview` 已跑通
  - `runs` 已跑通
  - 首轮审核不过后自动进入第二轮重写并通过

## 回家后续接建议
1. `git clone` 仓库后切到分支 `ui-redesign-plusIDENTITY`
2. 先阅读：
   - `memory/PROJECT_MEMORY.md`
   - `memory/FRONTEND_STUDIO_HANDOFF.md`
   - 本文件
3. 检查本机环境：
   - Python 虚拟环境
   - `.env` 或运行时环境变量
   - 阿里百炼 token
   - SQLite / PostgreSQL 配置
4. 启动本地前端：
   - `uvicorn futures_research.api.app:app --host 127.0.0.1 --port 8021`
5. 打开：
   - `http://127.0.0.1:8021/`
   - `http://127.0.0.1:8021/docs`

## 下一步优先方向
- 继续打磨网页端交互和视觉层次
- 或把当前前端交互抽象为公司客户端可嵌入的接口契约
- 暂时不要扩到 Phase 2

## 可直接复用的上下文提示词
```text
继续这个项目。先阅读以下记忆文件：
/Users/ann/Documents/投研agent/memory/PROJECT_MEMORY.md
/Users/ann/Documents/投研agent/memory/FRONTEND_STUDIO_HANDOFF.md
/Users/ann/Documents/投研agent/memory/HOME_MACHINE_HANDOFF_2026-04-03.md

当前代码以 GitHub 分支 `ui-redesign-plusIDENTITY` 为准，这个分支已经包含最新的网页端前端重构成果。
请基于当前状态继续开发，优先方向是：
1. 打磨网页端交互和视觉
2. 或整理成公司客户端可嵌入的接口契约
不要扩到 Phase 2。
```
