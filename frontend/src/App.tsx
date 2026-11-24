import React, { lazy, Suspense, useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { Button, Space, Spin } from 'antd';
import {
  DatabaseOutlined,
  ControlOutlined,
  DeploymentUnitOutlined,
  PartitionOutlined,
  SettingOutlined,
  PlayCircleOutlined,
  LineChartOutlined,
  FileTextOutlined,
  ExperimentOutlined,
  ProfileOutlined,
  PlusOutlined,
  MenuOutlined,
  SafetyCertificateOutlined,
  RadarChartOutlined,
  AuditOutlined,
} from '@ant-design/icons';

import LLMConfigPage from './pages/LLMConfigPage';
import DatasetListPage from './pages/DatasetListPage';
import DatasetDetailPage from './pages/DatasetDetailPage';
import RagDatasetBuilderPage from './pages/RagDatasetBuilderPage';
import ScenarioListPage from './pages/ScenarioListPage';
import MetricListPage from './pages/MetricListPage';
import EndpointTargetPage from './pages/EndpointTargetPage';
import EvaluationPage from './pages/EvaluationPage';
import ReportListPage from './pages/ReportListPage';
import ReportDetailPage from './pages/ReportDetailPage';
import BlindTestPage from './pages/BlindTestPage';
import HomePage from './pages/HomePage';
import JudgeCalibrationPage from './pages/JudgeCalibrationPage';
import AgentSandboxPage from './pages/AgentSandboxPage';
import ObservabilityPage from './pages/ObservabilityPage';
import * as api from './services/api';

const ExperimentWorkbenchPage = lazy(() => import('./pages/ExperimentWorkbenchPage'));

const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [resourceCounts, setResourceCounts] = useState({
    datasets: '…',
    metrics: '…',
    scenarios: '…',
    endpoints: '…',
    llms: '…',
  });

  useEffect(() => {
    let active = true;
    Promise.all([
      api.listDatasets().catch(() => []),
      api.listMetrics().catch(() => []),
      api.listScenarios().catch(() => []),
      api.listEndpointTargets().catch(() => []),
      api.listLLMConfigs().catch(() => []),
    ]).then(([datasets, metrics, scenarios, endpoints, llms]) => {
      if (!active) return;
      setResourceCounts({
        datasets: String(Array.isArray(datasets) ? datasets.length : 0),
        metrics: String(Array.isArray(metrics) ? metrics.length : 0),
        scenarios: String(Array.isArray(scenarios) ? scenarios.length : 0),
        endpoints: String(Array.isArray(endpoints) ? endpoints.length : 0),
        llms: String(Array.isArray(llms) ? llms.length : 0),
      });
    });
    return () => { active = false; };
  }, []);

  // 工作流导航项
  const workflowSteps = [
    { id: 'setup', label: '配置', icon: <SettingOutlined />, isActive: location.pathname.includes('/datasets') || location.pathname.includes('/metrics') || location.pathname.includes('/scenarios') || location.pathname.includes('/llm-configs') || location.pathname.includes('/endpoint-targets') },
    { id: 'execute', label: '执行', icon: <PlayCircleOutlined />, isActive: location.pathname.includes('/workbench') || location.pathname.includes('/evaluations') || location.pathname.includes('/blind-tests') },
    { id: 'analyze', label: '分析', icon: <LineChartOutlined />, isActive: location.pathname.includes('/reports') },
  ];

  // 快速资源卡片
  const quickResources = [
    { id: 'datasets', label: '数据集', icon: <DatabaseOutlined />, stat: resourceCounts.datasets, onClick: () => navigate('/datasets') },
    { id: 'metrics', label: '指标', icon: <ControlOutlined />, stat: resourceCounts.metrics, onClick: () => navigate('/metrics') },
    { id: 'scenarios', label: '场景', icon: <PartitionOutlined />, stat: resourceCounts.scenarios, onClick: () => navigate('/scenarios') },
    { id: 'endpoints', label: '接口', icon: <DeploymentUnitOutlined />, stat: resourceCounts.endpoints, onClick: () => navigate('/endpoint-targets') },
    { id: 'llms', label: '模型', icon: <SettingOutlined />, stat: resourceCounts.llms, onClick: () => navigate('/llm-configs') },
  ];

  // 资源库菜单项
  const resourceMenuItems = [
    { label: '数据管理', path: '/datasets', icon: <DatabaseOutlined /> },
    { label: '指标管理', path: '/metrics', icon: <ControlOutlined /> },
    { label: '场景管理', path: '/scenarios', icon: <PartitionOutlined /> },
    { label: '接口管理', path: '/endpoint-targets', icon: <DeploymentUnitOutlined /> },
    { label: 'LLM配置', path: '/llm-configs', icon: <SettingOutlined /> },
    { label: 'Agent 沙箱', path: '/agent-sandbox', icon: <SafetyCertificateOutlined /> },
    { label: 'Judge 校准', path: '/calibration', icon: <AuditOutlined /> },
    { label: '运行观测', path: '/observability', icon: <RadarChartOutlined /> },
  ];

  // 隐藏侧边栏的路径
  const hideSidebar = location.pathname === '/';

  return (
    <div className="app-shell">
      {/* 顶部 Header */}
      <header className="app-header">
        <div className="brand-mark">
          <div className="brand-icon">⚡</div>
          <div className="brand-text">
            <h3>Eval Labs</h3>
            <div className="subtitle">AI 评测中枢</div>
          </div>
        </div>

        <div className="header-status">
          <div className="status-dot"></div>
          <span>评测内核在线</span>
        </div>

        {!hideSidebar && (
          <Button
            type="text"
            icon={<MenuOutlined />}
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="header-menu-btn"
          />
        )}
      </header>

      <div className="app-body">
        {/* 工作流导航栏 */}
        {!hideSidebar && (
          <nav className="workflow-nav">
            {workflowSteps.map((step) => (
              <button
                key={step.id}
                className={`workflow-nav-item ${step.isActive ? 'active' : ''}`}
                onClick={() => {
                  if (step.id === 'setup') navigate('/datasets');
                  else if (step.id === 'execute') navigate('/workbench');
                  else if (step.id === 'analyze') navigate('/reports');
                }}
              >
                <span className="workflow-nav-icon">{step.icon}</span>
                <span>{step.label}</span>
              </button>
            ))}
            <span className="workflow-nav-divider" aria-hidden="true" />
            <button
              className={`workflow-nav-item ${location.pathname === '/evaluations' ? 'active' : ''}`}
              onClick={() => navigate('/evaluations')}
            >
              <span className="workflow-nav-icon"><FileTextOutlined /></span>
              <span>任务列表</span>
            </button>
            <button
              className={`workflow-nav-item ${location.pathname.includes('/blind-tests') ? 'active' : ''}`}
              onClick={() => navigate('/blind-tests')}
            >
              <span className="workflow-nav-icon"><ProfileOutlined /></span>
              <span>人工盲测</span>
            </button>
            <button className={`workflow-nav-item ${location.pathname === '/agent-sandbox' ? 'active' : ''}`} onClick={() => navigate('/agent-sandbox')}>
              <span className="workflow-nav-icon"><SafetyCertificateOutlined /></span>
              <span>Agent 沙箱</span>
            </button>
            <button className={`workflow-nav-item ${location.pathname === '/calibration' ? 'active' : ''}`} onClick={() => navigate('/calibration')}>
              <span className="workflow-nav-icon"><AuditOutlined /></span>
              <span>Judge 校准</span>
            </button>
            <button className={`workflow-nav-item ${location.pathname === '/observability' ? 'active' : ''}`} onClick={() => navigate('/observability')}>
              <span className="workflow-nav-icon"><RadarChartOutlined /></span>
              <span>运行观测</span>
            </button>
            <div style={{ flex: 1 }} />
            <button className="workflow-nav-item" onClick={() => navigate('/')}>
              <span className="workflow-nav-icon">📊</span>
              <span>首页</span>
            </button>
          </nav>
        )}

        {/* 快速资源栏 */}
        {!hideSidebar && location.pathname === '/evaluations' && (
          <div className="quick-resources">
            {quickResources.map((resource) => (
              <div
                key={resource.id}
                className="resource-card"
                onClick={resource.onClick}
              >
                <div className="resource-card-title">{resource.label}</div>
                <div className="resource-card-stat">{resource.stat}</div>
              </div>
            ))}
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => navigate('/evaluations')}
              style={{ marginLeft: 'auto' }}
            >
              新建评测
            </Button>
          </div>
        )}

        {/* 主内容区 */}
        <div className="workspace-layout">
          <div className="workspace-content">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/datasets" element={<DatasetListPage />} />
              <Route path="/datasets/rag-builder" element={<RagDatasetBuilderPage />} />
              <Route path="/datasets/:id" element={<DatasetDetailPage />} />
              <Route path="/metrics" element={<MetricListPage />} />
              <Route path="/endpoint-targets" element={<EndpointTargetPage />} />
              <Route path="/scenarios" element={<ScenarioListPage />} />
              <Route
                path="/workbench"
                element={
                  <Suspense fallback={<div className="route-loading"><Spin /></div>}>
                    <ExperimentWorkbenchPage />
                  </Suspense>
                }
              />
              <Route path="/evaluations" element={<EvaluationPage />} />
              <Route path="/blind-tests" element={<BlindTestPage />} />
              <Route path="/reports" element={<ReportListPage />} />
              <Route path="/reports/:id" element={<ReportDetailPage />} />
              <Route path="/llm-configs" element={<LLMConfigPage />} />
              <Route path="/agent-sandbox" element={<AgentSandboxPage />} />
              <Route path="/calibration" element={<JudgeCalibrationPage />} />
              <Route path="/observability" element={<ObservabilityPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </div>
      </div>

      {/* 侧边栏菜单 (移动端) */}
      {sidebarOpen && !hideSidebar && (
        <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)}>
          <div className="sidebar-menu" onClick={(e) => e.stopPropagation()}>
            <div className="sidebar-header">
              <h3>资源库</h3>
              <Button type="text" onClick={() => setSidebarOpen(false)}>×</Button>
            </div>
            <div className="sidebar-items">
              {resourceMenuItems.map((item) => (
                <button
                  key={item.path}
                  className="sidebar-item"
                  onClick={() => {
                    navigate(item.path);
                    setSidebarOpen(false);
                  }}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
