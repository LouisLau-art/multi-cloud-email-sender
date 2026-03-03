import React, { useState, useEffect } from 'react';
import { Layout, Menu, theme, Card, Form, Input, Button, Upload, message, Table, Select, Tag, Progress, Statistic, Popconfirm, DatePicker, Row, Col, Modal, Tabs, Divider, Space, Radio, Empty, Switch, InputNumber, Spin } from 'antd';
import { UploadOutlined, UserOutlined, MailOutlined, SettingOutlined, RocketOutlined, EditOutlined, DeleteOutlined, PlusOutlined, PieChartOutlined, CheckCircleOutlined, SyncOutlined, CloseCircleOutlined, EyeOutlined, DownloadOutlined } from '@ant-design/icons';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip, Legend, ResponsiveContainer } from 'recharts';
import DOMPurify from 'dompurify';
import api, { authApi, contactApi, settingsApi, dashboardApi, accountApi } from './services/api';
import dayjs from 'dayjs';

const { Header, Content, Sider } = Layout;
const { TextArea } = Input;

// --- Dashboard Component ---
const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [campaignSummaries, setCampaignSummaries] = useState([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState(undefined);
  const [details, setDetails] = useState({ items: [], total: 0, page: 1, size: 10 });
  const [loading, setLoading] = useState(false);
  const [chartRange, setChartRange] = useState(7); // Days
  const [detailFilter, setDetailFilter] = useState('all'); // all, sent, failed, opened, clicked
  const [searchText, setSearchText] = useState('');
  const [timeRange, setTimeRange] = useState(null);
  const [exportScope, setExportScope] = useState('all'); // all, page

  const showBackendConnectionError = (error) => {
    console.error('Dashboard API request failed:', error);
    message.error({
      key: 'dashboard-connection-error',
      content: '无法连接后端服务（http://localhost:8000）。请先启动后端。',
      duration: 3,
    });
  };

  const loadCampaigns = () => {
    dashboardApi.getCampaigns()
      .then((res) => setCampaignSummaries(res.data || []))
      .catch((error) => {
        setCampaignSummaries([]);
        showBackendConnectionError(error);
      });
  };

  const loadStats = (campaignId = selectedCampaignId) => {
    dashboardApi.getStats(campaignId)
      .then((res) => setStats(res.data))
      .catch((error) => {
        setStats({
          total_recipients: 0,
          sent_count: 0,
          delivery_rate: 0,
          delivered_count: 0,
          opened_count: 0,
          open_rate: 0,
          clicked_count: 0,
          click_rate: 0,
        });
        showBackendConnectionError(error);
      });
  };

  const loadChart = (days = chartRange, campaignId = selectedCampaignId) => {
    dashboardApi.getChartData(days, campaignId)
      .then((res) => setChartData(res.data))
      .catch((error) => {
        setChartData([]);
        showBackendConnectionError(error);
      });
  };

  const getSentTimeRangeParams = (range = timeRange) => {
    if (!range || range.length !== 2 || !range[0] || !range[1]) {
      return { startTime: null, endTime: null };
    }
    return {
      startTime: range[0].startOf('day').toISOString(),
      endTime: range[1].endOf('day').toISOString(),
    };
  };

  const loadDetails = (page, size, search, status, campaignId = selectedCampaignId, range = timeRange) => {
    setLoading(true);
    const statusParam = status === 'all' ? null : status;
    const { startTime, endTime } = getSentTimeRangeParams(range);
    dashboardApi.getDetails(page, size, search, statusParam, campaignId, startTime, endTime)
      .then((res) => {
        setDetails(res.data);
      })
      .catch((error) => {
        setDetails({ items: [], total: 0, page, size });
        showBackendConnectionError(error);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    loadCampaigns();
    loadStats(undefined);
    loadChart(7, undefined);
    loadDetails(1, 10, '', 'all', undefined, null);
  }, []);

  useEffect(() => {
    loadChart(chartRange, selectedCampaignId);
  }, [chartRange]);

  useEffect(() => {
    loadDetails(1, 10, searchText, detailFilter, selectedCampaignId, timeRange);
  }, [detailFilter, timeRange]); // Search triggers manually

  const handleSearch = (value) => {
    setSearchText(value);
    loadDetails(1, details.size, value, detailFilter, selectedCampaignId, timeRange);
  };

  const handleCampaignSelect = (campaignId) => {
    const normalizedCampaignId = campaignId || undefined;
    setSelectedCampaignId(normalizedCampaignId);
    loadStats(normalizedCampaignId);
    loadChart(chartRange, normalizedCampaignId);
    loadDetails(1, details.size, searchText, detailFilter, normalizedCampaignId, timeRange);
  };

  const handleExport = () => {
    const baseUrl = api.defaults.baseURL.startsWith('http')
      ? api.defaults.baseURL
      : window.location.origin + api.defaults.baseURL;
    const params = new URLSearchParams();
    const { startTime, endTime } = getSentTimeRangeParams(timeRange);
    if (selectedCampaignId) params.set('campaign_id', String(selectedCampaignId));
    if (searchText) params.set('search', searchText);
    if (detailFilter && detailFilter !== 'all') params.set('status', detailFilter);
    if (startTime) params.set('start_time', startTime);
    if (endTime) params.set('end_time', endTime);
    params.set('scope', exportScope);
    if (exportScope === 'page') {
      params.set('page', String(details.page || 1));
      params.set('size', String(details.size || 10));
    }
    const query = params.toString();
    const exportUrl = query ? `${baseUrl}/dashboard/export?${query}` : `${baseUrl}/dashboard/export`;
    window.open(exportUrl, '_blank');
  };

  const campaignColumns = [
    { title: '任务名称', dataIndex: 'name', key: 'name' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (text) => {
        const map = { pending: '等待中', sending: '发送中', completed: '已完成', paused: '已暂停', error: '错误', scheduled: '计划中' };
        const color = { sending: 'green', completed: 'blue', pending: 'orange', paused: 'red', scheduled: 'purple', error: 'red' };
        return <Tag color={color[text] || 'default'}>{map[text] || text}</Tag>;
      }
    },
    { title: '送达', dataIndex: 'delivered_count', key: 'delivered_count' },
    { title: '打开', dataIndex: 'opened_count', key: 'opened_count' },
    { title: '点击', dataIndex: 'clicked_count', key: 'clicked_count' },
    { title: '送达率', dataIndex: 'delivery_rate', key: 'delivery_rate', render: (value) => `${value}%` },
    { title: '打开率', dataIndex: 'open_rate', key: 'open_rate', render: (value) => `${value}%` },
    { title: '点击率', dataIndex: 'click_rate', key: 'click_rate', render: (value) => `${value}%` },
  ];

  const detailColumns = [
    { title: '任务名称', dataIndex: 'campaign_name', key: 'campaign_name' },
    { title: 'First Name', dataIndex: 'first_name', key: 'first_name', render: (t) => t || '-' },
    { title: 'Middle Name', dataIndex: 'middle_name', key: 'middle_name', render: (t) => t || '-' },
    { title: 'Last Name', dataIndex: 'last_name', key: 'last_name', render: (t) => t || '-' },
    { title: '邮箱地址', dataIndex: 'email', key: 'email' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (text) => {
        const map = { sent: '已发送', failed: '发送失败', opened: '已打开', clicked: '已点击', pending: '等待中' };
        const color = { sent: 'blue', failed: 'red', opened: 'green', clicked: 'purple', pending: 'default' };
        return <Tag color={color[text] || 'default'}>{map[text] || text}</Tag>;
      }
    },
    {
      title: '发送时间',
      dataIndex: 'sent_at',
      key: 'sent_at',
      render: (t) => t ? new Date(t + 'Z').toLocaleString('zh-CN', { hour12: false }) : '-'
    },
    {
      title: '打开时间',
      dataIndex: 'opened_at',
      key: 'opened_at',
      render: (t) => t ? new Date(t + 'Z').toLocaleString('zh-CN', { hour12: false }) : '-'
    },
    {
      title: '点击时间',
      dataIndex: 'clicked_at',
      key: 'clicked_at',
      render: (t) => t ? new Date(t + 'Z').toLocaleString('zh-CN', { hour12: false }) : '-'
    },
    { title: '错误信息', dataIndex: 'error_message', key: 'error', ellipsis: true }
  ];

  if (!stats) return <div style={{ padding: 50, textAlign: 'center' }}><SyncOutlined spin /> 加载数据中...</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <Row gutter={16}>
        <Col span={4}>
          <Card>
            <Statistic title="收件人数" value={stats.total_recipients} prefix={<UserOutlined />} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="发送封数" value={stats.sent_count} prefix={<RocketOutlined />} suffix={<span style={{ fontSize: 12, color: '#999' }}>送达率 {stats.delivery_rate}%</span>} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="送达封数" value={stats.delivered_count} prefix={<CheckCircleOutlined style={{ color: 'green' }} />} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="打开封数" value={stats.opened_count} prefix={<EyeOutlined style={{ color: 'orange' }} />} suffix={<span style={{ fontSize: 12, color: '#999' }}>打开率 {stats.open_rate}%</span>} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="点击人数" value={stats.clicked_count} prefix={<PieChartOutlined style={{ color: 'purple' }} />} suffix={<span style={{ fontSize: 12, color: '#999' }}>点击率 {stats.click_rate}%</span>} />
          </Card>
        </Col>
      </Row>

      <Card title="发信任务概览（点击行查看该任务详情）" extra={
        <Space>
          <Button
            onClick={() => handleCampaignSelect(undefined)}
            type={!selectedCampaignId ? 'primary' : 'default'}
          >
            全部任务
          </Button>
          <Select
            style={{ width: 260 }}
            allowClear
            placeholder="按任务筛选"
            value={selectedCampaignId}
            onChange={handleCampaignSelect}
            options={campaignSummaries.map((campaign) => ({
              label: `${campaign.name} (#${campaign.id})`,
              value: campaign.id,
            }))}
          />
        </Space>
      }>
        <Table
          size="small"
          rowKey="id"
          dataSource={campaignSummaries}
          columns={campaignColumns}
          pagination={{ pageSize: 6 }}
          onRow={(record) => ({
            onClick: () => handleCampaignSelect(record.id),
          })}
        />
      </Card>

      <Card title="任务效果 - 最近营销邮件表现" extra={
        <Radio.Group value={chartRange} onChange={(e) => setChartRange(e.target.value)}>
          <Radio.Button value={1}>24小时</Radio.Button>
          <Radio.Button value={7}>7天</Radio.Button>
          <Radio.Button value={30}>30天</Radio.Button>
        </Radio.Group>
      }>
        <div style={{ height: 300 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <ChartTooltip />
              <Legend />
              <Line type="monotone" dataKey="opened" name="打开人数" stroke="#1890ff" activeDot={{ r: 8 }} />
              <Line type="monotone" dataKey="clicked" name="点击人数" stroke="#722ed1" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card title="详细数据" extra={
        <Space wrap>
          <DatePicker.RangePicker
            value={timeRange}
            onChange={(value) => setTimeRange(value || null)}
            allowClear
          />
          <Select
            style={{ width: 150 }}
            value={exportScope}
            onChange={setExportScope}
            options={[
              { label: '导出全部', value: 'all' },
              { label: '仅当前页', value: 'page' },
            ]}
          />
          <Button icon={<DownloadOutlined />} onClick={handleExport}>导出 CSV</Button>
          <Input.Search placeholder="搜索联系人/任务" onSearch={handleSearch} style={{ width: 240 }} />
        </Space>
      }>
        <Tabs
          activeKey={detailFilter}
          onChange={setDetailFilter}
          items={[
            { key: 'all', label: '全部' },
            { key: 'sent', label: '已发送' },
            { key: 'opened', label: '已打开' },
            { key: 'clicked', label: '已点击' },
            { key: 'failed', label: '发送失败' },
          ]}
        />
        <Table
          columns={detailColumns}
          dataSource={details.items}
          rowKey="id"
          loading={loading}
          pagination={{
            current: details.page,
            pageSize: details.size,
            total: details.total,
            onChange: (p, s) => loadDetails(p, s, searchText, detailFilter, selectedCampaignId, timeRange)
          }}
        />
      </Card>
    </div>
  );
};

// --- Components ---

const Settings = () => {
  const [settingsForm] = Form.useForm();
  const [accountForm] = Form.useForm();
  const [accounts, setAccounts] = useState([]);
  const [editingAccountId, setEditingAccountId] = useState(null);
  const accountProvider = Form.useWatch('provider', accountForm) || 'aliyun';

  const loadSettings = () => {
    settingsApi.get().then(res => {
      if (res.data) {
        settingsForm.setFieldsValue({
          track_domain: res.data.track_domain,
          from_alias: res.data.from_alias,
        });
      }
    });
  };

  const loadAccounts = () => {
    accountApi.getAll().then(res => setAccounts(res.data || []));
  };

  useEffect(() => {
    loadSettings();
    loadAccounts();
    accountForm.setFieldsValue({ provider: 'aliyun', enabled: true });
  }, []);

  const onSaveSettings = (values) => {
    settingsApi.update(values).then(() => message.success('全局设置保存成功'));
  };

  const resetAccountForm = () => {
    setEditingAccountId(null);
    accountForm.resetFields();
    accountForm.setFieldsValue({ provider: 'aliyun', enabled: true });
  };

  const onEditAccount = (row) => {
    setEditingAccountId(row.id);
    accountForm.setFieldsValue({
      provider: row.provider,
      name: row.name,
      from_alias: row.from_alias,
      enabled: row.enabled,
      access_key_id: row.access_key_id,
      region_id: row.region_id || 'cn-hangzhou',
      tencent_secret_id: row.tencent_secret_id,
      tencent_region: row.tencent_region || 'ap-hongkong',
      access_key_secret: '',
      tencent_secret_key: '',
    });
  };

  const onSubmitAccount = async () => {
    try {
      const values = await accountForm.validateFields();
      const payload = {
        provider: values.provider,
        name: values.name,
        from_alias: values.from_alias,
        enabled: values.enabled,
        access_key_id: values.access_key_id,
        access_key_secret: values.access_key_secret,
        region_id: values.region_id,
        tencent_secret_id: values.tencent_secret_id,
        tencent_secret_key: values.tencent_secret_key,
        tencent_region: values.tencent_region,
      };
      if (editingAccountId) {
        await accountApi.update(editingAccountId, payload);
        message.success('账号更新成功');
      } else {
        await accountApi.create(payload);
        message.success('账号创建成功');
      }
      resetAccountForm();
      loadAccounts();
    } catch (e) {
      if (e?.errorFields) return;
      message.error('保存账号失败: ' + (e.response?.data?.detail || e.message));
    }
  };

  const onDeleteAccount = async (id) => {
    try {
      await accountApi.delete(id);
      message.success('账号删除成功');
      if (editingAccountId === id) resetAccountForm();
      loadAccounts();
    } catch (e) {
      message.error('删除失败: ' + (e.response?.data?.detail || e.message));
    }
  };

  const accountColumns = [
    {
      title: '服务商',
      dataIndex: 'provider',
      key: 'provider',
      render: (p) => p === 'aliyun' ? <Tag color="orange">阿里云</Tag> : <Tag color="blue">腾讯云</Tag>,
    },
    { title: '账号名称', dataIndex: 'name', key: 'name' },
    { title: 'AK/SecretID', dataIndex: 'access_key_id', key: 'ak', render: (_, row) => row.provider === 'aliyun' ? (row.access_key_id || '-') : (row.tencent_secret_id || '-') },
    { title: '区域', dataIndex: 'region_id', key: 'region', render: (_, row) => row.provider === 'aliyun' ? (row.region_id || '-') : (row.tencent_region || '-') },
    { title: '默认昵称', dataIndex: 'from_alias', key: 'alias', render: (v) => v || '-' },
    { title: '状态', dataIndex: 'enabled', key: 'enabled', render: (v) => v ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag> },
    {
      title: '操作',
      key: 'action',
      render: (_, row) => (
        <Space>
          <Button size="small" onClick={() => onEditAccount(row)}>编辑</Button>
          <Popconfirm title="确定删除该账号？" onConfirm={() => onDeleteAccount(row.id)}>
            <Button size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <Card title="全局设置">
        <Form form={settingsForm} layout="vertical" onFinish={onSaveSettings}>
          <Form.Item name="track_domain" label="追踪域名/IP 配置" tooltip="用于生成邮件中的开信和点击追踪链接。格式如：http://192.168.2.8:8000 或 https://your-domain.com。请确保收件人能访问此地址。"><Input placeholder="http://192.168.2.8:8000" /></Form.Item>
          <Form.Item name="from_alias" label="全局默认发件人昵称" tooltip="当模板和账号未设置昵称时使用"><Input /></Form.Item>
          <Button type="primary" htmlType="submit">保存全局设置</Button>
        </Form>
      </Card>

      <Card title="云账号管理">
        <Form form={accountForm} layout="vertical" initialValues={{ provider: 'aliyun', enabled: true }}>
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item name="provider" label="服务商" rules={[{ required: true, message: '请选择服务商' }]}>
                <Select disabled={!!editingAccountId}>
                  <Select.Option value="aliyun">阿里云 (DirectMail)</Select.Option>
                  <Select.Option value="tencent">腾讯云 (SES)</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="name" label="账号名称" rules={[{ required: true, message: '请输入账号名称' }]}>
                <Input placeholder="例如：阿里云-华东账号" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="from_alias" label="默认发件昵称">
                <Input placeholder="例如：市场部" />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item name="enabled" label="启用状态" valuePropName="checked">
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>
            </Col>
          </Row>

          {accountProvider === 'aliyun' ? (
            <Row gutter={16}>
              <Col span={10}>
                <Form.Item name="access_key_id" label="Aliyun Access Key ID" rules={[{ required: true, message: '请输入 Access Key ID' }]}>
                  <Input />
                </Form.Item>
              </Col>
              <Col span={10}>
                <Form.Item name="access_key_secret" label="Aliyun Access Key Secret" rules={editingAccountId ? [] : [{ required: true, message: '请输入 Access Key Secret' }]}>
                  <Input.Password placeholder={editingAccountId ? '留空表示不修改' : ''} />
                </Form.Item>
              </Col>
              <Col span={4}>
                <Form.Item name="region_id" label="区域 ID" initialValue="cn-hangzhou">
                  <Input placeholder="cn-hangzhou" />
                </Form.Item>
              </Col>
            </Row>
          ) : (
            <Row gutter={16}>
              <Col span={10}>
                <Form.Item name="tencent_secret_id" label="Tencent Secret ID" rules={[{ required: true, message: '请输入 Secret ID' }]}>
                  <Input />
                </Form.Item>
              </Col>
              <Col span={10}>
                <Form.Item name="tencent_secret_key" label="Tencent Secret Key" rules={editingAccountId ? [] : [{ required: true, message: '请输入 Secret Key' }]}>
                  <Input.Password placeholder={editingAccountId ? '留空表示不修改' : ''} />
                </Form.Item>
              </Col>
              <Col span={4}>
                <Form.Item name="tencent_region" label="区域" initialValue="ap-hongkong">
                  <Input placeholder="ap-hongkong" />
                </Form.Item>
              </Col>
            </Row>
          )}

          <Space>
            <Button type="primary" onClick={onSubmitAccount}>{editingAccountId ? '更新账号' : '新增账号'}</Button>
            {editingAccountId && <Button onClick={resetAccountForm}>取消编辑</Button>}
          </Space>
        </Form>

        <Divider />
        <Table dataSource={accounts} columns={accountColumns} rowKey="id" pagination={false} />
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
        const listName = options.file.name;
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
        * CSV 文件必须包含 <b>EmailAddr</b> 列（收件人邮箱），可选包含 <b>FirstName</b>/<b>MiddleName</b>/<b>LastName</b>、<b>UserName</b>、<b>Birthday</b> 等变量列。<br/>
        * 系统会自动过滤重复和无效的邮件地址，请在上传前删除文件底部的说明文字。
      </div>
    </Card>
  );
};

const Templates = () => {
  const [templates, setTemplates] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [filterProvider, setFilterProvider] = useState('local');
  const [filterAccountId, setFilterAccountId] = useState(undefined);
  const [form] = Form.useForm();
  const [importForm] = Form.useForm();
  const importProvider = Form.useWatch('provider', importForm) || 'aliyun';

  const refresh = () => {
    const params = {};
    if (filterProvider) params.provider = filterProvider;
    if (filterProvider !== 'local' && filterAccountId) {
      params.account_id = filterAccountId;
    }
    api.get('/templates', { params }).then(res => setTemplates(res.data || []));
  };

  const refreshAccounts = () => {
    accountApi.getAll().then(res => setAccounts(res.data || []));
  };

  useEffect(() => {
    refreshAccounts();
  }, []);

  useEffect(() => {
    refresh();
  }, [filterProvider, filterAccountId]);

  const onFinish = (values) => {
    const payload = {
      ...values,
      provider: 'local',
      account_id: null,
    };
    if (editingId) {
        api.put(`/templates/${editingId}`, payload).then(() => {
            message.success('模板更新成功');
            setEditingId(null);
            form.resetFields();
            refresh();
        });
    } else {
        api.post('/templates', payload).then(() => {
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

  const handleDeleteTemplate = async (record) => {
      try {
          await api.delete(`/templates/${record.id}`);
          message.success('模板已删除');
          if (editingId === record.id) {
              setEditingId(null);
              form.resetFields();
          }
          refresh();
      } catch (e) {
          message.error('删除失败: ' + (e.response?.data?.detail || e.message));
      }
  };
  
  const handleSync = async () => {
    if (filterProvider === 'local') {
      message.warning('本地模板无需同步云端');
      return;
    }
    if (!filterAccountId) {
      message.warning('请先选择要同步的账号');
      return;
    }
    message.loading({ content: '正在从云端同步...', key: 'syncing' });
    try {
      const res = await api.post('/templates/sync', null, { params: { account_id: filterAccountId } });
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
              template_id: values.template_id,
              account_id: values.account_id,
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
    { title: '所属账号', dataIndex: 'account_name', key: 'account_name', render: (v) => v || '-' },
    { title: '云端ID', dataIndex: 'provider_id', key: 'pid', render: (t) => t || '-' },
    { title: '发送人名称', dataIndex: 'from_alias', key: 'alias' },
    { title: '邮件标题', dataIndex: 'subject', key: 'subject' },
    { title: '操作', key: 'action', render: (_, record) => (
        <Space>
          {record.provider === 'local' ? (
            <Button icon={<EditOutlined />} size="small" onClick={() => handleEdit(record)}>编辑</Button>
          ) : (
            <Tag color="default">云模板</Tag>
          )}
          <Popconfirm
            title="确定删除该模板？"
            description={record.provider !== 'local' ? '删除后可通过“同步云端模板”重新拉取。' : undefined}
            onConfirm={() => handleDeleteTemplate(record)}
          >
            <Button icon={<DeleteOutlined />} size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
    )}
  ];

  const accountOptions = accounts
    .filter(a => a.provider === filterProvider)
    .map(a => ({ label: a.name, value: a.id }));
  const importAccountOptions = accounts
    .filter(a => a.provider === importProvider)
    .map(a => ({ label: a.name, value: a.id }));

  return (
    <div style={{ display: 'flex', gap: 20 }}>
      <Card title={editingId ? "编辑模板" : "新建模板"} style={{ flex: 1 }}>
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item name="title" label="模板名称 (内部标识)" rules={[{ required: true, message: '请输入模板名称' }]}><Input placeholder="例如：元旦促销模板" /></Form.Item>
          <Form.Item name="from_alias" label="发送人名称" rules={[{ required: true, message: '请输入发送人名称' }]} tooltip="例如：阿里云通知。收件人看到的邮件来源名称"><Input placeholder="例如：市场部" /></Form.Item>
          <Form.Item name="subject" label="邮件标题" rules={[{ required: true, message: '请输入邮件标题' }]} tooltip="使用 {Name} 代表收件人姓名，或 CSV 中的其他列名如 {Birthday}"><Input placeholder="例如：你好 {Name}，这是给你的专属优惠" /></Form.Item>
          <Form.Item label="邮件正文 (支持 HTML)" required tooltip="使用 {Name} 代表收件人姓名">
            <Tabs defaultActiveKey="1" items={[
                {
                    key: '1', label: '编辑代码', children: (
                        <Form.Item name="body" noStyle rules={[{ required: true, message: '请输入邮件正文' }]}>
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
                                        <div dangerouslySetInnerHTML={{__html: DOMPurify.sanitize(html)}} />
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
            <Select
              value={filterProvider}
              style={{ width: 130 }}
              onChange={(value) => {
                setFilterProvider(value);
                setFilterAccountId(undefined);
              }}
              options={[
                { label: '本地', value: 'local' },
                { label: '阿里云', value: 'aliyun' },
                { label: '腾讯云', value: 'tencent' },
              ]}
            />
            {filterProvider !== 'local' && (
              <Select
                value={filterAccountId}
                placeholder="选择账号"
                style={{ width: 180 }}
                onChange={setFilterAccountId}
                options={accountOptions}
                allowClear
              />
            )}
            <Button onClick={() => setIsImportModalOpen(true)}>指定ID导入</Button>
            <Button icon={<RocketOutlined />} onClick={handleSync} disabled={filterProvider === 'local'}>同步云端模板</Button>
          </div>
      }>
        <Table dataSource={templates} columns={columns} rowKey="id" />
      </Card>

      <Modal title="按 ID 导入模板" open={isImportModalOpen} onOk={handleImport} onCancel={() => setIsImportModalOpen(false)}>
          <Form form={importForm} layout="vertical">
              <Form.Item name="provider" label="服务商" initialValue="aliyun" rules={[{ required: true, message: '请选择服务商' }]}>
                  <Select>
                      <Select.Option value="aliyun">阿里云 (DirectMail)</Select.Option>
                      <Select.Option value="tencent">腾讯云 (SES)</Select.Option>
                  </Select>
              </Form.Item>
              <Form.Item name="account_id" label="云账号" rules={[{ required: true, message: '请选择云账号' }]}>
                  <Select options={importAccountOptions} placeholder="请选择账号" />
              </Form.Item>
              <Form.Item name="template_id" label="模板 ID" rules={[{ required: true, message: '请输入模板 ID' }]} tooltip="请在腾讯云/阿里云控制台查找模板 ID (数字)">
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

const App = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [authStatus, setAuthStatus] = useState({
    loading: true,
    authenticated: false,
    bootstrap_required: false,
    auth_enabled: true,
  });
  const [authSubmitting, setAuthSubmitting] = useState(false);
  const [authForm] = Form.useForm();
  const {
    token: { colorBgContainer },
  } = theme.useToken();

  const refreshAuthStatus = () => {
    authApi.status()
      .then((res) => {
        setAuthStatus({
          loading: false,
          authenticated: !!res.data?.authenticated,
          bootstrap_required: !!res.data?.bootstrap_required,
          auth_enabled: res.data?.auth_enabled !== false,
        });
      })
      .catch(() => {
        setAuthStatus({
          loading: false,
          authenticated: false,
          bootstrap_required: true,
        });
      });
  };

  useEffect(() => {
    refreshAuthStatus();
  }, []);

  const handleAuthSubmit = async () => {
    try {
      const values = await authForm.validateFields();
      setAuthSubmitting(true);
      if (authStatus.bootstrap_required) {
        await authApi.bootstrap(values.password);
        message.success('管理员密码设置成功');
      } else {
        await authApi.login(values.password);
        message.success('登录成功');
      }
      authForm.resetFields();
      refreshAuthStatus();
    } catch (e) {
      if (e?.errorFields) return;
      message.error(e.response?.data?.detail || '认证失败');
    } finally {
      setAuthSubmitting(false);
    }
  };

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } finally {
      refreshAuthStatus();
    }
  };

  if (authStatus.loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!authStatus.authenticated) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f5f5f5', padding: 16 }}>
        <Card
          title={authStatus.bootstrap_required ? '首次初始化管理员密码' : '管理员登录'}
          style={{ width: 420, maxWidth: '100%' }}
        >
          <Form form={authForm} layout="vertical" onFinish={handleAuthSubmit}>
            <Form.Item
              name="password"
              label="密码"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 8, message: '密码至少 8 位' },
              ]}
            >
              <Input.Password placeholder="请输入管理员密码" />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={authSubmitting} block>
              {authStatus.bootstrap_required ? '初始化并进入系统' : '登录'}
            </Button>
          </Form>
        </Card>
      </div>
    );
  }

  const menuItems = [
    { key: '/', icon: <PieChartOutlined />, label: '数据看板' }, // Changed to Dashboard
    { key: '/campaigns', icon: <RocketOutlined />, label: '发信任务' }, // Renamed path
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
          {authStatus.auth_enabled ? <Button onClick={handleLogout}>退出登录</Button> : null}
        </Header>
        <Content style={{ margin: '16px' }}>
          <Routes>
            <Route path="/" element={<Dashboard />} /> {/* New Home */}
            <Route path="/campaigns" element={<Campaigns />} /> {/* Moved Campaigns */}
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
