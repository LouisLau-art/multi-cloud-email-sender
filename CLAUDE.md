# CLAUDE.md

## 项目概述
多云邮件营销发送系统，集成阿里云DirectMail和腾讯云SES双通道，支持百万级邮件智能调度发送。面向非技术用户提供零门槛操作界面。

## 技术栈
- **后端**: Python 3.10+, FastAPI, SQLite, 阿里云SDK, 腾讯云SDK
- **前端**: React 18, Ant Design
- **打包**: PyInstaller (Windows EXE离线包)

## 常用命令

### 开发模式
```bash
# 后端启动
cd backend
uvicorn main:app --reload --port 8000

# 前端启动
cd frontend
bun install
bun run dev --port 3000
```

### 打包部署
```bash
# 构建Windows EXE离线包
pyinstaller --onefile --windowed --name EmailSender --add-data "frontend/build:frontend/build" backend/main.py

# Linux 部署
./start.sh
```

### 测试
```bash
cd backend
pytest tests/
```

## 项目架构
```
前端 (React) → 后端API (FastAPI) → 多云邮件服务商 (阿里云/腾讯云)
    ↓                     ↓
静态资源              SQLite数据库
```

## 核心文件
| 路径 | 用途 |
|------|------|
| `backend/main.py` | 后端入口 |
| `backend/app/` | 业务逻辑 |
| `frontend/src/` | 前端源码 |
| `start.sh` | Linux一键启动脚本 |
| `start.bat` | Windows一键启动脚本 |

## 部署指南
### EXE离线运行
1. 下载`EmailSender.zip`解压
2. 双击`EmailSender.exe`运行
3. 浏览器自动打开`http://localhost:8000`

### 源码部署
```bash
git clone <repo>
cd multi-cloud-email-sender
./start.sh
```

## 常见问题
- **发信失败**: 检查AccessKey配置、发信域名是否已验证、额度是否充足
- **中文乱码**: 确保CSV文件使用UTF-8编码
- **EXE启动慢**: 首次启动需要解包，属于正常现象
- **风控拦截**: 开启随机抖动和分批发送策略降低入箱率

## 开发约定
- Python代码遵循PEP8规范，使用类型提示
- 前端使用Bun作为包管理器
- 所有API接口遵循RESTful规范，自带Swagger文档 (`/docs`)