import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Button, message, Table, Select, Tag, Progress, Popconfirm, DatePicker, Row, Col, Divider, Space, Switch, InputNumber } from 'antd';
import { PlusOutlined, RocketOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import api, { settingsApi, accountApi } from '../services/api';

const Campaigns = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [lists, setLists] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [senders, setSenders] = useState([]);
  const [savedReplyTos, setSavedReplyTos] = useState([]);
  const [newReplyTo, setNewReplyTo] = useState('');
  const [form] = Form.useForm();
  
  const selectedProvider = Form.useWatch('provider', form);
  const selectedAccountId = Form.useWatch('account_id', form);

  const refreshCampaigns = () => {
    api.get('/campaigns').then(res => setCampaigns(res.data));
  };

  const refreshMetadata = () => {
    api.get('/contacts').then(res => setLists(res.data));
    api.get('/templates').then(res => setTemplates(res.data));
    accountApi.getAll().then(res => setAccounts((res.data || []).filter(a => a.enabled)));
    settingsApi.getReplyTos().then(res => setSavedReplyTos(res.data || []));
  };

  const refresh = () => {
    refreshCampaigns();
    refreshMetadata();
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
    const interval = setInterval(refreshCampaigns, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleValuesChange = (_, allValues) => {
    localStorage.setItem('campaign_draft', JSON.stringify(allValues));
  };

  const loadSenders = (accountId) => {
    if (!accountId) {
      setSenders([]);
      return;
    }
    api.get('/senders/sync', { params: { account_id: accountId } }).then(res => {
      setSenders(res.data.map(s => ({
          label: s.label || `${s.email} (${s.provider})`,
          value: s.email,
          provider: s.provider,
          reply_address: s.reply_address,
          account_id: s.account_id,
      })));
    }).catch(_e => message.error('加载发信地址失败'));
  };

  useEffect(() => {
    if (selectedAccountId) {
      loadSenders(selectedAccountId);
    } else {
      setSenders([]);
      form.setFieldValue('account_name', null);
    }
  }, [selectedAccountId]);

  const handleAccountChange = (value) => {
      // 阿里云自动填充回信地址
      if (selectedProvider === 'aliyun') {
          const sender = senders.find(s => s.value === value);
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
    const payload = {
      ...values,
      account_name: values.account_name,
      account_id: values.account_id ? parseInt(values.account_id, 10) : null,
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
  const accountOptions = accounts
    .filter(a => !selectedProvider || a.provider === selectedProvider)
    .map(a => ({ label: `${a.name} (${a.provider === 'aliyun' ? '阿里云' : '腾讯云'})`, value: a.id }));
  const filteredTemplates = templates.filter(t => {
    if (t.provider === 'local') return true;
    if (!selectedProvider || t.provider !== selectedProvider) return false;
    if (!selectedAccountId) return false;
    return Number(t.account_id) === Number(selectedAccountId);
  });

  const columns = [
    { title: '任务名称', dataIndex: 'name', key: 'name' },
    { title: '账号', dataIndex: 'account_label', key: 'account_label', render: (v) => v || '(未绑定)' },
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
              <Form.Item name="name" label="任务名称" rules={[{ required: true, message: '请输入任务名称' }]}><Input placeholder="例如：元旦促销第一波" /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="provider" label="服务商" initialValue="aliyun" rules={[{ required: true, message: '请选择服务商' }]}>
                <Select onChange={() => {
                  form.setFieldsValue({
                    account_id: null,
                    template_id: null,
                    account_name: null,
                    reply_to_address: null,
                  });
                }}>
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
            <Col span={6}>
              <Form.Item name="account_id" label="云账号" rules={[{ required: true, message: '请选择云账号' }]}>
                <Select
                  placeholder="请选择账号"
                  options={accountOptions}
                  onChange={() => form.setFieldsValue({ template_id: null, account_name: null, reply_to_address: null })}
                />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="template_id" label="选择模板" rules={[{ required: true, message: '请选择模板' }]}>
                <Select
                  placeholder="请选择"
                  options={filteredTemplates.map(t => ({ label: `${t.title}${t.account_name ? ` [${t.account_name}]` : ''}`, value: t.id }))}
                />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="list_id" label="选择联系人列表" rules={[{ required: true, message: '请选择联系人列表' }]}><Select placeholder="请选择" options={lists.map(l => ({label: l.name, value: l.id}))} /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="account_name" label="发信地址" rules={[{ required: true, message: '请选择发信地址' }]}>
                <Select 
                  placeholder={selectedProvider === 'tencent' ? "请选择腾讯云域名" : "请选择阿里云发信地址"}
                  onOpenChange={(open) => open && loadSenders(selectedAccountId)}
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
              <Form.Item name="batch_size" label="单次发送数量" initialValue={2000} rules={[{ required: true, message: '请输入单次发送数量' }]}>
                <InputNumber min={1} max={100000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={5}>
              <Form.Item name="interval_minutes" label="发送间隔(分钟)" initialValue={15} rules={[{ required: true, message: '请输入发送间隔' }]}>
                <InputNumber min={0} max={1440} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="scheduled_start_time" label="计划开始时间"><DatePicker showTime placeholder="立即开始" style={{width: '100%'}} /></Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={6}>
                <Form.Item name="track_opens" valuePropName="checked" initialValue={true} label="追踪开信" tooltip="插入像素点统计打开率。若遇到'身份验证'警告，请尝试关闭此项。">
                    <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                </Form.Item>
            </Col>
            <Col span={6}>
                <Form.Item name="track_clicks" valuePropName="checked" initialValue={true} label="追踪点击" tooltip="自动替换链接以统计点击率。">
                    <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                </Form.Item>
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

export default Campaigns;
