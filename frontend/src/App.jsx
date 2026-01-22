import React, { useState, useEffect } from 'react';
import { Layout, Menu, theme, Card, Form, Input, Button, Upload, message, Table, Select, Tag, Progress, Statistic, Popconfirm, DatePicker, Row, Col, Modal, Tabs, Divider, Space } from 'antd';
import { UploadOutlined, UserOutlined, MailOutlined, SettingOutlined, RocketOutlined, EditOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import api, { contactApi, settingsApi } from './services/api';
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
      <Card title="系统配置">
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <h3>阿里云配置 (DirectMail)</h3>
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
          <Form.Item name="tencent_region" label="腾讯云区域" initialValue="ap-hongkong"><Input placeholder="ap-hongkong" /></Form.Item>
          
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
        const listName = options.file.name.split('.')[0];
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
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [form] = Form.useForm();
  const [importForm] = Form.useForm();

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
    message.loading({ content: '正在从云端同步...', key: 'syncing' });
    try {
      const res = await api.post('/templates/sync');
      message.success({ content: res.data.message, key: 'syncing' });
      refresh();
    } catch (e) {
      message.error({ content: '同步失败: ' + (e.response?.data?.detail || e.message), key: 'syncing' });
    }
  };

  const handleImport = async () => {
      try {
          const values = await importForm.validateFields();
          message.loading({ content: '正在导入...', key: 'importing' });
          const res = await api.post('/templates/import', {
              provider: values.provider,
              template_id: values.template_id
          });
          message.success({ content: `成功导入: ${res.data.title}`, key: 'importing' });
          setIsImportModalOpen(false);
          importForm.resetFields();
          refresh();
      } catch (e) {
          message.error({ content: '导入失败: ' + (e.response?.data?.detail || e.message), key: 'importing' });
      }
  };

  const columns = [
    { title: '模板名称', dataIndex: 'title', key: 'title' },
    { title: '来源', dataIndex: 'provider', key: 'provider', render: (t) => t === 'tencent' ? <Tag color="blue">腾讯云</Tag> : t === 'aliyun' ? <Tag color="orange">阿里云</Tag> : <Tag>本地</Tag> },
    { title: '云端ID', dataIndex: 'provider_id', key: 'pid', render: (t) => t || '-' },
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
          <Form.Item label="邮件正文 (支持 HTML)" required tooltip="使用 {Name} 代表收件人姓名">
            <Tabs defaultActiveKey="1" items={[
                {
                    key: '1', label: '编辑代码', children: (
                        <Form.Item name="body" noStyle>
                            <TextArea rows={15} placeholder="<html><body><h1>你好 {Name}!</h1></body></html>" style={{fontFamily: 'monospace'}} />
                        </Form.Item>
                    )
                },
                {
                    key: '2', label: '预览效果', children: (
                        <Form.Item shouldUpdate={(prev, curr) => prev.body !== curr.body}>
                            {({ getFieldValue }) => {
                                const html = getFieldValue('body') || '';
                                return (
                                    <div style={{border: '1px solid #d9d9d9', borderRadius: 6, padding: 10, minHeight: 330, background: '#fff'}}>
                                        <div dangerouslySetInnerHTML={{__html: html}} />
                                    </div>
                                );
                            }}
                        </Form.Item>
                    )
                }
            ]} />
          </Form.Item>
          <div style={{display: 'flex', gap: 10}}>
              <Button type="primary" htmlType="submit">{editingId ? "更新模板" : "创建模板"}</Button>
              {editingId && <Button onClick={handleCancelEdit}>取消</Button>}
          </div>
        </Form>
      </Card>
      <Card title="已有模板" style={{ flex: 1 }} extra={
          <div style={{display: 'flex', gap: 10}}>
            <Button onClick={() => setIsImportModalOpen(true)}>指定ID导入</Button>
            <Button icon={<RocketOutlined />} onClick={handleSync}>同步云端模板</Button>
          </div>
      }>
        <Table dataSource={templates} columns={columns} rowKey="id" />
      </Card>

      <Modal title="按 ID 导入模板" open={isImportModalOpen} onOk={handleImport} onCancel={() => setIsImportModalOpen(false)}>
          <Form form={importForm} layout="vertical">
              <Form.Item name="provider" label="服务商" initialValue="tencent" required>
                  <Select>
                      <Select.Option value="tencent">腾讯云 (SES)</Select.Option>
                      <Select.Option value="aliyun">阿里云 (DirectMail)</Select.Option>
                  </Select>
              </Form.Item>
              <Form.Item name="template_id" label="模板 ID" required tooltip="请在腾讯云/阿里云控制台查找模板 ID (数字)">
                  <Input placeholder="例如：12345" />
              </Form.Item>
          </Form>
      </Modal>
    </div>
  );
};

