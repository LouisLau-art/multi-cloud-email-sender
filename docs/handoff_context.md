# AI Handoff Context: Email Marketing System

**Target Audience:** Future AI Agents operating on this repository.
**Date:** 2026-01-22
**Status:** Functional Prototype with Advanced Features (Dashboard, Tracking).

## 1. Project Overview
- **Type:** Full-stack Email Marketing Application (Single-file EXE capable).
- **Stack:** 
  - **Backend:** Python (FastAPI, SQLAlchemy, APScheduler, Alibabacloud SDK, Tencentcloud SDK).
  - **Frontend:** React 18 (Vite, Ant Design 5, Recharts 2). **Note:** React was explicitly downgraded from 19 to 18.2.0 to ensure Recharts compatibility.
  - **DB:** SQLite (`backend/email_app.db`).
- **Core Function:** Send bulk emails via Aliyun DirectMail and Tencent Cloud SES.

## 2. Recent Accomplishments
### 2.1. Data Dashboard & Tracking (The "Self-Hosted" Solution)
- **Architecture:** 
  - `CampaignRecipient` table tracks granular status (`sent`, `opened`, `clicked`) per email.
  - **Open Tracking:** Injects a 1x1 pixel (`<img src="{base_url}/api/track/open/{uuid}" />`) into the email body.
  - **Click Tracking:** Regex replaces `href="http..."` with `{base_url}/api/track/click/{uuid}?target=...`.
  - **Endpoints:** `backend/app/api/tracking.py` handles the requests.
  - **Scheduler:** `backend/app/core/scheduler.py` handles the injection logic during sending.
- **UI:** 
  - `Dashboard.jsx` visualizes this data with Recharts (LineChart) and Stats Cards.
  - **Export:** Supports streaming CSV export of recipient details.

### 2.2. Tracking Switches (Warning Mitigation)
- **Problem:** Self-hosted tracking links (especially HTTP IPs like `192.168.x.x`) trigger "Identity Verification" warnings in mail clients (e.g., QQ Mail).
- **Solution:** Added `track_opens` and `track_clicks` booleans to the `Campaign` model.
- **UI:** Switches added to the Campaign Creation form. Turning them OFF disables injection, removing the warning but sacrificing data.

### 2.3. Reply-To Management
- Implemented `SavedReplyTo` model and UI.
- **Aliyun:** Supports "Reply-To" via console configuration (boolean flag in API).
- **Tencent:** Supports dynamic "Reply-To" addresses via API.

## 3. Current Critical Context & Limitations
### 3.1. The "Intranet" Constraint
- The system runs on a user's local machine or intranet server (`192.168.x.x`).
- **Consequence:** We cannot use standard **Webhooks** from Aliyun/Tencent for tracking because they cannot reach the local machine.
- **Current Workaround:** We use the "Self-Hosted" tracking described in 2.1.
- **Current Issue:** The self-hosted links trigger security warnings because the domain (IP) doesn't match the sender domain.

### 3.2. Codebase Specifics
- **React Version:** STRICTLY keep React at `^18.2.0`. Do not upgrade to 19+ as it breaks `recharts` and `react-router-dom` interactions.
- **Icons:** Some Ant Design icons (like `ClickThroughOutlined`) were hallucinated in previous turns. Use standard icons (`PointerOutlined`).
- **Tencent Template Mode:** If using a synced Tencent template (with `provider_id`), we **cannot** inject tracking pixels because the HTML is rendered cloud-side. Injection only works for Local Templates or Aliyun.

## 4. Next Tasks (The Roadmap)

### Priority 1: Implement "Invisible Tracking" via Aliyun MNS
**Goal:** Get granular tracking data ("Who opened it") **without** modifying the email body (avoiding warnings).
**Concept:** Instead of self-hosted pixels, enable Aliyun's native tracking and pull logs from **Aliyun MNS (Message Service)**.

**Steps for Next AI:**
1.  **Research:** Confirm Aliyun DirectMail supports pushing "Open" and "Click" events to MNS.
2.  **Backend:** 
    - Add `mns-python-sdk` (or use `alibabacloud_mns` if available).
    - Create a background task (APScheduler) to **poll** the MNS queue periodically.
    - Parse the JSON messages from MNS.
    - Update `CampaignRecipient` status based on the message content (match by Email Address and Time, or Tag if possible).
3.  **UI:** Add MNS configuration fields to `Settings` (Queue Name, Endpoint).

### Priority 2: Improve Click Tracking Regex
- The current regex in `scheduler.py` is basic: `r'href\s*=\s*(["\'])(http[^"\']+)\1'`.
- **Risk:** It might break complex HTML or miss links with attributes between `href` and the URL.
- **Task:** Consider using `BeautifulSoup` for safer HTML manipulation if the user reports broken layouts.

### Priority 3: Tencent Cloud Pull-Tracking
- Investigate if Tencent SES has a similar "Message Queue" or "Log Pull" API for tracking events without Webhooks.

## 5. File Manifest
- `backend/app/core/scheduler.py`: **CRITICAL**. Handles sending logic and tracking injection.
- `backend/app/api/tracking.py`: Handles the pixel/redirect requests.
- `backend/app/api/dashboard.py`: Aggregates stats for the frontend.
- `frontend/src/App.jsx`: Main UI, includes Dashboard and Campaign creation.
- `backend/app/models/models.py`: Database schema.

**Good luck.** Focus on the MNS integration to solve the user's "Warning vs. Data" dilemma.
