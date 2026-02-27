import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import api from './services/api';

// Mock API
vi.mock('./services/api', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
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
    
    expect(screen.getByText(/邮件推送系统/i)).toBeInTheDocument();
    // Use waitFor to handle async rendering if needed, though menu is static
    expect(screen.getByText(/邮件任务/i)).toBeInTheDocument();
    expect(screen.getByText(/联系人管理/i)).toBeInTheDocument();
  });

  it('renders campaign form fields', async () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    );
    // 等待异步组件加载（如果需要），这里主要是检查静态文本
    // 检查新加的字段 Label
    expect(await screen.findByText(/计划开始时间/i)).toBeInTheDocument();
    expect(await screen.findByText(/本次任务昵称/i)).toBeInTheDocument();
  });
});
