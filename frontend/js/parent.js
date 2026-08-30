// ===== 父节点主逻辑 =====
let currentSubTab = 'assistant';
let currentRequirementId = null;
let allPositions = [];
let pollingTimer = null;
let newReqBadge = 0;
const NOTICE_KEY = 'parent_notices_v1';

// ★ XSS防护：所有用户输入渲染前必须过这个函数
function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

document.addEventListener('DOMContentLoaded', function() {
    if (!checkAuth()) return;
    document.getElementById('usernameDisplay').textContent = '管理员';
    loadRequirements();
    loadUsers();
    loadSettings();
    loadPositions();
    connectWebSocket();
    startPolling();
    renderStoredNotices();

    const input = document.getElementById('assistantInput');
    if (input) {
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); askAssistant(); }
        });
    }

    const form = document.getElementById('userForm');
    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            const userId = document.getElementById('editUserId').value;
            const username = document.getElementById('formUsername').value.trim();
            const password = document.getElementById('formPassword').value.trim();
            const department = document.getElementById('formDepartment').value.trim();
            const position = document.getElementById('formPosition').value.trim();
            if (!username) return showToast('请输入用户名', 'error');
            if (!userId && !password) return showToast('请输入密码', 'error');
            try {
                if (userId) {
                    const data = { username };
                    if (password) data.password = password;
                    if (department) data.department = department;
                    if (position) data.position = position;
                    await API.updateUser(parseInt(userId), data);
                } else {
                    await API.createUser({ username, password, department, position, role: 'user' });
                }
                showToast(userId ? '更新成功' : '添加成功', 'success');
                closeModal();
                loadUsers();
                loadPositions();
            } catch (e) {
                showToast('操作失败: ' + e.message, 'error');
            }
        });
    }
});

