import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Descriptions, Form, Input, InputNumber, Row, Select, Space, Table, Tag, Typography, message } from 'antd';
import { ExperimentOutlined, ReloadOutlined } from '@ant-design/icons';
import * as api from '../services/api';
import type { LLMConfig, MetricDefinition } from '../types';

const { Text, Title } = Typography;

const exampleText = JSON.stringify([
  { sample: { user_input: '订单 84219 已发货，预计 2026-12-03 送达。', reference: '准确告知已发货，预计 2026-12-03 送达。' }, expected_score: 1 },
  { sample: { user_input: '订单 84219 已发货，预计 2026-12-03 送达。', reference: '准确告知已发货，预计 2026-12-03 送达。' }, expected_score: 0 },
], null, 2);

const JudgeCalibrationPage: React.FC = () => {
  const [form] = Form.useForm();
  const [llms, setLlms] = useState<LLMConfig[]>([]);
  const [metrics, setMetrics] = useState<MetricDefinition[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [result, setResult] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try {
      const [nextLlms, nextMetrics, nextHistory] = await Promise.all([
        api.listLLMConfigs(), api.listMetrics(), api.listJudgeCalibrations(),
      ]);
      setLlms(nextLlms || []);
      setMetrics(nextMetrics || []);
      setHistory(nextHistory || []);
      if (!form.getFieldValue('llm_config_id') && nextLlms?.length) {
        form.setFieldValue('llm_config_id', nextLlms.find((item: LLMConfig) => item.is_default)?.id || nextLlms[0].id);
      }
    } catch {
      message.error('加载校准资源失败');
    }
  };

  useEffect(() => { void load(); }, []);

  const judgeTypes = new Set(['numeric', 'discrete', 'aspect_critic', 'builtin_faithfulness', 'builtin_context_recall', 'builtin_context_precision', 'builtin_contextual_relevancy', 'builtin_factual_correctness', 'builtin_answer_relevancy', 'builtin_agent_goal_accuracy', 'builtin_task_completion', 'builtin_topic_adherence', 'builtin_turn_relevancy', 'builtin_conversation_completeness', 'builtin_knowledge_retention', 'builtin_role_adherence', 'builtin_turn_faithfulness']);
  const metricOptions = useMemo(() => metrics.filter((item) => judgeTypes.has(item.metric_type.toLowerCase()) || item.name === 'answer_completeness').map((item) => ({
    value: item.id,
    label: `${item.display_name} · ${item.metric_type}`,
  })), [metrics]);

  const runCalibration = async () => {
    try {
      const values = await form.validateFields();
      const examples = JSON.parse(values.examples_json);
      if (!Array.isArray(examples) || examples.length === 0) throw new Error('样本必须是非空 JSON 数组');
      setLoading(true);
      const next = await api.calibrateJudge({
        llm_config_id: values.llm_config_id,
        metric_definition_id: values.metric_definition_id,
        repeats: values.repeats,
        examples,
      });
      setResult(next);
      await load();
      message.success('Judge 校准完成');
    } catch (error: any) {
      if (!error?.errorFields) message.error(error?.response?.data?.detail || error?.message || 'Judge 校准失败');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { title: '轮次', dataIndex: 'id', key: 'id', render: (id: number) => `#${id}` },
    { title: '指标', dataIndex: 'metric_name', key: 'metric_name' },
    { title: 'Judge 配置版本', dataIndex: 'llm_config_version', key: 'llm_config_version' },
    { title: '指标版本', dataIndex: 'metric_definition_version', key: 'metric_definition_version' },
    { title: '样本', dataIndex: 'requested_sample_count', key: 'requested_sample_count' },
    { title: 'MAE', dataIndex: 'mean_absolute_error', key: 'mae', render: (value: number | null) => value == null ? '-' : value.toFixed(4) },
    { title: '平均重复评分方差', dataIndex: 'score_variance', key: 'variance', render: (value: number | null) => value == null ? '-' : value.toFixed(6) },
    { title: '引擎版本', dataIndex: 'engine_version', key: 'engine_version' },
  ];

  return (
    <div className="page-container">
      <Space align="center" style={{ width: '100%', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>Judge 校准</Title>
          <Text type="secondary">用人工标注分数检查 Judge 的误差与重复评分稳定性。</Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新</Button>
      </Space>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card title="新建校准" size="small">
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message="校准是诊断工具，不会自动保证评分准确，也未接入 CI 阈值。"
              description="将调用所选供应商模型并按其价格计费。只保存样本哈希、标注分数和 Judge 结果；expected_score 应来自人工复核，范围为 0 到 1。单次最多 50 条，重复评分最多 3 次。"
            />
            <Form form={form} layout="vertical" initialValues={{ repeats: 1, examples_json: exampleText }}>
              <Form.Item name="llm_config_id" label="Judge LLM" rules={[{ required: true }]}>
                <Select options={llms.map((item) => ({ value: item.id, label: `${item.name} · ${item.model_name} · v${item.version}` }))} />
              </Form.Item>
              <Form.Item name="metric_definition_id" label="LLM 评判指标" rules={[{ required: true }]}>
                <Select showSearch optionFilterProp="label" options={metricOptions} />
              </Form.Item>
              <Form.Item name="repeats" label="每条样本重复次数" rules={[{ required: true }]}>
                <InputNumber min={1} max={3} style={{ width: 180 }} />
              </Form.Item>
              <Form.Item name="examples_json" label="校准样本 JSON" rules={[{ required: true }]}>
                <Input.TextArea rows={14} spellCheck={false} />
              </Form.Item>
              <Button type="primary" icon={<ExperimentOutlined />} loading={loading} onClick={runCalibration}>运行校准</Button>
            </Form>
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card title="最近校准结果" size="small">
            {result ? (
              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="指标">{result.metric_name}</Descriptions.Item>
                <Descriptions.Item label="有效样本">{result.sample_count}/{result.requested_sample_count}</Descriptions.Item>
                <Descriptions.Item label="评分误差 MAE">{result.mean_absolute_error ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="平均分">{result.mean_score ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="平均重复评分方差">{result.score_variance ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="版本">Judge v{result.llm_config_version} / 指标 v{result.metric_definition_version} / {result.engine_version}</Descriptions.Item>
              </Descriptions>
            ) : <Text type="secondary">运行校准后显示误差、均值和稳定性。</Text>}
            {result?.error_count > 0 && <Alert style={{ marginTop: 12 }} type="warning" showIcon message={`${result.error_count} 条样本未得到有效数值分数`} />}
            {!!result?.samples?.length && (
              <Table
                style={{ marginTop: 12 }}
                size="small"
                rowKey="index"
                pagination={false}
                dataSource={result.samples}
                columns={[
                  { title: '样本', dataIndex: 'index', key: 'index', render: (value: number) => value + 1 },
                  { title: '标注分', dataIndex: 'expected_score', key: 'expected_score' },
                  { title: 'Judge 分', dataIndex: 'observed_scores', key: 'observed_scores', render: (scores: number[]) => scores?.join(', ') || <Tag color="red">失败</Tag> },
                  { title: '误差 / 重复方差', dataIndex: 'mean_absolute_error', key: 'mean_absolute_error', render: (_value: number, row: any) => `${row.mean_absolute_error} / ${row.repeat_score_variance ?? '-'}` },
                ]}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Card title="校准历史" size="small" style={{ marginTop: 16 }}>
        <Table size="small" rowKey="id" dataSource={history} columns={columns} pagination={{ pageSize: 10 }} />
      </Card>
    </div>
  );
};

export default JudgeCalibrationPage;
