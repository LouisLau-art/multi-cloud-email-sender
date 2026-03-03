import axios from 'axios';

// Determine Base URL
// If running on port 5173 (Vite Dev Server), point to backend at port 8000 on the same host
// If running on port 8000 (Served by FastAPI), use relative path
const isDev = window.location.port === '5173';
const envBaseUrl = import.meta.env.VITE_API_BASE_URL;
const API_BASE_URL = isDev 
    ? (envBaseUrl || `http://${window.location.hostname}:8000/api`)
    : '/api';

console.log(`API Base URL: ${API_BASE_URL}`);

const api = axios.create({
    baseURL: API_BASE_URL,
    withCredentials: true,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const authApi = {
    status: () => api.get('/auth/status'),
    bootstrap: (password) => api.post('/auth/bootstrap', { password }),
    login: (password) => api.post('/auth/login', { password }),
    logout: () => api.post('/auth/logout'),
};

export const campaignApi = {
    getAll: () => api.get('/campaigns'),
    create: (data) => api.post('/campaigns', data),
    get: (id) => api.get(`/campaigns/${id}`),
    pause: (id) => api.post(`/campaigns/${id}/stop`),
    resume: (id) => api.post(`/campaigns/${id}/start`),
};

export const contactApi = {
    getAll: () => api.get('/contacts'),
    upload: (file, listName) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('list_name', listName || file.name); // 必填：列表名称，默认使用文件名
        return api.post('/contacts/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
    },
    delete: (id) => api.delete(`/contacts/${id}`),
};

export const templateApi = {
    getAll: () => api.get('/templates'),
    create: (data) => api.post('/templates', data),
    update: (id, data) => api.put(`/templates/${id}`, data),
    delete: (id) => api.delete(`/templates/${id}`),
    syncAliyun: (accessKeyId, accessKeySecret) => api.post('/templates/sync/aliyun', { accessKeyId, accessKeySecret }),
    syncTencent: (secretId, secretKey) => api.post('/templates/sync/tencent', { secretId, secretKey }),
    importTemplate: (provider, templateId) => api.post('/templates/import', { provider, template_id: templateId }),
};

export const settingsApi = {
    get: () => api.get('/settings'),
    update: (data) => api.post('/settings', data),
    testAliyun: () => api.post('/settings/test/aliyun'),
    testTencent: () => api.post('/settings/test/tencent'),
    getReplyTos: () => api.get('/settings/reply_tos'),
    addReplyTo: (address) => api.post('/settings/reply_tos', { address }),
};

export const accountApi = {
    getAll: (provider) => api.get('/accounts', { params: provider ? { provider } : {} }),
    create: (data) => api.post('/accounts', data),
    update: (id, data) => api.put(`/accounts/${id}`, data),
    delete: (id) => api.delete(`/accounts/${id}`),
};

export const dashboardApi = {
    getStats: (campaignId) => api.get('/dashboard/stats', { params: { campaign_id: campaignId } }),
    getChartData: (days, campaignId) => api.get('/dashboard/chart', { params: { days, campaign_id: campaignId } }),
    getCampaigns: () => api.get('/dashboard/campaigns'),
    getDetails: (page, size, search, status, campaignId, startTime, endTime) =>
        api.get('/dashboard/details', {
            params: {
                page,
                size,
                search,
                status,
                campaign_id: campaignId,
                start_time: startTime,
                end_time: endTime,
            },
        }),
};

export default api;
