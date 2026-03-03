import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App as AntApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App.jsx';
import 'antd/dist/reset.css';

console.log('Main entry point loaded');

try {
  const root = ReactDOM.createRoot(document.getElementById('root'));
  root.render(
    <ConfigProvider locale={zhCN}>
      <AntApp>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <App />
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
  console.log('React root rendered');
} catch (e) {
  console.error('React render failed:', e);
}
