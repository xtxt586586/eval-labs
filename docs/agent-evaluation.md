# Agent 评测增强

本项目使用 `agent-trajectory/v1` 作为统一轨迹格式。离线数据集可以把完整轨迹放在 `user_input` 或 `trajectory`，Endpoint 评测可以通过响应映射配置：

| 字段 | 映射键 | 用途 |
| --- | --- | --- |
| Agent 轨迹 | `trajectory_path` | human/assistant/tool 消息和工具调用 |
| 工具调用 | `tool_calls_path` | Tool Correctness、Argument Correctness、Step Efficiency |
| 工具返回 | `tool_results_path` | Tool Result Correctness |
| 最终状态 | `actual_state_path` | State Change Accuracy |
| 副作用 | `side_effects_path` | 记录发送消息、写库等业务副作用 |
| 安全事件 | `safety_events_path` | 记录策略违规或拒绝事件 |

数据集可选字段：

- `reference_tool_calls`
- `reference_tool_results`
- `expected_state`
- `safety_policy`，例如 `{\"forbidden_tools\":[\"delete_order\"],\"max_tool_calls\":5}`

评测任务会冻结数据集内容、场景指标和 Judge 配置摘要。执行器采用持久化任务状态的本地队列，进程重启时会把中断任务标记为可重试失败；生产环境可以把 `submit_evaluation` 替换为 Celery、Temporal 或其他持久化队列实现。

Judge 校准接口：

```text
POST /api/calibration/judge
```

它接收人工标注分数，返回平均绝对误差、重复评分方差和逐样本结果，用于检查 Judge 是否适合某个业务指标。
