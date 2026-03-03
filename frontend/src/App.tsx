import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Drawer,
  Form,
  Input,
  InputNumber,
  Layout,
  List,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import dayjs from 'dayjs';

import api from './api';
import type { CalendarEvent, Contact, Task, TaskDetails, TaskStatus } from './types';

const { Header, Content } = Layout;
const statusOptions: TaskStatus[] = ['todo', 'in_progress', 'blocked', 'done', 'cancelled'];

interface Overview {
  contact_tag_counts: Record<string, number>;
  platform_counts: Record<string, number>;
  work_category_counts: Record<string, number>;
  today_tasks: Task[];
  overdue_tasks: Task[];
  recent_messages: { id: number; content: string; sent_at: string; contact_name?: string }[];
  latest_summary: { summary_date: string; content: string; generated_at: string } | null;
}

interface TaskFilters {
  source_platform?: string;
  work_category?: string;
}

function App() {
  const [loading, setLoading] = useState(false);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [taskFilters, setTaskFilters] = useState<TaskFilters>({});
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [taskDetailsLoading, setTaskDetailsLoading] = useState(false);
  const [taskDetails, setTaskDetails] = useState<TaskDetails | null>(null);

  const loadTasksData = async (filters: TaskFilters = taskFilters) => {
    const params: Record<string, string> = {};
    if (filters.source_platform) {
      params.source_platform = filters.source_platform;
    }
    if (filters.work_category) {
      params.work_category = filters.work_category;
    }

    const ts = await api.get('/api/tasks', { params });
    setTasks(ts.data);
  };

  const loadAll = async () => {
    setLoading(true);
    try {
      const [ov, cs, es] = await Promise.all([
        api.get('/api/dashboard/overview'),
        api.get('/api/contacts'),
        api.get('/api/calendar/events'),
      ]);
      setOverview(ov.data);
      setContacts(cs.data);
      setEvents(es.data);
      await loadTasksData(taskFilters);
    } catch {
      message.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    loadTasksData(taskFilters).catch(() => {
      message.error('Failed to load tasks');
    });
  }, [taskFilters.source_platform, taskFilters.work_category]);

  const triggerSync = async (path: string) => {
    await api.post(path);
    await loadAll();
    message.success(`Triggered ${path}`);
  };

  const updateTask = async (taskId: number, patch: Partial<Task>) => {
    await api.patch(`/api/tasks/${taskId}`, patch);
    await loadTasksData(taskFilters);
    await api.get('/api/dashboard/overview').then((ov) => setOverview(ov.data));
    if (taskDetails && taskDetails.task.id === taskId) {
      await openTaskDetails(taskId);
    }
  };

  const openTaskDetails = async (taskId: number) => {
    setTaskDetailsLoading(true);
    setDetailsOpen(true);
    try {
      const response = await api.get(`/api/tasks/${taskId}/details`);
      setTaskDetails(response.data);
    } catch {
      message.error('Failed to load task breakdown');
      setDetailsOpen(false);
    } finally {
      setTaskDetailsLoading(false);
    }
  };

  const approvePendingTags = async (contactId: number) => {
    await api.post(`/api/contacts/${contactId}/tags/approve-pending`);
    await loadAll();
    message.success('Pending tags approved');
  };

  const tagRows = useMemo(() => {
    if (!overview) return [];
    return Object.entries(overview.contact_tag_counts).map(([name, count]) => ({ name, count }));
  }, [overview]);

  const platformRows = useMemo(() => {
    if (!overview) return [];
    return Object.entries(overview.platform_counts).map(([name, count]) => ({ name, count }));
  }, [overview]);

  const workCategoryRows = useMemo(() => {
    if (!overview) return [];
    return Object.entries(overview.work_category_counts).map(([name, count]) => ({ name, count }));
  }, [overview]);

  const platformOptions = useMemo(() => {
    const values = Object.keys(overview?.platform_counts || {});
    return values.map((item) => ({ label: item, value: item }));
  }, [overview]);

  const workCategoryOptions = useMemo(() => {
    const values = Object.keys(overview?.work_category_counts || {});
    return values.map((item) => ({ label: item, value: item }));
  }, [overview]);

  return (
    <Layout>
      <Header style={{ background: '#12263a', color: '#fff' }}>
        <div className="app-shell page-header">
          <Typography.Title style={{ color: '#fff', margin: 0 }} level={4}>
            Personal Assistant MVP
          </Typography.Title>
          <Space>
            <Button onClick={() => triggerSync('/api/sync/telegram')}>Sync Telegram</Button>
            <Button onClick={() => triggerSync('/api/sync/telegram/user')}>Sync Telegram User</Button>
            <Button onClick={() => triggerSync('/api/sync/calendar')}>Sync Calendar</Button>
            <Button type="primary" onClick={() => triggerSync('/api/summary/daily')}>
              Generate Daily Summary
            </Button>
          </Space>
        </div>
      </Header>
      <Content>
        <div className="app-shell">
          <Tabs
            items={[
              {
                key: 'overview',
                label: 'Overview',
                children: (
                  <Space direction="vertical" style={{ width: '100%' }} size={12}>
                    <Row gutter={12}>
                      <Col span={8}>
                        <Card>
                          <Statistic title="Today Tasks" value={overview?.today_tasks.length || 0} loading={loading} />
                        </Card>
                      </Col>
                      <Col span={8}>
                        <Card>
                          <Statistic title="Overdue Tasks" value={overview?.overdue_tasks.length || 0} loading={loading} />
                        </Card>
                      </Col>
                      <Col span={8}>
                        <Card>
                          <Statistic title="Contacts" value={contacts.length} loading={loading} />
                        </Card>
                      </Col>
                    </Row>

                    <div className="grid">
                      <Card title="Contact Tags" loading={loading}>
                        <Table
                          pagination={false}
                          size="small"
                          dataSource={tagRows}
                          rowKey="name"
                          columns={[
                            { title: 'Tag', dataIndex: 'name' },
                            { title: 'Count', dataIndex: 'count' },
                          ]}
                        />
                      </Card>

                      <Card title="Platform Message Distribution" loading={loading}>
                        <Table
                          pagination={false}
                          size="small"
                          dataSource={platformRows}
                          rowKey="name"
                          columns={[
                            { title: 'Platform', dataIndex: 'name' },
                            { title: 'Messages', dataIndex: 'count' },
                          ]}
                        />
                      </Card>

                      <Card title="Work Category Distribution" loading={loading}>
                        <Table
                          pagination={false}
                          size="small"
                          dataSource={workCategoryRows}
                          rowKey="name"
                          columns={[
                            { title: 'Category', dataIndex: 'name' },
                            { title: 'Tasks', dataIndex: 'count' },
                          ]}
                        />
                      </Card>

                      <Card title="Recent Messages" loading={loading}>
                        <Table
                          pagination={{ pageSize: 5 }}
                          size="small"
                          dataSource={overview?.recent_messages || []}
                          rowKey="id"
                          columns={[
                            { title: 'Contact', dataIndex: 'contact_name', render: (v: string) => v || '-' },
                            { title: 'Content', dataIndex: 'content', ellipsis: true },
                            {
                              title: 'Sent At',
                              dataIndex: 'sent_at',
                              render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
                            },
                          ]}
                        />
                      </Card>
                    </div>

                    <Card title="Latest Daily Summary" loading={loading}>
                      {overview?.latest_summary ? (
                        <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                          {overview.latest_summary.content}
                        </Typography.Paragraph>
                      ) : (
                        <Alert type="info" message="No summary yet. Click 'Generate Daily Summary'." />
                      )}
                    </Card>
                  </Space>
                ),
              },
              {
                key: 'contacts',
                label: 'Contacts',
                children: (
                  <Card title="Contacts & Tags" loading={loading}>
                    <Table
                      rowKey="id"
                      dataSource={contacts}
                      columns={[
                        { title: 'Name', dataIndex: 'display_name' },
                        { title: 'Platform', dataIndex: 'platform' },
                        {
                          title: 'Tags',
                          render: (_, record: Contact) => {
                            const manual = record.tags_json.manual || [];
                            const ai = record.tags_json.ai || [];
                            const pending = record.tags_json.pending || [];
                            const hasTags = manual.length || ai.length || pending.length;
                            if (!hasTags) return '-';

                            return (
                              <Space wrap>
                                {manual.map((tag) => (
                                  <Tag color="blue" key={`manual-${tag}`}>
                                    manual:{tag}
                                  </Tag>
                                ))}
                                {ai.map((tag) => (
                                  <Tag color="green" key={`ai-${tag}`}>
                                    ai:{tag}
                                  </Tag>
                                ))}
                                {pending.map((tag) => (
                                  <Tag color="orange" key={`pending-${tag}`}>
                                    pending:{tag}
                                  </Tag>
                                ))}
                              </Space>
                            );
                          },
                        },
                        {
                          title: 'Action',
                          render: (_, record: Contact) => {
                            const pending = record.tags_json.pending || [];
                            if (!pending.length) return '-';
                            return (
                              <Button size="small" onClick={() => approvePendingTags(record.id)}>
                                Approve Pending ({pending.length})
                              </Button>
                            );
                          },
                        },
                        { title: 'Last Seen', dataIndex: 'last_seen_at', render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm') },
                      ]}
                    />
                  </Card>
                ),
              },
              {
                key: 'tasks',
                label: 'Tasks',
                children: (
                  <Space direction="vertical" style={{ width: '100%' }} size={12}>
                    <Card title="Create Task">
                      <TaskCreateForm onCreated={loadAll} />
                    </Card>
                    <Card
                      title="Task Cards"
                      loading={loading}
                      extra={
                        <Space>
                          <Select
                            allowClear
                            placeholder="Filter platform"
                            style={{ width: 180 }}
                            value={taskFilters.source_platform}
                            options={platformOptions}
                            onChange={(value) => setTaskFilters((prev) => ({ ...prev, source_platform: value || undefined }))}
                          />
                          <Select
                            allowClear
                            placeholder="Filter work category"
                            style={{ width: 220 }}
                            value={taskFilters.work_category}
                            options={workCategoryOptions}
                            onChange={(value) => setTaskFilters((prev) => ({ ...prev, work_category: value || undefined }))}
                          />
                        </Space>
                      }
                    >
                      <Row gutter={[12, 12]}>
                        {tasks.map((task) => (
                          <Col xs={24} md={12} xl={8} key={task.id}>
                            <Card
                              size="small"
                              title={task.title}
                              extra={<Tag>{task.status}</Tag>}
                              actions={[
                                <Button type="link" onClick={() => openTaskDetails(task.id)} key={`view-${task.id}`}>
                                  View Breakdown
                                </Button>,
                              ]}
                            >
                              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                                <Typography.Text type="secondary">
                                  {task.source_message_preview || task.description || 'No chat summary available'}
                                </Typography.Text>
                                <Typography.Text>Platform: {task.source_platform}</Typography.Text>
                                <Typography.Text>Category: {task.work_category || 'uncategorized'}</Typography.Text>
                                <Typography.Text>Due: {task.due_at ? dayjs(task.due_at).format('YYYY-MM-DD HH:mm') : '-'}</Typography.Text>
                                <Space>
                                  <Typography.Text>Assignee:</Typography.Text>
                                  <Input
                                    size="small"
                                    defaultValue={task.assignee_name || ''}
                                    placeholder="assignee"
                                    style={{ width: 140 }}
                                    onBlur={(e) => {
                                      if ((task.assignee_name || '') !== e.target.value) {
                                        updateTask(task.id, { assignee_name: e.target.value || null });
                                      }
                                    }}
                                  />
                                </Space>
                                <Space>
                                  <Typography.Text>Status:</Typography.Text>
                                  <Select
                                    size="small"
                                    value={task.status}
                                    style={{ width: 140 }}
                                    onChange={(next) => updateTask(task.id, { status: next })}
                                    options={statusOptions.map((s) => ({ label: s, value: s }))}
                                  />
                                </Space>
                              </Space>
                            </Card>
                          </Col>
                        ))}
                      </Row>
                    </Card>
                  </Space>
                ),
              },
              {
                key: 'calendar',
                label: 'Calendar',
                children: (
                  <Card title="Calendar Events" loading={loading}>
                    <Table
                      rowKey="id"
                      dataSource={events}
                      columns={[
                        { title: 'Source', dataIndex: 'source' },
                        { title: 'Title', dataIndex: 'title' },
                        { title: 'Start', dataIndex: 'start_at', render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm') },
                        { title: 'End', dataIndex: 'end_at', render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm') },
                        { title: 'Location', dataIndex: 'location', render: (v: string) => v || '-' },
                      ]}
                    />
                  </Card>
                ),
              },
              {
                key: 'settings',
                label: 'Settings',
                children: (
                  <Card title="MVP Settings & Notes">
                    <Alert
                      type="warning"
                      message="Only process data from accounts you explicitly own or are authorized to use."
                      style={{ marginBottom: 16 }}
                    />
                    <Typography.Paragraph>
                      Configure secrets in backend <code>.env</code>:
                    </Typography.Paragraph>
                    <Typography.Paragraph code>
                      OPENAI_API_KEY=... TELEGRAM_BOT_TOKEN=... TELEGRAM_NOTIFY_CHAT_ID=...
                    </Typography.Paragraph>
                    <Typography.Paragraph code>
                      TELEGRAM_SYNC_MODE=user TELEGRAM_USER_API_ID=... TELEGRAM_USER_API_HASH=...
                    </Typography.Paragraph>
                    <Typography.Paragraph code>TELEGRAM_USER_STRING_SESSION=...</Typography.Paragraph>
                    <Typography.Paragraph>
                      Google Calendar sync is mocked through backend/data/google_calendar_mock.json in this MVP.
                    </Typography.Paragraph>
                  </Card>
                ),
              },
            ]}
          />

          <Drawer
            title={taskDetails?.task.title || 'Task Breakdown'}
            open={detailsOpen}
            onClose={() => setDetailsOpen(false)}
            width={560}
            loading={taskDetailsLoading}
          >
            {taskDetails ? (
              <Space direction="vertical" style={{ width: '100%' }} size={16}>
                <Card size="small" title="Task Summary">
                  <Typography.Paragraph>{taskDetails.summary}</Typography.Paragraph>
                  <Space wrap>
                    <Tag>{taskDetails.task.status}</Tag>
                    <Tag>{taskDetails.task.source_platform}</Tag>
                    <Tag>{taskDetails.task.work_category || 'uncategorized'}</Tag>
                  </Space>
                </Card>

                <Tabs
                  items={[
                    {
                      key: 'todo',
                      label: 'To-Do List',
                      children: (
                        <List
                          bordered
                          dataSource={taskDetails.todo_items}
                          renderItem={(item, index) => (
                            <List.Item>
                              {index + 1}. {item}
                            </List.Item>
                          )}
                        />
                      ),
                    },
                    {
                      key: 'stakeholders',
                      label: 'Stakeholder List',
                      children: (
                        <List
                          bordered
                          dataSource={taskDetails.stakeholders}
                          renderItem={(item) => <List.Item>{item}</List.Item>}
                        />
                      ),
                    },
                    {
                      key: 'source',
                      label: 'Source Chat',
                      children: (
                        <Card size="small">
                          <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                            {taskDetails.source_message_content || 'No source message linked.'}
                          </Typography.Paragraph>
                        </Card>
                      ),
                    },
                  ]}
                />
              </Space>
            ) : null}
          </Drawer>
        </div>
      </Content>
    </Layout>
  );
}

function TaskCreateForm({ onCreated }: { onCreated: () => Promise<void> }) {
  const [form] = Form.useForm();

  const submit = async () => {
    const values = await form.validateFields();
    await api.post('/api/tasks', {
      title: values.title,
      description: values.description || null,
      priority: values.priority ?? 3,
      due_at: values.due_at ? values.due_at.toISOString() : null,
      location: values.location || null,
      assignee_name: values.assignee_name || null,
      work_category: values.work_category || null,
    });
    form.resetFields();
    message.success('Task created');
    await onCreated();
  };

  return (
    <Form form={form} layout="vertical">
      <Row gutter={12}>
        <Col span={6}>
          <Form.Item name="title" label="Title" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </Col>
        <Col span={6}>
          <Form.Item name="assignee_name" label="Assignee">
            <Input />
          </Form.Item>
        </Col>
        <Col span={4}>
          <Form.Item name="priority" label="Priority" initialValue={3}>
            <InputNumber min={1} max={5} style={{ width: '100%' }} />
          </Form.Item>
        </Col>
        <Col span={4}>
          <Form.Item name="work_category" label="Work Category">
            <Input placeholder="general_work" />
          </Form.Item>
        </Col>
        <Col span={4}>
          <Form.Item name="due_at" label="Due At">
            <DatePicker showTime style={{ width: '100%' }} />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={12}>
        <Col span={8}>
          <Form.Item name="location" label="Location">
            <Input />
          </Form.Item>
        </Col>
        <Col span={16}>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Col>
      </Row>
      <Button type="primary" onClick={submit}>
        Create Task
      </Button>
    </Form>
  );
}

export default App;
