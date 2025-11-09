// Telegram Web App initialization
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

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
                    ${statusInfo.emoji} ${torrent.state} TEST
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

// Load torrents from API
async function loadTorrents() {
    const loadingEl = document.getElementById('loading');
    const errorEl = document.getElementById('error');
    const torrentsListEl = document.getElementById('torrentsList');
    
    // Save scroll position before update
    const scrollPosition = window.scrollY || document.documentElement.scrollTop;
    
    // Don't show loading spinner on auto-refresh (only on initial load)
    const isInitialLoad = loadingEl.style.display === 'flex' || torrentsListEl.innerHTML === '';
    
    if (isInitialLoad) {
        loadingEl.style.display = 'flex';
        errorEl.style.display = 'none';
        torrentsListEl.innerHTML = '';
    }
    
    try {
        // Get initData from Telegram Web App
        const initData = tg.initData || tg.initDataUnsafe || '';
        
        // Build API URL with auth
        const apiUrl = '/api/torrents';
        const headers = {
            'X-Telegram-Init-Data': initData
        };
        
        const response = await fetch(apiUrl, { headers });
        
        if (!response.ok) {
            if (response.status === 403) {
                throw new Error('Unauthorized. Please use this app through Telegram.');
            }
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        const torrents = data.torrents || [];
        
        loadingEl.style.display = 'none';
        
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
        // Use requestAnimationFrame to ensure DOM is fully updated
        requestAnimationFrame(() => {
            window.scrollTo(0, scrollPosition);
        });
        
    } catch (error) {
        console.error('Error loading torrents:', error);
        loadingEl.style.display = 'none';
        errorEl.style.display = 'block';
        errorEl.querySelector('p').textContent = `❌ ${error.message}`;
    }
}

// Auto-refresh every 5 seconds
let refreshInterval;

function startAutoRefresh() {
    refreshInterval = setInterval(loadTorrents, 5000);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    loadTorrents();
    startAutoRefresh();
    
    // Stop auto-refresh when page is hidden, resume when visible
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopAutoRefresh();
        } else {
            startAutoRefresh();
            loadTorrents(); // Refresh immediately when visible
        }
    });
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    stopAutoRefresh();
});

