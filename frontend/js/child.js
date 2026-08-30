// ===== 子节点逻辑 =====
let currentConversationId = null;
let currentRequirementId = null;
let allConversations = [];
let pollingTimer = null;
let isLoading = false;
let _waitingAiReply = false;   // ★ 等待AI回复标记（占位联动）

// ★ XSS防护
function escapeHtml(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

document.addEventListener('DOMContentLoaded', function() {
    if (!checkAuth()) return;
    const user = getCurrentUser();
    document.getElementById('usernameDisplay').textContent = user ? (user.username || `用户 ${user.id}`) : '用户';
    loadModelOptions();
    loadConversations();
    startPolling();
    connectWebSocket();
});

function toggleSidebar() { document.getElementById('sideSidebar').classList.toggle('collapsed'); }

// ===== AI思考占位 =====
function showThinking() {
    const c = document.getElementById('chatMessages');
    if (!c || c.querySelector('.ai-thinking')) return;
    c.insertAdjacentHTML('beforeend', `
        <div class="message ai ai-thinking">
            <span class="msg-sender">AI助手</span>
            ⏳ AI思考中…
            <span class="msg-time">刚刚</span>
        </div>`);
    scrollToBottom();
}
function hideThinking() { document.querySelector('.ai-thinking')?.remove(); }

function updateInputPlaceholder(conv) {
    const input = document.getElementById('messageInput');
    if (!input) return;
    if (!conv) { input.placeholder = '输入消息，Enter发送…'; return; }
    if (conv.requirement_id) {
        input.placeholder = '需求跟进中：直接输入补充内容，管理员会同步收到…';
    } else if (conv.mode === 'chat') {
        input.placeholder = '助手模式：自由提问…（/req 切回需求收集模式）';
    } else {
        input.placeholder = '输入消息，Enter发送…（/chat 切换助手模式，/req 切回本模式）';
    }
}

async function loadConversations() {
    try {
        const convs = await API.getConversations();
        allConversations = convs;
        renderConversationList(convs);
        if (convs.length > 0 && !currentConversationId) {
            selectConversation(convs[0].id);
        }
    } catch (e) {
        console.error('加载对话列表失败:', e);
        document.getElementById('conversationList').innerHTML = `
            <div style="text-align:center;color:#94a3b8;padding:40px 20px;">
                <div style="font-size:32px;margin-bottom:8px;">🌐</div>
                <div>无法连接服务器，请检查后端是否运行</div>
                <div style="font-size:13px;margin-top:8px;color:#cbd5e1;">点击
                    <span style="color:#2563eb;cursor:pointer;" onclick="loadConversations()">刷新</span> 重试</div>
            </div>`;
    }
}

function renderConversationList(convs) {
    const container = document.getElementById('conversationList');
    if (!convs || convs.length === 0) {
        container.innerHTML = `<div style="text-align:center;color:#94a3b8;padding:40px 20px;">
            <div style="font-size:40px;margin-bottom:12px;">📭</div><div>暂无需求，点击"新建"开始</div></div>`;
        return;
    }
    const sorted = [...convs].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
    let html = '';
    for (const conv of sorted) {
        const isActive = conv.id === currentConversationId ? 'active' : '';
        const isChat = conv.mode === 'chat';
        const savedTitle = localStorage.getItem(`conv_title_${conv.id}`);
        let title = conv.title || savedTitle || (conv.requirement_id ? `需求 #${conv.requirement_id}` : (isChat ? '助手对话' : '未命名需求'));
        const statusText = isChat ? '助手' : (conv.requirement_id ? '待处理' : '草稿');
        const statusClass = isChat ? '' : (conv.requirement_id ? 'pending' : '');
        const delBtn = conv.requirement_id ? '' :
            `<button class="btn-icon-del" type="button" title="隐藏此对话（数据保留在数据库）"
              onclick="event.stopPropagation();deleteConversation('${conv.id}')">🗑</button>`;
        html += `
        <div class="conv-item ${isActive}" data-id="${conv.id}" onclick="selectConversation('${conv.id}')">
            <div class="conv-title">
                <span>${isChat ? '🤖 ' : ''}${escapeHtml(title)}</span>
                <span class="status-badge ${statusClass}">${statusText}</span>
            </div>
            <div class="conv-preview">点击查看详情</div>
            <div class="conv-time">${formatTime(conv.updated_at)}
                ${delBtn}
                <span style="float:right;cursor:pointer;padding:4px 6px;border-radius:6px;" title="重命名"
                  onmouseover="this.style.background='#eef2f7'" onmouseout="this.style.background='transparent'"
                  onclick="event.stopPropagation();renameConversation('${conv.id}')">✏️</span></div>
        </div>`;
    }
    container.innerHTML = html;
}

async function deleteConversation(convId) {
    if (!(await showConfirm('将隐藏该对话（消息数据仍保留在数据库，不影响已提交的需求）。', { title: '隐藏对话', danger: true, okText: '隐藏' }))) return;
    try {
        await API.deleteConversation(convId);
        localStorage.removeItem(`conv_title_${convId}`);
        showToast('已隐藏（数据保留在数据库）', 'success');
        if (currentConversationId === convId) {
            currentConversationId = null;
            currentRequirementId = null;
            _waitingAiReply = false;
            hideThinking();
            document.getElementById('chatMessages').innerHTML = '<div class="empty-state">← 从左侧选择需求开始沟通</div>';
            document.getElementById('chatTitle').textContent = '请选择一个需求';
            document.getElementById('chatStatus').textContent = '';
        }
        await loadConversations();
    } catch (e) { showToast('操作失败: ' + e.message, 'error'); }
}

async function selectConversation(convId) {
    if (isLoading) return;
    _waitingAiReply = false;   // ★ 切换对话清掉上一个的等待状态
    hideThinking();
    isLoading = true;
    currentConversationId = convId;
    document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
    document.querySelector(`.conv-item[data-id="${convId}"]`)?.classList.add('active');
    try {
        const messages = await API.getMessages(convId);
        renderMessages(messages);
        const conv = allConversations.find(c => c.id === convId);
        let title = '未命名需求';
        if (conv) {
            const savedTitle = localStorage.getItem(`conv_title_${conv.id}`);
            if (savedTitle) title = savedTitle;
            else if (conv.requirement_id) title = `需求 #${conv.requirement_id}`;
            document.getElementById('chatStatus').textContent = conv.requirement_id ? '待处理' : '草稿';
            if (conv.requirement_id) {
                currentRequirementId = conv.requirement_id;
                try {
                    const req = await API.getRequirementDetail(conv.requirement_id);
                    const statusMap = { '待处理':'pending','处理中':'processing','待反馈':'waiting','已解决':'resolved' };
                    const el = document.getElementById('chatStatus');
                    el.textContent = req.status || '待处理';
                    el.className = `chat-status ${statusMap[req.status] || ''}`;
                } catch (e) {}
            } else {
                currentRequirementId = null;
            }
        }
        updateModeBadge(conv);
        updateInputPlaceholder(conv);
        document.getElementById('chatTitle').textContent = title;
        scrollToBottom();
    } catch (e) {
        console.error('加载消息失败:', e);
    } finally {
        isLoading = false;
    }
}

function renderMessages(messages) {
    const container = document.getElementById('chatMessages');
    if (!messages || messages.length === 0) {
        container.innerHTML = `<div class="empty-state">💬 开始沟通吧，AI会帮你整理需求</div>`;
        if (_waitingAiReply) showThinking();
        return;
    }
    let html = '';
    for (const msg of messages) {
        const senderMap = { 'user':'我', 'ai':'AI助手', 'admin':'管理员' };
        const attach = msg.attachment_path ? `<a href="${(window.BACKEND_ORIGIN||'')}/uploads/${encodeURIComponent(msg.attachment_path)}" download="${escapeHtml(msg.attachment_name)}" style="display:inline-block;margin-top:6px;font-size:13px;color:${msg.sender_type === 'user' ? '#dbeafe' : '#2563eb'};text-decoration:underline;">📎 ${escapeHtml(msg.attachment_name)}</a>` : '';
        html += `
        <div class="message ${msg.sender_type}">
            <span class="msg-sender">${senderMap[msg.sender_type] || escapeHtml(msg.sender_type)}</span>
            ${escapeHtml(msg.content).replace(/\n/g, '<br>')}${attach}
            <span class="msg-time">${formatTime(msg.created_at)}</span>
        </div>`;
    }
    container.innerHTML = html;
    // ★ 占位联动：等待AI期间保持"思考中"；AI回复已到则解除等待
    if (_waitingAiReply) {
        const last = messages[messages.length - 1];
        if (last && last.sender_type === 'ai') { _waitingAiReply = false; }
        else { showThinking(); }
    }
    scrollToBottom();
}

async function sendMessage() {
    if (!currentConversationId) { showToast('请先从左侧选择一个需求', 'error'); return; }
    const input = document.getElementById('messageInput');
    const content = input.value.trim();
    if (!content) return;
    // 斜杠快捷切换（与顶部徽章按钮等效）
    const cmd = content.toLowerCase();
    if (cmd === '/chat' || cmd === '/req') {
        input.value = '';
        await switchMode(cmd === '/chat' ? 'chat' : 'requirement');
        return;
    }
    input.value = '';
    const btn = document.getElementById('sendBtn');
    btn.disabled = true; btn.textContent = '发送中...';
    const container = document.getElementById('chatMessages');
    if (container.querySelector('.empty-state')) container.innerHTML = '';
    container.insertAdjacentHTML('beforeend', `
        <div class="message user">
            <span class="msg-sender">我</span>
            ${escapeHtml(content).replace(/\n/g, '<br>')}
            <span class="msg-time">刚刚</span>
        </div>`);
    scrollToBottom();
    _waitingAiReply = true;
    showThinking();   // ★ 立即出现"AI思考中"，不再是毫无反应
    try {
        await API.sendMessage(currentConversationId, content);
        await loadConversations();
        let retry = 0;
        const refreshTimer = setInterval(async () => {
            retry++;
            if (!_waitingAiReply || currentConversationId === null) { clearInterval(refreshTimer); return; }
            try {
                const messages = await API.getMessages(currentConversationId);
                const last = messages[messages.length - 1];
                if ((last && last.sender_type === 'ai') || retry >= 30) {
                    _waitingAiReply = false;
                    clearInterval(refreshTimer);
                    renderMessages(messages);
                    await loadConversationsSilent();
                }
            } catch (e) {}
        }, 1500);
    } catch (e) {
        _waitingAiReply = false;
        hideThinking();
        console.error('发送失败:', e);
        showToast('发送失败，请重试', 'error');
    } finally {
        btn.disabled = false; btn.textContent = '发送';
    }
}

async function refreshCurrentConversation() {
    if (!currentConversationId) return;
    try {
        const messages = await API.getMessages(currentConversationId);
        const container = document.getElementById('chatMessages');
        const rendered = container.querySelectorAll('.message').length;
        if (messages.length !== rendered || container.querySelector('.empty-state')) {
            renderMessages(messages);
        }
        if (currentRequirementId) {
            try {
                const req = await API.getRequirementDetail(currentRequirementId);
                document.getElementById('chatStatus').textContent = req.status || '待处理';
            } catch (e) {}
        }
    } catch (e) {
        console.error('刷新失败:', e);
    }
}

function showNewConvModal() {
    document.getElementById('newConvModal').style.display = 'flex';
    const t = document.getElementById('newConvTitle');
    if (t) { t.value = ''; t.focus(); }
}
function closeNewConvModal() { document.getElementById('newConvModal').style.display = 'none'; }

async function createNewConversation() {
    const btn = document.getElementById('createConvBtn');
    const title = document.getElementById('newConvTitle').value.trim();
    if (!title) { showToast('请输入标题再创建（不想创建就点"取消"）', 'error'); return; }
    if (btn) { btn.disabled = true; btn.textContent = '创建中...'; }
    try {
        const conv = await API.createConversation('requirement', title);
        localStorage.setItem(`conv_title_${conv.id}`, title);
        closeNewConvModal();
        await loadConversations();
        selectConversation(conv.id);
        document.getElementById('messageInput').focus();
    } catch (e) {
        showToast('创建失败: ' + (e.message || '请重试'), 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '创建'; }
    }
}

async function renameConversation(convId) {
    const conv = allConversations.find(c => c.id === convId);
    const current = (conv && conv.title) || localStorage.getItem(`conv_title_${convId}`) || '';
    const newTitle = await showPrompt('修改对话标题', current, { placeholder: '输入新标题' });
    if (newTitle === null) return;
    const t = newTitle.trim();
    if (!t) return showToast('标题不能为空', 'error');
    try {
        await API.renameConversation(convId, t);
        localStorage.setItem(`conv_title_${convId}`, t);
        await loadConversations();
        if (currentConversationId === convId) document.getElementById('chatTitle').textContent = t;
    } catch (e) { showToast('改名失败: ' + (e.message || '请重试'), 'error'); }
}

// ===== 模式徽章与切换 =====
function updateModeBadge(conv) {
    const badge = document.getElementById('modeBadge');
    if (!badge) return;
    if (!conv) { badge.style.display = 'none'; return; }
    badge.style.display = '';
    if (conv.requirement_id) {
        badge.textContent = '💬 跟进模式';
        badge.className = 'mode-badge follow';
    } else if (conv.mode === 'chat') {
        badge.textContent = '🤖 助手模式';
        badge.className = 'mode-badge chat';
    } else {
        badge.textContent = '📋 需求模式';
        badge.className = 'mode-badge';
    }
}

async function toggleMode() {
    const conv = allConversations.find(c => c.id === currentConversationId);
    if (!conv) return;
    if (conv.requirement_id) { showToast('该需求已提交，处于跟进阶段，无法切换模式', 'info'); return; }
    await switchMode(conv.mode === 'chat' ? 'requirement' : 'chat');
}

// ★ 永远原地切换，不再新建会话；隐私由后端 is_private 消息标记保障
async function switchMode(mode) {
    if (!currentConversationId) return;
    const cur = allConversations.find(c => c.id === currentConversationId);
    if (!cur) return;
    if (cur.requirement_id) { showToast('该需求已提交，处于跟进阶段，模式固定', 'info'); return; }
    if (cur.mode === mode) { showToast('当前已处于该模式', 'info'); return; }
    try {
        await API.switchMode(currentConversationId, mode);
        cur.mode = mode;
        updateModeBadge(cur);
        updateInputPlaceholder(cur);
        showToast(mode === 'chat' ? '已切换为助手模式：此后的提问管理员不可见' : '已切换为需求模式：继续描述需求，AI将帮你整理提交', 'success');
    } catch (e) { showToast('切换失败: ' + e.message, 'error'); }
}

function filterConversations() {
    const keyword = document.getElementById('searchInput').value.toLowerCase();
    document.querySelectorAll('.conv-item').forEach(item => {
        item.style.display = item.textContent.toLowerCase().includes(keyword) ? '' : 'none';
    });
}

function formatTime(isoStr) {
    if (!isoStr) return '';
    if (!/Z$|[+-]\d{2}:?\d{2}$/.test(isoStr)) { isoStr = isoStr + 'Z'; }
    const date = new Date(isoStr);
    const now = new Date();
    const diff = now - date;
    if (diff < 60000) return '刚刚';
    if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
    if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
    return date.toLocaleDateString('zh-CN') + ' ' + date.toLocaleTimeString('zh-CN', {hour:'2-digit', minute:'2-digit'});
}

function scrollToBottom() {
    const container = document.getElementById('chatMessages');
    setTimeout(() => container.scrollTop = container.scrollHeight, 50);
}

function startPolling() {
    if (pollingTimer) clearInterval(pollingTimer);
    pollingTimer = setInterval(async () => {
        if (currentConversationId && !isLoading) {
            try {
                const messages = await API.getMessages(currentConversationId);
                const container = document.getElementById('chatMessages');
                if (messages.length !== container.querySelectorAll('.message').length) renderMessages(messages);
            } catch (e) {}
        }
        await loadConversationsSilent();
    }, 15000);
}

async function loadConversationsSilent() {
    try {
        const convs = await API.getConversations();
        allConversations = convs;
        renderConversationList(convs);
    } catch (e) {}
}

function onWebSocketMessage(data) {
    if (data.type === 'new_message' && data.conversation_id === currentConversationId) refreshCurrentConversation();
    if (data.type === 'requirement_update' && data.requirement_id === currentRequirementId) refreshCurrentConversation();
    loadConversations();
}

// ===== 个人专属AI模型（自带Key，仅本人生效）=====
let myAIConfig = null;

async function loadModelOptions() {
    try {
        const [sysRes, mine] = await Promise.all([
            API.getModelsList().catch(() => ({ models: [] })),
            API.getMyAI().catch(() => null)
        ]);
        myAIConfig = mine;
        const sel = document.getElementById('modelSelect');
        if (!sel) return;
        const me = getCurrentUser();
        const sysModels = Array.isArray(sysRes) ? sysRes : ((sysRes && sysRes.models) || []);
        let html = `<option value="">系统默认模型</option>`;
        sysModels.forEach(m => {
            const name = typeof m === 'string' ? m : (m.name || '');
            if (!name) return;
            html += `<option value="${escapeHtml(name)}" ${!(myAIConfig && myAIConfig.configured) && me && me.preferred_model === name ? 'selected' : ''}>${escapeHtml(name)}</option>`;
        });
        if (myAIConfig && myAIConfig.configured) {
            html = `<option value="__personal__" selected>🌟 个人专属：${escapeHtml(myAIConfig.model)}</option>` + html;
        }
        sel.innerHTML = html;
    } catch (e) { console.error('加载模型列表失败', e); }
}

async function onModelChange(model) {
    if (model === '__personal__') return;
    if (myAIConfig && myAIConfig.configured) {
        showToast('当前已启用个人专属模型（优先生效）。如需用系统模型，请先在 ✨ 中恢复默认', 'info');
        loadModelOptions();
        return;
    }
    try {
        await API.setMyModel(model);
        const cached = getCurrentUser() || {};
        cached.preferred_model = model;
        localStorage.setItem('current_user', JSON.stringify(cached));
        showToast(model ? `已切换为系统模型 ${model}` : '已恢复系统默认', 'success');
    } catch (e) { showToast('切换失败: ' + e.message, 'error'); }
}

async function openMyAIModal() {
    document.getElementById('modelModal').style.display = 'flex';
    const status = document.getElementById('myAIStatus');
    status.innerHTML = '';
    try {
        const cfg = await API.getMyAI();
        document.getElementById('myAIProvider').value = cfg.provider || 'zhipu';
        document.getElementById('myAIKey').value = cfg.api_key || '';
        document.getElementById('myAIKey').placeholder = cfg.configured ? '已保存（重输可覆盖）' : 'sk-...';
        document.getElementById('myAIModel').value = cfg.model || '';
        document.getElementById('myAIBase').value = cfg.base_url || '';
        status.innerHTML = cfg.configured ? '<span style="color:#16a34a;">✅ 已启用个人专属模型</span>' : '<span style="color:#94a3b8;">当前使用系统默认模型</span>';
    } catch (e) {}
}

function closeMyAIModal() { document.getElementById('modelModal').style.display = 'none'; }

function fillDefaultBase() {
    const p = document.getElementById('myAIProvider').value;
    const bases = {
        zhipu: 'https://open.bigmodel.cn/api/paas/v4',
        siliconflow: 'https://api.siliconflow.cn/v1',
        deepseek: 'https://api.deepseek.com/v1',
        moonshot: 'https://api.moonshot.cn/v1',
        dashscope: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        openai: 'https://api.openai.com/v1',
        openrouter: 'https://openrouter.ai/api/v1',
        groq: 'https://api.groq.com/openai/v1',
        ollama: 'http://localhost:11434/v1',
        lmstudio: 'http://localhost:1234/v1',
        custom: ''
    };
    const hints = {
        zhipu: 'glm-4-flash / glm-4-plus',
        siliconflow: 'deepseek-ai/DeepSeek-V3 / Qwen/Qwen2.5-72B-Instruct',
        deepseek: 'deepseek-chat / deepseek-reasoner',
        moonshot: 'moonshot-v1-8k / moonshot-v1-32k',
        dashscope: 'qwen-plus / qwen-turbo / qwen-max',
        openai: 'gpt-4o-mini / gpt-4o',
        openrouter: 'openai/gpt-4o-mini / anthropic/claude-3.5-sonnet',
        groq: 'llama-3.3-70b-versatile',
        ollama: 'qwen2.5:7b / llama3.1:8b',
        lmstudio: '本地已加载的模型名',
        custom: '按你的服务商文档填写模型名'
    };
    document.getElementById('myAIBase').value = bases[p] || '';
    document.getElementById('myAIModel').placeholder = hints[p] || '';
}

async function saveMyAI() {
    const data = {
        provider: document.getElementById('myAIProvider').value,
        api_key: document.getElementById('myAIKey').value.trim(),
        model: document.getElementById('myAIModel').value.trim(),
        base_url: document.getElementById('myAIBase').value.trim()
    };
    if (!data.model) { showToast('请填写模型名称', 'error'); return; }
    try {
        await API.setMyAI(data);
        showToast('个人专属模型已保存，仅对你生效', 'success');
        await openMyAIModal();
        loadModelOptions();
    } catch (e) { showToast('保存失败: ' + e.message, 'error'); }
}

async function testMyAIConn() {
    const status = document.getElementById('myAIStatus');
    status.innerHTML = '<span style="color:#2563eb;">⏳ 正在测试连接...</span>';
    try {
        const r = await API.testMyAI({
            provider: document.getElementById('myAIProvider').value,
            api_key: document.getElementById('myAIKey').value.trim(),
            model: document.getElementById('myAIModel').value.trim(),
            base_url: document.getElementById('myAIBase').value.trim()
        });
        status.innerHTML = r.ok ? `<span style="color:#16a34a;">✅ 连接成功：${escapeHtml(r.reply)}</span>`
                                : `<span style="color:#e74c3c;">❌ ${escapeHtml(r.error)}</span>`;
    } catch (e) {
        status.innerHTML = `<span style="color:#e74c3c;">❌ ${escapeHtml(e.message)}</span>`;
    }
}

async function resetMyAI() {
    try {
        await API.resetMyAI();
        showToast('已恢复系统默认模型', 'success');
        closeMyAIModal();
        loadModelOptions();
    } catch (e) { showToast('操作失败: ' + e.message, 'error'); }
}

// ===== 附件上传 =====
async function uploadFile(input) {
    const file = input.files[0];
    input.value = '';
    if (!file) return;
    if (!currentConversationId) return showToast('请先选择一个对话', 'error');
    showToast('上传中...', 'info');
    try {
        await API.uploadMessageFile(currentConversationId, file);
        await refreshCurrentConversation();
        showToast('文件已发送，AI将阅读其内容', 'success');
    } catch (e) { showToast('上传失败: ' + e.message, 'error'); }
}

window.addEventListener('beforeunload', function() {
    if (pollingTimer) clearInterval(pollingTimer);
    disconnectWebSocket();
});
