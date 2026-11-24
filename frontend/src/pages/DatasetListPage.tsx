import React, { useEffect, useState } from 'react';
import {
  Button,
  Modal,
  Form,
  Input,
  Radio,
  Select,
  Checkbox,
  Space,
  message,
  Popconfirm,
  Tag,
  Spin,
  Row,
  Col,
  Card,
} from 'antd';
import { PlusOutlined, DeleteOutlined, MinusCircleOutlined, FileSearchOutlined, DatabaseOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { Dataset, FieldDefinition } from '../types';
import * as api from '../services/api';
import { Typography } from 'antd';

const { Title } = Typography;

const fieldTypeOptions = [
  { label: 'text', value: 'text' },
  { label: 'number', value: 'number' },
  { label: 'text_list', value: 'text_list' },
  { label: 'conversation', value: 'conversation' },
  { label: 'tool_call_list', value: 'tool_call_list' },
];

const sampleTypeColorMap: Record<string, string> = {
  single_turn: 'blue',
  multi_turn: 'purple',
};

const singleTurnDefaults: FieldDefinition[] = [
  { name: 'user_input', type: 'text', required: true, description: '用户输入' },
  { name: 'response', type: 'text', required: true, description: 'LLM 回复' },
  { name: 'reference', type: 'text', required: false, description: '参考答案' },
  { name: 'retrieved_contexts', type: 'text_list', required: false, description: '检索上下文列表' },
];

const multiTurnDefaults: FieldDefinition[] = [
  { name: 'user_input', type: 'conversation', required: true, description: '多轮对话输入' },
  { name: 'reference', type: 'text', required: false, description: '参考答案' },
  { name: 'reference_tool_calls', type: 'tool_call_list', required: false, description: '参考工具调用' },
];

const DatasetListPage: React.FC = () => {
  const navigate = useNavigate();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();
  const [fieldSchema, setFieldSchema] = useState<FieldDefinition[]>([...singleTurnDefaults]);

  const fetchDatasets = async () => {
    setLoading(true);
    try {
      const data = await api.listDatasets();
      setDatasets(Array.isArray(data) ? data : []);
    } catch {
      message.error('加载数据集列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
  }, []);

  const handleSampleTypeChange = (value: string) => {
    if (value === 'single_turn') {
      setFieldSchema([...singleTurnDefaults]);
    } else if (value === 'multi_turn') {
      setFieldSchema([...multiTurnDefaults]);
    }
  };

  const addField = () => {
    setFieldSchema([...fieldSchema, { name: '', type: 'text', required: false, description: '' }]);
  };

  const removeField = (index: number) => {
    const newSchema = [...fieldSchema];
    newSchema.splice(index, 1);
    setFieldSchema(newSchema);
  };

  const updateField = (index: number, key: keyof FieldDefinition, value: any) => {
    const newSchema = [...fieldSchema];
    (newSchema[index] as any)[key] = value;
    setFieldSchema(newSchema);
  };

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      const validFields = fieldSchema.filter(f => f.name.trim() !== '');
      if (validFields.length === 0) {
        message.error('请至少定义一个字段');
        return;
      }
      setSubmitting(true);
      await api.createDataset({
        name: values.name,
        description: values.description || '',
        sample_type: values.sample_type,
        field_schema: validFields,
      });
      message.success('数据集创建成功');
      setModalOpen(false);
      form.resetFields();
      setFieldSchema([...singleTurnDefaults]);
      fetchDatasets();
    } catch {
      message.error('创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteDataset(id);
      message.success('删除成功');
      fetchDatasets();
    } catch {
      message.error('删除失败');
    }
  };

  return (
    <Spin spinning={loading}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, color: 'var(--text-primary)' }}>数据集管理</h2>
          <p style={{ margin: '4px 0 0', color: 'var(--text-secondary)', fontSize: 13 }}>
            管理评测所需的测试数据集，支持单轮/多轮对话、RAG、Agent 等场景。
          </p>
        </div>
        <Space>
          <Button icon={<FileSearchOutlined />} onClick={() => navigate('/datasets/rag-builder')}>
            RAG 构建
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            新建数据集
          </Button>
        </Space>
      </div>

      {datasets.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '60px 20px',
          background: 'var(--bg-secondary)',
          borderRadius: 8,
          border: '1px dashed var(--border-color)',
        }}>
          <DatabaseOutlined style={{ fontSize: 40, color: 'var(--text-tertiary)', marginBottom: 16 }} />
          <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>暂无数据集，创建第一个开始评测</p>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            新建数据集
          </Button>
        </div>
      ) : (
        <Row gutter={[16, 16]}>
          {datasets.map((dataset) => (
            <Col key={dataset.id} xs={24} sm={12} md={8} lg={6}>
              <Card
                hoverable
                style={{ height: '100%', cursor: 'pointer' }}
                onClick={() => navigate(`/datasets/${dataset.id}`)}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, height: '100%' }}>
                  {/* 标题行 */}
                  <div>
                    <h4 style={{
                      margin: '0 0 4px',
                      fontSize: 15,
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {dataset.name}
                    </h4>
                    {dataset.description && (
                      <p style={{
                        margin: 0,
                        fontSize: 12,
                        color: 'var(--text-tertiary)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}>
                        {dataset.description}
                      </p>
                    )}
                  </div>

                  {/* 标签 */}
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <Tag color={sampleTypeColorMap[dataset.sample_type] || 'default'}>
                      {dataset.sample_type}
                    </Tag>
                    <Tag color="gold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                      {dataset.row_count} 行
                    </Tag>
                  </div>

                  {/* 时间 */}
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 'auto' }}>
                    {new Date(dataset.created_at).toLocaleDateString('zh-CN')}
                  </div>

                  {/* 操作 */}
                  <div
                    style={{
                      display: 'flex',
                      gap: 8,
                      paddingTop: 10,
                      borderTop: '1px solid var(--border-color)',
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Button
                      size="small"
                      type="text"
                      onClick={() => navigate(`/datasets/${dataset.id}`)}
                    >
                      查看
                    </Button>
                    <Popconfirm
                      title="确认删除此数据集？"
                      onConfirm={() => handleDelete(dataset.id)}
                    >
                      <Button size="small" danger type="text" icon={<DeleteOutlined />}>
                        删除
                      </Button>
                    </Popconfirm>
                  </div>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title="新建数据集"
        open={modalOpen}
        onOk={handleCreate}
        confirmLoading={submitting}
        onCancel={() => {
          setModalOpen(false);
          form.resetFields();
          setFieldSchema([...singleTurnDefaults]);
        }}
        okText="创建"
        cancelText="取消"
        width={720}
      >
        <Form form={form} layout="vertical" initialValues={{ sample_type: 'single_turn' }}>
          <Form.Item
            name="name"
            label="数据集名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="例如: RAG 测试数据集" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="可选描述信息" rows={2} />
          </Form.Item>
          <Form.Item name="sample_type" label="样本类型" rules={[{ required: true }]}>
            <Radio.Group onChange={(e) => handleSampleTypeChange(e.target.value)}>
              <Radio.Button value="single_turn">单轮对话</Radio.Button>
              <Radio.Button value="multi_turn">多轮对话</Radio.Button>
            </Radio.Group>
          </Form.Item>
        </Form>

        <div style={{ marginBottom: 8 }}>
          <Typography.Text strong>字段定义</Typography.Text>
        </div>
        <div style={{ maxHeight: 300, overflowY: 'auto' }}>
          {fieldSchema.map((field, index) => (
            <Space key={index} style={{ display: 'flex', marginBottom: 8 }} align="start">
              <Input
                placeholder="字段名"
                value={field.name}
                onChange={(e) => updateField(index, 'name', e.target.value)}
                style={{ width: 140 }}
              />
              <Select
                value={field.type}
                onChange={(val) => updateField(index, 'type', val)}
                options={fieldTypeOptions}
                style={{ width: 140 }}
              />
              <Checkbox
                checked={field.required}
                onChange={(e) => updateField(index, 'required', e.target.checked)}
              >
                必填
              </Checkbox>
              <Input
                placeholder="描述"
                value={field.description}
                onChange={(e) => updateField(index, 'description', e.target.value)}
                style={{ width: 160 }}
              />
              <Button
                type="text"
                danger
                icon={<MinusCircleOutlined />}
                onClick={() => removeField(index)}
              />
            </Space>
          ))}
        </div>
        <Button type="dashed" onClick={addField} block icon={<PlusOutlined />} style={{ marginTop: 8 }}>
          添加字段
        </Button>
      </Modal>
    </Spin>
  );
};

export default DatasetListPage;