// ===== 提醒持久化 =====
function readNotices() {
    try { return JSON.parse(localStorage.getItem(NOTICE_KEY) || '[]'); } catch (e) { return []; }
}
function writeNotices(arr) {
    try { localStorage.setItem(NOTICE_KEY, JSON.stringify(arr.slice(0, 30))); } catch (e) {}
}
function saveNotice(n) {
    const arr = readNotices();
    const id = `nt_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    arr.unshift({ ...n, _id: id, _ts: Date.now() });
    writeNotices(arr);
    return id;
}
function removeNoticeFromStore(id) { writeNotices(readNotices().filter(n => n._id !== id)); }
function renderStoredNotices() {
    const fresh = readNotices().filter(n => Date.now() - (n._ts || 0) < 24 * 3600 * 1000);
    fresh.forEach(n => {
        if (n.type === 'new_requirement') appendNewRequirementCard(n, n._id);
        else appendFollowUpCard(n, n._id);
    });
    newReqBadge = fresh.length;
    updateTaskBadge();
}
function dismissNotice(noticeId) {
    removeNoticeFromStore(noticeId);
    const el = document.getElementById(noticeId);
    if (el) el.remove();
    newReqBadge = Math.max(0, newReqBadge - 1);
    updateTaskBadge();
}

// ===== Tab切换 =====
function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.menu-item').forEach(el => el.classList.remove('active'));
    document.getElementById(`tab-${tabId}`).classList.add('active');
    document.querySelector(`.menu-item[data-tab="${tabId}"]`).classList.add('active');
    if (tabId === 'tasks') switchSubTab(currentSubTab);
    if (tabId === 'reports') loadReport();
    if (tabId === 'users') loadUsers();
    if (tabId === 'knowledge') loadKnowledge();
}
function switchSubTab(subId) {
    currentSubTab = subId;
    document.querySelectorAll('.sub-tab').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.sub-content').forEach(el => el.classList.remove('active'));
    document.querySelector(`.sub-tab[data-sub="${subId}"]`).classList.add('active');
    document.getElementById(`sub-${subId}`).classList.add('active');
    if (subId === 'list') loadRequirements();
    if (subId === 'assistant') { newReqBadge = 0; updateTaskBadge(); }
}
function toggleSidebar() {
    const menu = document.getElementById('sideMenu');
    menu.classList.toggle('collapsed');
    menu.querySelector('.toggle-sidebar').textContent = menu.classList.contains('collapsed') ? '▶' : '◀';
}

// ===== 需求列表 =====
async function loadRequirements() {
    const container = document.getElementById('requirementList');
    const status = document.getElementById('filterStatus').value;
    const priority = document.getElementById('filterPriority').value;
    try {
        const params = {};
        if (status) params.status = status;
        if (priority) params.priority = priority;
        const reqs = await API.getRequirements(params);
        window._reqsCache = reqs;
        if (!reqs || reqs.length === 0) {
            container.innerHTML = `<div style="text-align:center;color:#94a3b8;padding:40px;">暂无需求</div>`;
            return;
        }
        const statusMap = { '待处理':'pending','处理中':'processing','待反馈':'waiting','已解决':'resolved' };
        let html = '';
        for (const req of reqs) {
            const pClass = req.priority === '高' ? 'priority-high' : req.priority === '中' ? 'priority-medium' : 'priority-low';
            const uname = escapeHtml(req.username || ('用户 #' + req.user_id));
            const dept = req.department ? ' · ' + escapeHtml(req.department) : '';
            html += `
            <div class="req-item" onclick="showRequirementDetail(${req.id})">
                <div class="req-info">
                    <div class="req-title">${escapeHtml(req.title)}</div>
                    <div class="req-meta">
                        <span>👤 ${uname}${dept}</span>
                        <span class="${pClass}">${escapeHtml(req.priority)}</span>
                        <span class="status-tag ${statusMap[req.status] || ''}">${escapeHtml(req.status)}</span>
                        <span>🕐 ${formatTime(req.updated_at)}</span>
                    </div>
                </div>
                <div class="req-actions">
                    <button class="btn-primary" onclick="event.stopPropagation();showRequirementDetail(${req.id})">查看</button>
                </div>
            </div>`;
        }
        container.innerHTML = html;
    } catch (e) {
        console.error('加载需求失败:', e);
        container.innerHTML = `<div style="text-align:center;color:#e74c3c;padding:40px;">加载失败: ${escapeHtml(e.message)}</div>`;
    }
}

// ===== 需求详情弹窗 =====
async function showRequirementDetail(reqId) {
    currentRequirementId = reqId;
    const cached = (window._reqsCache || []).find(r => r.id === reqId);
    const submitter = cached ? `${escapeHtml(cached.username || '')}${cached.department ? ' · ' + escapeHtml(cached.department) : ''}` : ('用户 #' + reqId);
    const modal = document.getElementById('requirementModal');
    const body = document.getElementById('reqDetailBody');
    modal.style.display = 'flex';
    body.innerHTML = '<div style="text-align:center;color:#94a3b8;padding:20px;">加载中...</div>';
    try {
        const req = await API.getRequirementDetail(reqId);
        window._detailConvId = req.conversation_id || null;
        document.getElementById('reqModalTitle').textContent = req.title;
        const pClass = req.priority === '高' ? 'priority-high' : req.priority === '中' ? 'priority-medium' : 'priority-low';
        const visibleMsgs = (req.messages || []).filter(m => !m.is_private);
        let html = `
        <div style="margin-bottom:16px;">
            <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px;font-size:13px;color:#475569;">
                <span><strong>状态:</strong> ${escapeHtml(req.status)}</span>
                <span><strong>优先级:</strong> <span class="${pClass}">${escapeHtml(req.priority)}</span></span>
                <span><strong>提交人:</strong> ${submitter}</span>
                <span><strong>创建:</strong> ${formatTime(req.created_at)}</span>
            </div>
            <div style="background:#f8fafc;padding:12px 16px;border-radius:8px;margin-bottom:12px;">
                <strong>需求描述:</strong>
                <p style="margin-top:6px;white-space:pre-wrap;">${escapeHtml(req.description)}</p>
            </div>
            ${req.solution ? `<div style="background:#d1fae5;padding:12px 16px;border-radius:8px;margin-bottom:12px;">
                <strong>✅ 解决方案:</strong> <p style="margin-top:6px;white-space:pre-wrap;">${escapeHtml(req.solution)}</p></div>` : ''}
        </div>
        <div style="border-top:1px solid #e8ecf1;padding-top:12px;margin-bottom:12px;">
            <strong>💬 沟通记录 (${visibleMsgs.length}条)</strong>
            <div style="max-height:200px;overflow-y:auto;margin-top:8px;">`;
        if (visibleMsgs.length > 0) {
            const senderMap = { 'user':'子节点','ai':'AI','admin':'管理员' };
            for (const msg of visibleMsgs) {
                const attach = msg.attachment_path
                    ? `<a href="${(window.BACKEND_ORIGIN||'')}/uploads/${encodeURIComponent(msg.attachment_path)}" download="${escapeHtml(msg.attachment_name)}" style="color:#2563eb;margin-left:6px;">📎 ${escapeHtml(msg.attachment_name)}</a>` : '';
                html += `
                <div style="padding:6px 0;border-bottom:1px solid #f1f5f9;font-size:13px;">
                    <strong>${senderMap[msg.sender_type] || escapeHtml(msg.sender_type)}:</strong>
                    <span style="color:#475569;">${escapeHtml(msg.content)}</span>${attach}
                    <span style="color:#94a3b8;font-size:11px;margin-left:8px;">${formatTime(msg.created_at)}</span>
                </div>`;
            }
        } else {
            html += `<div style="color:#94a3b8;padding:8px 0;">暂无消息</div>`;
        }
        html += `</div></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start;border-top:1px solid #e8ecf1;padding-top:16px;">
            <textarea id="replyContent" rows="2" placeholder="回复子节点..." style="flex:1;padding:8px 12px;border:1px solid #e2e8f0;border-radius:8px;resize:vertical;font-family:inherit;font-size:14px;min-width:200px;"></textarea>
            <div style="display:flex;flex-direction:column;gap:8px;">
                <button class="btn-primary" onclick="replyRequirement()">回复</button>
                ${window._detailConvId ? `<input type="file" id="adminAttachInput" accept=".txt,.md,.docx" style="display:none;" onchange="uploadDetailAttachment(this)">
                <button class="btn-secondary" onclick="document.getElementById('adminAttachInput').click()" title="发送文件给该子节点（AI也会读取）">📎 附件</button>` : ''}
            </div>
            <div style="display:flex;flex-direction:column;gap:8px;">
                ${req.status !== '已解决' ? `<button class="btn-primary" onclick="showResolveForm()" style="background:#22c55e;">标记解决</button>` : ''}
                <button class="btn-secondary" onclick="closeRequirementModal()">关闭</button>
            </div>
        </div>`;
        body.innerHTML = html;
    } catch (e) {
        console.error('加载详情失败:', e);
        body.innerHTML = `<div style="color:#e74c3c;padding:20px;">加载失败: ${escapeHtml(e.message)}</div>`;
    }
}
async function uploadDetailAttachment(input) {
    const f = input.files[0];
    input.value = '';
    if (!f || !window._detailConvId) return;
    showToast('上传中...', 'info');
    try {
        await API.uploadMessageFile(window._detailConvId, f);
        showToast('附件已发送', 'success');
        showRequirementDetail(currentRequirementId);
    } catch (e) { showToast('上传失败: ' + e.message, 'error'); }
}
async function replyRequirement() {
    const content = document.getElementById('replyContent').value.trim();
    if (!content) return showToast('请输入回复内容', 'error');
    if (!currentRequirementId) return;
    try {
        await API.replyRequirement(currentRequirementId, content);
        document.getElementById('replyContent').value = '';
        showToast('回复已发送', 'success');
        showRequirementDetail(currentRequirementId);
        loadRequirements();
    } catch (e) { showToast('回复失败: ' + e.message, 'error'); }
}
function showResolveForm() {
    document.getElementById('reqDetailBody').insertAdjacentHTML('beforeend', `
    <div style="background:#f8fafc;padding:16px;border-radius:8px;margin:8px 0;">
        <h4 style="margin-bottom:12px;">📌 标记解决</h4>
        <div class="form-group"><label>处理结果</label>
            <select id="resolveResult">
                <option value="已解决">✅ 已解决</option>
                <option value="部分解决">⚠️ 部分解决（需继续跟进）</option>
                <option value="暂无法解决">❌ 暂无法解决</option>
            </select></div>
        <div class="form-group"><label>解决方案描述 <span style="color:#e74c3c;">*</span></label>
            <textarea id="resolveSolution" rows="3" placeholder="详细说明如何解决的..."></textarea></div>
        <div class="form-group"><label>备注（可选）</label><input type="text" id="resolveRemark" placeholder="补充说明"></div>
        <div style="display:flex;gap:10px;">
            <button class="btn-primary" onclick="submitResolve()" style="background:#22c55e;">提交解决</button>
            <button class="btn-secondary" onclick="showRequirementDetail(currentRequirementId)">取消</button>
        </div>
    </div>`);
}
async function submitResolve() {
    const result = document.getElementById('resolveResult').value;
    const solution = document.getElementById('resolveSolution').value.trim();
    const remark = document.getElementById('resolveRemark').value.trim();
    if (!solution) return showToast('请填写解决方案描述', 'error');
    if (!currentRequirementId) return;
    try {
        await API.resolveRequirement(currentRequirementId, result, solution, remark);
        showToast('解决反馈已提交，已通知子节点', 'success');
        showRequirementDetail(currentRequirementId);
        loadRequirements();
    } catch (e) { showToast('提交失败: ' + e.message, 'error'); }
}
function closeRequirementModal() {
    document.getElementById('requirementModal').style.display = 'none';
    currentRequirementId = null;
}

// ===== AI助手 =====
async function askAssistant(query) {
    const input = document.getElementById('assistantInput');
    const question = (query || input.value).trim();
    if (!question) return;
    input.value = '';
    const container = document.getElementById('assistantMessages');
    const welcome = container.querySelector('.assistant-welcome');
    if (welcome) welcome.remove();
    container.insertAdjacentHTML('beforeend', `
    <div class="message user">
        <div class="avatar">👤</div>
        <div class="bubble"><span class="msg-sender">我</span> ${escapeHtml(question).replace(/\n/g, '<br>')} <span class="msg-time">${formatTime(new Date().toISOString())}</span></div>
    </div>`);
    const loadingId = 'loading_' + Date.now();
    container.insertAdjacentHTML('beforeend', `
    <div class="message ai" id="${loadingId}">
        <div class="avatar">🤖</div>
        <div class="bubble"><span class="msg-sender">AI助手</span><span>⏳ 检索知识库并思考中...</span></div>
    </div>`);
    scrollToBottom('assistantMessages');
    try {
        const res = await API.askKnowledge(question);
        const el = document.getElementById(loadingId);
        if (el) {
            el.querySelector('.bubble').innerHTML = `<span class="msg-sender">AI助手</span> ${escapeHtml(res.answer || '（AI未返回内容）').replace(/\n/g, '<br>')} <span class="msg-time">${formatTime(new Date().toISOString())}</span>`;
            scrollToBottom('assistantMessages');
        }
    } catch (e) {
        const el = document.getElementById(loadingId);
        if (el) el.querySelector('.bubble').innerHTML = `<span class="msg-sender">AI助手</span><span style="color:#e74c3c;">处理失败：${escapeHtml(e.message)}</span>`;
    }
}
function clearAssistantChat() {
    const c = document.getElementById('assistantMessages');
    if (c) c.innerHTML = `<div class="assistant-welcome"><h3>欢迎回来，管理员 👋</h3><p>我可以帮你查询需求、分析重点，回答基于企业知识库的问题。</p></div>`;
}

// ===== 解决报告 =====
function _dayKey(isoStr) {
    if (!isoStr) return '';
    if (!/Z$|[+-]\d{2}:?\d{2}$/.test(isoStr)) isoStr = isoStr + 'Z';
    const d = new Date(isoStr);
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
window._trendType = localStorage.getItem('report_trend_type') || 'bar';
async function loadReport() {
    const container = document.getElementById('reportContainer');
    if (!container) { console.error('reportContainer 不存在，请检查parent.html'); return; }
    container.innerHTML = '<div style="text-align:center;color:#94a3b8;padding:40px;">报告生成中...</div>';
    try { window._reqsCache = await API.getRequirements({}); } catch (e) { console.warn(e); }
    let data = null;
    try { data = await API.getMonthlyReport(); } catch (e) {}
    if (!data) { try { data = await API.getWeeklyReport(); } catch (e) {} }
    if (!data) { container.innerHTML = '<div style="color:#e74c3c;padding:20px;">报告数据加载失败</div>'; return; }
    renderReport(data, container);
}
function smoothPath(pts) {
    if (pts.length < 2) return '';
    let d = `M ${pts[0][0]} ${pts[0][1]}`;
    for (let i = 0; i < pts.length - 1; i++) {
        const p0 = pts[i-1] || pts[i], p1 = pts[i], p2 = pts[i+1], p3 = pts[i+2] || p2;
        d += ` C ${p1[0]+(p2[0]-p0[0])/6} ${p1[1]+(p2[1]-p0[1])/6}, ${p2[0]-(p3[0]-p1[0])/6} ${p2[1]-(p3[1]-p1[1])/6}, ${p2[0]} ${p2[1]}`;
    }
    return d;
}
function buildLineChartSVG(labels, s1, s2, name1, name2, c1, c2) {
    const W=720,H=250,L=46,R=16,T=30,B=36;
    const maxV = Math.max(...s1, ...s2, 1);
    const iw = W-L-R, ih = H-T-B;
    const n = Math.max(labels.length - 1, 1);
    const pts1 = s1.map((v,i)=>[L+iw*i/n, T+ih-(v/maxV)*ih]);
    const pts2 = s2.map((v,i)=>[L+iw*i/n, T+ih-(v/maxV)*ih]);
    let grid = '';
    for (let g=0; g<=4; g++) {
        const y = T+ih*g/4;
        grid += `<line x1="${L}" y1="${y}" x2="${W-R}" y2="${y}" stroke="#eef2f7"/>
        <text x="${L-8}" y="${y+4}" font-size="10" fill="#94a3b8" text-anchor="end">${Math.round(maxV*(4-g)/4)}</text>`;
    }
    const gid = 'g' + Date.now();
    let dots = '', vals = '';
    pts1.forEach((p,i)=>{
        dots += `<circle cx="${p[0]}" cy="${p[1]}" r="3.5" fill="#fff" stroke="${c1}" stroke-width="2"><title>${name1} ${s1[i]}</title></circle>`;
        vals += `<text x="${p[0]}" y="${p[1]-9}" font-size="10" fill="${c1}" text-anchor="middle">${s1[i]||''}</text>`;
    });
    pts2.forEach((p,i)=>{
        dots += `<circle cx="${p[0]}" cy="${p[1]}" r="3.5" fill="#fff" stroke="${c2}" stroke-width="2"><title>${name2} ${s2[i]}</title></circle>`;
    });
    const step = Math.ceil(labels.length/12);
    const xlabels = labels.map((lb,i)=> i%step===0 ? `<text x="${pts1[i][0]}" y="${H-10}" font-size="10" fill="#64748b" text-anchor="middle">${lb}</text>` : '').join('');
    return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;display:block;">
    <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="${c1}" stop-opacity="0.22"/><stop offset="100%" stop-color="${c1}" stop-opacity="0"/>
    </linearGradient></defs>
    ${grid}
    <path d="M ${pts1[0][0]} ${T+ih} ${smoothPath(pts1).slice(1)} L ${pts1[pts1.length-1][0]} ${T+ih} Z" fill="url(#${gid})"/>
    <path d="${smoothPath(pts1)}" fill="none" stroke="${c1}" stroke-width="2.5" stroke-linecap="round"/>
    <path d="${smoothPath(pts2)}" fill="none" stroke="${c2}" stroke-width="2.5" stroke-linecap="round"/>
    ${dots}${vals}${xlabels}
    <g font-size="12"><rect x="${L+4}" y="4" width="12" height="12" rx="3" fill="${c1}"/><text x="${L+22}" y="14" fill="#475569">${name1}</text>
    <rect x="${L+72}" y="4" width="12" height="12" rx="3" fill="${c2}"/><text x="${L+90}" y="14" fill="#475569">${name2}</text></g>
    </svg>`;
}
function renderTrend(reqs) {
    const days = [];
    for (let i=6; i>=0; i--) days.push(_dayKey(new Date(Date.now() - i*86400000)));
    const labels = days.map(k=>k.slice(5).replace('-','/'));
    const submitted = days.map(k=>reqs.filter(r=>_dayKey(r.created_at)===k).length);
    const solved = days.map(k=>reqs.filter(r=>r.status==='已解决' && _dayKey(r.updated_at)===k).length);
    if (window._trendType === 'line') return buildLineChartSVG(labels, submitted, solved, '提交', '解决', '#2563eb', '#22c55e');
    const maxV = Math.max(...submitted, ...solved, 1);
    return `<div style="display:flex;align-items:flex-end;gap:10px;height:150px;">` +
        labels.map((lb,i)=>`
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:6px;min-width:0;">
            <div style="display:flex;gap:4px;align-items:flex-end;height:110px;">
                <div title="提交 ${submitted[i]}" style="width:14px;height:${Math.round(submitted[i]/maxV*100)}%;min-height:2px;background:#2563eb;border-radius:4px 4px 0 0;"></div>
                <div title="解决 ${solved[i]}" style="width:14px;height:${Math.round(solved[i]/maxV*100)}%;min-height:2px;background:#22c55e;border-radius:4px 4px 0 0;"></div>
            </div><span style="font-size:11px;color:#94a3b8;">${lb}</span></div>`).join('') + `</div>`;
}
function toggleTrendType() {
    window._trendType = window._trendType === 'bar' ? 'line' : 'bar';
    try { localStorage.setItem('report_trend_type', window._trendType); } catch(e) {}
    const box = document.getElementById('trendBox');
    if (box) {
        box.innerHTML = renderTrend(window._reqsCache || []);
        document.getElementById('trendToggleBtn').textContent = window._trendType === 'bar' ? '📈 切换曲线图' : '📊 切换柱状图';
    }
}
function renderReport(data, container) {
    const reqs = window._reqsCache || [];
    const total = data.total || reqs.length || 0;
    const resolved = data.resolved || 0;
    const rate = total ? Math.round(resolved/total*100) : 0;
    const trendHtml = reqs.length ? renderTrend(reqs) : '<div style="color:#94a3b8;font-size:13px;">暂无数据</div>';
    const statusCount = { '待处理':0, '处理中':0, '待反馈':0, '已解决':0 };
    reqs.forEach(r => { if (statusCount[r.status] !== undefined) statusCount[r.status]++; });
    const sTotal = reqs.length || 1;
    const sColors = { '待处理':'#eab308','处理中':'#2563eb','待反馈':'#f97316','已解决':'#22c55e' };
    const statusHtml = Object.keys(statusCount).map(s => `
    <div style="margin-bottom:10px;">
        <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px;"><span>${s}</span><strong>${statusCount[s]} 个 · ${Math.round(statusCount[s]/sTotal*100)}%</strong></div>
        <div style="height:10px;background:#f1f5f9;border-radius:5px;"><div style="width:${Math.round(statusCount[s]/sTotal*100)}%;height:100%;border-radius:5px;background:${sColors[s]};"></div></div>
    </div>`).join('');
    const colors = ['#2563eb','#22c55e','#f59e0b','#8b5cf6'];
    let rankHtml = '';
    (data.user_ranking || []).forEach((item,i) => {
        const pct = total ? Math.round(item.count/total*100) : 0;
        const name = escapeHtml(item.username || ('用户 #'+item.user_id));
        const dept = item.department ? ' · ' + escapeHtml(item.department) : '';
        rankHtml += `<div style="margin-bottom:12px;">
        <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px;">
        <span>${i===0?'🥇':i===1?'🥈':i===2?'🥉':'👤'} ${name}${dept}</span><strong>${item.count} 个</strong></div>
        <div style="height:8px;background:#f1f5f9;border-radius:4px;"><div style="width:${pct}%;height:100%;border-radius:4px;background:${colors[i%4]}"></div></div></div>`;
    });
    const pri = { '高':0, '中':1, '低':2 };
    const todo = reqs.filter(r=>r.status!=='已解决').sort((a,b)=>(pri[a.priority]??3)-(pri[b.priority]??3)).slice(0,5);
    const todoHtml = todo.length ? todo.map(r=>`
    <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:13px;cursor:pointer;" onclick="showRequirementDetail(${r.id})">
        <span>${r.priority==='高'?'🔴':r.priority==='中'?'🟡':'🟢'} ${escapeHtml(r.title)}</span>
        <span style="color:#94a3b8;">${escapeHtml(r.username || ('用户 #'+r.user_id))} · ${escapeHtml(r.status)}</span></div>`).join('') : '<div style="color:#94a3b8;padding:8px 0;">🎉 暂无待办，全部解决！</div>';
    const statusMap = { '待处理':'pending','处理中':'processing','待反馈':'waiting','已解决':'resolved' };
    const recent = reqs.slice(0,5).map(r=>`<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f1f5f9;font-size:13px;">
    <span>${escapeHtml(r.title)}</span><span class="status-tag ${statusMap[r.status]||'pending'}">${escapeHtml(r.status)}</span></div>`).join('');
    container.innerHTML = `
    <div class="report-card">
        <div class="report-stat" style="background:linear-gradient(135deg,#eff6ff,#dbeafe);"><div class="number" style="color:#2563eb;">${total}</div><div class="label">需求总数</div></div>
        <div class="report-stat" style="background:linear-gradient(135deg,#f0fdf4,#dcfce7);"><div class="number" style="color:#16a34a;">${resolved}</div><div class="label">已解决</div></div>
        <div class="report-stat" style="background:linear-gradient(135deg,#fefce8,#fef9c3);"><div class="number" style="color:#ca8a04;">${rate}%</div><div class="label">完成率</div></div>
        <div class="report-stat"><div class="number">${data.avg_processing_hours ?? '-'}h</div><div class="label">平均处理时长</div></div>
        <div class="report-stat"><div class="number">${data.pending_critical ?? 0}</div><div class="label">未解决重点需求</div></div>
    </div>
    <h4 style="margin:16px 0 8px;display:flex;justify-content:space-between;align-items:center;">📈 近7天提交与解决趋势
    <button class="btn-secondary" id="trendToggleBtn" style="font-size:12px;padding:4px 12px;" onclick="toggleTrendType()">${window._trendType==='bar'?'📈 切换曲线图':'📊 切换柱状图'}</button></h4>
    <div style="background:#fff;border:1px solid #e9eef5;border-radius:10px;padding:16px;"><div id="trendBox">${trendHtml}</div></div>
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:16px;">
        <div style="flex:1;min-width:280px;background:#fff;border:1px solid #e9eef5;border-radius:10px;padding:16px;"><h4 style="margin-bottom:12px;">🥧 状态分布</h4>${statusHtml||'<div style="color:#94a3b8;font-size:13px;">暂无数据</div>'}</div>
        <div style="flex:1;min-width:280px;background:#fff;border:1px solid #e9eef5;border-radius:10px;padding:16px;"><h4 style="margin-bottom:12px;">🏆 各子节点提交排行</h4>${rankHtml||'<div style="color:#94a3b8;font-size:13px;">暂无数据</div>'}</div>
    </div>
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:16px;">
        <div style="flex:1;min-width:280px;background:#fff;border:1px solid #e9eef5;border-radius:10px;padding:16px;"><h4 style="margin-bottom:8px;">🔥 待办重点（按优先级）</h4>${todoHtml}</div>
        <div style="flex:1;min-width:280px;background:#fff;border:1px solid #e9eef5;border-radius:10px;padding:16px;"><h4 style="margin-bottom:8px;">🕒 最近动态</h4>${recent||'<div style="color:#94a3b8;font-size:13px;">暂无数据</div>'}</div>
    </div>
    <div style="margin-top:16px;color:#94a3b8;font-size:13px;">📅 统计周期: ${data.period ? `${data.period.start} ~ ${data.period.end}` : '近30天'} ｜ 数据实时取自系统</div>`;
}

