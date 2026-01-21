# Multi-Cloud Email Sender (Pro)

A robust, enterprise-grade email marketing solution designed for non-technical users. Supports **Aliyun DirectMail** and **Tencent Cloud SES**, featuring automated batch scheduling, anti-spam strategies, and resilient data processing.

![Dashboard Preview](https://via.placeholder.com/800x400?text=Dashboard+Preview)

## 🚀 Key Features

*   **☁️ Multi-Cloud Support**: Seamlessly switch between **Aliyun** and **Tencent Cloud** for optimal deliverability.
*   **🛡️ Anti-Ban Strategy**: Built-in "Jitter" (randomized delays) and automated batching to mimic human behavior and avoid rate limits.
*   **⏰ Scheduled Campaigns**: Plan your campaigns ahead of time. Set it and forget it.
*   **💪 Robust CSV Parsing**: intelligently handles broken encodings (GBK/UTF-8), BOM headers, and even tab-separated files. Auto-cleans dirty email formats.
*   **📝 Template Management**: Sync templates directly from the cloud console. Supports dynamic variables like `{Name}`, `{Gender}` from your CSV.
*   **👀 Observability**: Real-time progress tracking and detailed sending logs.

## 🛠️ Tech Stack

*   **Backend**: Python 3.10+ (FastAPI, SQLAlchemy, APScheduler, Pandas)
*   **Frontend**: React (Vite, Ant Design)
*   **Database**: SQLite (Zero-config, portable)

## 📦 Deployment Guide

You can run this project directly from source (Development Mode) or package it into a standalone executable (Production Mode).

### Option A: Run from Source (Recommended for Devs)

Requires **Python 3.10+** and **Node.js 18+**.

**Linux / macOS:**
```bash
# 1. Clone & Install
git clone https://github.com/LouisLau-art/multi-cloud-email-sender.git
cd multi-cloud-email-sender

# 2. Start
./start.sh
```

**Windows:**
1.  Double-click `start.bat`.
2.  The script will install dependencies and launch both backend and frontend servers.

### Option B: Build Standalone Executable (Recommended for End Users)

You can package the entire application (Backend + Frontend + Python Runtime) into a single executable file. No installation required for the end user.

**Build for Linux:**
```bash
./build_linux.sh
```
*   Output: `dist/EmailSender_Linux`
*   Usage: `./dist/EmailSender_Linux` then open `http://localhost:8000`

**Build for Windows:**
1.  Double-click `build_windows.bat`.
2.  Wait for the process to finish.
3.  Output: `dist\EmailSender\EmailSender.exe`
4.  Usage: Send the `dist\EmailSender` folder to your user. They just need to run `EmailSender.exe`.

---

## 📖 User Guide

1.  **Configuration**: Go to **Settings** and enter your AccessKey/Secret for Aliyun or Tencent Cloud.
2.  **Contacts**: Upload your recipient list (CSV). The system auto-detects `EmailAddr` and other variables.
3.  **Templates**: Create a template or sync from the cloud. Use `{Variable}` syntax for personalization.
4.  **Campaigns**: Create a task, choose your provider, and set a schedule.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
