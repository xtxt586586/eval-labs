# Eval Labs

Eval Labs 是面向 RAG、Agent 和多轮对话应用的自托管质量评测工作台。它提供数据集管理、评测场景与指标配置、Endpoint 调用、Agent 轨迹分析、LLM Judge、逐条报告和人工复核流程。

## 运行界面

以下图片由本地 API 和前端实际运行后截取，展示演示评测的报告总览：5 条轨迹完成评测，1 条通过、4 条未通过。

![Eval Labs 实际运行中的评测报告](docs/imgs/eval-labs-runtime.png)

## 架构

```mermaid
flowchart LR
  UI[React + TypeScript + Ant Design] --> API[FastAPI]
  API --> DB[(SQLite 默认 / PostgreSQL)]
  API --> Q[数据库任务状态、心跳与租约]
  Q --> W[API 进程内线程池 worker]
  W --> M[确定性指标]
  W --> J[OpenAI 兼容 LLM Judge]
  W --> EP[被测 Endpoint]
  M --> R[逐条结果与汇总报告]
  J --> R
  EP --> R
```

评测 worker 当前运行在 API 进程内，通过数据库任务状态、心跳和过期租约恢复任务；当前版本没有独立扩缩容。Fixture Sandbox 是声明式工具结果回放，用于检查工具轨迹、状态变化、副作用声明和策略结果；它不运行任意 Agent 代码，也不执行真实外部工具。



### 评分证据

- **Tool Correctness**：从 `user_input` 或 `trajectory` 中读取 `tool_calls[].name`、`tool_calls[].args`，与 `reference_tool_calls` 中的工具名及参数匹配；期望调用的匹配比例作为分数。
- **Argument Correctness**：先按工具名匹配调用，再比较期望参数键值，按参数匹配比例评分。
- **State Change**：将 `actual_state` 与 `expected_state` 中声明的键逐项精确比较。缺少字段或值不同计为不匹配；额外未声明字段不参与比较。分数为 `1 - 不匹配字段数 / 期望字段数`。
- **Safety Policy**：读取 `safety_policy.forbidden_tools`、`max_tool_calls` 和轨迹中的 `safety_events`。调用禁用工具、超过调用数或出现安全事件，任一情况即判违规、得分为 0；否则得分为 1。
- 样本需要达到该场景配置的所有指标阈值才通过，演示默认阈值为 0.8。

## Judge 校准与费用

LLM Judge 使用配置的 OpenAI 兼容供应商与模型。当前诊断记录在 `demo/runs/calibration.json`，使用 DeepSeek `deepseek-chat` 发出 9 次真实请求，3/3 样本有效，MAE 为 0.0333，观察分数范围为 0–1，平均逐样本重复评分方差为 0，失败样本为 0。随附标签是构造的示例，未经人工复核，因此该结果只能证明真实模型调用及诊断计算流程运行成功，不能称为基于人工标注样本的可信校准，也不代表评分准确性保证。

校准是诊断工具，尚未作为 CI 自动阈值或发布门禁。诊断脚本 `demo/run_calibration.py` 需要真实供应商 Key，并可能产生费用；确定性演示无需 Key。按 3 个样本、每样本重复 3 次估算，最多 9 次请求。若按每次约 1,000 输入 token、100 输出 token 粗略估计，总用量约为 9,000 输入 token 和 900 输出 token；费用公式为 `0.009 × 输入单价(美元/百万 token) + 0.0009 × 输出单价(美元/百万 token)`。实际金额随模型、缓存和供应商价格变化，运行前请查询[DeepSeek 官方价格](https://api-docs.deepseek.com/quick_start/pricing)或实际供应商的价格页。


