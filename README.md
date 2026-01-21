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

## ⚡️ Quick Start

### Prerequisites
*   Python 3.10+
*   Node.js 18+

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/your-username/multi-cloud-email-sender.git
    cd multi-cloud-email-sender
    ```

2.  **Install Dependencies**
    ```bash
    # Backend
    pip install -r backend/requirements.txt
    
    # Frontend
    cd frontend
    npm install
    cd ..
    ```

3.  **Run the Application**
    ```bash
    ./start.sh
    ```
    Access the UI at `http://localhost:5173`.

## 📖 User Guide

1.  **Configuration**: Go to **Settings** and enter your AccessKey/Secret for Aliyun or Tencent Cloud.
2.  **Contacts**: Upload your recipient list (CSV). The system auto-detects `EmailAddr` and other variables.
3.  **Templates**: Create a template or sync from the cloud. Use `{Variable}` syntax for personalization.
4.  **Campaigns**: Create a task, choose your provider, and set a schedule.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.