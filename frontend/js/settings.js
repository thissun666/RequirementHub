// settings.js - 模型设置管理

async function loadSettings() {
    try {
        const settings = await API.getModelSettings();
        document.getElementById('settingProvider').value = settings.provider || 'zhipu';
        document.getElementById('settingModel').value = settings.model || '';
        document.getElementById('settingBaseUrl').value = settings.base_url || '';
        document.getElementById('settingApiKey').value = settings.api_key || '';
                const dl = document.getElementById('modelHistoryList');
        if (dl && Array.isArray(settings.models)) {
            dl.innerHTML = settings.models.map(m => `<option value="${m}"></option>`).join('');
        }

    } catch (e) {
        console.error('加载设置失败:', e);
        const resultEl = document.getElementById('settingResult');
        if (resultEl) resultEl.innerHTML = '<span style="color:#e74c3c;">加载设置失败</span>';
    }
}

async function saveSettings() {
        const apiKeyInput = document.getElementById('settingApiKey').value.trim();
    const data = {
        provider: document.getElementById('settingProvider').value,
        // 输入框里显示的是 ***xxxx 掩码时不上传，后端会自动沿用旧 key
        api_key: apiKeyInput.startsWith('***') ? '' : apiKeyInput,
        model: document.getElementById('settingModel').value,
        base_url: document.getElementById('settingBaseUrl').value,
    };

    try {
        await API.updateModelSettings(data);
        const resultEl = document.getElementById('settingResult');
        if (resultEl) resultEl.innerHTML = '<span style="color:#27ae60;">✅ 设置已保存</span>';
        setTimeout(() => { if (resultEl) resultEl.innerHTML = ''; }, 3000);
    } catch (e) {
        const resultEl = document.getElementById('settingResult');
        if (resultEl) resultEl.innerHTML = `<span style="color:#e74c3c;">❌ 保存失败: ${e.message}</span>`;
    }
}

// 页面加载时自动加载设置
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('settingProvider')) {
        loadSettings();
    }
});