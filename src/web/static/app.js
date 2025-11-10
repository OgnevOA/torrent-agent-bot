// Telegram Web App initialization
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// WebSocket connection
let socket = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

// Format bytes to human-readable format
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Format speed
function formatSpeed(bytesPerSec) {
    return formatBytes(bytesPerSec) + '/s';
}

// Format ETA
function formatETA(etaSeconds) {
    if (etaSeconds < 0) return '∞';
    if (etaSeconds < 60) return `${etaSeconds}s`;
    if (etaSeconds < 3600) {
        const minutes = Math.floor(etaSeconds / 60);
        const seconds = etaSeconds % 60;
        return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
    }
    const hours = Math.floor(etaSeconds / 3600);
    const minutes = Math.floor((etaSeconds % 3600) / 60);
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
}

// Get status emoji and class
function getStatusInfo(state) {
    const stateLower = state.toLowerCase();
    if (stateLower === 'downloading') {
        return { emoji: '🟢', class: 'downloading' };
    } else if (['seeding', 'uploading', 'stalledup', 'queuedup'].includes(stateLower)) {
        return { emoji: '🔵', class: 'seeding' };
    } else if (['paused', 'queueddl', 'stalleddl'].includes(stateLower)) {
        return { emoji: '⚪', class: 'paused' };
    } else if (stateLower === 'error') {
        return { emoji: '🔴', class: 'error' };
    }
    return { emoji: '⚪', class: 'paused' };
}

