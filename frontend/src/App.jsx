import React, { useState, useEffect } from 'react';
import { Layout, Menu, theme, Card, Form, Input, Button, Upload, message, Table, Select, Tag, Progress, Statistic, Popconfirm, DatePicker, Row, Col } from 'antd';
import { UploadOutlined, UserOutlined, MailOutlined, SettingOutlined, RocketOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { Routes, Route, Link, useNavigate, useLocation } from 'react-router-dom';
import api, { contactApi } from './services/api';
import dayjs from 'dayjs';

const { Header, Content, Sider } = Layout;
const { TextArea } = Input;

// --- Components ---

const Settings = () => {
  const [form] = Form.useForm();

  useEffect(() => {
    api.get('/settings').then(res => {
      if(res.data) form.setFieldsValue(res.data);
    });
  }, []);

  const onFinish = (values) => {
    api.post('/settings', values).then(() => message.success('保存成功！'));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <Card title="阿里云配置 (DirectMail)">
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <div style={{ display: 'flex', gap: 20 }}>
            <Form.Item name="access_key_id" label="Aliyun Access Key ID" style={{flex: 1}}><Input /></Form.Item>
            <Form.Item name="access_key_secret" label="Aliyun Access Key Secret" style={{flex: 1}}><Input.Password /></Form.Item>
          </div>
          <Form.Item name="region_id" label="区域 ID" initialValue="cn-hangzhou"><Input placeholder="cn-hangzhou" /></Form.Item>
          
          <hr style={{ border: '0.5px solid #eee', margin: '20px 0' }} />
          
          <h3>腾讯云配置 (SES)</h3>
          <div style={{ display: 'flex', gap: 20 }}>
            <Form.Item name="tencent_secret_id" label="Tencent Secret ID" style={{flex: 1}}><Input /></Form.Item>
            <Form.Item name="tencent_secret_key" label="Tencent Secret Key" style={{flex: 1}}><Input.Password /></Form.Item>
          </div>
          <Form.Item name="tencent_region" label="腾讯云区域" initialValue="ap-guangzhou"><Input placeholder="ap-guangzhou" /></Form.Item>
          
          <hr style={{ border: '0.5px solid #eee', margin: '20px 0' }} />
          
          <Form.Item name="from_alias" label="全局默认发件人昵称" tooltip="当模板未设置时使用"><Input /></Form.Item>
          <Button type="primary" htmlType="submit">保存所有配置</Button>
        </Form>
      </Card>
    </div>
  );
};

const Contacts = () => {
  const [lists, setLists] = useState([]);
  
  const refresh = () => api.get('/contacts').then(res => setLists(res.data));
  useEffect(() => { refresh(); }, []);

  const uploadProps = {
    name: 'file',
    customRequest: async (options) => {
      try {
        // 使用文件名作为列表名
        const listName = options.file.name.split('.')[0];
        // 调用封装好的上传方法，它会自动处理 FormData 和 list_name
        await contactApi.upload(options.file, listName);
        message.success('上传成功');
        refresh();
        options.onSuccess();
      } catch (e) {
        console.error(e);
        message.error('上传失败: ' + (e.response?.data?.detail || e.message));
        options.onError();
      }
    }
  };

  const handleDelete = (id) => {
      api.delete(`/contacts/${id}`).then(() => {
          message.success('列表已删除');
          refresh();
      });
  };

  const columns = [
    { title: '列表名称', dataIndex: 'name', key: 'name' },
    { title: '总人数', dataIndex: 'total_count', key: 'count' },
    { title: '创建时间', dataIndex: 'created_at', key: 'date', render: (text) => new Date(text + (text.endsWith('Z') ? '' : 'Z')).toLocaleString('zh-CN', { hour12: false }) },
    { title: '操作', key: 'action', render: (_, record) => (
        <Popconfirm title="确定删除吗？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger type="text">删除</Button>
        </Popconfirm>
    )}
  ];

  return (
    <Card title="联系人列表管理" extra={<Upload {...uploadProps} showUploadList={false}><Button icon={<UploadOutlined />}>上传 CSV 文件</Button></Upload>}>
      <Table dataSource={lists} columns={columns} rowKey="id" />
      <div style={{marginTop: 10, color: '#666'}}>
        * CSV 文件必须包含 <b>EmailAddr</b> 列（收件人邮箱），可选包含 <b>UserName</b>, <b>Birthday</b> 等变量列。<br/>
        * 系统会自动过滤重复和无效的邮件地址，请在上传前删除文件底部的说明文字。
      </div>
    </Card>
  );
};

const Templates = () => {
  const [templates, setTemplates] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form] = Form.useForm();

  const refresh = () => api.get('/templates').then(res => setTemplates(res.data));
  useEffect(() => { refresh(); }, []);

  const onFinish = (values) => {
    if (editingId) {
        api.put(`/templates/${editingId}`, values).then(() => {
            message.success('模板更新成功');
            setEditingId(null);
            form.resetFields();
            refresh();
        });
    } else {
        api.post('/templates', values).then(() => {
            message.success('模板创建成功');
            form.resetFields();
            refresh();
        });
    }
  };
  
  const handleEdit = (record) => {
      setEditingId(record.id);
      form.setFieldsValue(record);
  };
  
  const handleCancelEdit = () => {
      setEditingId(null);
      form.resetFields();
  };
  
  const handleSync = async () => {
    message.loading({ content: '正在从阿里云同步...', key: 'syncing' });
    try {
      const res = await api.post('/templates/sync');
      message.success({ content: res.data.message, key: 'syncing' });
      refresh();
    } catch (e) {
      message.error({ content: '同步失败: ' + (e.response?.data?.detail || e.message), key: 'syncing' });
    }
  };

  const columns = [
    { title: '模板名称', dataIndex: 'title', key: 'title' },
    { title: '发送人名称', dataIndex: 'from_alias', key: 'alias' },
    { title: '邮件标题', dataIndex: 'subject', key: 'subject' },
    { title: '操作', key: 'action', render: (_, record) => (
        <Button icon={<EditOutlined />} size="small" onClick={() => handleEdit(record)}>编辑</Button>
    )}
  ];

  return (
    <div style={{ display: 'flex', gap: 20 }}>
      <Card title={editingId ? "编辑模板" : "新建模板"} style={{ flex: 1 }}>
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item name="title" label="模板名称 (内部标识)" required><Input placeholder="例如：元旦促销模板" /></Form.Item>
          <Form.Item name="from_alias" label="发送人名称" required tooltip="例如：阿里云通知。收件人看到的邮件来源名称"><Input placeholder="例如：市场部" /></Form.Item>
          <Form.Item name="subject" label="邮件标题" required tooltip="使用 {Name} 代表收件人姓名，或 CSV 中的其他列名如 {Birthday}"><Input placeholder="例如：你好 {Name}，这是给你的专属优惠" /></Form.Item>
          <Form.Item name="body" label="邮件正文 (支持 HTML)" required tooltip="使用 {Name} 代表收件人姓名"><TextArea rows={6} placeholder="<html><body><h1>你好 {Name}!</h1></body></html>" /></Form.Item>
          <div style={{display: 'flex', gap: 10}}>
              <Button type="primary" htmlType="submit">{editingId ? "更新模板" : "创建模板"}</Button>
              {editingId && <Button onClick={handleCancelEdit}>取消</Button>}
          </div>
        </Form>
      </Card>
      <Card title="已有模板" style={{ flex: 1 }} extra={<Button icon={<RocketOutlined />} onClick={handleSync}>从阿里云同步</Button>}>
        <Table dataSource={templates} columns={columns} rowKey="id" />
      </Card>
    </div>
  );
};

