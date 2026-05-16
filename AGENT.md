# Agent Instructions

本文件记录本仓库中 AI 编程代理的项目级协作约定。除非用户在当前会话中给出更新的指示，否则优先遵守这里的规则。

## Session 启动流程

- 新的 session 开头先读取 `ARCHITECTURE.md`，理解当前架构、数据流、合并策略和 rating 逻辑。
- 读取架构文档后，根据用户 prompt 行事；不要在没有需求的情况下主动重跑大型数据任务。
- 如果任务涉及新增流程、重要规则、架构变化、数据处理策略或长期约定，结束前把更新内容补充回 `ARCHITECTURE.md`。

## Python 环境

- 本机显式 Python 解释器为：`C:\ProgramData\anaconda3\python.exe`。
- 运行项目脚本、测试或临时验证时，优先使用该解释器，例如：
  - `C:\ProgramData\anaconda3\python.exe main.py --help`
  - `C:\ProgramData\anaconda3\python.exe -m unittest discover -s tests`
- 不要依赖隐式的 `python`、`py` 或当前 shell PATH，除非用户明确要求或正在排查环境问题。

## 执行任务偏好

- 较大的任务优先使用 VS Code Task，包括但不限于：
  - 更新比赛列表：`main.py update`
  - 批量合并比赛：`main.py merge --batch --years ...`
  - 更新 rating：`main.py rating --type ...`
  - 大范围 README 或数据再生成流程
- 若仓库中尚无合适的 VS Code Task，执行大型任务前优先创建或建议创建对应 task，并使用显式 Python 解释器。
- 较小的验证可以直接使用命令行，例如单元测试、`--help`、只读检查、少量文件搜索。
- 不要使用 PowerShell 作为大型任务的首选执行方式；仅在小验证、查看文件、或没有合适 VS Code Task 时使用。
- 不要通过 MCP 服务器执行本仓库的大型数据任务；优先使用 VS Code Task 或本地显式 Python 命令。

## 代码与数据约定

- 保持现有 CLI 入口 `main.py` 的命令行兼容性；交互式入口不能破坏旧参数用法。
- 修改数据处理逻辑时，同步考虑 `data/contests/contests.csv`、`data/merged/*`、`data/rating/*` 和 README 生成链路的影响。
- `csv`、`json` 等生成数据文件应避免直接手动修改；优先修改生成它们的代码或配置，使重新运行流程后能得到正确结果。
- 批量合并默认仍应保持严格 rank 对齐，不要擅自启用实体匹配兜底。
- 对会改变可重复生成结果的规则，尽量补充轻量级测试或可复现验证。

## 收尾要求

- 完成任务前运行与改动范围匹配的验证；小改动至少运行相关单元测试或 CLI help。
- 在最终回复中说明使用了哪些验证，以及是否没有运行某些较重任务。
- 若更新了长期约定、架构说明或工作流，确保 `ARCHITECTURE.md` 已同步记录。