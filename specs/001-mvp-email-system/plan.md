# Implementation Plan: Email Web UI MVP

**Branch**: `001-mvp-email-system` | **Date**: 2026-01-19 | **Spec**: [specs/001-mvp-email-system/spec.md](./spec.md)
**Input**: MVP for Aliyun Direct Mail Web UI for non-technical users.

## Summary

We will build a full-stack web application to simplify Aliyun Direct Mail operations. The system will allow non-technical users to manage recipients, create templates with dynamic subject lines, and schedule batch email campaigns. The system handles the complexity of API limits (batch splitting) and scheduling automatically.

## Technical Context

**Language/Version**: Python 3.10+ (Backend), Node.js 18+ (Frontend Build)
**Primary Dependencies**: 
- Backend: `fastapi`, `uvicorn`, `sqlalchemy` (ORM), `apscheduler` (Scheduling), `alibabacloud_dm20151123` (Aliyun SDK), `pandas` (CSV processing).
- Frontend: `react`, `vite`, `antd` (UI Library), `axios`.
**Storage**: SQLite (File-based, zero config).
**Testing**: `pytest` (Backend).
**Target Platform**: Linux Server / Local Machine.
**Project Type**: Web Application (Monorepo).
**Performance Goals**: Support parsing 100k+ rows CSVs; Schedule reliable batches every 15 mins.
**Constraints**: MVP focus - Speed of implementation is priority. No external heavy infra (Redis/Postgres) unless necessary.

## Constitution Check

*GATE: Must pass before Phase 0 research.*
- **Library-First**: N/A (Application focus).
- **CLI Interface**: N/A (Web UI focus, though backend is API-driven).
- **Test-First**: Will implement critical integration tests for batch logic.

## Project Structure

### Documentation (this feature)

```text
specs/001-mvp-email-system/
├── plan.md              # This file
├── spec.md              # Requirements and User Stories
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/             # API Routes
│   ├── core/            # Config & Scheduler
│   ├── models/          # DB Models (SQLAlchemy)
│   ├── services/        # Business Logic (Aliyun SDK, CSV parsing)
│   └── main.py          # Entry point
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/           # Dashboard, Campaign, Contacts, Settings
│   └── App.jsx
├── package.json
└── vite.config.js
```

**Structure Decision**: Monorepo with separated `frontend` and `backend` directories for clear separation of concerns while keeping deployment simple.
