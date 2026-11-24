import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Col, Descriptions, Row, Space, Statistic, Table, Tag, Typography, message } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import * as api from '../services/api';

const { Text, Title } = Typography;

const ObservabilityPage: React.FC = () => {
  const [metrics, setMetrics] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [traces, setTraces] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextHealth, nextMetrics, nextTraces] = await Promise.all([
        api.getObservabilityHealth(), api.getObservabilityMetrics(), api.getObservabilityTraces(),
      ]);
      setHealth(nextHealth);
      setMetrics(nextMetrics);
      setTraces(nextTraces || []);
    } catch {
      message.error('读取运行观测数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  const queue = metrics?.queue || health?.queue || {};
  const tasks = metrics?.evaluation_tasks || {};
  const latency = metrics?.task_latency_ms || {};

  const columns = [
    { title: '任务', dataIndex: 'name', key: 'name', render: (name: string, row: any) => <span>{name || `评测 #${row.task_id}`}</span> },
    { title: 'Trace ID', dataIndex: 'trace_id', key: 'trace_id', render: (value: string) => value ? <Text code copyable>{value}</Text> : '-' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (value: string) => <Tag color={value === 'completed' ? 'success' : value === 'failed' ? 'error' : value === 'running' ? 'processing' : 'default'}>{value}</Tag> },
    { title: '进度', key: 'progress', render: (_: unknown, row: any) => `${row.completed_rows}/${row.total_rows}` },
    { title: '耗时', dataIndex: 'duration_ms', key: 'duration_ms', render: (value: number | null) => value == null ? '-' : `${Math.round(value)} ms` },
    { title: '尝试', dataIndex: 'queue_attempts', key: 'queue_attempts' },
    { title: '错误', dataIndex: 'error', key: 'error', ellipsis: true, render: (value: string | null) => value || '-' },
  ];

  return (
    <div className="page-container">
      <Space align="center" style={{ width: '100%', justifyContent: 'space-between', marginBottom: 16 }}>
        <div><Title level={3} style={{ margin: 0 }}>运行观测</Title><Text type="secondary">任务队列、评测结果、耗时分布与 trace 索引。</Text></div>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>刷新</Button>
      </Space>
      {health?.status !== 'ready' && <Alert type="error" showIcon style={{ marginBottom: 16 }} message="服务尚未就绪" description={health?.database || '无法连接观测接口'} />}
      <Row gutter={[12, 12]}>
        <Col xs={12} md={6}><Card size="small"><Statistic title="排队中" value={queue.pending_count || 0} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="运行中" value={queue.active_count || 0} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="完成任务" value={tasks.completed || 0} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="失败任务" value={tasks.failed || 0} /></Card></Col>
      </Row>
      <Row gutter={[12, 12]} style={{ marginTop: 4 }}>
        <Col xs={24} lg={12}>
          <Card size="small" title="任务耗时">
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="样本数">{latency.count || 0}</Descriptions.Item>
              <Descriptions.Item label="平均">{latency.mean == null ? '-' : `${latency.mean} ms`}</Descriptions.Item>
              <Descriptions.Item label="P50">{latency.p50 == null ? '-' : `${latency.p50} ms`}</Descriptions.Item>
              <Descriptions.Item label="P95">{latency.p95 == null ? '-' : `${latency.p95} ms`}</Descriptions.Item>
              <Descriptions.Item label="最长">{latency.max == null ? '-' : `${latency.max} ms`}</Descriptions.Item>
              <Descriptions.Item label="队列 worker">{queue.worker_count || 0}</Descriptions.Item>
              <Descriptions.Item label="最老排队">{queue.oldest_pending_seconds == null ? '-' : `${queue.oldest_pending_seconds} 秒`}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="评测行统计">
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="总行数">{metrics?.evaluation_rows || 0}</Descriptions.Item>
              <Descriptions.Item label="错误行">{metrics?.evaluation_errors || 0}</Descriptions.Item>
              <Descriptions.Item label="通过行">{metrics?.evaluation_pass_rows || 0}</Descriptions.Item>
              <Descriptions.Item label="未通过行">{metrics?.evaluation_fail_rows || 0}</Descriptions.Item>
              <Descriptions.Item label="数据库">{health?.database || '-'}</Descriptions.Item>
              <Descriptions.Item label="服务状态">{health?.status || '-'}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>
      <Card size="small" title="近期任务 Trace" style={{ marginTop: 16 }}>
        <Table size="small" rowKey="task_id" loading={loading} dataSource={traces} columns={columns} pagination={{ pageSize: 10 }} scroll={{ x: 900 }} />
      </Card>
    </div>
  );
};

export default ObservabilityPage;