// ===== 导出月报/年报 =====
async function exportReport(period) {
    showToast('正在生成报告...', 'info');
    let reqs = window._reqsCache;
    if (!reqs || !reqs.length) { try { reqs = await API.getRequirements({}); } catch(e) {} }
    const list = reqs || [];
    const now = new Date();
    let buckets = [], filename, rangeText, unit;
    if (period === 'monthly') {
        const y = now.getFullYear(), m = now.getMonth();
        const dim = new Date(y, m+1, 0).getDate();
        filename = `需求月报_${y}-${String(m+1).padStart(2,'0')}`;
        unit = 'day';
        for (let d=1; d<=dim; d++) buckets.push({ key:`${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`, label:String(d) });
        rangeText = `${y}-${String(m+1).padStart(2,'0')}-01 ~ ${y}-${String(m+1).padStart(2,'0')}-${dim}`;
    } else {
        const y = now.getFullYear();
        filename = `需求年报_${y}`;
        unit = 'month';
        for (let m=1; m<=12; m++) buckets.push({ key:`${y}-${String(m).padStart(2,'0')}`, label:`${m}月` });
        rangeText = `${y}-01-01 ~ ${y}-12-31`;
    }
    const keyOf = (r, field) => { const k = _dayKey(r[field]); return unit==='month' ? k.slice(0,7) : k; };
    const submitted = list.filter(r => buckets.some(b=>b.key===keyOf(r,'created_at')));
    const solvedInP = list.filter(r => r.status==='已解决' && buckets.some(b=>b.key===keyOf(r,'updated_at')));
    const rate = submitted.length ? Math.round(solvedInP.length/submitted.length*100) : 0;
    const pendingAll = list.filter(r=>r.status!=='已解决').length;
    const rank = {};
    submitted.forEach(r=>{ const n=r.username||('用户#'+r.user_id); rank[n]=(rank[n]||0)+1; });
    const rankRows = Object.entries(rank).sort((a,b)=>b[1]-a[1]).map(([n,c],i)=>`<tr><td>${i+1}</td><td>${escapeHtml(n)}</td><td>${c}</td></tr>`).join('') || '<tr><td colspan="3" class="mut">无</td></tr>';
    const statusCount = { '待处理':0,'处理中':0,'待反馈':0,'已解决':0 };
    submitted.forEach(r=>{ if (statusCount[r.status]!==undefined) statusCount[r.status]++; });
    const solvedRows = solvedInP.map(r=>`<tr><td>${escapeHtml(r.title)}</td><td>${escapeHtml(r.username||'')}</td><td>${escapeHtml(r.solution ? (''+r.solution).slice(0,80) : '详见系统')}</td><td>${_dayKey(r.updated_at)}</td></tr>`).join('') || '<tr><td colspan="4" class="mut">本期无解决记录</td></tr>';
    const pendingRows = list.filter(r=>r.status!=='已解决')
        .sort((a,b)=>({'高':0,'中':1,'低':2}[a.priority]??3)-({'高':0,'中':1,'低':2}[b.priority]??3)).slice(0,10)
        .map(r=>`<tr><td>${escapeHtml(r.title)}</td><td>${escapeHtml(r.priority)}</td><td>${escapeHtml(r.status)}</td><td>${escapeHtml(r.username||'')}</td></tr>`).join('') || '<tr><td colspan="4" class="mut">无待办</td></tr>';
    const chart = buckets.length > 1 ? buildLineChartSVG(buckets.map(b=>b.label), buckets.map(b=>submitted.filter(r=>keyOf(r,'created_at')===b.key).length), buckets.map(b=>solvedInP.filter(r=>keyOf(r,'updated_at')===b.key).length), '提交', '解决', '#2563eb', '#22c55e') : '<p class="mut">周期内数据点不足，暂无趋势图</p>';
    const html = `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>${filename}</title><style>
    body{font-family:'Segoe UI','Microsoft YaHei',sans-serif;color:#1e293b;max-width:900px;margin:0 auto;padding:32px;}
    h1{font-size:22px;margin-bottom:4px;} h2{font-size:16px;margin:28px 0 10px;border-left:4px solid #2563eb;padding-left:10px;}
    .sub{color:#64748b;font-size:13px;} .kpi{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0;}
    .kpi div{flex:1;min-width:120px;background:#f8fafc;border:1px solid #e9eef5;border-radius:10px;padding:14px;text-align:center;}
    .kpi b{font-size:24px;display:block;} table{width:100%;border-collapse:collapse;font-size:13px;}
    th,td{border-bottom:1px solid #e9eef5;padding:7px 8px;text-align:left;} th{background:#f8fafc;} .mut{color:#94a3b8;}
    @media print{body{padding:0;}} </style></head><body>
    <h1>📋 需求处理${period==='monthly'?'月报':'年报'}</h1>
    <div class="sub">统计周期：${rangeText} ｜ 生成时间：${new Date().toLocaleString('zh-CN')} ｜ 数据来源：需求中枢系统（实时导出）</div>
    <div class="kpi">
        <div><b>${submitted.length}</b>本期提交</div><div><b>${solvedInP.length}</b>本期解决</div>
        <div><b>${rate}%</b>本期完成率</div><div><b>${pendingAll}</b>当前未解决总数</div>
    </div>
    <h2>📈 提交与解决趋势</h2>${chart}
    <h2>📋 状态分布（本期提交）</h2><table><tr><th>状态</th><th>数量</th></tr>${Object.entries(statusCount).map(([k,v])=>`<tr><td>${k}</td><td>${v}</td></tr>`).join('')}</table>
    <h2>🏆 提交排行（本期）</h2><table><tr><th>#</th><th>用户</th><th>提交数</th></tr>${rankRows}</table>
    <h2>✅ 本期解决清单（解决了什么）</h2><table><tr><th>需求</th><th>提交人</th><th>解决方案摘要</th><th>解决日期</th></tr>${solvedRows}</table>
    <h2>🔥 当前待办重点</h2><table><tr><th>需求</th><th>优先级</th><th>状态</th><th>提交人</th></tr>${pendingRows}</table>
    <p class="sub" style="margin-top:24px;">提示：浏览器中按 Ctrl+P 可将本报告另存为 PDF 用于会议分发。</p>
    </body></html>`;
    const blob = new Blob([html], { type:'text/html;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename + '.html';
    a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href), 3000);
    showToast('已导出 ' + filename + '.html', 'success');
}

