# AI Handoff: Multi-Cloud Email Sender Project State

## 🤖 Context Overview
This project is a high-availability email marketing system for non-technical users, supporting **Aliyun DirectMail** and **Tencent Cloud SES**. 

### Stack
- **Backend**: FastAPI, SQLAlchemy (SQLite), APScheduler (In-process task queue).
- **Frontend**: React (Vite, Ant Design).
- **Persistence**: SQLite (Local file `email_app.db` locked to `os.getcwd()` for EXE stability).
- **Deployment**: Single-folder EXE (PyInstaller), Source (start.sh/bat).

## 🛠️ Accomplished Today (2026-01-22)

### 1. Tencent Cloud SES Integration (Advanced)
- **Template Mode**: Implemented Template-based sending to bypass Tencent's "Custom HTML Permission" restriction.
- **Data Mapping**: Local `vars_map` (from CSV) is serialized to JSON and passed as `TemplateData` (not `TemplateParam`).
- **Base64 Handling**: Added server-side auto-decoding for Tencent template content (HTML/Text) to ensure human-readable editing in the UI.
- **Sync Logic**: Resolved API field mismatch (Tencent returns `TemplatesMetadata` instead of `Templates`).
- **Identity Patching**: Auto-prepends `notification@` prefix if only a domain is provided as the sender address.

### 2. Scheduler & Core Engine
- **Bug Fix**: Resolved `sent_count` double-incrementing bug.
- **Variable Injection**: Enhanced `subject` line processing to support local replacement of `{var}` and `{{var}}` even in cloud template mode.
- **Persistence**: Added `localStorage` draft saving in `Campaigns.jsx` to prevent data loss on route changes.
- **Syntax/Indentation**: Fixed multi-line SQLAlchemy query `IndentationError` by wrapping calls in parentheses.

### 3. DevOps & Tooling
- **Triple-Remote Sync**: Automated pushing to GitHub, Gitee, and Internal Gitea (`192.168.2.8`).
- **CLI**: Installed and configured `tea` (Gitea CLI) on the host.

## 📂 Current Data State
- **Test CSV**: `docs/test_recipients.csv` (Contains 8 recipients with variables for both Text and HTML templates).
- **HTML Sample**: `docs/tencent_template.html` (Strictly follows Tencent SES variable and word-count guidelines).

## ⚠️ Known Issues & Technical Debt
- **Tencent Approval**: Sub-domain `qq.louisliu.fun` currently fails with `NotAuthenticatedSender` because it's pending Tencent manual review. Use `louisliu.fun` (root) for testing.
- **Concurrency**: SQLite WAL mode is not explicitly enabled; heavy concurrent uploads + scheduler runs might cause transient `Database Locked` errors.
- **UI State**: Form persistence is via `localStorage`. For production, a global state (Zustand/Redux) or server-side drafts would be more robust.

## 🔜 Next Actions for Successor
1. **Attachment Feature**: Boss requested attachment support (needs `SendRawEmail` implementation for Tencent/Aliyun).
2. **Analytics**: Implement open-tracking pixel (requires an accessible public endpoint).
3. **Template Validation**: Add a "Preview" mode in the UI that performs local variable substitution before sending.

---
**Louis Shawn AI Handoff v1.0**