const Campaigns = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [lists, setLists] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [senders, setSenders] = useState([]);
  const [form] = Form.useForm();
  
  // 监听表单中的 provider 字段
  const selectedProvider = Form.useWatch('provider', form);

  const refresh = () => {
    api.get('/campaigns').then(res => setCampaigns(res.data));
    api.get('/contacts').then(res => setLists(res.data));
    api.get('/templates').then(res => setTemplates(res.data));
  };
  
  useEffect(() => { 
      refresh(); 
      const interval = setInterval(refresh, 3000);
      return () => clearInterval(interval);
  }, []);

  const loadSenders = () => {
    api.get('/senders/sync').then(res => {
      // 后端返回 [{email, provider, label}, ...]
      setSenders(res.data.map(s => ({
          label: s.label || `${s.email} (${s.provider})`, 
          value: s.email,
          provider: s.provider // 保留 provider 用于过滤
      })));
    }).catch(e => message.error('加载发信地址失败'));
  };

  // ... (handlers omitted)

  // 根据当前选择的服务商过滤发信地址
  const filteredSenders = senders.filter(s => !selectedProvider || s.provider === selectedProvider);

  // ... (columns omitted)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <Card title="创建新任务">
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="name" label="任务名称" required><Input placeholder="例如：元旦促销第一波" /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="provider" label="服务商" initialValue="aliyun" required>
                <Select>
                  <Select.Option value="aliyun">阿里云 (DirectMail)</Select.Option>
                  <Select.Option value="tencent">腾讯云 (SES)</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="from_alias" label="本次任务发信人昵称" tooltip="留空则使用模板设置或全局设置"><Input placeholder="例如：促销小助手" /></Form.Item>
            </Col>
          </Row>
          
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="template_id" label="选择模板" required><Select placeholder="请选择" options={templates.map(t => ({label: t.title, value: t.id}))} /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="list_id" label="选择联系人列表" required><Select placeholder="请选择" options={lists.map(l => ({label: l.name, value: l.id}))} /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="account_name" label="发信地址" required>
                <Select 
                  placeholder={selectedProvider === 'tencent' ? "请选择腾讯云域名" : "请选择阿里云发信地址"}
                  mode="tags" 
                  maxCount={1}
                  onDropdownVisibleChange={(open) => open && loadSenders()}
                  options={filteredSenders}
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={6}>
              <Form.Item name="batch_size" label="单次发送数量" initialValue={2000}><Input type="number" /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="interval_minutes" label="发送间隔(分钟)" initialValue={15}><Input type="number" /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="scheduled_start_time" label="计划开始时间"><DatePicker showTime placeholder="立即开始" style={{width: '100%'}} /></Form.Item>
            </Col>
            <Col span={6} style={{display: 'flex', alignItems: 'center'}}>
              <Button type="primary" htmlType="submit" size="large" style={{width: '100%'}} icon={<RocketOutlined />}>创建任务</Button>
            </Col>
          </Row>
        </Form>
      </Card>
      <Card title="任务列表">
        <Table dataSource={campaigns} columns={columns} rowKey="id" />
      </Card>
    </div>
  );
};

const App = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    token: { colorBgContainer },
  } = theme.useToken();

  const menuItems = [
    { key: '/', icon: <RocketOutlined />, label: '邮件任务' },
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
        <Header style={{ padding: 0, background: colorBgContainer }} />
        <Content style={{ margin: '16px' }}>
          <Routes>
            <Route path="/" element={<Campaigns />} />
            <Route path="/contacts" element={<Contacts />} />
            <Route path="/templates" element={<Templates />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
};

export default App;