// ===== 账号管理 =====
async function loadUsers() {
    const tbody = document.getElementById('usersTableBody');
    try {
        const users = await API.getUsers();
        if (!users || users.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:30px;">暂无子节点账号</td></tr>`;
            return;
        }
        let html = '';
        for (const user of users) {
            html += `
            <tr>
                <td>${user.id}</td>
                <td>${escapeHtml(user.username)}</td>
                <td>${escapeHtml(user.department || '-')}</td>
                <td>${escapeHtml(user.position || '-')}</td>
                <td>${formatTime(user.created_at)}</td>
                <td>
                    <button class="btn-primary" style="font-size:12px;padding:2px 10px;" onclick="editUser(${user.id})">编辑</button>
                    <button class="btn-danger" onclick="deleteUser(${user.id})">删除</button>
                </td>
            </tr>`;
        }
        tbody.innerHTML = html;
    } catch (e) {
        console.error('加载用户失败:', e);
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:#e74c3c;padding:30px;">加载失败: ${escapeHtml(e.message)}</td></tr>`;
    }
}
function showAddUserForm() {
    document.getElementById('modalTitle').textContent = '添加子节点账号';
    document.getElementById('editUserId').value = '';
    document.getElementById('formUsername').value = '';
    document.getElementById('formPassword').value = '';
    document.getElementById('formDepartment').value = '';
    document.getElementById('formPosition').value = '';
    document.getElementById('userModal').style.display = 'flex';
    loadPositions();
}
async function editUser(userId) {
    try {
        const users = await API.getUsers();
        const user = users.find(u => u.id === userId);
        if (!user) return showToast('用户不存在', 'error');
        document.getElementById('modalTitle').textContent = '编辑子节点账号';
        document.getElementById('editUserId').value = userId;
        document.getElementById('formUsername').value = user.username;
        document.getElementById('formPassword').value = '';
        document.getElementById('formDepartment').value = user.department || '';
        document.getElementById('formPosition').value = user.position || '';
        document.getElementById('userModal').style.display = 'flex';
        await loadPositions();
    } catch (e) { showToast('加载用户信息失败', 'error'); }
}
async function deleteUser(userId) {
    if (!(await showConfirm('该用户的全部对话、消息与需求将一并删除，且不可恢复。', { title: '确认删除该用户？', danger: true, okText: '删除' }))) return;
    try {
        await API.deleteUser(userId);
        showToast('删除成功', 'success');
        loadUsers();
    } catch (e) { showToast('删除失败: ' + e.message, 'error'); }
}
function closeModal() { document.getElementById('userModal').style.display = 'none'; }

