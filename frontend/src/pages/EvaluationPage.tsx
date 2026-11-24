import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  Card,
  Button,
  Form,
  Input,
  Select,
  Space,
  message,
  Tag,
  Progress,
  Popconfirm,
  Spin,
  Alert,
  Radio,
  Row,
  Col,
  Modal,
  Tabs,
  Empty,
  Table,
  Drawer,
} from 'antd';
import {
  PlayCircleOutlined,
  StopOutlined,
  FileTextOutlined,
  CodeOutlined,
  CloseOutlined,
  CopyOutlined,
  PlusOutlined,
  ArrowRightOutlined,
  BugOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { EvalTask, Dataset, EndpointTarget, EvalScenario, LLMConfig } from '../types';
import * as api from '../services/api';
import MetricWaveMonitor from '../components/MetricWaveMonitor';

const { TextArea } = Input;

const statusLabelMap: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  cancelling: '取消中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

const metricRequiredFields: Record<string, string[]> = {
  faithfulness: ['response', 'retrieved_contexts'],
  context_recall: ['retrieved_contexts', 'reference'],
  context_precision: ['user_input', 'retrieved_contexts'],
  contextual_relevancy: ['user_input', 'retrieved_contexts'],
  factual_correctness: ['response', 'reference'],
  answer_relevancy: ['user_input', 'response'],
  answer_completeness: ['response', 'reference'],
  retrieval_hit_rate: ['retrieved_context_ids', 'reference_context_ids'],
  retrieval_mrr: ['retrieved_context_ids', 'reference_context_ids'],
  task_completion: ['user_input', 'reference'],
  tool_call_accuracy: ['user_input', 'reference_tool_calls'],
  argument_correctness: ['user_input', 'reference_tool_calls'],
  step_efficiency: ['user_input', 'reference_tool_calls'],
  agent_goal_accuracy: ['user_input', 'reference'],
  topic_adherence: ['user_input', 'reference_topics'],
  turn_relevancy: ['user_input'],
  conversation_completeness: ['user_input', 'reference'],
  knowledge_retention: ['user_input'],
  role_adherence: ['user_input', 'reference_role'],
  turn_faithfulness: ['user_input', 'retrieved_contexts'],
};

const DEFAULT_DEEPSEEK_ENDPOINT_URL = 'https://api.deepseek.com/v1/chat/completions';
const DEFAULT_ENDPOINT_BODY = JSON.stringify(
  {
    model: 'deepseek-chat',
    messages: [{ role: 'user', content: '{{user_input}}' }],
    temperature: 0.2,
    stream: false,
  },
  null,
  2,
);

const EvaluationPage: React.FC = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<EvalTask[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [scenarios, setScenarios] = useState<EvalScenario[]>([]);
  const [llmConfigs, setLLMConfigs] = useState<LLMConfig[]>([]);
  const [endpointTargets, setEndpointTargets] = useState<EndpointTarget[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [consoleTaskId, setConsoleTaskId] = useState<number | null>(null);
  const [consoleLogs, setConsoleLogs] = useState('');
  const [consoleStatus, setConsoleStatus] = useState('');
  const [debugging, setDebugging] = useState(false);
  const [debugResult, setDebugResult] = useState<any>(null);
  const [debugModalOpen, setDebugModalOpen] = useState(false);
  const consoleTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const consoleBoxRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef(false);
  const [formDrawerOpen, setFormDrawerOpen] = useState(false);
  const [cloneSourceTask, setCloneSourceTask] = useState<EvalTask | null>(null);
  const selectedDatasetId = Form.useWatch('dataset_id', form);
  const selectedScenarioId = Form.useWatch('scenario_id', form);
  const selectedEvaluationMode = Form.useWatch('evaluation_mode', form) || 'offline';

  const fetchTasks = useCallback(async () => {
    try {
      const data = await api.listEvaluations();
      const normalized = Array.isArray(data) ? data : data?.items || [];
      setTasks(normalized);
      return normalized;
    } catch {
      message.error('加载评测任务失败');
      return [];
    }
  }, []);

  const fetchOptions = useCallback(async () => {
    try {
      const [ds, sc, lc, et] = await Promise.all([
        api.listDatasets(),
        api.listScenarios(),
        api.listLLMConfigs(),
        api.listEndpointTargets(),
      ]);
      setDatasets(Array.isArray(ds) ? ds : []);
      setScenarios(Array.isArray(sc) ? sc : []);
      setLLMConfigs(Array.isArray(lc) ? lc : []);
      setEndpointTargets(Array.isArray(et) ? et : []);
    } catch {
      message.error('加载选项数据失败');
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchTasks(), fetchOptions()]).finally(() => setLoading(false));
  }, [fetchTasks, fetchOptions]);

  useEffect(() => {
    const hasRunning = tasks.some((t) => ['pending', 'running', 'cancelling'].includes(t.status));
    if (hasRunning) {
      timerRef.current = setInterval(fetchTasks, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [tasks, fetchTasks]);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      const compatibility = getSelectionCompatibility(values.dataset_id, values.scenario_id);
      if (!compatibility.ok) {
        message.error(compatibility.message);
        return;
      }
      setSubmitting(true);
      const created = await api.createEvaluation(values);
      message.success('评测任务已创建');
      form.resetFields();
      setCloneSourceTask(null);
      setFormDrawerOpen(false);
      setTasks((prev) => [created, ...prev.filter((t) => t.id !== created.id)]);
      setConsoleTaskId(created.id);
    } catch {
      message.error('创建评测失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDebugEvaluation = async () => {
    try {
      const values = await form.validateFields();
      const compatibility = getSelectionCompatibility(values.dataset_id, values.scenario_id);
      if (!compatibility.ok) {
        message.error(compatibility.message);
        return;
      }
      setDebugging(true);
      const result = await api.debugEvaluation(values);
      setDebugResult(result);
      setDebugModalOpen(true);
      if (result.success) {
        message.success('评测流程验证通过');
      }
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '验证失败');
    } finally {
      setDebugging(false);
    }
  };

  const handleCancel = async (id: number) => {
    try {
      await api.cancelEvaluation(id);
      message.success('已取消评测');
      fetchTasks();
    } catch {
      message.error('取消失败');
    }
  };

  const handleClone = (task: EvalTask) => {
    const timestamp = new Date().toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
    form.setFieldsValue({
      name: `${task.name} 复跑 ${timestamp}`,
      dataset_id: task.dataset_id,
      scenario_id: task.scenario_id,
      llm_config_id: task.llm_config_id,
      evaluation_mode: task.evaluation_mode || 'offline',
    });
    setCloneSourceTask(task);
    setFormDrawerOpen(true);
    message.success('已复制任务配置');
  };

  const getSelectionCompatibility = (datasetId?: number, scenarioId?: number) => {
    const dataset = datasets.find((d) => d.id === datasetId);
    const scenario = scenarios.find((s) => s.id === scenarioId);
    if (!dataset || !scenario) return { ok: true, message: '' };

    if (dataset.sample_type !== scenario.sample_type) {
      return {
        ok: false,
        message: `样本类型不匹配：数据集是 ${dataset.sample_type}，场景需要 ${scenario.sample_type}`,
      };
    }
    return { ok: true, message: '✓ 兼容' };
  };

  // Setup console polling
  useEffect(() => {
    if (consoleTaskId === null) return;

    const pollLogs = async () => {
      try {
        const data = await api.getEvaluationLogs(consoleTaskId);
        setConsoleLogs(data.logs || '');
        setConsoleStatus(data.status || '');
        if (!userScrolledUp.current && consoleBoxRef.current) {
          setTimeout(() => {
            const box = consoleBoxRef.current;
            if (box) box.scrollTop = box.scrollHeight;
          }, 100);
        }
      } catch {}
    };

    pollLogs();
    consoleTimerRef.current = setInterval(pollLogs, 1000);

    return () => {
      if (consoleTimerRef.current) clearInterval(consoleTimerRef.current);
    };
  }, [consoleTaskId]);

  const progressTask = tasks.find((t) => ['running', 'pending', 'cancelling'].includes(t.status));
  const compatibilityResult = getSelectionCompatibility(selectedDatasetId, selectedScenarioId);

  return (
    <div style={{ padding: 0 }}>
      <Spin spinning={loading}>
        {/* 实时监控区 - 如果有运行中的任务 */}
        {progressTask && (
          <div style={{ marginBottom: 28 }}>
            <Card
              style={{
                background: 'linear-gradient(135deg, rgba(0, 217, 255, 0.08), rgba(255, 200, 87, 0.04))',
                borderColor: 'var(--color-cyan)',
                borderWidth: 1,
              }}
            >
              <Row gutter={24} align="middle" style={{ marginBottom: 16 }}>
                <Col flex="auto">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: 'var(--color-cyan)',
                        animation: 'pulse 2s infinite',
                      }}
                    />
                    <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
                      {progressTask.name}
                    </h3>
                    <Tag color="processing">{statusLabelMap[progressTask.status]}</Tag>
                  </div>
                  <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
                    进度: {progressTask.completed_rows || 0} / {progressTask.total_rows || '?'} 样本
                  </p>
                </Col>
                <Col>
                  <Progress
                    type="circle"
                    percent={Math.min(
                      100,
                      Math.round(
                        ((progressTask.completed_rows || 0) / (progressTask.total_rows || 1)) * 100
                      )
                    )}
                    width={60}
                    format={(percent) => `${percent}%`}
                  />
                </Col>
                <Col>
                  <Space>
                    <Button icon={<CodeOutlined />} onClick={() => setConsoleTaskId(progressTask.id)}>
                      日志
                    </Button>
                    {progressTask.status === 'running' && (
                      <Popconfirm title="确认取消?" onConfirm={() => handleCancel(progressTask.id)}>
                        <Button icon={<StopOutlined />} danger>
                          取消
                        </Button>
                      </Popconfirm>
                    )}
                  </Space>
                </Col>
              </Row>

              <Progress percent={Math.min(100, Math.round(((progressTask.completed_rows || 0) / (progressTask.total_rows || 1)) * 100))} />

              {/* 实时波形监控 */}
              {progressTask.summary_scores && Object.keys(progressTask.summary_scores).length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <MetricWaveMonitor
                    taskId={progressTask.id}
                    metrics={Object.entries(progressTask.summary_scores).map(([name, val]: [string, any]) => ({
                      metric_name: name,
                      metric_display_name: name,
                      metric_type: 'numeric',
                      current_score: typeof val === 'number' ? val : val?.mean ?? null,
                      status: 'completed' as const,
                    }))}
                  />
                </div>
              )}
            </Card>
          </div>
        )}

        {/* 主操作栏 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, color: 'var(--text-primary)' }}>
            评测工作室
          </h2>
          <Button
            type="primary"
            size="large"
            icon={<PlusOutlined />}
            onClick={() => {
              form.resetFields();
              setCloneSourceTask(null);
              setFormDrawerOpen(true);
            }}
          >
            新建评测
          </Button>
        </div>

        {/* 评测表格 */}
        <Card>
          {tasks.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无评测任务"
              style={{ padding: '40px 0' }}
            >
              <Button
                type="primary"
                onClick={() => {
                  form.resetFields();
                  setFormDrawerOpen(true);
                }}
              >
                创建第一个评测
              </Button>
            </Empty>
          ) : (
            <Table
              rowKey="id"
              dataSource={tasks}
              pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 条` }}
              columns={[
                {
                  title: '任务名称',
                  dataIndex: 'name',
                  key: 'name',
                  width: 200,
                },
                {
                  title: '数据集',
                  key: 'dataset',
                  width: 140,
                  render: (_, record) =>
                    record.dataset?.name || datasets.find((d) => d.id === record.dataset_id)?.name || '-',
                },
                {
                  title: '场景',
                  key: 'scenario',
                  width: 140,
                  render: (_, record) =>
                    record.scenario?.name || scenarios.find((s) => s.id === record.scenario_id)?.name || '-',
                },
                {
                  title: '状态',
                  dataIndex: 'status',
                  width: 100,
                  render: (status) => (
                    <Tag
                      color={
                        status === 'completed'
                          ? 'green'
                          : status === 'failed'
                          ? 'red'
                          : status === 'running' || status === 'cancelling'
                          ? 'processing'
                          : 'default'
                      }
                    >
                      {statusLabelMap[status] || status}
                    </Tag>
                  ),
                },
                {
                  title: '进度',
                  key: 'progress',
                  width: 180,
                  render: (_, record) => (
                    <Space direction="vertical" style={{ width: '100%' }} size={4}>
                      <Progress
                        percent={Math.min(100, Math.round(((record.completed_rows || 0) / (record.total_rows || 1)) * 100))}
                        size="small"
                      />
                      <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                        {record.completed_rows || 0} / {record.total_rows || '?'}
                      </span>
                    </Space>
                  ),
                },
                {
                  title: '操作',
                  key: 'actions',
                  width: 240,
                  render: (_, record) => (
                    <Space size="small">
                      <Button
                        type="link"
                        size="small"
                        icon={<CopyOutlined />}
                        onClick={() => handleClone(record)}
                      >
                        克隆
                      </Button>
                      <Button
                        type="link"
                        size="small"
                        icon={<CodeOutlined />}
                        onClick={() => setConsoleTaskId(record.id)}
                      >
                        日志
                      </Button>
                      {record.status === 'completed' && (
                        <Button
                          type="link"
                          size="small"
                          icon={<FileTextOutlined />}
                          onClick={() => navigate(`/reports/${record.id}`)}
                        >
                          报告
                        </Button>
                      )}
                      {(record.status === 'running' || record.status === 'pending') && (
                        <Popconfirm title="确认取消?" onConfirm={() => handleCancel(record.id)}>
                          <Button type="link" size="small" icon={<StopOutlined />} danger>
                            取消
                          </Button>
                        </Popconfirm>
                      )}
                    </Space>
                  ),
                },
              ]}
            />
          )}
        </Card>

        {/* 控制台 Drawer */}
        {consoleTaskId !== null && (
          <Drawer
            title={`评测日志 - 任务 #${consoleTaskId}`}
            onClose={() => setConsoleTaskId(null)}
            placement="bottom"
            height="50vh"
            bodyStyle={{ padding: 0 }}
          >
            <div
              ref={consoleBoxRef}
              onScroll={() => {
                const el = consoleBoxRef.current;
                if (!el) return;
                const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
                userScrolledUp.current = !atBottom;
              }}
              style={{
                background: '#1e1e1e',
                padding: '12px 16px',
                height: '100%',
                overflowY: 'auto',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 12,
                lineHeight: 1.7,
                color: '#d4d4d4',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {consoleLogs
                ? consoleLogs.split('\n').map((line, i) => {
                    let color = '#d4d4d4';
                    if (line.includes('✓')) color = '#4ec9b0';
                    else if (line.includes('✗')) color = '#f44747';
                    else if (line.includes('⚠')) color = '#dcdcaa';
                    return (
                      <div key={i} style={{ color, minHeight: 20 }}>
                        {line}
                      </div>
                    );
                  })
                : '等待日志输出...'}
            </div>
          </Drawer>
        )}

        {/* 新建/克隆表单 Drawer */}
        <Drawer
          title={cloneSourceTask ? `克隆评测 #${cloneSourceTask.id}` : '新建评测'}
          onClose={() => setFormDrawerOpen(false)}
          open={formDrawerOpen}
          width="100%"
          bodyStyle={{ padding: '24px', maxWidth: '1200px' }}
        >
          <Form
            form={form}
            layout="vertical"
            initialValues={{
              evaluation_mode: 'offline',
            }}
          >
            <Row gutter={16}>
              <Col xs={24} sm={12} md={6}>
                <Form.Item
                  name="name"
                  label="任务名称"
                  rules={[{ required: true, message: '请输入名称' }]}
                >
                  <Input placeholder="评测任务名称" />
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Form.Item
                  name="evaluation_mode"
                  label="评测类型"
                  rules={[{ required: true }]}
                >
                  <Radio.Group
                    options={[
                      { label: '已有结果', value: 'offline' },
                      { label: '实时接口', value: 'endpoint' },
                    ]}
                  />
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Form.Item
                  name="dataset_id"
                  label="数据集"
                  rules={[{ required: true, message: '请选择' }]}
                >
                  <Select
                    placeholder="选择数据集"
                    options={datasets.map((d) => ({
                      label: `${d.name} · ${d.sample_type}`,
                      value: d.id,
                    }))}
                  />
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Form.Item
                  name="scenario_id"
                  label="评测场景"
                  rules={[{ required: true, message: '请选择' }]}
                >
                  <Select
                    placeholder="选择场景"
                    options={scenarios.map((s) => ({
                      label: `${s.name} · ${s.scene_type}`,
                      value: s.id,
                    }))}
                  />
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Form.Item
                  name="llm_config_id"
                  label="Judge LLM"
                  rules={[{ required: true, message: '请选择' }]}
                >
                  <Select
                    placeholder="选择 LLM"
                    options={llmConfigs.map((c) => ({
                      label: `${c.name} (${c.model_name})`,
                      value: c.id,
                    }))}
                  />
                </Form.Item>
              </Col>
            </Row>

            {selectedDatasetId && selectedScenarioId && (
              <Alert
                style={{ marginBottom: 16 }}
                type={compatibilityResult.ok ? 'success' : 'warning'}
                showIcon
                message={compatibilityResult.ok ? '✓ 兼容' : '⚠ 警告'}
                description={compatibilityResult.message}
              />
            )}

            <Space>
              <Button icon={<BugOutlined />} loading={debugging} onClick={handleDebugEvaluation}>
                流程验证
              </Button>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={submitting}
                disabled={!compatibilityResult.ok}
                onClick={handleCreate}
              >
                开始评测
              </Button>
            </Space>
          </Form>
        </Drawer>

        {/* 调试结果 Modal */}
        <Modal
          title="评测流程验证"
          open={debugModalOpen}
          onCancel={() => setDebugModalOpen(false)}
          width={900}
          footer={<Button onClick={() => setDebugModalOpen(false)}>关闭</Button>}
        >
          {debugResult && (
            <Space direction="vertical" style={{ width: '100%' }} size={16}>
              <Alert
                type={debugResult.success ? 'success' : 'warning'}
                showIcon
                message={debugResult.message}
                description={
                  <Space wrap>
                    <Tag>{debugResult.is_pass ? '✓ 通过' : '✗ 不通过'}</Tag>
                    <span>{debugResult.execution_time_ms || 0}ms</span>
                  </Space>
                }
              />
              {debugResult.errors?.length > 0 && (
                <Alert type="error" showIcon message="错误" description={debugResult.errors.join('; ')} />
              )}
              {debugResult.warnings?.length > 0 && (
                <Alert
                  type="warning"
                  showIcon
                  message="风险提示"
                  description={debugResult.warnings.join('; ')}
                />
              )}
            </Space>
          )}
        </Modal>

        <style>{`
          @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
          }
        `}</style>
      </Spin>
    </div>
  );
};

export default EvaluationPage;
