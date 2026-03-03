import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Button, message, Table, Select, Tag, Popconfirm, Space, Divider, Row, Col, Switch } from 'antd';
import { settingsApi, accountApi } from '../services/api';

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

export default Settings;