// ===== 职位管理（输入框 + 自定义下拉，可自动创建） =====
async function loadPositions() {
    try { allPositions = await API.getPositions(); }
    catch (e) { console.error('加载职位列表失败:', e); allPositions = []; }
}
function showPositionDropdown() {
    const input = document.getElementById('formPosition');
    const dropdown = document.getElementById('positionDropdown');
    if (input.value.trim()) { filterPositions(input.value); }
    else { renderPositionDropdown(allPositions.map(p => p.name)); }
    dropdown.style.display = 'block';
}
function hidePositionDropdown() {
    setTimeout(() => { document.getElementById('positionDropdown').style.display = 'none'; }, 200);
}
function filterPositions(keyword) {
    const dropdown = document.getElementById('positionDropdown');
    const filtered = allPositions.map(p => p.name).filter(name => name.includes(keyword));
    renderPositionDropdown(filtered);
    dropdown.style.display = filtered.length > 0 ? 'block' : 'none';
}
function renderPositionDropdown(names) {
    const dropdown = document.getElementById('positionDropdown');
    if (names.length === 0) {
        dropdown.innerHTML = `<div style="padding:8px 14px;color:#94a3b8;">无匹配职位，将自动创建</div>`;
        return;
    }
    dropdown.innerHTML = names.map(name => `
    <div style="padding:8px 14px;cursor:pointer;border-bottom:1px solid #f1f5f9;"
         onmouseover="this.style.background='#f1f5f9'" onmouseout="this.style.background='white'"
         onclick="selectPosition('${name}')">${escapeHtml(name)}</div>`).join('');
}
function selectPosition(name) {
    document.getElementById('formPosition').value = name;
    document.getElementById('positionDropdown').style.display = 'none';
}

