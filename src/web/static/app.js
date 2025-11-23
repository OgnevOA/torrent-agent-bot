// Telegram Web App initialization
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// WebSocket connection
let socket = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

// ============================================================================
// Simple Glass Effect System (Fallback Mode - Performance Optimized)
// ============================================================================

/**
 * Initialize simple glass effects - just adds fallback class for CSS
 * All effects are handled via CSS backdrop-filter without SVG filters
 */
function initAllLiquidGlass() {
    // Force fallback mode for all elements (better performance)
    document.body.classList.add('glass-fallback-mode');
}

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
    } else if (['paused', 'queueddl', 'stalleddl', 'stoppedup', 'stoppeddl'].includes(stateLower)) {
        return { emoji: '⚪', class: 'paused' };
    } else if (stateLower === 'error') {
        return { emoji: '🔴', class: 'error' };
    }
    return { emoji: '⚪', class: 'paused' };
}

// Global state
let currentTorrentHash = null;
let currentTorrentFiles = [];
let currentFilter = 'all';

// Touch event tracking for scroll detection
let touchStartX = 0;
let touchStartY = 0;
let touchStartTime = 0;
let isScrolling = false;
let touchTargetHash = null;
let touchTargetState = null;

// Render torrent card
function renderTorrent(torrent) {
    const statusInfo = getStatusInfo(torrent.state);
    const progress = Math.min(100, Math.max(0, torrent.progress));
    const metadata = torrent.metadata || null;
    
    // Build metadata elements
    let posterHtml = '';
    let metadataContentHtml = '';
    
    if (metadata) {
        if (metadata.poster_url) {
            posterHtml = `<img src="${escapeHtml(metadata.poster_url)}" alt="Poster" class="torrent-poster" onerror="this.style.display='none'">`;
        }
        
        const rating = metadata.rating ? `<div class="metadata-rating">⭐ ${metadata.rating.toFixed(1)}</div>` : '';
        const genres = metadata.genres && metadata.genres.length > 0 ? `<div class="metadata-genres">${metadata.genres.slice(0, 3).join(', ')}</div>` : '';
        const description = metadata.description ? `<div class="metadata-description">${escapeHtml(metadata.description.length > 150 ? metadata.description.substring(0, 150) + '...' : metadata.description)}</div>` : '';
        
        if (rating || genres || description) {
            metadataContentHtml = `
                <div class="metadata-content">
                    ${rating}
                    ${genres}
                    ${description}
                </div>
            `;
        }
    }
    
    return `
        <div class="torrent-card ${metadata ? 'has-metadata' : ''}" data-hash="${escapeHtml(torrent.hash)}" ontouchstart="handleTorrentTouchStart(event, '${escapeHtml(torrent.hash)}', '${escapeHtml(torrent.state)}')" ontouchend="handleTorrentTouchEnd(event)" onclick="handleTorrentClick(event, '${escapeHtml(torrent.hash)}', '${escapeHtml(torrent.state)}')">
            ${posterHtml}
            <div class="torrent-content-wrapper">
                <div class="torrent-header">
                    <div class="torrent-name">${escapeHtml(torrent.name)}</div>
                    <div class="torrent-status ${statusInfo.class}">
                        ${statusInfo.emoji} ${torrent.state}
                    </div>
                </div>
                ${metadataContentHtml}
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

// Update individual torrent card in place
function updateTorrentCard(cardElement, torrent) {
    const statusInfo = getStatusInfo(torrent.state);
    const progress = Math.min(100, Math.max(0, torrent.progress));
    
    // Update torrent name if changed
    const nameEl = cardElement.querySelector('.torrent-name');
    if (nameEl && nameEl.textContent !== torrent.name) {
        nameEl.textContent = torrent.name;
    }
    
    // Update status
    const statusEl = cardElement.querySelector('.torrent-status');
    if (statusEl) {
        const newStatusHtml = `${statusInfo.emoji} ${torrent.state}`;
        if (statusEl.innerHTML !== newStatusHtml) {
            statusEl.innerHTML = newStatusHtml;
            statusEl.className = `torrent-status ${statusInfo.class}`;
        }
    }
    
    // Update progress bar
    const progressBar = cardElement.querySelector('.progress-bar');
    if (progressBar) {
        const newWidth = `${progress}%`;
        if (progressBar.style.width !== newWidth) {
            progressBar.style.width = newWidth;
        }
    }
    
    // Update progress text
    const progressText = cardElement.querySelector('.progress-text');
    if (progressText) {
        const progressSpans = progressText.querySelectorAll('span');
        if (progressSpans.length >= 2) {
            const progressPercent = progressSpans[0];
            const sizeSpan = progressSpans[1];
            
            const newProgress = `${progress.toFixed(1)}%`;
            const newSize = formatBytes(torrent.size);
            
            if (progressPercent.textContent !== newProgress) {
                progressPercent.textContent = newProgress;
            }
            if (sizeSpan.textContent !== newSize) {
                sizeSpan.textContent = newSize;
            }
        }
    }
    
    // Update info items
    const infoItems = cardElement.querySelectorAll('.info-item .info-value');
    if (infoItems.length >= 6) {
        // Status
        if (infoItems[0].textContent !== torrent.state) {
            infoItems[0].textContent = torrent.state;
        }
        
        // Seeds
        const seedsValue = String(torrent.seeds);
        if (infoItems[1].textContent !== seedsValue) {
            infoItems[1].textContent = seedsValue;
            infoItems[1].className = `info-value ${torrent.seeds > 0 ? 'highlight' : ''}`;
        }
        
        // Peers
        const peersValue = String(torrent.peers);
        if (infoItems[2].textContent !== peersValue) {
            infoItems[2].textContent = peersValue;
        }
        
        // Down Speed
        const downSpeed = formatSpeed(torrent.dlspeed);
        if (infoItems[3].textContent !== downSpeed) {
            infoItems[3].textContent = downSpeed;
            infoItems[3].className = `info-value ${torrent.dlspeed > 0 ? 'highlight' : ''}`;
        }
        
        // Up Speed
        const upSpeed = formatSpeed(torrent.upspeed);
        if (infoItems[4].textContent !== upSpeed) {
            infoItems[4].textContent = upSpeed;
        }
        
        // ETA
        const eta = formatETA(torrent.eta);
        if (infoItems[5].textContent !== eta) {
            infoItems[5].textContent = eta;
            infoItems[5].className = `info-value ${torrent.eta > 0 && torrent.eta < 3600 ? 'warning' : ''}`;
        }
    }
    
    // Update event handlers if state changed
    const currentState = cardElement.getAttribute('onclick')?.match(/'([^']+)'\)/)?.[1];
    if (currentState !== torrent.state) {
        cardElement.setAttribute('ontouchstart', `handleTorrentTouchStart(event, '${escapeHtml(torrent.hash)}', '${escapeHtml(torrent.state)}')`);
        cardElement.setAttribute('onclick', `handleTorrentClick(event, '${escapeHtml(torrent.hash)}', '${escapeHtml(torrent.state)}')`);
    }
}

// Group and sort torrents by category and added date
function groupAndSortTorrents(torrents) {
    // Filter torrents based on current filter
    let filteredTorrents = torrents;
    if (currentFilter !== 'all') {
        filteredTorrents = torrents.filter(t => t.category === currentFilter);
    }
    
    // Group by category
    const categories = {
        'movies': [],
        'tv_shows': [],
        'other': []
    };
    
    filteredTorrents.forEach(torrent => {
        const category = torrent.category || 'other';
        if (categories[category]) {
            categories[category].push(torrent);
        } else {
            categories['other'].push(torrent);
        }
    });
    
    // Sort each category by added_on (newest first)
    Object.keys(categories).forEach(category => {
        categories[category].sort((a, b) => {
            const aTime = a.added_on || 0;
            const bTime = b.added_on || 0;
            return bTime - aTime; // Descending order (newest first)
        });
    });
    
    return categories;
}

// Get category display name
function getCategoryName(category) {
    const names = {
        'movies': '🎬 Movies',
        'tv_shows': '📺 TV Shows',
        'other': '📦 Other'
    };
    return names[category] || category;
}

// Update torrents list smoothly
function updateTorrentsList(torrents) {
    const loadingEl = document.getElementById('loading');
    const errorEl = document.getElementById('error');
    const torrentsListEl = document.getElementById('torrentsList');
    
    loadingEl.style.display = 'none';
    errorEl.style.display = 'none';
    
    if (torrents.length === 0) {
        // Only replace if not already showing empty state
        if (!torrentsListEl.querySelector('.empty-state')) {
            torrentsListEl.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <div class="empty-state-text">No torrents found</div>
                    <div class="empty-state-subtext">Add some torrents to see them here</div>
                </div>
            `;
        }
        updateStats(torrents);
        return;
    }
    
    // Group and sort torrents
    const categories = groupAndSortTorrents(torrents);
    
    // Check if any category has torrents
    const hasTorrents = Object.values(categories).some(cat => cat.length > 0);
    
    if (!hasTorrents) {
        if (!torrentsListEl.querySelector('.empty-state')) {
            torrentsListEl.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <div class="empty-state-text">No torrents in this category</div>
                    <div class="empty-state-subtext">Try selecting a different filter</div>
                </div>
            `;
        }
        updateStats(torrents);
        return;
    }
    
    // Remove empty state if present
    const emptyState = torrentsListEl.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }
    
    // Map existing cards by hash for efficient updates
    const existingCards = new Map();
    const allCards = torrentsListEl.querySelectorAll('.torrent-card');
    allCards.forEach(card => {
        const hash = card.dataset.hash;
        if (hash) {
            existingCards.set(hash, card);
        }
    });
    
    // Map new torrents by hash
    const newTorrentsMap = new Map();
    Object.values(categories).forEach(categoryTorrents => {
        categoryTorrents.forEach(torrent => {
            newTorrentsMap.set(torrent.hash, torrent);
        });
    });
    
    // Remove cards for torrents that no longer exist
    existingCards.forEach((card, hash) => {
        if (!newTorrentsMap.has(hash)) {
            card.remove();
            existingCards.delete(hash);
        }
    });
    
    // Define category order
    const categoryOrder = ['movies', 'tv_shows', 'other'];
    
    // Get or create category sections
    const categorySections = new Map();
    categoryOrder.forEach(category => {
        let categorySection = torrentsListEl.querySelector(`.category-section[data-category="${category}"]`);
        
        if (!categorySection) {
            // Create new category section
            categorySection = document.createElement('div');
            categorySection.className = 'category-section';
            categorySection.dataset.category = category;
            
            const categoryHeader = document.createElement('div');
            categoryHeader.className = 'category-header';
            categoryHeader.innerHTML = `
                <div class="category-title">${getCategoryName(category)}</div>
                <div class="category-count">0</div>
            `;
            categorySection.appendChild(categoryHeader);
            
            const categoryTorrentsContainer = document.createElement('div');
            categoryTorrentsContainer.className = 'torrents-list';
            categorySection.appendChild(categoryTorrentsContainer);
            
            // Insert in correct order
            let insertBefore = null;
            for (let i = categoryOrder.indexOf(category) + 1; i < categoryOrder.length; i++) {
                const nextCategory = categoryOrder[i];
                const nextSection = torrentsListEl.querySelector(`.category-section[data-category="${nextCategory}"]`);
                if (nextSection) {
                    insertBefore = nextSection;
                    break;
                }
            }
            if (insertBefore) {
                torrentsListEl.insertBefore(categorySection, insertBefore);
            } else {
                torrentsListEl.appendChild(categorySection);
            }
        }
        
        categorySections.set(category, categorySection);
    });
    
    // Update each category
    categoryOrder.forEach(category => {
        const categoryTorrents = categories[category];
        const categorySection = categorySections.get(category);
        const categoryTorrentsContainer = categorySection.querySelector('.torrents-list');
        const categoryCount = categorySection.querySelector('.category-count');
        
        // Update category count
        if (categoryCount) {
            categoryCount.textContent = categoryTorrents.length;
        }
        
        // Show/hide category section based on whether it has torrents
        if (categoryTorrents.length === 0) {
            categorySection.style.display = 'none';
            return;
        } else {
            categorySection.style.display = 'block';
        }
        
        // Map existing cards in this category by hash
        const existingCardsInCategory = new Map();
        categoryTorrentsContainer.querySelectorAll('.torrent-card').forEach(card => {
            const hash = card.dataset.hash;
            if (hash) {
                existingCardsInCategory.set(hash, card);
            }
        });
        
        // Update or add torrents in this category
        categoryTorrents.forEach((torrent, index) => {
            const existingCard = existingCardsInCategory.get(torrent.hash) || existingCards.get(torrent.hash);
            
            if (existingCard) {
                // Update existing card in place
                updateTorrentCard(existingCard, torrent);
                
                // Move card to correct position if needed
                const currentContainer = existingCard.closest('.torrents-list');
                if (currentContainer !== categoryTorrentsContainer) {
                    // Card is in wrong category, move it
                    categoryTorrentsContainer.appendChild(existingCard);
                } else {
                    // Card is in right category, check position
                    const currentIndex = Array.from(categoryTorrentsContainer.children).indexOf(existingCard);
                    if (currentIndex !== index) {
                        // Move to correct position
                        const referenceNode = categoryTorrentsContainer.children[index];
                        if (referenceNode && referenceNode !== existingCard) {
                            categoryTorrentsContainer.insertBefore(existingCard, referenceNode);
                        } else if (!referenceNode) {
                            categoryTorrentsContainer.appendChild(existingCard);
                        }
                    }
                }
                
                existingCardsInCategory.delete(torrent.hash);
            } else {
                // Create new card
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = renderTorrent(torrent);
                const newCard = tempDiv.firstElementChild;
                
                // Insert at correct position
                const referenceNode = categoryTorrentsContainer.children[index];
                if (referenceNode) {
                    categoryTorrentsContainer.insertBefore(newCard, referenceNode);
                } else {
                    categoryTorrentsContainer.appendChild(newCard);
                }
                
                existingCards.set(torrent.hash, newCard);
            }
        });
        
        // Remove cards that are no longer in this category
        existingCardsInCategory.forEach((card) => {
            card.remove();
            existingCards.delete(card.dataset.hash);
        });
    });
    
    updateStats(torrents);
}

// Set filter and update display
function setFilter(filter) {
    currentFilter = filter;
    
    // Update filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        if (btn.dataset.filter === filter) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    // Re-render torrents with new filter
    // We need to get the current torrents from the DOM or store them
    // For now, we'll trigger a re-render by getting the last received torrents
    if (window.lastTorrents) {
        updateTorrentsList(window.lastTorrents);
    }
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
    const chatId = getChatId();
    
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
    
    // Prepare auth and query data
    const authData = {
        initData: initData
    };
    const queryData = {
        initData: initData
    };
    
    // Add chat_id if available (for additional security layer)
    if (chatId) {
        authData.chatId = chatId;
        queryData.chatId = chatId;
    }
    
    // Connect to WebSocket server
    socket = io({
        auth: authData,
        query: queryData,
        extraHeaders: chatId ? {
            'X-Chat-ID': chatId
        } : {},
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
        window.lastTorrents = torrents; // Store for filtering
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
    initContextMenu();
    initAllLiquidGlass(); // Initialize liquid glass effects
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

// Touch event handlers for mobile devices
function handleTorrentTouchStart(event, hash, state) {
    const touch = event.touches[0];
    touchStartX = touch.clientX;
    touchStartY = touch.clientY;
    touchStartTime = Date.now();
    isScrolling = false;
    touchTargetHash = hash;
    touchTargetState = state;
}

function handleTorrentTouchEnd(event) {
    // Only process if we have a valid touch target
    if (!touchTargetHash || !touchTargetState) {
        return;
    }
    
    const touch = event.changedTouches[0];
    const touchEndX = touch.clientX;
    const touchEndY = touch.clientY;
    const touchDuration = Date.now() - touchStartTime;
    
    // Calculate movement distance
    const deltaX = Math.abs(touchEndX - touchStartX);
    const deltaY = Math.abs(touchEndY - touchStartY);
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
    
    // Only show menu if:
    // 1. Touch was quick (< 300ms) - indicates a tap, not a long press
    // 2. Movement was small (< 15px) - indicates a tap, not a scroll
    // 3. Not currently scrolling
    if (touchDuration < 300 && distance < 15 && !isScrolling) {
        event.preventDefault();
        event.stopPropagation();
        
        // Create a synthetic event object for showContextMenu
        const syntheticEvent = {
            currentTarget: event.target.closest('.torrent-card'),
            preventDefault: () => {},
            stopPropagation: () => {}
        };
        
        showContextMenu(syntheticEvent, touchTargetHash, touchTargetState);
    }
    
    // Reset touch tracking
    touchTargetHash = null;
    touchTargetState = null;
}

// Click handler for desktop
function handleTorrentClick(event, hash, state) {
    // On mobile, ignore click events that were triggered by touch
    // (browsers fire both touch and click events on mobile)
    if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
        const timeSinceTouch = Date.now() - touchStartTime;
        // If a touch event happened recently (< 500ms), ignore this click
        if (timeSinceTouch < 500) {
            return;
        }
    }
    
    showContextMenu(event, hash, state);
}

// Context Menu Functions
function showContextMenu(event, hash, state) {
    event.preventDefault();
    event.stopPropagation();
    
    const menu = document.getElementById('contextMenu');
    if (!menu) {
        console.error('Context menu not found in DOM');
        return;
    }
    
    const pauseItem = menu.querySelector('[data-action="pause"]');
    const resumeItem = menu.querySelector('[data-action="resume"]');
    
    if (!pauseItem || !resumeItem) {
        console.error('Context menu items not found');
        return;
    }
    
    // Show/hide pause/resume based on state
    // Pause is available for active states (downloading, uploading, seeding, etc.)
    // Resume is available for paused states
    const isPaused = ['paused', 'queueddl', 'stalleddl', 'stoppedup', 'stoppeddl'].includes(state.toLowerCase());
    const canPause = !isPaused && ['downloading', 'uploading', 'seeding', 'stalledup', 'queuedup'].includes(state.toLowerCase());
    
    pauseItem.style.display = canPause ? 'flex' : 'none';
    resumeItem.style.display = isPaused ? 'flex' : 'none';
    
    currentTorrentHash = hash;
    
    // Get the target element
    const targetElement = event.currentTarget || event.target.closest('.torrent-card');
    if (!targetElement) {
        console.error('Could not find target element');
        return;
    }
    
    // Position menu relative to the clicked element
    const rect = targetElement.getBoundingClientRect();
    const menuWidth = 180;
    const menuHeight = 200;
    
    let left = rect.left + (rect.width / 2) - (menuWidth / 2);
    let top = rect.bottom + 5;
    
    // Adjust if menu goes off screen
    if (left + menuWidth > window.innerWidth) {
        left = window.innerWidth - menuWidth - 10;
    }
    if (left < 10) {
        left = 10;
    }
    
    if (top + menuHeight > window.innerHeight) {
        top = rect.top - menuHeight - 5;
    }
    if (top < 10) {
        top = 10;
    }
    
    // Force display and positioning
    menu.style.display = 'block';
    menu.style.visibility = 'visible';
    menu.style.opacity = '1';
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
    menu.style.zIndex = '10000';
    menu.style.pointerEvents = 'auto';
    
    // Bring to front
    menu.style.position = 'fixed';
}

// Hide context menu when clicking outside
document.addEventListener('click', (e) => {
    const menu = document.getElementById('contextMenu');
    if (menu && menu.style.display === 'block' && !menu.contains(e.target)) {
        // Check if click is not on a torrent card
        if (!e.target.closest('.torrent-card')) {
            menu.style.display = 'none';
        }
    }
});

// Also hide on scroll
document.addEventListener('scroll', () => {
    const menu = document.getElementById('contextMenu');
    if (menu) {
        menu.style.display = 'none';
    }
    // Mark as scrolling to prevent menu from appearing
    isScrolling = true;
}, true);

// Detect touchmove to mark scrolling (prevents menu from appearing during scroll)
document.addEventListener('touchmove', (e) => {
    // Check if touch moved significantly
    if (e.touches && e.touches.length > 0) {
        const touch = e.touches[0];
        const deltaX = Math.abs(touch.clientX - touchStartX);
        const deltaY = Math.abs(touch.clientY - touchStartY);
        
        // If moved more than 10px, it's definitely a scroll
        if (deltaX > 10 || deltaY > 10) {
            isScrolling = true;
            // Clear touch target to prevent menu from showing
            touchTargetHash = null;
            touchTargetState = null;
        }
    }
}, { passive: true });

// Context menu actions - wait for DOM to be ready
let contextMenuInitialized = false;
function initContextMenu() {
    if (contextMenuInitialized) return;
    
    const menu = document.getElementById('contextMenu');
    if (!menu) {
        console.error('Context menu element not found');
        return;
    }
    
    menu.addEventListener('click', (e) => {
        e.stopPropagation();
        const action = e.target.closest('.context-menu-item')?.dataset.action;
        if (!action || !currentTorrentHash) return;
        
        menu.style.display = 'none';
        
        switch (action) {
            case 'pause':
                pauseTorrent(currentTorrentHash);
                break;
            case 'resume':
                resumeTorrent(currentTorrentHash);
                break;
            case 'files':
                showFileModal(currentTorrentHash);
                break;
            case 'delete':
                showDeleteModal(currentTorrentHash);
                break;
        }
    });
    
    contextMenuInitialized = true;
}

// API Functions
function getChatId() {
    // Extract chat_id from Telegram Web App initData
    try {
        const initData = tg.initData || tg.initDataUnsafe || '';
        if (initData) {
            // Parse initData to extract user.id (chat_id)
            const params = new URLSearchParams(initData);
            const userParam = params.get('user');
            if (userParam) {
                const userData = JSON.parse(userParam);
                return userData.id ? String(userData.id) : null;
            }
        }
        // Fallback: try to get from Telegram Web App user object
        if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
            return String(tg.initDataUnsafe.user.id);
        }
    } catch (error) {
        console.error('Error extracting chat_id:', error);
    }
    return null;
}

function getAuthHeader() {
    const initData = tg.initData || tg.initDataUnsafe || '';
    const chatId = getChatId();
    const headers = {
        'X-Telegram-Init-Data': initData,
        'Content-Type': 'application/json'
    };
    // Add chat_id header if available
    if (chatId) {
        headers['X-Chat-ID'] = chatId;
    }
    return headers;
}

async function pauseTorrent(hash) {
    try {
        const response = await fetch(`/api/torrents/${hash}/pause`, {
            method: 'POST',
            headers: getAuthHeader()
        });
        const data = await response.json();
        if (data.success) {
            tg.showPopup({ 
                title: 'Success', 
                message: 'Torrent paused',
                buttons: [{ type: 'ok' }]
            });
        } else {
            tg.showPopup({ 
                title: 'Error', 
                message: data.error || 'Failed to pause torrent',
                buttons: [{ type: 'ok' }]
            });
        }
    } catch (error) {
        tg.showPopup({ 
            title: 'Error', 
            message: 'Failed to pause torrent',
            buttons: [{ type: 'ok' }]
        });
    }
}

async function resumeTorrent(hash) {
    try {
        const response = await fetch(`/api/torrents/${hash}/resume`, {
            method: 'POST',
            headers: getAuthHeader()
        });
        const data = await response.json();
        if (data.success) {
            tg.showPopup({ 
                title: 'Success', 
                message: 'Torrent resumed',
                buttons: [{ type: 'ok' }]
            });
        } else {
            tg.showPopup({ 
                title: 'Error', 
                message: data.error || 'Failed to resume torrent',
                buttons: [{ type: 'ok' }]
            });
        }
    } catch (error) {
        tg.showPopup({ 
            title: 'Error', 
            message: 'Failed to resume torrent',
            buttons: [{ type: 'ok' }]
        });
    }
}

async function showFileModal(hash) {
    const modal = document.getElementById('fileModal');
    const fileList = document.getElementById('fileList');
    const title = document.getElementById('fileModalTitle');
    
    modal.style.display = 'flex';
    fileList.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading files...</p></div>';
    
    try {
        const initData = tg.initData || tg.initDataUnsafe || '';
        const chatId = getChatId();
        const headers = {
            'X-Telegram-Init-Data': initData
        };
        if (chatId) {
            headers['X-Chat-ID'] = chatId;
        }
        const response = await fetch(`/api/torrents/${hash}/files?_auth=${encodeURIComponent(initData)}`, {
            headers: headers
        });
        const data = await response.json();
        
        if (data.files) {
            currentTorrentFiles = data.files;
            currentTorrentHash = hash;
            
            // Get torrent name for title
            const torrents = Array.from(document.querySelectorAll('.torrent-card'));
            const torrentCard = torrents.find(card => card.dataset.hash === hash);
            const torrentName = torrentCard?.querySelector('.torrent-name')?.textContent || 'Torrent';
            title.textContent = `Files: ${torrentName.substring(0, 40)}${torrentName.length > 40 ? '...' : ''}`;
            
            renderFileList(data.files);
        } else {
            fileList.innerHTML = `<div class="error">❌ ${data.error || 'Failed to load files'}</div>`;
        }
    } catch (error) {
        fileList.innerHTML = '<div class="error">❌ Failed to load files</div>';
    }
}

function closeFileModal() {
    document.getElementById('fileModal').style.display = 'none';
    currentTorrentFiles = [];
}

function renderFileList(files) {
    const fileList = document.getElementById('fileList');
    
    if (files.length === 0) {
        fileList.innerHTML = '<div class="empty-state">No files found</div>';
        return;
    }
    
    fileList.innerHTML = files.map(file => {
        const priorityOptions = [
            { value: 0, label: 'Do not download' },
            { value: 1, label: 'Normal' },
            { value: 6, label: 'High' },
            { value: 7, label: 'Maximum' }
        ];
        
        const optionsHtml = priorityOptions.map(opt => 
            `<option value="${opt.value}" ${file.priority === opt.value ? 'selected' : ''}>${opt.label}</option>`
        ).join('');
        
        return `
            <div class="file-item">
                <div class="file-header">
                    <div class="file-name">${escapeHtml(file.name)}</div>
                    <div class="file-size">${formatBytes(file.size)}</div>
                </div>
                <div class="file-progress">Progress: ${file.progress.toFixed(1)}%</div>
                <div class="file-controls">
                    <label>Priority:</label>
                    <select class="priority-select" data-file-id="${file.id}" onchange="setFilePriority(${file.id}, this.value)">
                        ${optionsHtml}
                    </select>
                </div>
            </div>
        `;
    }).join('');
}

async function setFilePriority(fileId, priority) {
    if (!currentTorrentHash) return;
    
    try {
        const initData = tg.initData || tg.initDataUnsafe || '';
        const chatId = getChatId();
        const headers = {
            'X-Telegram-Init-Data': initData,
            'Content-Type': 'application/json'
        };
        if (chatId) {
            headers['X-Chat-ID'] = chatId;
        }
        const response = await fetch(`/api/torrents/${currentTorrentHash}/files/priority`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                file_ids: [fileId],
                priority: parseInt(priority)
            })
        });
        
        const data = await response.json();
        if (data.success) {
            // Update local state
            const file = currentTorrentFiles.find(f => f.id === fileId);
            if (file) {
                file.priority = parseInt(priority);
            }
        } else {
            tg.showPopup({ 
                title: 'Error', 
                message: data.error || 'Failed to set priority',
                buttons: [{ type: 'ok' }]
            });
            // Reload files to reset UI
            showFileModal(currentTorrentHash);
        }
    } catch (error) {
        tg.showPopup({ 
            title: 'Error', 
            message: 'Failed to set file priority',
            buttons: [{ type: 'ok' }]
        });
    }
}

function showDeleteModal(hash) {
    currentTorrentHash = hash;
    document.getElementById('deleteModal').style.display = 'flex';
    document.getElementById('deleteFiles').checked = false;
}

function closeDeleteModal() {
    document.getElementById('deleteModal').style.display = 'none';
    currentTorrentHash = null;
}

async function confirmDelete() {
    if (!currentTorrentHash) return;
    
    const deleteFiles = document.getElementById('deleteFiles').checked;
    
    try {
        const initData = tg.initData || tg.initDataUnsafe || '';
        const chatId = getChatId();
        const headers = {
            'X-Telegram-Init-Data': initData,
            'Content-Type': 'application/json'
        };
        if (chatId) {
            headers['X-Chat-ID'] = chatId;
        }
        const response = await fetch(`/api/torrents/${currentTorrentHash}/delete`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ delete_files: deleteFiles })
        });
        
        const data = await response.json();
        if (data.success) {
            tg.showPopup({ 
                title: 'Success', 
                message: 'Torrent deleted',
                buttons: [{ type: 'ok' }]
            });
            closeDeleteModal();
        } else {
            tg.showPopup({ 
                title: 'Error', 
                message: data.error || 'Failed to delete torrent',
                buttons: [{ type: 'ok' }]
            });
        }
    } catch (error) {
        tg.showPopup({ 
            title: 'Error', 
            message: 'Failed to delete torrent',
            buttons: [{ type: 'ok' }]
        });
    }
}

// Close modals when clicking overlay
document.getElementById('fileModal').addEventListener('click', (e) => {
    if (e.target.id === 'fileModal') {
        closeFileModal();
    }
});

document.getElementById('deleteModal').addEventListener('click', (e) => {
    if (e.target.id === 'deleteModal') {
        closeDeleteModal();
    }
});
