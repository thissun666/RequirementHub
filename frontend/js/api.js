// API 基础配置
// ===== 后端地址解析（兼容三种打开方式：后端托管/file://双击/8080静态服务）=====
const API_BASE = (() => {
    const override = localStorage.getItem('api_base');
    if (override) return override.replace(/\/+$/, '') + '/api';
    if (location.protocol === 'file:') return 'http://localhost:8000/api';
    if (location.port === '8000') return window.location.origin + '/api';
    return 'http://' + (location.hostname || 'localhost') + ':8000/api';
})();
const BACKEND_ORIGIN = API_BASE.replace(/\/api$/, '');

// 通用请求函数
async function request(endpoint, method = 'GET', data = null, token = null) {
    const url = `${API_BASE}${endpoint}`;
    const headers = {
        'Content-Type': 'application/json',
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    const config = {
        method,
        headers,
        body: data ? JSON.stringify(data) : null,
    };
    const response = await fetch(url, config);
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `请求失败 (${response.status})`);
    }
    return response.json();
}

// 带 token 的请求
function authRequest(endpoint, method = 'GET', data = null) {
    const token = localStorage.getItem('access_token');
    return request(endpoint, method, data, token);
}

// 登录
async function login(username, password) {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData,
    });
    if (!response.ok) {
        throw new Error('登录失败');
    }
    const data = await response.json();
    if (data.access_token) {
        localStorage.setItem('access_token', data.access_token);
        const payload = parseJwt(data.access_token);
        if (payload) {
            localStorage.setItem('user_role', payload.role || 'user');
                        // 拉取并缓存完整用户信息（含用户名）
            try {
                const me = await authRequest('/auth/me');
                localStorage.setItem('current_user', JSON.stringify(me));
            } catch (e) { /* 失败则退回JWT解析 */ }

            localStorage.setItem('user_id', payload.sub);
        }
        return data;
    }
    return null;
}

// 解析 JWT
function parseJwt(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(c => {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch (e) {
        return null;
    }
}

// 获取当前用户信息
function getCurrentUser() {
    const cached = localStorage.getItem('current_user');
    if (cached) { try { return JSON.parse(cached); } catch (e) {} }
    const token = localStorage.getItem('access_token');
    if (!token) return null;
    const payload = parseJwt(token);
    if (!payload) return null;
    return { id: parseInt(payload.sub), role: payload.role };
}


// 登出
function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('user_id');
    localStorage.removeItem('current_user');

    if (typeof disconnectWebSocket === 'function') {
        disconnectWebSocket();
    }
    window.location.href = 'login.html';
}

// API 对象
const API = {
    // 用户管理
    getUsers: () => authRequest('/admin/users/'),
    createUser: (data) => authRequest('/admin/users/', 'POST', data),
    updateUser: (id, data) => authRequest(`/admin/users/${id}`, 'PUT', data),
    deleteUser: (id) => authRequest(`/admin/users/${id}`, 'DELETE'),

    // 职位管理
    getPositions: () => authRequest('/admin/positions/'),

    // 对话
    createConversation: (mode = 'requirement', title = '未命名需求') =>
    authRequest(`/conversations/?mode=${encodeURIComponent(mode)}&title=${encodeURIComponent(title)}`, 'POST'),
renameConversation: (id, title) => authRequest(`/conversations/${id}/title`, 'PUT', { title }),
    deleteConversation: (id) => authRequest(`/conversations/${id}`, 'DELETE'),

switchMode: (id, mode) => authRequest(`/conversations/${id}/mode`, 'PUT', { mode }),
getModelsList: () => authRequest('/settings/models'),
setMyModel: (model) => authRequest('/auth/me/model', 'PUT', { model }),
    getMyAI: () => authRequest('/my-ai', 'GET'),
    setMyAI: (data) => authRequest('/my-ai', 'PUT', data),
    testMyAI: (data) => authRequest('/my-ai/test', 'POST', data),
    resetMyAI: () => authRequest('/my-ai', 'DELETE'),

uploadMessageFile: (convId, file) => {
    const fd = new FormData(); fd.append('file', file);
    const token = localStorage.getItem('access_token');
    return fetch(`${API_BASE}/conversations/${convId}/upload`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fd,
    }).then(async r => {
        if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || '上传失败'); }
        return r.json();
    });
},
askKnowledge: (question) => authRequest('/knowledge/ask', 'POST', { question }),
getKnowledgeDocs: () => authRequest('/knowledge/'),
addKnowledgeText: (title, content) => authRequest('/knowledge/text', 'POST', { title, content }),
uploadKnowledgeDoc: (file) => {
    const fd = new FormData(); fd.append('file', file);
    const token = localStorage.getItem('access_token');
    return fetch(`${API_BASE}/knowledge/upload`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fd,
    }).then(async r => {
        if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || '上传失败'); }
        return r.json();
    });
},
deleteKnowledgeDoc: (docId) => authRequest(`/knowledge/doc/${docId}`, 'DELETE'),

getConversations: () => authRequest('/conversations/'),

    getMessages: (convId) => authRequest(`/conversations/${convId}/messages`),
    sendMessage: (convId, content) => authRequest(`/conversations/${convId}/messages`, 'POST', { content }),

    // 需求
       getRequirements: (params = {}) => {
        const query = new URLSearchParams(params).toString();
        return authRequest(`/requirements/?${query}`);
    },

    getRequirementDetail: (id) => authRequest(`/requirements/${id}`),
    replyRequirement: (id, content) => authRequest(`/requirements/${id}/reply`, 'POST', { content }),
    resolveRequirement: (id, result, solution, remark = '') => 
        authRequest(`/requirements/${id}/resolve`, 'POST', { result, solution, remark }),
    updateRequirementStatus: (id, status) => 
        authRequest(`/requirements/${id}/status`, 'PUT', { status }),

    // 报告
    getReport: (start, end) => authRequest(`/reports?start_date=${start}&end_date=${end}`),
    getWeeklyReport: () => authRequest('/reports/weekly'),
    getMonthlyReport: () => authRequest('/reports/monthly'),

    // 设置
    getModelSettings: () => authRequest('/settings/model'),
    updateModelSettings: (data) => authRequest('/settings/model', 'POST', data),
};