// ===== 工具函数 =====
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
function scrollToBottom(containerId) {
    const container = document.getElementById(containerId);
    if (container) { setTimeout(() => container.scrollTop = container.scrollHeight, 50); }
}
function startPolling() {
    if (pollingTimer) clearInterval(pollingTimer);
    pollingTimer = setInterval(() => {
        if (document.getElementById('sub-list')?.classList.contains('active')) loadRequirements();
    }, 10000);
}

// ===== WebSocket提醒 =====
function onWebSocketMessage(data) {
    if (data.type === 'new_requirement') {
        addNewRequirementNotice(data);
        if (document.getElementById('sub-list')?.classList.contains('active')) loadRequirements();
    }
    if (data.type === 'new_message' && data.title) addFollowUpNotice(data);
    if (data.type === 'new_message' || data.type === 'requirement_update') {
        if (document.getElementById('sub-list')?.classList.contains('active')) loadRequirements();
    }
}
function addNewRequirementNotice(data) {
    const id = saveNotice({ type: 'new_requirement', ...data });
    appendNewRequirementCard(data, id);
    if (!document.getElementById('sub-assistant')?.classList.contains('active')) { newReqBadge++; updateTaskBadge(); }
}
function appendNewRequirementCard(data, noticeId) {
    const container = document.getElementById('assistantMessages');
    if (!container || document.getElementById(noticeId)) return;
    const welcome = container.querySelector('.assistant-welcome');
    if (welcome) welcome.remove();
    container.insertAdjacentHTML('beforeend', `
    <div class="message notice" id="${noticeId}">
        <div class="avatar">🔔</div>
        <div class="bubble"><span class="msg-sender">新任务提醒 <span style="float:right;cursor:pointer;" title="关闭" onclick="dismissNotice('${noticeId}')">✕</span></span>
        📋 <strong>${escapeHtml(data.title || '新需求')}</strong><br>
        <span style="font-size:13px;opacity:.8;">👤 来自：${escapeHtml(data.username || ('用户 #' + data.user_id))}</span>
        <div style="margin-top:8px;">
            <button class="btn-primary" style="font-size:12px;padding:4px 12px;" onclick="jumpToRequirement(${data.requirement_id}, '${noticeId}')">点击查看详情 →</button>
        </div>
        <span class="msg-time">${formatTime(new Date().toISOString())}</span></div>
    </div>`);
    scrollToBottom('assistantMessages');
}
function addFollowUpNotice(data) {
    const id = saveNotice({ type: 'new_message', ...data });
    appendFollowUpCard(data, id);
}
function appendFollowUpCard(data, noticeId) {
    const container = document.getElementById('assistantMessages');
    if (!container || document.getElementById(noticeId)) return;
    const content = (data.content || '').slice(0, 40);
    container.insertAdjacentHTML('beforeend', `
    <div class="message notice" id="${noticeId}">
        <div class="avatar">💬</div>
        <div class="bubble"><span class="msg-sender">子节点补充消息 <span style="float:right;cursor:pointer;" title="关闭" onclick="dismissNotice('${noticeId}')">✕</span></span>
        📋 <strong>${escapeHtml(data.title)}</strong>（${escapeHtml(data.username)}）<br>
        <span style="opacity:.85;">"${escapeHtml(content)}${(data.content || '').length > 40 ? '…' : ''}"</span>
        <div style="margin-top:8px;">
            <button class="btn-primary" style="font-size:12px;padding:4px 12px;" onclick="jumpToRequirement(${data.requirement_id}, '${noticeId}')">查看对话 →</button>
        </div></div>
    </div>`);
    scrollToBottom('assistantMessages');
}
function updateTaskBadge() {
    const menu = document.querySelector('.menu-item[data-tab="tasks"]');
    if (!menu) return;
    let badge = document.getElementById('taskBadge');
    if (newReqBadge > 0) {
        if (!badge) {
            badge = document.createElement('span');
            badge.id = 'taskBadge';
            menu.appendChild(badge);
        }
        badge.textContent = newReqBadge;
        badge.style.cssText = 'margin-left:6px;background:#ef4444;color:#fff;border-radius:10px;padding:0 6px;font-size:11px;';
    } else if (badge) { badge.remove(); }
}
async function jumpToRequirement(reqId, noticeId) {
    if (noticeId) dismissNotice(noticeId);
    switchTab('tasks');
    switchSubTab('list');
    showRequirementDetail(reqId);
}

