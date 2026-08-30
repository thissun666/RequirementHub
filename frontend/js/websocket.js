// WebSocket 客户端
let ws = null;
let wsReconnectTimer = null;

function connectWebSocket() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        console.log('未登录，跳过WebSocket连接');
        return;
    }
                    const wsHost = (location.port === '8000') ? location.host
            : ((location.hostname || 'localhost') + ':8000');

        const wsUrl = `ws://${wsHost}/ws?token=${token}`;

    try {
        ws = new WebSocket(wsUrl);
        ws.onopen = function() {
            console.log('WebSocket 已连接');
        };
        ws.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                console.log('收到WebSocket消息:', data);
                if (typeof onWebSocketMessage === 'function') {
                    onWebSocketMessage(data);
                }
            } catch (e) {
                console.error('解析WebSocket消息失败:', e);
            }
        };
        ws.onclose = function() {
            console.log('WebSocket 断开，尝试重连...');
            if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
            wsReconnectTimer = setTimeout(() => {
                connectWebSocket();
            }, 5000);
        };
        ws.onerror = function(error) {
            console.error('WebSocket 错误:', error);
        };
    } catch (e) {
        console.error('WebSocket 连接失败:', e);
    }
}

function disconnectWebSocket() {
    if (ws) {
        ws.close();
        ws = null;
    }
    if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
    }
}