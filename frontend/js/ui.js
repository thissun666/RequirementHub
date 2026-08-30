// ===== 通用美观UI组件（Toast / Prompt / Confirm）=====
(function () {
    const style = document.createElement('style');
    style.textContent = `
    .ui-toast-wrap { position: fixed; top: 20px; right: 20px; z-index: 99999; display: flex; flex-direction: column; gap: 10px; }
    .ui-toast { min-width: 200px; max-width: 360px; padding: 12px 18px; border-radius: 10px; color: #fff; font-size: 14px; box-shadow: 0 4px 16px rgba(0,0,0,.18); animation: uiToastIn .25s ease; display: flex; align-items: center; gap: 8px; }
    .ui-toast.success { background: linear-gradient(135deg,#22c55e,#16a34a); }
    .ui-toast.error   { background: linear-gradient(135deg,#ef4444,#dc2626); }
    .ui-toast.info    { background: linear-gradient(135deg,#3b82f6,#2563eb); }
    @keyframes uiToastIn { from { opacity:0; transform: translateX(30px);} to { opacity:1; transform:none; } }
    .ui-dialog-mask { position: fixed; inset:0; background: rgba(15,23,42,.45); z-index: 99998; display:flex; align-items:center; justify-content:center; }
    .ui-dialog { background:#fff; border-radius:14px; padding:22px 24px; width:360px; max-width:90vw; box-shadow:0 20px 50px rgba(0,0,0,.25); animation: uiPop .18s ease; }
    @keyframes uiPop { from{ transform:scale(.94); opacity:0 } to{ transform:none; opacity:1 } }
    .ui-dialog h4 { margin:0 0 6px; font-size:16px; color:#1e293b; }
    .ui-dialog p { margin:0 0 6px; font-size:14px; color:#64748b; }
    .ui-dialog input { width:100%; padding:10px 12px; border:1px solid #e2e8f0; border-radius:8px; font-size:14px; outline:none; box-sizing:border-box; }
    .ui-dialog input:focus { border-color:#2563eb; }
    .ui-dialog-btns { display:flex; justify-content:flex-end; gap:10px; margin-top:18px; }
    .ui-dialog-btns button { padding:8px 20px; border-radius:8px; border:1px solid #e2e8f0; background:#fff; color:#475569; cursor:pointer; font-size:14px; }
    .ui-dialog-btns .ui-btn-primary { background:#2563eb; color:#fff; border-color:#2563eb; }
    .ui-dialog-btns .ui-btn-primary:hover { background:#1d4ed8; }
    .ui-dialog-btns .ui-btn-danger { background:#ef4444; color:#fff; border-color:#ef4444; }`;
    document.head.appendChild(style);

    function ensureToastWrap() {
        let w = document.querySelector('.ui-toast-wrap');
        if (!w) { w = document.createElement('div'); w.className = 'ui-toast-wrap'; document.body.appendChild(w); }
        return w;
    }
    window.showToast = function (msg, type = 'info', duration = 2600) {
        const t = document.createElement('div');
        t.className = `ui-toast ${type}`;
        const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
        t.innerHTML = `<span>${icon}</span><span>${msg}</span>`;
        ensureToastWrap().appendChild(t);
        setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 300); }, duration);
    };
    window.showConfirm = function (msg, opts = {}) {
        return new Promise(resolve => {
            const mask = document.createElement('div');
            mask.className = 'ui-dialog-mask';
            mask.innerHTML = `<div class="ui-dialog"><h4>${opts.title || '确认操作'}</h4><p>${msg}</p>
                <div class="ui-dialog-btns"><button data-act="cancel">取消</button>
                <button class="${opts.danger ? 'ui-btn-danger' : 'ui-btn-primary'}" data-act="ok">${opts.okText || '确定'}</button></div></div>`;
            mask.querySelector('[data-act=ok]').onclick = () => { mask.remove(); resolve(true); };
            mask.querySelector('[data-act=cancel]').onclick = () => { mask.remove(); resolve(false); };
            document.body.appendChild(mask);
        });
    };
    window.showPrompt = function (title, defaultVal = '', opts = {}) {
        return new Promise(resolve => {
            const mask = document.createElement('div');
            mask.className = 'ui-dialog-mask';
            mask.innerHTML = `<div class="ui-dialog"><h4>${title}</h4>
                <input type="text" value="${(defaultVal || '').replace(/"/g, '&quot;')}" placeholder="${opts.placeholder || ''}">
                <div class="ui-dialog-btns"><button data-act="cancel">取消</button>
                <button class="ui-btn-primary" data-act="ok">${opts.okText || '确定'}</button></div></div>`;
            const input = mask.querySelector('input');
            const ok = () => { const v = input.value.trim(); mask.remove(); resolve(v || null); };
            mask.querySelector('[data-act=ok]').onclick = ok;
            mask.querySelector('[data-act=cancel]').onclick = () => { mask.remove(); resolve(null); };
            input.addEventListener('keydown', e => { if (e.key === 'Enter') ok(); });
            setTimeout(() => { input.focus(); input.select(); }, 50);
            document.body.appendChild(mask);
        });
    };
})();
