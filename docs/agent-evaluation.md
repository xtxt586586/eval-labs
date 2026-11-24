# Agent 评测增强

本项目把输入 trace 归一化到 `otel-agent-trajectory/v1`。支持常见消息格式、工具调用列表、OTLP JSON `resourceSpans/scopeSpans/spans`、扁平 spans，以及 SSE 事件数组。离线数据集可把轨迹放在 `trajectory`；Endpoint 评测可通过响应映射配置：

| 字段 | 映射键 | 用途 |
| --- | --- | --- |
| Agent 轨迹 | `trajectory_path` | human/assistant/tool 消息、OTel spans 和 span events |
| 工具调用 | `tool_calls_path` | Tool Correctness、Argument Correctness、Step Efficiency |
| 工具返回 | `tool_results_path` | Tool Result |
| 最终状态 | `actual_state_path` | State Change |
| 副作用 | `side_effects_path` | 记录发送消息、写库等业务副作用 |
| 安全事件 | `safety_events_path` | 记录策略违规或拒绝事件 |

数据集可选字段：

- `reference_tool_calls`
- `reference_tool_results`
- `expected_state`
- `safety_policy`，例如 `{\"forbidden_tools\":[\"delete_order\"],\"max_tool_calls\":5}`

评测任务会冻结数据集内容、场景指标和 Judge 配置摘要，并保存内容哈希。数据库任务队列通过原子状态更新领取任务；每个 worker 定期刷新心跳，启动恢复只回收超过租约时间的任务，以免多实例启动误判其他实例正在执行的任务。默认最大尝试次数为 3，可用 `EVAL_MAX_TASK_ATTEMPTS` 和 `EVAL_TASK_LEASE_TIMEOUT_SECONDS` 调整。worker 仍运行在 API 进程中；需要独立扩缩容时，应接入 broker-backed worker。

Judge 校准接口：

```text
POST /api/calibration/judge
```

它接收人工标注分数，返回平均绝对误差、重复评分方差、版本信息和逐样本结果，用于检查 Judge 是否适合某个业务指标。当前不会自动应用校准阈值或阻断 CI。

## Operational API

- `GET /api/observability/health` checks database readiness and queue state.
- `GET /api/observability/metrics` returns task counts, queue depth, pass/fail/error totals, and latency percentiles from up to 500 recent completed tasks.
- `GET /api/observability/traces` returns recent task IDs, trace IDs, status, progress, lease attempts, and duration.

These endpoints expose platform task metadata. They do not export OpenTelemetry spans to an OTLP collector.

## Fixture Sandbox

对于需要验证工具返回、状态变化和副作用的 Agent，可以使用安全的工具 Fixture 回放接口：

```text
POST /api/agent-sandbox/run
```

请求中的 `tools` 为 JSON Fixture，每个工具可以声明 `result`、`state_patch` 和 `side_effect`。Sandbox 会按轨迹顺序回放工具调用，应用状态变更，收集副作用，并根据 `safety_policy` 检查禁止工具、最大调用次数和允许的副作用。它不执行任意代码或网络请求，适合开发机和 CI 回归。
