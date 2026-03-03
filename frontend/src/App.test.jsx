import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock API
vi.mock('./services/api', () => ({
  authApi: {
    status: vi.fn(() => Promise.resolve({ data: { authenticated: true, bootstrap_required: false } })),
    bootstrap: vi.fn(() => Promise.resolve({ data: { status: 'ok' } })),
    login: vi.fn(() => Promise.resolve({ data: { status: 'ok' } })),
    logout: vi.fn(() => Promise.resolve({ data: { status: 'ok' } })),
  },
  contactApi: {
    upload: vi.fn(() => Promise.resolve({ data: { id: 1, count: 0 } })),
    getAll: vi.fn(() => Promise.resolve({ data: [] })),
  },
  settingsApi: {
    get: vi.fn(() => Promise.resolve({ data: { track_domain: '', from_alias: '' } })),
    update: vi.fn(() => Promise.resolve({ data: {} })),
    getReplyTos: vi.fn(() => Promise.resolve({ data: [] })),
    addReplyTo: vi.fn(() => Promise.resolve({ data: { address: 'a@b.com' } })),
  },
  dashboardApi: {
    getStats: vi.fn(() => Promise.resolve({ data: { total_recipients: 0, sent_count: 0, delivered_count: 0, opened_count: 0, clicked_count: 0, delivery_rate: 0, open_rate: 0, click_rate: 0 } })),
    getChartData: vi.fn(() => Promise.resolve({ data: [] })),
    getCampaigns: vi.fn(() => Promise.resolve({ data: [] })),
    getDetails: vi.fn(() => Promise.resolve({ data: { items: [], total: 0, page: 1, size: 10 } })),
  },
  accountApi: {
    getAll: vi.fn(() => Promise.resolve({ data: [] })),
    create: vi.fn(() => Promise.resolve({ data: {} })),
    update: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
  default: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
    create: vi.fn(() => ({
      get: vi.fn(),
      post: vi.fn(),
    })),
  },
}));

// Mock matchMedia for Ant Design
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders menu items', async () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    );
    
    expect(await screen.findByText(/邮件推送系统/i)).toBeInTheDocument();
    expect(screen.getByText(/数据看板/i)).toBeInTheDocument();
    expect(screen.getByText(/发信任务/i)).toBeInTheDocument();
    expect(screen.getByText(/联系人管理/i)).toBeInTheDocument();
  });

  it('renders dashboard shell', async () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    );
    expect(await screen.findByText(/详细数据/i)).toBeInTheDocument();
  });
});