// ===== 企业知识库 =====
async function loadKnowledge() {
    const box = document.getElementById('knowledgeList');
    if (!box) return;
    try {
        const docs = await API.getKnowledgeDocs();
        if (!docs.length) {
            box.innerHTML = '<div style="color:#94a3b8;text-align:center;padding:30px;">知识库为空。上传企业文档（txt/md/docx）或粘贴文本，AI助手即可引用回答。</div>';
            return;
        }
        box.innerHTML = docs.map(d => `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 12px;border-bottom:1px solid #f1f5f9;">
            <div><strong>${escapeHtml(d.title)}</strong> <span style="color:#94a3b8;font-size:12px;margin-left:8px;">${d.chunks} 个片段 · ${escapeHtml(d.source_name || '手输入')}</span></div>
            <button class="btn-danger" onclick="deleteKnowledgeDoc('${d.doc_id}')">删除</button>
        </div>`).join('');
    } catch (e) { box.innerHTML = `<div style="color:#e74c3c;padding:20px;">加载失败: ${escapeHtml(e.message)}</div>`; }
}
async function uploadKnowledgeFile(input) {
    const f = input.files[0];
    input.value = '';
    if (!f) return;
    if (f.size > 10 * 1024 * 1024) return showToast('文件超过10MB，请拆分后上传', 'error');
    if (window._kbUploading) return showToast('上一次上传仍在处理中，请稍候…', 'info');
    window._kbUploading = true;
    showToast(`正在解析并向量化「${f.name}」，大文档需1-2分钟，请勿关闭页面…`, 'info');
    try {
        const r = await API.uploadKnowledgeDoc(f);
        showToast(`已入库「${r.title || f.name}」（${r.chunks ?? '?'}个片段）`, 'success');
        loadKnowledge();
    } catch (e) {
        showToast('入库失败: ' + e.message, 'error');
    } finally {
        window._kbUploading = false;   // 无论成败都解锁
    }
}

