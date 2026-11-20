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
            colorPrimary: '#0f766e',
            colorInfo: '#0f766e',
            colorSuccess: '#16846d',
            colorWarning: '#c27a16',
            colorError: '#c05640',
            colorText: '#17202b',
            colorTextSecondary: '#69736f',
            colorBgBase: '#fbfaf7',
            colorBgLayout: '#f4f1eb',
            colorBorder: '#d6d1c8',
            borderRadius: 5,
            boxShadowSecondary: '0 8px 22px rgba(23, 32, 43, 0.07)',
            fontFamily:
              'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          },
          components: {
            Button: {
              controlHeight: 36,
              borderRadius: 5,
              primaryShadow: '0 4px 12px rgba(15, 118, 110, 0.18)',
            },
            Card: {
              borderRadiusLG: 6,
              headerBg: '#fbfaf7',
              paddingLG: 20,
            },
            Layout: {
              bodyBg: '#f4f1eb',
              headerBg: '#fbfaf7',
              siderBg: '#17202b',
            },
            Menu: {
              darkItemBg: '#17202b',
              darkSubMenuItemBg: '#17202b',
              darkItemSelectedBg: '#f4c95d',
              darkItemHoverBg: '#263342',
              darkItemSelectedColor: '#17202b',
              itemBorderRadius: 5,
            },
            Modal: {
              borderRadiusLG: 6,
            },
            Table: {
              headerBg: '#f0ece5',
              headerColor: '#65717d',
              rowHoverBg: '#fff8e7',
              borderColor: '#ded9d0',
            },
            Tag: {
              borderRadiusSM: 4,
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
