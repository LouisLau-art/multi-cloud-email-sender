import React, { useState, useEffect } from 'react';
import { Card, message, Table, Select, Tag, Button, DatePicker, Row, Col, Tabs, Space, Radio, Statistic, Input } from 'antd';
import { UserOutlined, RocketOutlined, PieChartOutlined, CheckCircleOutlined, EyeOutlined, DownloadOutlined, SyncOutlined } from '@ant-design/icons';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip, Legend, ResponsiveContainer } from 'recharts';
import api, { dashboardApi } from '../services/api';
import '../dashboard-selection.css';

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

  const isCampaignSelected = (campaignId) =>
    selectedCampaignId !== undefined && String(campaignId) === String(selectedCampaignId);

  const selectedCampaign = campaignSummaries.find((campaign) => isCampaignSelected(campaign.id));

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
    {
      title: '任务名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => {
        const selected = isCampaignSelected(record.id);
        return (
          <span className="dashboard-campaign-name-cell">
            <span
              className={`dashboard-campaign-name-icon${selected ? ' is-visible' : ''}`}
              aria-hidden="true"
            >
              <CheckCircleOutlined />
            </span>
            <span>{text}</span>
          </span>
        );
      },
    },
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
    { title: '姓名', dataIndex: 'name', key: 'name', render: (t) => t || '-' },
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
        <div className="dashboard-selection-indicator">
          {selectedCampaign ? (
            <span>
              当前已选任务：
              <span style={{ marginLeft: 8, marginRight: 6, fontWeight: 600, color: '#1f2937' }}>
                {selectedCampaign.name}
              </span>
              <span style={{ color: '#6b7280' }}>#{selectedCampaign.id}</span>
            </span>
          ) : (
            <span>当前查看：全部任务</span>
          )}
        </div>
        <Table
          size="small"
          rowKey="id"
          dataSource={campaignSummaries}
          columns={campaignColumns}
          pagination={{ pageSize: 6 }}
          rowClassName={(record) =>
            isCampaignSelected(record.id)
              ? 'dashboard-campaign-row dashboard-campaign-row-selected'
              : 'dashboard-campaign-row'
          }
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

export default Dashboard;
