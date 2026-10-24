import { useRef } from 'react'
import { Alert, Button, Form, Input, Modal, Space, Tabs, Upload } from 'antd'
import { UploadOutlined } from '@ant-design/icons'

export interface TextForm {
  title?: string
  content: string
}

export interface UploadForm {
  title?: string
}

export interface UrlForm {
  url: string
  title?: string
}

interface CreateEntryModalProps {
  open: boolean
  loading: boolean
  onClose: () => void
  onCreateText: (values: TextForm) => void
  onCreateUpload: (file: File, values: UploadForm) => void
  onCreateUrl: (values: UrlForm) => void
}

/** 新建知识库弹窗：文本录入 / 文件上传 / 网页链接 三种方式。 */
export default function CreateEntryModal({
  open,
  loading,
  onClose,
  onCreateText,
  onCreateUpload,
  onCreateUrl,
}: CreateEntryModalProps) {
  const [textForm] = Form.useForm<TextForm>()
  const [uploadForm] = Form.useForm<UploadForm>()
  const [urlForm] = Form.useForm<UrlForm>()
  /** 选中的文件（Upload 自身管理展示，这里只存引用） */
  const uploadFileRef = useRef<File | null>(null)

  return (
    <Modal
      title="新建知识库"
      open={open}
      onCancel={onClose}
      afterClose={() => {
        uploadFileRef.current = null
        textForm.resetFields()
        uploadForm.resetFields()
        urlForm.resetFields()
      }}
      footer={null}
      width={640}
      forceRender
      destroyOnHidden
    >
      <Tabs
        items={[
          {
            key: 'text',
            label: '文本录入',
            children: (
              <Form<TextForm> layout="vertical" form={textForm} onFinish={onCreateText}>
                <Form.Item name="title" label="标题（可选，缺省取正文首行前 30 字）">
                  <Input placeholder="请输入标题" maxLength={100} />
                </Form.Item>
                <Form.Item
                  name="content"
                  label="正文内容"
                  rules={[{ required: true, message: '请输入正文内容' }]}
                >
                  <Input.TextArea
                    rows={10}
                    placeholder="请粘贴技术笔记、文档或源码片段…"
                    showCount
                    maxLength={100000}
                  />
                </Form.Item>
                <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
                  <Space>
                    <Button onClick={onClose}>取消</Button>
                    <Button type="primary" htmlType="submit" loading={loading}>
                      提交录入
                    </Button>
                  </Space>
                </Form.Item>
              </Form>
            ),
          },
          {
            key: 'file',
            label: '文件上传',
            children: (
              <Form<UploadForm>
                layout="vertical"
                form={uploadForm}
                onFinish={(values) => {
                  const file = uploadFileRef.current
                  if (file) onCreateUpload(file, values)
                }}
              >
                <Alert
                  type="info"
                  showIcon
                  message="支持 .txt / .md / .pdf / .docx，大小不超过 10MB"
                  description="PDF 需含文本层（扫描件不支持 OCR）；DOCX 提取段落与表格文本。"
                  style={{ marginBottom: 16 }}
                />
                <Form.Item name="title" label="标题（可选，缺省自动识别）">
                  <Input placeholder="请输入标题" maxLength={100} />
                </Form.Item>
                <Form.Item label="选择文件" required>
                  <Upload
                    accept=".txt,.md,.pdf,.docx"
                    maxCount={1}
                    beforeUpload={(file) => {
                      uploadFileRef.current = file
                      return false
                    }}
                    onRemove={() => {
                      uploadFileRef.current = null
                    }}
                  >
                    <Button icon={<UploadOutlined />}>选择文件</Button>
                  </Upload>
                </Form.Item>
                <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
                  <Space>
                    <Button onClick={onClose}>取消</Button>
                    <Button type="primary" htmlType="submit" loading={loading}>
                      上传并处理
                    </Button>
                  </Space>
                </Form.Item>
              </Form>
            ),
          },
          {
            key: 'url',
            label: '网页链接',
            children: (
              <Form<UrlForm> layout="vertical" form={urlForm} onFinish={onCreateUrl}>
                <Alert
                  type="info"
                  showIcon
                  message="抓取网页正文（自动去除导航/广告/页脚）"
                  description="需要公开可访问的 http/https 页面；需登录或纯动态渲染的页面可能提取失败。"
                  style={{ marginBottom: 16 }}
                />
                <Form.Item
                  name="url"
                  label="网页链接"
                  rules={[
                    { required: true, message: '请输入网页链接' },
                    {
                      pattern: /^https?:\/\/.+/i,
                      message: 'URL 必须以 http:// 或 https:// 开头',
                    },
                  ]}
                >
                  <Input placeholder="例如 https://example.com/article" maxLength={2000} />
                </Form.Item>
                <Form.Item name="title" label="标题（可选，缺省取网页标题）">
                  <Input placeholder="请输入标题" maxLength={100} />
                </Form.Item>
                <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
                  <Space>
                    <Button onClick={onClose}>取消</Button>
                    <Button type="primary" htmlType="submit" loading={loading}>
                      抓取并处理
                    </Button>
                  </Space>
                </Form.Item>
              </Form>
            ),
          },
        ]}
      />
    </Modal>
  )
}