// Render torrent card
function renderTorrent(torrent) {
    const statusInfo = getStatusInfo(torrent.state);
    const progress = Math.min(100, Math.max(0, torrent.progress));
    
    return `
        <div class="torrent-card">
            <div class="torrent-header">
                <div class="torrent-name">${escapeHtml(torrent.name)}</div>
                <div class="torrent-status ${statusInfo.class}">
                    ${statusInfo.emoji} ${torrent.state}
                </div>
            </div>
            <div class="progress-container">
                <div class="progress-bar-wrapper">
                    <div class="progress-bar" style="width: ${progress}%"></div>
                </div>
                <div class="progress-text">
                    <span>${progress.toFixed(1)}%</span>
                    <span>${formatBytes(torrent.size)}</span>
                </div>
            </div>
            <div class="torrent-info">
                <div class="info-item">
                    <span class="info-label">Status</span>
                    <span class="info-value">${torrent.state}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Seeds</span>
                    <span class="info-value ${torrent.seeds > 0 ? 'highlight' : ''}">${torrent.seeds}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Peers</span>
                    <span class="info-value">${torrent.peers}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Down Speed</span>
                    <span class="info-value ${torrent.dlspeed > 0 ? 'highlight' : ''}">${formatSpeed(torrent.dlspeed)}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Up Speed</span>
                    <span class="info-value">${formatSpeed(torrent.upspeed)}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">ETA</span>
                    <span class="info-value ${torrent.eta > 0 && torrent.eta < 3600 ? 'warning' : ''}">${formatETA(torrent.eta)}</span>
                </div>
            </div>
        </div>
    `;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Update statistics
function updateStats(torrents) {
    const total = torrents.length;
    const downloading = torrents.filter(t => t.state.toLowerCase() === 'downloading').length;
    const seeding = torrents.filter(t => 
        ['seeding', 'uploading', 'stalledup', 'queuedup'].includes(t.state.toLowerCase())
    ).length;
    
    document.getElementById('totalTorrents').textContent = total;
    document.getElementById('downloadingCount').textContent = downloading;
    document.getElementById('seedingCount').textContent = seeding;
}

// Update connection status indicator
function updateConnectionStatus(status, connected) {
    const statusEl = document.getElementById('connectionStatus');
    const dotEl = document.getElementById('connectionDot');
    
    statusEl.textContent = status;
    
    if (connected) {
        dotEl.style.background = 'var(--accent-green)';
        dotEl.style.animation = 'pulse 2s ease-in-out infinite';
    } else {
        dotEl.style.background = 'var(--accent-orange)';
        dotEl.style.animation = 'none';
    }
}

// Update torrents list smoothly
function updateTorrentsList(torrents) {
    const loadingEl = document.getElementById('loading');
    const errorEl = document.getElementById('error');
    const torrentsListEl = document.getElementById('torrentsList');
    
    // Save scroll position before update
    const scrollPosition = window.scrollY || document.documentElement.scrollTop;
    
    loadingEl.style.display = 'none';
    errorEl.style.display = 'none';
    
    if (torrents.length === 0) {
        torrentsListEl.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <div class="empty-state-text">No torrents found</div>
                <div class="empty-state-subtext">Add some torrents to see them here</div>
            </div>
        `;
    } else {
        torrentsListEl.innerHTML = torrents.map(renderTorrent).join('');
        updateStats(torrents);
    }
    
    // Restore scroll position after DOM update
    requestAnimationFrame(() => {
        window.scrollTo(0, scrollPosition);
    });
}

// Connect WebSocket
function connectWebSocket() {
    const loadingEl = document.getElementById('loading');
    const errorEl = document.getElementById('error');
    
    // Show loading on initial connect
    if (!socket || !socket.connected) {
        loadingEl.style.display = 'flex';
        errorEl.style.display = 'none';
    }
    
    updateConnectionStatus('Connecting...', false);
    
    // Get initData from Telegram Web App
    const initData = tg.initData || tg.initDataUnsafe || '';
    
    if (!initData) {
        updateConnectionStatus('No auth data', false);
        loadingEl.style.display = 'none';
        errorEl.style.display = 'block';
        errorEl.querySelector('p').textContent = '❌ No authentication data available';
        return;
    }
    
    // Disconnect existing socket if any
    if (socket) {
        socket.disconnect();
    }
    
    // Connect to WebSocket server
    socket = io({
        auth: {
            initData: initData
        },
        query: {
            initData: initData
        },
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: maxReconnectAttempts
    });
    
    // Connection successful
    socket.on('connect', () => {
        console.log('WebSocket connected');
        reconnectAttempts = 0;
        updateConnectionStatus('Connected', true);
        loadingEl.style.display = 'none';
        errorEl.style.display = 'none';
    });
    
    // Receive torrent updates
    socket.on('torrents_update', (data) => {
        const torrents = data.torrents || [];
        updateTorrentsList(torrents);
    });
    
    // Connection error
    socket.on('connect_error', (error) => {
        console.error('WebSocket connection error:', error);
        reconnectAttempts++;
        
        if (reconnectAttempts >= maxReconnectAttempts) {
            updateConnectionStatus('Connection failed', false);
            loadingEl.style.display = 'none';
            errorEl.style.display = 'block';
            errorEl.querySelector('p').textContent = '❌ Failed to connect. Please check your connection.';
        } else {
            updateConnectionStatus(`Reconnecting (${reconnectAttempts}/${maxReconnectAttempts})...`, false);
        }
    });
    
    // Disconnected
    socket.on('disconnect', (reason) => {
        console.log('WebSocket disconnected:', reason);
        updateConnectionStatus('Disconnected', false);
        
        if (reason === 'io server disconnect') {
            // Server disconnected, don't reconnect automatically
            loadingEl.style.display = 'none';
            errorEl.style.display = 'block';
            errorEl.querySelector('p').textContent = '❌ Server disconnected. Please refresh.';
        }
    });
    
    // Reconnecting
    socket.on('reconnect_attempt', (attemptNumber) => {
        console.log('Reconnection attempt:', attemptNumber);
        updateConnectionStatus(`Reconnecting (${attemptNumber}/${maxReconnectAttempts})...`, false);
    });
    
    // Reconnected
    socket.on('reconnect', (attemptNumber) => {
        console.log('Reconnected after', attemptNumber, 'attempts');
        reconnectAttempts = 0;
        updateConnectionStatus('Connected', true);
        errorEl.style.display = 'none';
    });
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();
    
    // Reconnect when page becomes visible
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && (!socket || !socket.connected)) {
            connectWebSocket();
        }
    });
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (socket) {
        socket.disconnect();
    }
});