async function saveKnowledgeText() {
    const title = document.getElementById('kbTitle').value.trim() || '未命名文档';
    const content = document.getElementById('kbContent').value.trim();
    if (!content) return showToast('内容不能为空', 'error');
    if (content.length > 200000) return showToast('文本过长（>20万字），请分批入库', 'error');
    if (window._kbUploading) return showToast('上一次入库仍在处理中，请稍候…', 'info');
    window._kbUploading = true;
    showToast('正在向量化，请稍候…', 'info');
    try {
        const r = await API.addKnowledgeText(title, content);
        showToast(`已入库（${r.chunks}个片段）`, 'success');
        document.getElementById('kbTitle').value = '';
        document.getElementById('kbContent').value = '';
        loadKnowledge();
    } catch (e) {
        showToast('入库失败: ' + e.message, 'error');
    } finally {
        window._kbUploading = false;
    }
}
async function deleteKnowledgeDoc(docId) {
    if (!(await showConfirm('将删除该文档的全部片段，确定吗？', { title: '删除文档', danger: true, okText: '删除' }))) return;
    try {
        await API.deleteKnowledgeDoc(docId);
        showToast('已删除', 'success');
        loadKnowledge();
    } catch (e) { showToast('删除失败: ' + e.message, 'error'); }
}
