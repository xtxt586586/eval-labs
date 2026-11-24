import React, { useEffect, useState } from 'react';
import { Card, Space, Tag, Progress, Empty, Spin } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined } from '@ant-design/icons';

interface MetricWaveData {
  metric_name: string;
  metric_display_name: string;
  metric_type: string;
  current_score?: number | null;
  reason?: string;
  is_pass?: boolean | null;
  error?: string | null;
  status: 'computing' | 'completed' | 'failed';
}

interface MetricWaveMonitorProps {
  taskId: number | null;
  metrics?: MetricWaveData[];
  totalProgress?: number;
  completedRows?: number;
  totalRows?: number;
  elapsedTime?: number;
}

const MetricWaveMonitor: React.FC<MetricWaveMonitorProps> = ({
  taskId,
  metrics = [],
  totalProgress = 0,
  completedRows = 0,
  totalRows = 0,
  elapsedTime = 0,
}) => {
  const [waveforms, setWaveforms] = useState<Record<string, number[]>>({});

  useEffect(() => {
    if (!metrics.length) return;

    // 模拟波形数据生成（实际应由 WebSocket 或轮询提供）
    metrics.forEach((metric) => {
      const key = metric.metric_name;
      if (!waveforms[key]) {
        setWaveforms((prev) => ({
          ...prev,
          [key]: [],
        }));
      }
      if (metric.current_score !== undefined && metric.current_score !== null) {
        const newScore: number = metric.current_score;
        setWaveforms((prev) => ({
          ...prev,
          [key]: [...(prev[key] || []), newScore].slice(-20),
        }));
      }
    });
  }, [metrics, waveforms]);

  const formatTime = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  const getMetricStatus = (metric: MetricWaveData) => {
    if (metric.status === 'computing') {
      return <LoadingOutlined style={{ color: '#ff9500', animation: 'spin 1s linear infinite' }} />;
    }
    if (metric.status === 'failed') {
      return <CloseCircleOutlined style={{ color: '#ff5252' }} />;
    }
    if (metric.is_pass === true) {
      return <CheckCircleOutlined style={{ color: '#2ecc71' }} />;
    }
    if (metric.is_pass === false) {
      return <CloseCircleOutlined style={{ color: '#ff5252' }} />;
    }
    return null;
  };

  // 简单波形可视化（ASCII art 风格）
  const generateWaveASCII = (values: number[]) => {
    if (!values.length) return '';
    const normalized = values.map((v) => Math.round(v * 10));
    return normalized.map((v) => (v > 5 ? '█' : v > 2 ? '▆' : '░')).join('');
  };

  if (!metrics.length) {
    return <Empty description="暂无指标数据" />;
  }

  return (
    <div className="metric-wave-monitor">
      {/* 全局进度条 */}
      {totalRows > 0 && (
        <Card className="monitor-progress-card" style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>
                评测进度
              </span>
              <span style={{ fontSize: 12, color: 'var(--text-tertiary)', fontFamily: "'JetBrains Mono', monospace" }}>
                {completedRows} / {totalRows} · 耗时 {formatTime(elapsedTime)}
              </span>
            </div>
            <Progress
              percent={totalProgress}
              strokeColor={{
                '0%': '#00d9ff',
                '100%': '#ffc857',
              }}
              status={totalProgress === 100 ? 'success' : 'active'}
              format={(percent) => `${percent}%`}
              style={{ marginBottom: 0 }}
            />
          </Space>
        </Card>
      )}

      {/* 指标通道卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
        {metrics.map((metric) => (
          <Card
            key={metric.metric_name}
            className="metric-wave-chart"
            style={{
              borderColor:
                metric.status === 'failed'
                  ? '#ff5252'
                  : metric.is_pass === true
                    ? '#2ecc71'
                    : metric.is_pass === false
                      ? '#ff5252'
                      : '#00d9ff',
            }}
          >
            <div className="metric-wave-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1 }}>
                <div style={{ fontSize: 14 }}>
                  {getMetricStatus(metric)}
                </div>
                <div>
                  <div className="metric-wave-title">
                    {metric.metric_display_name || metric.metric_name}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
                    {metric.metric_type}
                  </div>
                </div>
              </div>
              {metric.status === 'computing' && (
                <Tag color="processing">计算中</Tag>
              )}
            </div>

            {/* 波形值显示 */}
            {metric.current_score !== undefined && metric.current_score !== null ? (
              <div style={{ marginBottom: 12, paddingBottom: 12, borderBottom: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <div className="metric-wave-value">
                    {metric.current_score.toFixed(2)}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                    / 1.00
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ marginBottom: 12, paddingBottom: 12, borderBottom: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: 12, color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
                  {metric.status === 'computing' ? '计算中...' : '未计算'}
                </div>
              </div>
            )}

            {/* 理由 */}
            {metric.reason && (
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 12 }}>
                <strong style={{ display: 'block', marginBottom: 4 }}>评分理由：</strong>
                {metric.reason}
              </div>
            )}

            {/* 错误信息 */}
            {metric.error && (
              <div style={{ fontSize: 12, color: '#ff5252', padding: 8, background: 'rgba(255, 82, 82, 0.08)', borderRadius: 4 }}>
                <strong>错误：</strong> {metric.error}
              </div>
            )}

            {/* 简单波形图 */}
            {waveforms[metric.metric_name]?.length > 0 && (
              <div style={{ marginTop: 12, padding: '8px 0', borderTop: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>波形历史</div>
                <div
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 14,
                    color: 'var(--color-cyan)',
                    letterSpacing: 2,
                    wordBreak: 'break-all',
                  }}
                >
                  {generateWaveASCII(waveforms[metric.metric_name])}
                </div>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
};

export default MetricWaveMonitor;
