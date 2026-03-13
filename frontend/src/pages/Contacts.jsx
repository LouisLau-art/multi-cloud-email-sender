import React, { useState, useEffect } from 'react';
import { Card, Upload, Button, message, Table, Popconfirm } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import api, { contactApi } from '../services/api';

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

  const handleDelete = async (id) => {
      try {
        await contactApi.delete(id);
        message.success('列表已删除');
        refresh();
      } catch (e) {
        message.error('删除失败: ' + (e.response?.data?.detail || e.message));
      }
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
        * CSV 文件必须包含 <b>EmailAddr</b> 列（收件人邮箱），建议包含 <b>Name</b>；也可加入 <b>UserName</b>、<b>Birthday</b> 等变量列。<br/>
        * 系统会自动过滤重复和无效的邮件地址，请在上传前删除文件底部的说明文字。
      </div>
    </Card>
  );
};

export default Contacts;