const Campaigns = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [lists, setLists] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [senders, setSenders] = useState([]);
  const [savedReplyTos, setSavedReplyTos] = useState([]);
  const [newReplyTo, setNewReplyTo] = useState('');
  const [form] = Form.useForm();
  
  const selectedProvider = Form.useWatch('provider', form);

  const refresh = () => {
    api.get('/campaigns').then(res => setCampaigns(res.data));
    api.get('/contacts').then(res => setLists(res.data));
    api.get('/templates').then(res => setTemplates(res.data));
    settingsApi.getReplyTos().then(res => setSavedReplyTos(res.data || []));
  };
  
  useEffect(() => {
    // 恢复草稿
    const draft = localStorage.getItem('campaign_draft');
    if (draft) {
      try {
        const values = JSON.parse(draft);
        if (values.scheduled_start_time) {
          values.scheduled_start_time = dayjs(values.scheduled_start_time);
        }
        form.setFieldsValue(values);
      } catch (e) {
        console.error('恢复草稿失败', e);
      }
    }
    
    refresh(); 
    const interval = setInterval(refresh, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleValuesChange = (_, allValues) => {
    localStorage.setItem('campaign_draft', JSON.stringify(allValues));
  };

  const loadSenders = () => {
    api.get('/senders/sync').then(res => {
      setSenders(res.data.map(s => ({
          label: s.label || `${s.email} (${s.provider})`, 
          value: s.email,
          provider: s.provider,
          reply_address: s.reply_address
      })));
    }).catch(e => message.error('加载发信地址失败'));
  };

  const handleAccountChange = (value) => {
      // 阿里云自动填充回信地址
      if (selectedProvider === 'aliyun') {
          // value 可能是数组 (mode="tags")
          const email = Array.isArray(value) ? value[0] : value;
          const sender = senders.find(s => s.value === email);
          if (sender && sender.reply_address) {
              form.setFieldsValue({ reply_to_address: sender.reply_address });
              message.info(`已自动加载阿里云回信地址: ${sender.reply_address}`);
          }
      }
  };

  const addReplyTo = (e) => {
      e.preventDefault();
      if (!newReplyTo) return;
      settingsApi.addReplyTo(newReplyTo).then(res => {
          setSavedReplyTos([res.data, ...savedReplyTos]);
          setNewReplyTo('');
          message.success('回信地址已保存');
      });
  };

  const handleStart = (id) => {
    api.post(`/campaigns/${id}/start`).then(() => {
      message.success('任务已激活');
      refresh();
    });
  };

  const handleStop = (id) => {
    api.post(`/campaigns/${id}/stop`).then(() => {
      message.warning('任务已暂停');
      refresh();
    });
  };
  
  const handleDelete = (id) => {
      api.delete(`/campaigns/${id}`).then(() => {
          message.success('任务已删除');
          refresh();
      });
  };

  const onFinish = (values) => {
    let accName = values.account_name;
    if (Array.isArray(accName)) {
        accName = accName[0];
    }

    const payload = {
      ...values,
      account_name: accName,
      batch_size: parseInt(values.batch_size, 10),
      interval_minutes: parseInt(values.interval_minutes, 10),
      scheduled_start_time: values.scheduled_start_time ? values.scheduled_start_time.toISOString() : null
    };
    api.post('/campaigns', payload).then(() => {
      message.success('任务创建成功');
      localStorage.removeItem('campaign_draft');
      form.resetFields();
      refresh();
    }).catch(err => {
        message.error('创建失败: ' + (err.response?.data?.detail || '参数错误'));
    });
  };

  const filteredSenders = senders.filter(s => !selectedProvider || s.provider === selectedProvider);

  const columns = [
    { title: '任务名称', dataIndex: 'name', key: 'name' },
    { title: '发件人', dataIndex: 'from_alias', key: 'from', render: (t) => t || '(默认)' },
    { title: '服务商', dataIndex: 'provider', key: 'provider', render: (text) => text === 'tencent' ? '腾讯云' : '阿里云' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (text) => {
        const map = { pending: '等待中', sending: '发送中', completed: '已完成', paused: '已暂停', error: '错误', scheduled: '计划中' };
        const color = { sending: 'green', completed: 'blue', pending: 'orange', paused: 'red', scheduled: 'purple' };
        return <Tag color={color[text] || 'default'}>{map[text] || text}</Tag>;
    }},
    { title: '发送进度', key: 'progress', width: 150, render: (_, record) => (
      <div>
        <Progress percent={Math.round((record.sent_count / record.total_recipients) * 100)} size="small" />
        <small>{record.sent_count} / {record.total_recipients}</small>
      </div>
    )},
    { title: '计划开始', dataIndex: 'scheduled_start_time', key: 'start', render: (t) => t ? new Date(t + (t.endsWith('Z') ? '' : 'Z')).toLocaleString('zh-CN', { hour12: false }) : '-' },
    { title: '操作', key: 'action', render: (_, record) => (
      <div style={{display: 'flex', gap: 5}}>
        {record.status === 'pending' || record.status === 'paused' || record.status === 'scheduled' ? 
        <Button type="primary" size="small" onClick={() => handleStart(record.id)}>{record.status === 'scheduled' ? '立即开始' : '开始发送'}</Button> :
        record.status === 'sending' ?
        <Button danger size="small" onClick={() => handleStop(record.id)}>暂停</Button> : null}
        <Popconfirm title="确定删除吗？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger type="text">删除</Button>
        </Popconfirm>
      </div>
    )}
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <Card title="创建新任务">
        <Form form={form} layout="vertical" onFinish={onFinish} onValuesChange={handleValuesChange}>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="name" label="任务名称" required><Input placeholder="例如：元旦促销第一波" /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="provider" label="服务商" initialValue="aliyun" required>
                <Select onChange={() => form.setFieldValue('account_name', null)}>
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
                  onOpenChange={(open) => open && loadSenders()}
                  onChange={handleAccountChange}
                  options={filteredSenders}
                />
              </Form.Item>
            </Col>
          </Row>

           <Row gutter={16}>
            <Col span={8}>
               <Form.Item name="reply_to_address" label="回信地址 (Reply-To)" tooltip={selectedProvider === 'aliyun' ? "阿里云限制：必须在阿里云控制台预先配置回信地址。此处仅做展示，无法修改。" : "收件人点击回复时，邮件将发送到此地址"}>
                   <Select
                        placeholder={selectedProvider === 'aliyun' ? "（根据发信地址自动加载）" : "请输入或选择回信地址"}
                        disabled={selectedProvider === 'aliyun'}
                        allowClear={selectedProvider !== 'aliyun'}
                        dropdownRender={(menu) => (
                            <>
                                {menu}
                                <Divider style={{ margin: '8px 0' }} />
                                <Space style={{ padding: '0 8px 4px' }}>
                                    <Input
                                        placeholder="输入新地址"
                                        value={newReplyTo}
                                        onChange={(e) => setNewReplyTo(e.target.value)}
                                        onKeyDown={(e) => e.stopPropagation()}
                                    />
                                    <Button type="text" icon={<PlusOutlined />} onClick={addReplyTo}>
                                        保存
                                    </Button>
                                </Space>
                            </>
                        )}
                        options={savedReplyTos.map(item => ({ label: item.address, value: item.address }))}
                   />
               </Form.Item>
            </Col>
            <Col span={5}>
              <Form.Item name="batch_size" label="单次发送数量" initialValue={2000}><Input type="number" /></Form.Item>
            </Col>
            <Col span={5}>
              <Form.Item name="interval_minutes" label="发送间隔(分钟)" initialValue={15}><Input type="number" /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="scheduled_start_time" label="计划开始时间"><DatePicker showTime placeholder="立即开始" style={{width: '100%'}} /></Form.Item>
            </Col>
          </Row>
          
          <Row>
            <Col span={24} style={{display: 'flex', justifyContent: 'flex-end'}}>
              <Button type="primary" htmlType="submit" size="large" style={{width: '200px'}} icon={<RocketOutlined />}>创建任务</Button>
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