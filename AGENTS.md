# Agentic Coding Guidelines for Email Marketing System

This repository contains a full-stack email marketing application designed for high availability and portability (single-file EXE).

## 1. Development & Build Commands

### Backend (Python/FastAPI)
- **Install Dependencies:** `pip install -r backend/requirements.txt`
- **Start Development Server:** `python backend/app/main.py` (starts uvicorn on 0.0.0.0:8000)
- **Run All Tests:** `pytest` (Run from project root or `backend/` directory)
- **Run Single Test:** `pytest backend/tests/test_core.py::test_settings_update_multicloud`
- **Linting:** Standard PEP8 is preferred.

### Frontend (React/Vite)
- **Install Dependencies:** `npm install` (within `frontend/` directory)
- **Start Development Server:** `npm run dev`
- **Build for Production:** `npm run build`
- **Run All Tests:** `npm run test` (uses Vitest)
- **Run Single Test:** `npx vitest run src/App.test.jsx`
- **Linting:** `npm run lint` (uses ESLint)

### Packaging (PyInstaller)
- **Linux Build:** `./build_linux.sh`
- **Windows Build:** `build_windows.bat` (Note: Uses a virtual environment to ensure stability)

---

## 2. Code Style Guidelines

### Backend (Python)
- **Framework:** FastAPI, Pydantic, SQLAlchemy, APScheduler.
- **Database:** SQLite (`email_app.db`).
  - **Crucial:** The DB path is locked to `os.getcwd()` to ensure the EXE can find it in the working directory, not the temporary `_MEIPASS` directory.
- **Naming:** `snake_case` for variables/functions, `PascalCase` for Classes/Models.
- **Async:** Use `async def` for I/O bound routes (uploading, querying APIs).
- **Service Layer:** Cloud providers (Aliyun/Tencent) are isolated in `backend/app/services/`.

### Frontend (React)
- **Stack:** React 19, Vite, Ant Design, Axios.
- **State:** 
  - Local state (`useState`) is preferred.
  - **Drafts:** Complex forms (like Campaign creation) use `localStorage` to prevent data loss on navigation.
- **Routing:** React Router 7.
- **UI/UX:** Ant Design components. Visual consistency is key.

---

## 3. Critical Architecture Context

### Cloud Provider Integration
- **Aliyun DirectMail:** Uses standard API.
- **Tencent Cloud SES:**
  - **Template Mode:** We use "Template Mode" to bypass custom HTML restrictions.
  - **Data Mapping:** Local variables mapped from CSV are serialized to JSON and passed as `TemplateData`.
  - **Encoding:** Cloud templates are Base64 decoded server-side to ensure they are human-readable in the UI.

### Variable Substitution
- **Format:** The system supports `{UserName}` style placeholders.
- **Behavior:** 
  - **Subject:** Variables replaced locally. **Important:** Unmatched variables like `{CompanyName}` are stripped of braces (e.g., becomes `CompanyName`) to support "literal" usage in templates.
  - **Body (Tencent HTML/Aliyun):** Variables replaced locally. Unmatched variables are also stripped of braces if they look like variables (alphanumeric/Chinese), preserving CSS/JS syntax.
  - **Body (Tencent Template):** Variables replaced by cloud provider using `TemplateData`.

### Scheduler
- **APScheduler:** Runs in-process. 
- **Concurrency:** Be aware that SQLite WAL mode is not explicitly enabled; heavy concurrent writes might cause locking.

---

## 4. Known Issues & Workarounds
- **Tencent Domains:** Sub-domains (e.g., `qq.louisliu.fun`) may fail with `NotAuthenticatedSender` if pending review. Use the root domain for testing.
- **Windows Permissions:** The database file is generated in the program's root directory to avoid permission issues in system folders.
- **CSV Handling:** The CSV parser handles BOM and supports arbitrary columns (treated as variables).

## 5. Deployment
- **Static Files:** The backend serves the `frontend/dist` folder.
- **Frozen Mode:** The app detects if it's running as a script or Frozen EXE (`sys.frozen`) and adjusts static file paths accordingly.

## 6. Roadmap (Upcoming Tasks)
1. **Attachments:** Implement `SendRawEmail` support for both providers to handle attachments.
2. **Analytics:** Add open-tracking pixels.
3. **Template Preview:** Add a UI feature to preview variable substitution before sending.
