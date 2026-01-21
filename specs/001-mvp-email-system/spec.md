# Feature Specification: Email Web UI MVP

**Feature Branch**: `001-mvp-email-system`
**Created**: 2026-01-19
**Status**: Draft
**Input**: User request for Aliyun Direct Mail GUI wrapper.

## User Scenarios & Testing

### User Story 1 - System Configuration (Priority: P1)
As an administrator, I need to input my Aliyun Access Key ID and Secret so that the system can communicate with the email service.

**Why this priority**: Without credentials, the system cannot function.
**Independent Test**: API endpoint `/api/config` accepts keys, validates them against Aliyun `DescAccountSummary` API, and returns success.
**Acceptance Scenarios**:
1. **Given** valid keys, **When** I save settings, **Then** system connects and shows "Connected".
2. **Given** invalid keys, **When** I save settings, **Then** system shows specific error from Aliyun.

### User Story 2 - Recipient Management (Priority: P1)
As a user, I need to upload a CSV file with thousands of contacts so that I can send emails to them without manual entry.

**Why this priority**: Bulk sending is the primary use case.
**Independent Test**: Upload a CSV with 15,000 rows. Backend parses it, creates a "Contact List" entity, and splits it internally into 2 batches of 7,500 (or similar logic) in the database.
**Acceptance Scenarios**:
1. **Given** a CSV with headers `email, name`, **When** uploaded, **Then** a Contact List is created with correct count.

### User Story 3 - Template Management (Priority: P1)
As a user, I need to create email templates where the Subject Line can contain variables (e.g., "Hello ${name}") so recipients feel the email is personalized.

**Why this priority**: Key user pain point (Aliyun Console limitations).
**Independent Test**: Create a template via UI. Backend saves it.
**Acceptance Scenarios**:
1. **Given** a template text with `${name}`, **When** saved, **Then** it is stored in DB.

### User Story 4 - Campaign Scheduling (Priority: P1)
As a user, I need to select a Template and a Contact List to start a sending campaign that automatically spaces out batches.

**Why this priority**: To avoid hitting rate limits and ensure deliverability.
**Independent Test**: Create a campaign. Trigger the scheduler. Verify that `BatchSendMail` is called for the first chunk, and subsequent chunks are queued.
**Acceptance Scenarios**:
1. **Given** a list of 20,000 users and a template, **When** "Start" is clicked, **Then** system schedules multiple API calls over time (e.g., every 15 mins).

## Requirements

### Functional Requirements
- **FR-001**: System MUST store Aliyun Credentials securely (local DB for MVP).
- **FR-002**: System MUST parse CSV/TXT files and extract standard fields (email, name).
- **FR-003**: System MUST allow defining variables in Subject lines and Body.
- **FR-004**: System MUST strictly adhere to Aliyun `BatchSendMail` limits (max 10k per call).
- **FR-005**: System MUST provide a "Stop" button to cancel pending batches.

### Key Entities
- **Settings**: Stores AccessKey, Secret, FromAlias.
- **ContactList**: Metadata about an uploaded file.
- **Contact**: Individual recipient (email, name, arbitrary vars).
- **Template**: Subject, Body, Aliyun Template ID (optional/if synced).
- **Campaign**: Links Template + ContactList + Status + Progress.

## Success Criteria

### Measurable Outcomes
- **SC-001**: Non-technical user can send a batch of 100 emails within 5 minutes of opening the app.
- **SC-002**: System successfully handles a file with 10,000 rows without crashing.
- **SC-003**: Emails arrive with correct variable replacement in the Subject line.
