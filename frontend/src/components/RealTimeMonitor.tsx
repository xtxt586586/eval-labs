import React from 'react';
import { Card, Space, Row, Col } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined } from '@ant-design/icons';

interface MetricWaveProps {
  metricName: string;
  displayName: string;
  score?: number | null;
  reason?: string;
  threshold?: number | null;
  isLoading?: boolean;
  hasError?: boolean;
  errorMessage?: string;
}

// 模拟波形数据生成
const generateWaveformData = (count: number = 40): number[] => {
  const data: number[] = [];
  for (let i = 0; i < count; i++) {
    data.push(Math.sin(i * 0.3) * 0.3 + 0.5 + Math.random() * 0.1);
  }
  return data;
};

/**
 * 实时评测指标波形显示组件
 * 模拟示波器的多通道显示
 */
export const MetricWaveChart: React.FC<MetricWaveProps> = ({
  metricName,
  displayName,
  score,
  reason,
  threshold,
  isLoading,
  hasError,
  errorMessage,
}) => {
  const waveData = generateWaveformData(40);

  // 判断是否通过阈值
  const isPassed = score !== null && score !== undefined && threshold ? score >= threshold : undefined;

  // 绘制波形的 SVG
  const points = waveData
    .map((value, i) => `${(i / (waveData.length - 1)) * 100},${(1 - value) * 100}`)
    .join(' ');

  return (
    <div className="metric-wave-chart">
      <div className="metric-wave-header">
        <div>
          <div className="metric-wave-title">{displayName}</div>
          <div className="metric-wave-status" style={{ marginTop: 4 }}>
            {isLoading ? (
              <span style={{ color: '#ff9500', display: 'flex', alignItems: 'center', gap: 6 }}>
                <ClockCircleOutlined /> 计算中...
              </span>
            ) : hasError ? (
              <span style={{ color: '#ff5252', display: 'flex', alignItems: 'center', gap: 6 }}>
                <CloseCircleOutlined /> {errorMessage || '错误'}
              </span>
            ) : score !== null && score !== undefined ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {isPassed ? (
                  <CheckCircleOutlined style={{ color: '#2ecc71' }} />
                ) : (
                  <CloseCircleOutlined style={{ color: '#ff5252' }} />
                )}
                {reason && <span style={{ fontSize: 12, color: '#a9b1bb' }}>{reason}</span>}
              </span>
            ) : null}
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          {score !== null && score !== undefined && (
            <div className="metric-wave-value">{score.toFixed(2)}</div>
          )}
          {threshold !== null && threshold !== undefined && (
            <div style={{ fontSize: 11, color: '#a9b1bb', marginTop: 2 }}>
              阈值: {threshold.toFixed(2)}
            </div>
          )}
        </div>
      </div>

      {/* 波形 SVG */}
      {!isLoading && !hasError && (
        <svg viewBox="0 0 100 100" style={{ width: '100%', height: 60, marginTop: 8 }}>
          {/* 背景网格 */}
          <g stroke="rgba(255, 255, 255, 0.05)" strokeWidth="0.5">
            {[0, 25, 50, 75, 100].map((y) => (
              <line key={`h-${y}`} x1="0" y1={y} x2="100" y2={y} />
            ))}
            {[0, 25, 50, 75, 100].map((x) => (
              <line key={`v-${x}`} x1={x} y1="0" x2={x} y2="100" />
            ))}
          </g>

          {/* 波形曲线 */}
          <polyline
            points={points}
            fill="none"
            stroke="url(#waveGradient)"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
          />

          {/* 渐变定义 */}
          <defs>
            <linearGradient id="waveGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(0, 217, 255, 0.3)" />
              <stop offset="50%" stopColor="rgba(0, 217, 255, 0.8)" />
              <stop offset="100%" stopColor="rgba(255, 200, 87, 0.6)" />
            </linearGradient>
          </defs>

          {/* 阈值线 */}
          {threshold !== null && threshold !== undefined && (
            <line
              x1="0"
              y1={(1 - threshold) * 100}
              x2="100"
              y2={(1 - threshold) * 100}
              stroke="rgba(255, 149, 0, 0.4)"
              strokeWidth="0.8"
              strokeDasharray="2,2"
              vectorEffect="non-scaling-stroke"
            />
          )}
        </svg>
      )}
    </div>
  );
};

