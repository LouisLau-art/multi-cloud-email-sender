import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Button, message, Table, Select, Tag, Popconfirm, Modal, Tabs, Divider, Space } from 'antd';
import { EditOutlined, DeleteOutlined, RocketOutlined } from '@ant-design/icons';
import DOMPurify from 'dompurify';
import api, { accountApi } from '../services/api';

const { TextArea } = Input;

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

export default Templates;
