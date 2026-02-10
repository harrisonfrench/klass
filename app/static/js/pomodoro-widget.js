/**
 * Pomodoro Timer Widget
 * A persistent floating timer that works across page navigation
 */

(function() {
    'use strict';

    const STORAGE_KEY = 'pomodoro_state';

    // Default settings (will be loaded from server)
    let settings = {
        work: 25,
        short_break: 5,
        long_break: 15,
        sessions_until_long: 4
    };

    let classes = [];
    let state = {
        isRunning: false,
        isPaused: false,
        sessionId: null,
        type: 'work',
        endTime: null,
        duration: 25,
        classId: null,
        completedSessions: 0
    };

    let timerInterval = null;
    let isExpanded = false;

    // Audio for notifications
    const notificationSound = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBhiR3euMGgAAVLjQmj8OBjWb89KZMgAAQKHl5ZAbAAAfruHkfwYAABy46+FuAAAAIML26mIAAAAiyPfoUwAAAC3V/fJDAAAAP+X/+C8AAABW9f/7GwAAAHD///8FAAAA');

    // DOM Elements (will be set after widget is created)
    let widget, timerDisplay, playBtn, typeLabel, progressBar;
    let expandedPanel, typeTabs, classSelect;

    /**
     * Initialize the widget
     */
    async function init() {
        createWidget();
        loadState();
        await fetchSettings();
        updateDisplay();

        // Start timer if it was running
        if (state.isRunning && state.endTime) {
            startInterval();
        }

        // Request notification permission
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

    /**
     * Create the widget DOM structure
     */
    function createWidget() {
        widget = document.createElement('div');
        widget.className = 'pomodoro-widget';
        widget.innerHTML = `
            <div class="pomo-collapsed" id="pomo-collapsed">
                <span class="pomo-time" id="pomo-time">25:00</span>
                <button class="pomo-play-btn" id="pomo-play-btn">
                    <svg viewBox="0 0 24 24" fill="currentColor" id="pomo-icon-play">
                        <polygon points="5,3 19,12 5,21"/>
                    </svg>
                    <svg viewBox="0 0 24 24" fill="currentColor" id="pomo-icon-pause" style="display:none;">
                        <rect x="6" y="4" width="4" height="16"/>
                        <rect x="14" y="4" width="4" height="16"/>
                    </svg>
                </button>
                <button class="pomo-expand-btn" id="pomo-expand-btn">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="6,9 12,15 18,9"/>
                    </svg>
                </button>
            </div>
            <div class="pomo-expanded" id="pomo-expanded" style="display:none;">
                <div class="pomo-expanded-header">
                    <span class="pomo-type-label" id="pomo-type-label">Focus</span>
                    <button class="pomo-close-btn" id="pomo-close-btn">&times;</button>
                </div>
                <div class="pomo-progress-bar">
                    <div class="pomo-progress-fill" id="pomo-progress-fill"></div>
                </div>
                <div class="pomo-time-large" id="pomo-time-large">25:00</div>
                <div class="pomo-controls">
                    <button class="pomo-ctrl-btn" id="pomo-reset-btn" title="Reset">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                            <path d="M3 3v5h5"/>
                        </svg>
                    </button>
                    <button class="pomo-ctrl-btn pomo-ctrl-primary" id="pomo-play-btn-lg">
                        <svg viewBox="0 0 24 24" fill="currentColor" id="pomo-icon-play-lg">
                            <polygon points="5,3 19,12 5,21"/>
                        </svg>
                        <svg viewBox="0 0 24 24" fill="currentColor" id="pomo-icon-pause-lg" style="display:none;">
                            <rect x="6" y="4" width="4" height="16"/>
                            <rect x="14" y="4" width="4" height="16"/>
                        </svg>
                    </button>
                    <button class="pomo-ctrl-btn" id="pomo-skip-btn" title="Skip">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polygon points="5,4 15,12 5,20" fill="currentColor"/>
                            <line x1="19" y1="5" x2="19" y2="19"/>
                        </svg>
                    </button>
                </div>
                <div class="pomo-type-tabs" id="pomo-type-tabs">
                    <button class="pomo-type-tab active" data-type="work">Focus</button>
                    <button class="pomo-type-tab" data-type="short_break">Short</button>
                    <button class="pomo-type-tab" data-type="long_break">Long</button>
                </div>
                <div class="pomo-class-select">
                    <select id="pomo-class-select">
                        <option value="">No class</option>
                    </select>
                </div>
                <div class="pomo-sessions" id="pomo-sessions"></div>
                <div class="pomo-settings-section">
                    <div class="pomo-settings-row">
                        <label>Focus</label>
                        <div class="pomo-duration-input">
                            <button class="pomo-dur-btn" data-type="work" data-dir="-1">-</button>
                            <span id="pomo-dur-work">25</span>
                            <button class="pomo-dur-btn" data-type="work" data-dir="1">+</button>
                        </div>
                    </div>
                    <div class="pomo-settings-row">
                        <label>Short</label>
                        <div class="pomo-duration-input">
                            <button class="pomo-dur-btn" data-type="short" data-dir="-1">-</button>
                            <span id="pomo-dur-short">5</span>
                            <button class="pomo-dur-btn" data-type="short" data-dir="1">+</button>
                        </div>
                    </div>
                    <div class="pomo-settings-row">
                        <label>Long</label>
                        <div class="pomo-duration-input">
                            <button class="pomo-dur-btn" data-type="long" data-dir="-1">-</button>
                            <span id="pomo-dur-long">15</span>
                            <button class="pomo-dur-btn" data-type="long" data-dir="1">+</button>
                        </div>
                    </div>
                </div>
                <div class="pomo-stats-link">
                    <span id="pomo-today-count">0</span> sessions today
                </div>
            </div>
        `;

        // Insert into navbar, to the left of username
        const userName = document.querySelector('.navbar-end .user-name');
        if (userName) {
            userName.parentNode.insertBefore(widget, userName);
        } else {
            const navbarEnd = document.querySelector('.navbar-end');
            if (navbarEnd) {
                navbarEnd.insertBefore(widget, navbarEnd.firstChild);
            } else {
                document.body.appendChild(widget);
            }
        }

        // Get references to elements
        timerDisplay = document.getElementById('pomo-time');
        playBtn = document.getElementById('pomo-play-btn');
        typeLabel = document.getElementById('pomo-type-label');
        progressBar = document.getElementById('pomo-progress-fill');
        expandedPanel = document.getElementById('pomo-expanded');
        typeTabs = document.getElementById('pomo-type-tabs');
        classSelect = document.getElementById('pomo-class-select');

        // Event listeners
        document.getElementById('pomo-collapsed').addEventListener('click', (e) => {
            if (e.target.closest('#pomo-play-btn')) return;
            if (e.target.closest('#pomo-expand-btn')) {
                toggleExpanded();
                return;
            }
        });

        playBtn.addEventListener('click', toggleTimer);
        document.getElementById('pomo-play-btn-lg').addEventListener('click', toggleTimer);
        document.getElementById('pomo-close-btn').addEventListener('click', () => toggleExpanded(false));
        document.getElementById('pomo-reset-btn').addEventListener('click', resetTimer);
        document.getElementById('pomo-skip-btn').addEventListener('click', skipSession);

        typeTabs.querySelectorAll('.pomo-type-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                if (!state.isRunning) {
                    setSessionType(tab.dataset.type);
                }
            });
        });

        classSelect.addEventListener('change', () => {
            state.classId = classSelect.value || null;
            saveState();
        });

        // Duration adjustment buttons
        document.querySelectorAll('.pomo-dur-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const type = btn.dataset.type;
                const dir = parseInt(btn.dataset.dir);
                adjustDuration(type, dir);
            });
        });
    }

    /**
     * Adjust timer duration
     */
    function adjustDuration(type, direction) {
        const min = 1;
        const max = type === 'work' ? 60 : 30;

        if (type === 'work') {
            settings.work = Math.max(min, Math.min(max, settings.work + direction));
            document.getElementById('pomo-dur-work').textContent = settings.work;
        } else if (type === 'short') {
            settings.short_break = Math.max(min, Math.min(max, settings.short_break + direction));
            document.getElementById('pomo-dur-short').textContent = settings.short_break;
        } else if (type === 'long') {
            settings.long_break = Math.max(min, Math.min(max, settings.long_break + direction));
            document.getElementById('pomo-dur-long').textContent = settings.long_break;
        }

        // Update current timer if not running
        if (!state.isRunning) {
            setSessionType(state.type);
        }

        // Save to server
        saveSettingsToServer();
    }

    /**
     * Save settings to server
     */
    async function saveSettingsToServer() {
        try {
            await fetch('/pomodoro/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    work_duration: settings.work,
                    short_break: settings.short_break,
                    long_break: settings.long_break,
                    sessions_until_long: settings.sessions_until_long
                })
            });
        } catch (e) {
            console.error('Failed to save settings:', e);
        }
    }

    /**
     * Fetch settings and classes from server
     */
    async function fetchSettings() {
        try {
            const response = await fetch('/pomodoro/active');
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    settings.work = data.settings.pomodoro_work_duration || 25;
                    settings.short_break = data.settings.pomodoro_short_break || 5;
                    settings.long_break = data.settings.pomodoro_long_break || 15;
                    settings.sessions_until_long = data.settings.pomodoro_sessions_until_long || 4;
                    classes = data.classes || [];
                    state.completedSessions = data.today_sessions || 0;

                    // Populate class dropdown
                    classSelect.innerHTML = '<option value="">No class</option>';
                    classes.forEach(cls => {
                        const opt = document.createElement('option');
                        opt.value = cls.id;
                        opt.textContent = cls.name;
                        classSelect.appendChild(opt);
                    });

                    // If no active timer, set default duration
                    if (!state.isRunning && !state.endTime) {
                        state.duration = settings.work;
                    }

                    // Update duration displays
                    document.getElementById('pomo-dur-work').textContent = settings.work;
                    document.getElementById('pomo-dur-short').textContent = settings.short_break;
                    document.getElementById('pomo-dur-long').textContent = settings.long_break;

                    // Update today's count
                    document.getElementById('pomo-today-count').textContent = state.completedSessions || data.today_sessions || 0;

                    updateSessionIndicators();
                }
            }
        } catch (e) {
            console.error('Failed to fetch pomodoro settings:', e);
        }
    }

    /**
     * Toggle expanded/collapsed state
     */
    function toggleExpanded(force) {
        isExpanded = force !== undefined ? force : !isExpanded;
        expandedPanel.style.display = isExpanded ? 'block' : 'none';
        document.getElementById('pomo-collapsed').classList.toggle('hidden', isExpanded);
    }

    /**
     * Set session type (work, short_break, long_break)
     */
    function setSessionType(type) {
        state.type = type;

        // Update duration based on type
        if (type === 'work') {
            state.duration = settings.work;
        } else if (type === 'short_break') {
            state.duration = settings.short_break;
        } else {
            state.duration = settings.long_break;
        }

        state.endTime = null;
        state.isRunning = false;
        state.isPaused = false;

        // Update tabs
        typeTabs.querySelectorAll('.pomo-type-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.type === type);
        });

        // Update label
        const labels = { work: 'Focus', short_break: 'Short Break', long_break: 'Long Break' };
        typeLabel.textContent = labels[type];

        // Update widget color
        widget.classList.remove('break', 'long-break');
        if (type === 'short_break') widget.classList.add('break');
        if (type === 'long_break') widget.classList.add('long-break');

        saveState();
        updateDisplay();
    }

    /**
     * Toggle timer (start/pause)
     */
    async function toggleTimer() {
        if (state.isRunning) {
            // Pause
            state.isPaused = true;
            state.isRunning = false;
            clearInterval(timerInterval);
            // Store remaining time
            const remaining = Math.max(0, state.endTime - Date.now());
            state.pausedRemaining = remaining;
            state.endTime = null;
        } else {
            // Start or resume
            if (state.isPaused && state.pausedRemaining) {
                state.endTime = Date.now() + state.pausedRemaining;
                state.pausedRemaining = null;
            } else {
                state.endTime = Date.now() + (state.duration * 60 * 1000);
            }
            state.isRunning = true;
            state.isPaused = false;

            // Start session on server if new session
            if (!state.sessionId) {
                try {
                    const response = await fetch('/pomodoro/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            type: state.type,
                            duration: state.duration,
                            class_id: state.classId
                        })
                    });
                    const data = await response.json();
                    if (data.success) {
                        state.sessionId = data.session_id;
                    }
                } catch (e) {
                    console.error('Failed to start session:', e);
                }
            }

            startInterval();
        }

        saveState();
        updateDisplay();
    }

    /**
     * Start the timer interval
     */
    function startInterval() {
        clearInterval(timerInterval);
        timerInterval = setInterval(() => {
            const remaining = state.endTime - Date.now();

            if (remaining <= 0) {
                clearInterval(timerInterval);
                completeSession();
            }

            updateDisplay();
        }, 1000);
    }

    /**
     * Complete the current session
     */
    async function completeSession() {
        state.isRunning = false;
        state.endTime = null;

        // Play sound
        try {
            notificationSound.play();
        } catch (e) {}

        // Show notification
        if (Notification.permission === 'granted') {
            new Notification('Pomodoro Complete!', {
                body: state.type === 'work' ? 'Time for a break!' : 'Ready to focus?',
            });
        }

        // Mark complete on server
        if (state.sessionId) {
            try {
                await fetch(`/pomodoro/complete/${state.sessionId}`, { method: 'POST' });
            } catch (e) {
                console.error('Failed to complete session:', e);
            }
        }

        // Update completed sessions and determine next type
        if (state.type === 'work') {
            state.completedSessions++;
            document.getElementById('pomo-today-count').textContent = state.completedSessions;
            updateSessionIndicators();

            if (state.completedSessions >= settings.sessions_until_long) {
                state.completedSessions = 0;
                setSessionType('long_break');
            } else {
                setSessionType('short_break');
            }
        } else {
            setSessionType('work');
        }

        state.sessionId = null;
        saveState();
        updateDisplay();
    }

    /**
     * Reset the timer
     */
    async function resetTimer() {
        if (state.sessionId) {
            try {
                await fetch(`/pomodoro/cancel/${state.sessionId}`, { method: 'POST' });
            } catch (e) {}
        }

        clearInterval(timerInterval);
        state.isRunning = false;
        state.isPaused = false;
        state.endTime = null;
        state.sessionId = null;
        state.pausedRemaining = null;

        saveState();
        updateDisplay();
    }

    /**
     * Skip to next session
     */
    async function skipSession() {
        if (state.sessionId) {
            try {
                await fetch(`/pomodoro/cancel/${state.sessionId}`, { method: 'POST' });
            } catch (e) {}
        }

        clearInterval(timerInterval);
        state.isRunning = false;
        state.endTime = null;
        state.sessionId = null;

        // Move to next type
        if (state.type === 'work') {
            if (state.completedSessions >= settings.sessions_until_long - 1) {
                setSessionType('long_break');
            } else {
                setSessionType('short_break');
            }
        } else {
            setSessionType('work');
        }

        saveState();
    }

    /**
     * Update the display
     */
    function updateDisplay() {
        let remaining;
        if (state.isRunning && state.endTime) {
            remaining = Math.max(0, state.endTime - Date.now());
        } else if (state.isPaused && state.pausedRemaining) {
            remaining = state.pausedRemaining;
        } else {
            remaining = state.duration * 60 * 1000;
        }

        const totalSeconds = Math.ceil(remaining / 1000);
        const mins = Math.floor(totalSeconds / 60);
        const secs = totalSeconds % 60;
        const timeStr = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;

        // Update both displays
        timerDisplay.textContent = timeStr;
        document.getElementById('pomo-time-large').textContent = timeStr;

        // Update progress bar
        const total = state.duration * 60 * 1000;
        const progress = ((total - remaining) / total) * 100;
        progressBar.style.width = `${progress}%`;

        // Update play/pause icons
        const showPause = state.isRunning;
        document.getElementById('pomo-icon-play').style.display = showPause ? 'none' : 'block';
        document.getElementById('pomo-icon-pause').style.display = showPause ? 'block' : 'none';
        document.getElementById('pomo-icon-play-lg').style.display = showPause ? 'none' : 'block';
        document.getElementById('pomo-icon-pause-lg').style.display = showPause ? 'block' : 'none';

        // Update running class for animation
        widget.classList.toggle('running', state.isRunning);
    }

    /**
     * Update session indicators (dots)
     */
    function updateSessionIndicators() {
        const container = document.getElementById('pomo-sessions');
        container.innerHTML = '';
        for (let i = 0; i < settings.sessions_until_long; i++) {
            const dot = document.createElement('span');
            dot.className = 'pomo-session-dot' + (i < state.completedSessions ? ' completed' : '');
            container.appendChild(dot);
        }
    }

    /**
     * Save state to localStorage
     */
    function saveState() {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }

    /**
     * Load state from localStorage
     */
    function loadState() {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved) {
                const parsed = JSON.parse(saved);
                Object.assign(state, parsed);

                // Check if timer expired while page was closed
                if (state.isRunning && state.endTime && state.endTime < Date.now()) {
                    // Timer finished while away - reset
                    state.isRunning = false;
                    state.endTime = null;
                    state.sessionId = null;
                }

                // Restore session type UI
                setSessionType(state.type);

                // Restore class selection
                if (state.classId) {
                    classSelect.value = state.classId;
                }
            }
        } catch (e) {
            console.error('Failed to load pomodoro state:', e);
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