/**
 * 实时监控面板 - 显示所有正在评测的指标
 */
export const RealTimeMonitorPanel: React.FC<{
  taskName: string;
  progress: number;
  completedRows: number;
  totalRows: number;
  elapsedTime: string;
  metrics: MetricWaveProps[];
}> = ({ taskName, progress, completedRows, totalRows, elapsedTime, metrics }) => {
  return (
    <Card
      style={{
        background: 'var(--bg-secondary)',
        marginBottom: 24,
      }}
      title={
        <div>
          <div style={{ fontSize: 14, color: '#a9b1bb', fontWeight: 500 }}>实时评测监控</div>
          <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4 }}>{taskName}</div>
        </div>
      }
      extra={
        <div style={{ fontSize: 12, color: '#a9b1bb' }}>
          {completedRows}/{totalRows} · {elapsedTime}
        </div>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }} size={4}>
        {/* 总体进度条 */}
        <div style={{ marginBottom: 16 }}>
          <div
            style={{
              background: 'linear-gradient(90deg, #00d9ff, #ffc857)',
              height: 2,
              borderRadius: 1,
              width: `${progress}%`,
              transition: 'width 0.3s ease',
            }}
          />
          <div
            style={{
              fontSize: 11,
              color: '#a9b1bb',
              marginTop: 4,
              display: 'flex',
              justifyContent: 'space-between',
            }}
          >
            <span>已完成</span>
            <span>{progress}%</span>
          </div>
        </div>

        {/* 指标波形 */}
        <div style={{ paddingTop: 8 }}>
          {metrics.map((metric) => (
            <MetricWaveChart key={metric.metricName} {...metric} />
          ))}
        </div>
      </Space>
    </Card>
  );
};

/**
 * 评测配置面板 - 可折叠的配置编辑器
 */
export const EvaluationConfigPanel: React.FC<{
  isExpanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}> = ({ isExpanded, onToggle, children }) => {
  return (
    <div style={{ marginBottom: 24 }}>
      <div
        onClick={onToggle}
        style={{
          padding: '12px 16px',
          background: 'var(--bg-tertiary)',
          border: '1px solid var(--border-color)',
          borderRadius: 8,
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          transition: 'all 0.2s',
          marginBottom: isExpanded ? 16 : 0,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = '#00d9ff';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = 'var(--border-color)';
        }}
      >
        <span style={{ fontWeight: 600, fontSize: 14 }}>评测配置</span>
        <span style={{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>
          ▼
        </span>
      </div>

      {isExpanded && (
        <Card
          style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            marginTop: 0,
          }}
        >
          {children}
        </Card>
      )}
    </div>
  );
};

/**
 * 评测历史列表 - 简洁卡片式
 */
export const EvaluationHistoryPanel: React.FC<{
  tasks: any[];
  onSelectTask: (taskId: number) => void;
  onCloneTask: (task: any) => void;
}> = ({ tasks, onSelectTask, onCloneTask }) => {
  return (
    <Card title="评测历史" style={{ marginTop: 24 }}>
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        {tasks.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '20px 0', color: '#a9b1bb' }}>
            暂无评测记录
          </div>
        ) : (
          tasks.map((task) => (
            <Row
              key={task.id}
              gutter={12}
              align="middle"
              onClick={() => onSelectTask(task.id)}
              style={{
                padding: 12,
                background: 'var(--bg-tertiary)',
                borderRadius: 6,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--border-color-light)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'var(--bg-tertiary)';
              }}
            >
              <Col flex="auto">
                <div style={{ fontWeight: 600, marginBottom: 4 }}>{task.name}</div>
                <div style={{ fontSize: 12, color: '#a9b1bb' }}>
                  {new Date(task.created_at).toLocaleString('zh-CN')}
                </div>
              </Col>
              <Col>
                <div style={{ fontSize: 12, color: '#00d9ff', fontFamily: "'JetBrains Mono', monospace" }}>
                  {task.completed_rows}/{task.total_rows}
                </div>
              </Col>
            </Row>
          ))
        )}
      </Space>
    </Card>
  );
};
