import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Space, Progress, Spin, message, Tag, Tooltip, Empty, Row, Col } from 'antd';
import {
  PlusOutlined,
  ArrowRightOutlined,
  DatabaseOutlined,
  ControlOutlined,
  PartitionOutlined,
  DeploymentUnitOutlined,
  SettingOutlined,
  LineChartOutlined,
  PlayCircleOutlined,
  ExperimentOutlined,
  ProfileOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import type { EvalTask, Dataset, EvalScenario, MetricDefinition, EndpointTarget, LLMConfig } from '../types';
import * as api from '../services/api';

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    datasets: 0,
    metrics: 0,
    scenarios: 0,
    endpoints: 0,
    llmConfigs: 0,
    recentEvals: [] as EvalTask[],
    runningEval: null as EvalTask | null,
  });

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      const [datasets, metrics, scenarios, endpoints, llmConfigs, evals] = await Promise.all([
        api.listDatasets().catch(() => []),
        api.listMetrics().catch(() => []),
        api.listScenarios().catch(() => []),
        api.listEndpointTargets().catch(() => []),
        api.listLLMConfigs().catch(() => []),
        api.listEvaluations().catch(() => []),
      ]);

      const evalList: EvalTask[] = Array.isArray(evals) ? evals : (evals as any)?.items || [];
      const runningTask: EvalTask | null = evalList.find((t: EvalTask) => t.status === 'running' || t.status === 'pending') ?? null;
      const recent = evalList.slice(0, 5);

      setStats({
        datasets: Array.isArray(datasets) ? datasets.length : 0,
        metrics: Array.isArray(metrics) ? metrics.length : 0,
        scenarios: Array.isArray(scenarios) ? scenarios.length : 0,
        endpoints: Array.isArray(endpoints) ? endpoints.length : 0,
        llmConfigs: Array.isArray(llmConfigs) ? llmConfigs.length : 0,
        recentEvals: recent,
        runningEval: runningTask,
      });
    } catch (error) {
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const timer = setInterval(fetchStats, 5000);
    return () => clearInterval(timer);
  }, [fetchStats]);

  const resourceCards = [
    {
      title: '数据集',
      icon: <DatabaseOutlined />,
      count: stats.datasets,
      path: '/datasets',
      color: 'cyan',
      description: '管理评测数据',
    },
    {
      title: '指标',
      icon: <ControlOutlined />,
      count: stats.metrics,
      path: '/metrics',
      color: 'gold',
      description: '配置评分指标',
    },
    {
      title: '场景',
      icon: <PartitionOutlined />,
      count: stats.scenarios,
      path: '/scenarios',
      color: 'cyan',
      description: '定义评测场景',
    },
    {
      title: '接口',
      icon: <DeploymentUnitOutlined />,
      count: stats.endpoints,
      path: '/endpoint-targets',
      color: 'gold',
      description: '配置被测接口',
    },
    {
      title: 'LLM',
      icon: <SettingOutlined />,
      count: stats.llmConfigs,
      path: '/llm-configs',
      color: 'cyan',
      description: '管理大语言模型',
    },
  ];

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleOutlined style={{ color: 'var(--color-emerald)' }} />;
      case 'failed':
        return <ExclamationCircleOutlined style={{ color: 'var(--color-red)' }} />;
      case 'running':
      case 'pending':
        return <ClockCircleOutlined style={{ color: 'var(--color-amber)', animation: 'spin 2s linear infinite' }} />;
      default:
        return null;
    }
  };

  const getStatusLabel = (status: string) => {
    const map: Record<string, string> = {
      pending: '等待中',
      running: '运行中',
      completed: '已完成',
      failed: '失败',
      cancelled: '已取消',
    };
    return map[status] || status;
  };

  return (
    <div style={{ padding: '0' }}>
      <Spin spinning={loading}>
        {/* Hero Section - 当前运行任务 */}
        {stats.runningEval ? (
          <Card className="hero-card" style={{ marginBottom: 32, background: 'linear-gradient(135deg, rgba(57, 118, 110, 0.08), rgba(154, 107, 39, 0.04))', borderColor: 'var(--color-cyan)', borderWidth: 1 }}>
            <Row gutter={24} align="middle">
              <Col flex="auto">
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                  <div style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--color-cyan)', animation: 'pulse 2s infinite' }}></div>
                  <h3 style={{ margin: 0, color: 'var(--color-cyan)', fontSize: 16, fontWeight: 600 }}>
                    当前评测进行中
                  </h3>
                </div>
                <h2 style={{ margin: '8px 0 4px', color: 'var(--text-primary)', fontSize: 20 }}>
                  {stats.runningEval.name}
                </h2>
                <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: 13 }}>
                  已完成 {stats.runningEval.completed_rows || 0} / {stats.runningEval.total_rows || '?'} 样本
                </p>
              </Col>
              <Col>
                <Progress
                  type="circle"
                  percent={Math.round(((stats.runningEval.completed_rows || 0) / (stats.runningEval.total_rows || 1)) * 100)}
                  width={80}
                  strokeColor={{
                    '0%': 'var(--color-cyan)',
                    '100%': 'var(--color-gold)',
                  }}
                  format={(percent) => `${percent}%`}
                />
              </Col>
              <Col>
                <Button
                  type="primary"
                  onClick={() => navigate('/evaluations')}
                  icon={<ArrowRightOutlined />}
                >
                  查看详情
                </Button>
              </Col>
            </Row>
          </Card>
        ) : (
          <Card style={{ marginBottom: 24, textAlign: 'center', padding: '18px 20px', background: 'var(--bg-secondary)', border: '1px dashed var(--border-color)' }}>
            <PlayCircleOutlined style={{ fontSize: 28, color: 'var(--color-gold)', marginBottom: 8 }} />
            <p style={{ color: 'var(--text-secondary)', marginBottom: 12 }}>暂无运行中的评测</p>
            <Button
              type="primary"
              size="large"
              icon={<PlusOutlined />}
              onClick={() => navigate('/workbench')}
            >
              开始新评测
            </Button>
          </Card>
        )}

        {/* 快速资源卡片 */}
        <div style={{ marginBottom: 32 }}>
          <h3 style={{ marginBottom: 16, fontSize: 18, fontWeight: 600 }}>资源概览</h3>
          <div className="resource-grid">
            {resourceCards.map((resource) => (
              <div key={resource.path}>
                <Card
                  hoverable
                  style={{ cursor: 'pointer', minHeight: 140, display: 'flex', flexDirection: 'column' }}
                  onClick={() => navigate(resource.path)}
                >
                  <Space direction="vertical" style={{ flex: 1 }}>
                    <div style={{ fontSize: 20 }}>{resource.icon}</div>
                    <div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: `var(--color-${resource.color})`, fontFamily: "'JetBrains Mono', monospace" }}>
                        {resource.count}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                        {resource.title}
                      </div>
                    </div>
                  </Space>
                  <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 'auto' }}>
                    {resource.description}
                  </div>
                </Card>
              </div>
            ))}
          </div>
        </div>

        {/* 快速开始 */}
        <div style={{ marginBottom: 32 }}>
          <h3 style={{ marginBottom: 16, fontSize: 18, fontWeight: 600 }}>快速开始</h3>
          <div className="quick-start-grid">
            <div>
              <Card hoverable onClick={() => navigate('/datasets')} style={{ textAlign: 'center', padding: '24px 16px' }}>
                <DatabaseOutlined style={{ fontSize: 28, color: 'var(--color-cyan)', marginBottom: 12 }} />
                <h4 style={{ margin: '0 0 8px' }}>导入数据集</h4>
                <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: 0 }}>上传或创建评测数据</p>
              </Card>
            </div>
            <div>
              <Card hoverable onClick={() => navigate('/scenarios')} style={{ textAlign: 'center', padding: '24px 16px' }}>
                <PartitionOutlined style={{ fontSize: 28, color: 'var(--color-gold)', marginBottom: 12 }} />
                <h4 style={{ margin: '0 0 8px' }}>创建场景</h4>
                <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: 0 }}>定义评测指标和规则</p>
              </Card>
            </div>
            <div>
              <Card hoverable onClick={() => navigate('/endpoint-targets')} style={{ textAlign: 'center', padding: '24px 16px' }}>
                <DeploymentUnitOutlined style={{ fontSize: 28, color: 'var(--color-cyan)', marginBottom: 12 }} />
                <h4 style={{ margin: '0 0 8px' }}>配置接口</h4>
                <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: 0 }}>连接待测的 API 或模型</p>
              </Card>
            </div>
            <div>
              <Card hoverable onClick={() => navigate('/workbench')} style={{ textAlign: 'center', padding: '24px 16px' }}>
                <ExperimentOutlined style={{ fontSize: 28, color: 'var(--color-emerald)', marginBottom: 12 }} />
                <h4 style={{ margin: '0 0 8px' }}>实验工作台</h4>
                <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: 0 }}>配置、试跑并执行评测</p>
              </Card>
            </div>
            <div>
              <Card hoverable onClick={() => navigate('/blind-tests')} style={{ textAlign: 'center', padding: '24px 16px' }}>
                <ProfileOutlined style={{ fontSize: 28, color: 'var(--color-gold)', marginBottom: 12 }} />
                <h4 style={{ margin: '0 0 8px' }}>人工盲测</h4>
                <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: 0 }}>收集并比较人工偏好</p>
              </Card>
            </div>
            <div>
              <Card hoverable onClick={() => navigate('/evaluations')} style={{ textAlign: 'center', padding: '24px 16px' }}>
                <PlayCircleOutlined style={{ fontSize: 28, color: 'var(--color-emerald)', marginBottom: 12 }} />
                <h4 style={{ margin: '0 0 8px' }}>评测任务</h4>
                <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: 0 }}>查看进度、日志和历史</p>
              </Card>
            </div>
          </div>
        </div>

        {/* 最近评测历史 */}
        {stats.recentEvals.length > 0 && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>最近评测</h3>
              <Button type="text" onClick={() => navigate('/evaluations')}>
                查看全部 <ArrowRightOutlined />
              </Button>
            </div>
            <Card>
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                {stats.recentEvals.map((task) => (
                  <div
                    key={task.id}
                    onClick={() => navigate(`/reports/${task.id}`)}
                    style={{
                      padding: 12,
                      background: 'var(--bg-tertiary)',
                      borderRadius: 6,
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'var(--border-color-light)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'var(--bg-tertiary)';
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        {getStatusIcon(task.status)}
                        <strong>{task.name}</strong>
                        <Tag color={task.status === 'completed' ? 'green' : task.status === 'failed' ? 'red' : 'processing'}>
                          {getStatusLabel(task.status)}
                        </Tag>
                      </div>
                      <p style={{ margin: 0, fontSize: 12, color: 'var(--text-tertiary)' }}>
                        创建于 {new Date(task.created_at).toLocaleString('zh-CN')}
                      </p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 12, color: 'var(--color-cyan)', fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>
                        {task.completed_rows || 0} / {task.total_rows || '?'}
                      </div>
                      <Progress
                        percent={Math.round(((task.completed_rows || 0) / (task.total_rows || 1)) * 100)}
                        size="small"
                        style={{ marginTop: 4, width: 100 }}
                      />
                    </div>
                  </div>
                ))}
              </Space>
            </Card>
          </div>
        )}
      </Spin>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default HomePage;
