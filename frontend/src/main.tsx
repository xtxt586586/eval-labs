import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App as AntdApp, ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: theme.defaultAlgorithm,
          token: {
            colorPrimary: '#39766E',
            colorInfo: '#39766E',
            colorSuccess: '#39805E',
            colorWarning: '#A76620',
            colorError: '#B94C4C',
            colorText: '#263432',
            colorTextSecondary: '#596B67',
            colorBgBase: '#F3F6F4',
            colorBgLayout: '#F3F6F4',
            colorBgContainer: '#FFFFFF',
            colorBgElevated: '#FFFFFF',
            colorBorder: '#DCE5E1',
            colorBorderSecondary: '#E7EDEA',
            borderRadius: 6,
            fontFamily:
              'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          },
          components: {
            Button: {
              controlHeight: 36,
              borderRadius: 6,
              primaryShadow: '0 2px 8px rgba(57, 118, 110, 0.18)',
              defaultBg: '#FFFFFF',
              defaultBorderColor: '#DCE5E1',
              defaultColor: '#354642',
            },
            Card: {
              borderRadiusLG: 8,
              headerBg: 'transparent',
              colorBgContainer: '#FFFFFF',
              paddingLG: 20,
            },
            Table: {
              headerBg: '#EEF3F0',
              headerColor: '#536560',
              rowHoverBg: '#F5F8F6',
              borderColor: '#E1E8E4',
              colorBgContainer: 'transparent',
            },
            Modal: {
              borderRadiusLG: 8,
              contentBg: '#FFFFFF',
              headerBg: 'transparent',
            },
            Drawer: {
              colorBgElevated: '#FFFFFF',
            },
            Select: {
              colorBgContainer: '#FFFFFF',
              colorBgElevated: '#FFFFFF',
              optionSelectedBg: '#E8F1EE',
            },
            Input: {
              colorBgContainer: '#FFFFFF',
              activeBorderColor: '#39766E',
              hoverBorderColor: '#9EAEA8',
            },
            Progress: {
              defaultColor: '#39766E',
            },
            Tag: {
              borderRadiusSM: 4,
            },
            Menu: {
              darkItemBg: '#F3F6F4',
              darkItemSelectedBg: '#E8F1EE',
              darkItemSelectedColor: '#39766E',
            },
          },
        }}
      >
        <AntdApp>
          <App />
        </AntdApp>
      </ConfigProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
