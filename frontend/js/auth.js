// 检查登录状态，未登录则跳转到登录页
// ===== 登录态检查与登出 =====
function checkAuth() {
    const token = localStorage.getItem('access_token');
    if (!token) { window.location.href = 'login.html'; return false; }
    try {
        const payload = parseJwt(token);
        if (!payload || !payload.exp) { logout(); return false; }
        if (Date.now() > payload.exp * 1000) { logout(); return false; }
        return true;
    } catch (e) { logout(); return false; }
}

function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('user_id');
    localStorage.removeItem('current_user');
    if (typeof disconnectWebSocket === 'function') disconnectWebSocket();
    window.location.href = 'login.html';
}

document.addEventListener('DOMContentLoaded', function () {
    if (!window.location.pathname.includes('login.html')) checkAuth();
});

// 页面加载时检查
document.addEventListener('DOMContentLoaded', function() {
    // 不在登录页时检查
    if (!window.location.pathname.includes('login.html')) {
        checkAuth();
    }
});
// ... 之前的代码 ...

// 登出
function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('user_id');
    disconnectWebSocket();
    window.location.href = 'login.html';
}