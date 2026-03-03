import React, { lazy, Suspense } from 'react';
import { Layout, Menu, Spin, theme } from 'antd';
import { UserOutlined, MailOutlined, SettingOutlined, RocketOutlined, PieChartOutlined } from '@ant-design/icons';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Campaigns = lazy(() => import('./pages/Campaigns'));
const Contacts = lazy(() => import('./pages/Contacts'));
const Templates = lazy(() => import('./pages/Templates'));
const Settings = lazy(() => import('./pages/Settings'));

const { Header, Content, Sider } = Layout;

const routeFallback = (
  <div style={{ padding: 50, textAlign: 'center' }}>
    <Spin size="large" />
  </div>
);

const App = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    token: { colorBgContainer },
  } = theme.useToken();

  const menuItems = [
    { key: '/', icon: <PieChartOutlined />, label: '数据看板' },
    { key: '/campaigns', icon: <RocketOutlined />, label: '发信任务' },
    { key: '/contacts', icon: <UserOutlined />, label: '联系人管理' },
    { key: '/templates', icon: <MailOutlined />, label: '模板管理' },
    { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible>
        <div style={{ height: 32, margin: 16, background: 'rgba(255, 255, 255, 0.2)', textAlign: 'center', color: '#fff', lineHeight: '32px', fontSize: '14px', fontWeight: 'bold' }}>邮件推送系统</div>
        <Menu theme="dark" selectedKeys={[location.pathname]} mode="inline" onClick={(e) => navigate(e.key)} items={menuItems} />
      </Sider>
      <Layout>
        <Header style={{ padding: '0 16px', background: colorBgContainer, display: 'flex', justifyContent: 'flex-end', alignItems: 'center' }}>
          {/* 登录已移除，保留页头区域用于后续扩展 */}
        </Header>
        <Content style={{ margin: '16px' }}>
          <Suspense fallback={routeFallback}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/campaigns" element={<Campaigns />} />
              <Route path="/contacts" element={<Contacts />} />
              <Route path="/templates" element={<Templates />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </Suspense>
        </Content>
      </Layout>
    </Layout>
  );
};

export default App;
