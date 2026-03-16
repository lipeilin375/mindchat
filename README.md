# MindChat - 心理健康监测系统

基于语音对话的AI心理健康监测Web应用。

## 功能特性

- 🎤 语音对话：通过语音与AI进行自然对话
- 😊 情绪分析：实时分析用户情绪状态
- 📊 抑郁评估：评估用户抑郁倾向并预警
- 📈 数据可视化：展示情绪和心理健康趋势
- 👥 管理员功能：跟踪所有用户心理状况

## 技术栈

- **后端**: FastAPI + SQLite
- **前端**: React + Vite + Ant Design
- **AI模型**:
  - Whisper (语音转文本)
  - MindChat-Internlm2-7B (对话)
  - GLM-4.5-air (情绪分析)
  - 自定义模型 (抑郁评估)
- **部署**: Docker + Docker Compose

## 快速开始

### 前置要求

- Docker 和 Docker Compose
- Ollama (安装并运行在宿主机)
- 情绪分析API密钥

### 1. 配置环境变量

```bash
cp backend/.env.example .env
```

编辑 `.env` 文件：
```
JWT_SECRET=your-secret-key
EMOTION_API_KEY=your-api-key
```

### 2. 启动Ollama并加载模型

```bash
ollama pull mindchat-internlm2-7b
```

### 3. 启动服务

```bash
docker-compose up -d
```

- 后端API: http://localhost:8000
- 前端: http://localhost:5173
- API文档: http://localhost:8000/docs

## 使用说明

1. 注册账号并登录
2. 进入聊天页面，点击"开始录音"
3. 说话后点击"停止录音"，系统会自动处理
4. 查看AI回复和情绪分析结果
5. 在数据面板查看历史趋势

## 管理员功能

创建管理员账号需要直接修改数据库：
```sql
UPDATE users SET is_admin = 1 WHERE username = 'admin';
```

## 项目结构

```
mindchat/
├── backend/          # FastAPI后端
├── frontend/         # React前端
└── docker-compose.yml
```

## API端点

- `POST /api/auth/register` - 注册
- `POST /api/auth/login` - 登录
- `POST /api/chat/voice` - 语音处理
- `GET /api/data/emotions` - 情绪历史
- `GET /api/admin/users` - 用户列表(管理员)

## 注意事项

1. 确保宿主机Ollama服务运行在11434端口
2. 抑郁评估模型需放在 `backend/model/anti_depression/`
3. 音频文件限制5MB以内
4. 首次启动会自动创建数据库

## License

MIT
