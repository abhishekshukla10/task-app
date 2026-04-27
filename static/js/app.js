// Global state
let allTasks = [];
let currentFilter = 'overdue';
let rescheduleSuggestions = null; // ✅ NEW: Store reschedule data

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (window.location.pathname === '/dashboard') {
        loadTasks();
        generateTop3Priorities(); // ✅ CHANGED: was loadSmartBriefing()
        // ✅ REMOVED: checkEveningReflection()
    }
});

// Load all tasks
async function loadTasks() {
    try {
        const response = await fetch('/api/tasks');
        const data = await response.json();
        allTasks = data.tasks;
        renderTasks();
        updateCounts();
        updateFooter();
        generateTop3Priorities(); // ✅ NEW: Update briefing when tasks load
        checkRescheduleHint(); // ✅ NEW: Check if reschedule hint should show
    } catch (error) {
        console.error('Error loading tasks:', error);
        showToast('Failed to load tasks');
    }
}

// ✅ NEW FUNCTION: Generate Top 3 Priorities Briefing (replaces loadSmartBriefing + generateClientBriefing)
function generateTop3Priorities() {
    const today = new Date().toISOString().split('T')[0];

    // Get all active tasks
    const activeTasks = allTasks.filter(t =>
        t.status !== 'Complete' && t.status !== 'Dropped'
    );

    if (activeTasks.length === 0) {
        document.getElementById('briefing-card').style.display = 'none';
        return;
    }

    // ✅ Sort by due_date (earliest first), then by created_at (oldest first)
    const sortByDateAndCreation = (a, b) => {
        // Primary sort: by due date
        if (!a.due_date && !b.due_date) {
            // Both have no date, sort by creation
            return new Date(a.created_at) - new Date(b.created_at);
        }
        if (!a.due_date) return 1;  // Tasks without dates go last
        if (!b.due_date) return -1;

        const dateCompare = a.due_date.localeCompare(b.due_date);
        if (dateCompare !== 0) return dateCompare;

        // Secondary sort: if same date, sort by creation date (oldest first)
        return new Date(a.created_at) - new Date(b.created_at);
    };

    const overdue = activeTasks.filter(t => t.due_date && t.due_date < today)
        .sort(sortByDateAndCreation);
    const todayTasks = activeTasks.filter(t => t.due_date === today)
        .sort(sortByDateAndCreation);
    const upcoming = activeTasks.filter(t => !t.due_date || t.due_date > today)
        .sort(sortByDateAndCreation);

    let top3 = [];

    // ✅ PRIORITY 1: Overdue + starred
    const overdueStarred = overdue.filter(t => t.priority);
    if (overdueStarred.length > 0) {
        top3.push(overdueStarred[0]);
    }

    // ✅ PRIORITY 2: Today + starred
    if (top3.length < 3) {
        const todayStarred = todayTasks.filter(t => t.priority);
        if (todayStarred.length > 0) top3.push(todayStarred[0]);
    }

    // ✅ PRIORITY 3: Upcoming + starred (YOUR FIX!)
    if (top3.length < 3) {
        const upcomingStarred = upcoming.filter(t => t.priority);
        if (upcomingStarred.length > 0) {
            // Add as many starred upcoming as needed to fill top 3
            const needed = 3 - top3.length;
            top3.push(...upcomingStarred.slice(0, needed));
        }
    }

    // ✅ PRIORITY 4: Any overdue (fallback)
    if (top3.length < 3 && overdue.length > 0) {
        const notInTop3 = overdue.filter(t => !top3.includes(t));
        if (notInTop3.length > 0) top3.push(notInTop3[0]);
    }

    // ✅ PRIORITY 5: Any today (fallback)
    if (top3.length < 3 && todayTasks.length > 0) {
        const notInTop3 = todayTasks.filter(t => !top3.includes(t));
        if (notInTop3.length > 0) top3.push(notInTop3[0]);
    }

    // ✅ PRIORITY 6: Any upcoming (fallback)
    if (top3.length < 3 && upcoming.length > 0) {
        const notInTop3 = upcoming.filter(t => !top3.includes(t));
        const needed = 3 - top3.length;
        top3.push(...notInTop3.slice(0, needed));
    }

    // Build briefing text (max 3 lines)
    let briefingHTML = '';
    top3.slice(0, 3).forEach((task, index) => {
        const star = task.priority ? '★ ' : '';
        const title = task.title.length > 35 ? task.title.substring(0, 35) + '...' : task.title;

        let badge = '';
        if (task.due_date) {
            const dueDate = new Date(task.due_date);
            if (task.due_date < today) {
                const daysOverdue = Math.floor((new Date() - dueDate) / (1000 * 60 * 60 * 24));
                badge = `(${daysOverdue}d overdue)`;
            } else if (task.due_date === today) {
                badge = '(today)';
            } else {
                badge = `(${formatDate(task.due_date)})`;
            }
        }

        briefingHTML += `${index + 1}. ${star}${title} ${badge}<br>`;
    });

    // Update briefing card
    document.getElementById('briefing-title').textContent = "Let's do it.. ⚡";
    document.getElementById('briefing-text').innerHTML = briefingHTML || 'No tasks yet. Add your first task!';
    document.getElementById('briefing-card').style.display = 'block';
}

// ✅ REMOVED: loadSmartBriefing() - replaced by generateTop3Priorities()
// ✅ REMOVED: generateClientBriefing() - replaced by generateTop3Priorities()
// ✅ REMOVED: checkEveningReflection() - no longer needed
// ✅ REMOVED: showReflectionPrompt() - no longer needed

// ✅ NEW FUNCTION: Check if smart reschedule hint should show
function checkRescheduleHint() {
    const today = new Date().toISOString().split('T')[0];
    const overdueTasks = allTasks.filter(t =>
        t.status !== 'Complete' &&
        t.status !== 'Dropped' &&
        t.due_date &&
        t.due_date < today
    );

    const hint = document.getElementById('reschedule-hint');
    if (hint) {
        if (overdueTasks.length >= 5) {
            document.getElementById('reschedule-count').textContent = overdueTasks.length;
            hint.style.display = 'block';
        } else {
            hint.style.display = 'none';
        }
    }
}

// ✅ NEW FUNCTION: Show smart reschedule modal
async function showRescheduleModal() {
    try {
        const response = await fetch('/api/smart-reschedule', { method: 'POST' });
        const data = await response.json();

        if (!data.suggestions || data.suggestions.length === 0) {
            showToast('No rescheduling suggestions available');
            return;
        }

        rescheduleSuggestions = data.suggestions;

        // Build suggestions HTML grouped by date
        let html = '';
        const grouped = {};

        data.suggestions.forEach(s => {
            if (!grouped[s.new_date]) {
                grouped[s.new_date] = [];
            }
            grouped[s.new_date].push(s);
        });

        Object.keys(grouped).forEach(date => {
            const tasks = grouped[date];
            html += `
                <div style="margin-bottom: 16px;">
                    <div style="font-size: 13px; font-weight: 500; color: #5F5E5A; margin-bottom: 8px;">
                        ${formatDate(date)} (${tasks.length} task${tasks.length !== 1 ? 's' : ''})
                    </div>
            `;

            tasks.forEach(t => {
                const task = allTasks.find(task => task.id === t.task_id);
                if (task) {
                    html += `
                        <div style="font-size: 12px; color: #888780; margin-left: 12px; margin-bottom: 4px;">
                            • ${task.title.substring(0, 40)}${task.title.length > 40 ? '...' : ''}
                            <br><span style="font-size: 11px; color: #B4B2A9;">${t.reason}</span>
                        </div>
                    `;
                }
            });

            html += `</div>`;
        });

        document.getElementById('reschedule-suggestions').innerHTML = html;
        document.getElementById('reschedule-modal').style.display = 'flex';

    } catch (error) {
        console.error('Error loading reschedule suggestions:', error);
        showToast('Failed to load suggestions');
    }
}

// ✅ NEW FUNCTION: Close reschedule modal
function closeRescheduleModal() {
    document.getElementById('reschedule-modal').style.display = 'none';
    rescheduleSuggestions = null;
}

// ✅ NEW FUNCTION: Apply reschedule suggestions
async function applyReschedule() {
    if (!rescheduleSuggestions || rescheduleSuggestions.length === 0) {
        showToast('No suggestions to apply');
        return;
    }

    try {
        let successCount = 0;
        for (const suggestion of rescheduleSuggestions) {
            const response = await fetch(`/api/tasks/${suggestion.task_id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ due_date: suggestion.new_date })
            });

            if (response.ok) {
                successCount++;
            }
        }

        closeRescheduleModal();
        showToast(`✓ Rescheduled ${successCount} tasks`);
        loadTasks(); // Reload to show updated dates

    } catch (error) {
        console.error('Error applying reschedule:', error);
        showToast('Failed to reschedule tasks');
    }
}

// Render tasks based on current filter
function renderTasks() {
    const today = new Date().toISOString().split('T')[0];

    let overdueTasks = allTasks.filter(t =>
        t.status !== 'Complete' &&
        t.status !== 'Dropped' &&
        t.due_date &&
        t.due_date < today
    );

    let todayTasks = allTasks.filter(t =>
        t.status !== 'Complete' &&
        t.status !== 'Dropped' &&
        t.due_date === today
    );

    let upcomingTasks = allTasks.filter(t =>
        t.status !== 'Complete' &&
        t.status !== 'Dropped' &&
        (!t.due_date || t.due_date > today)
    );

    const doneTasks = allTasks.filter(t =>
        t.status === 'Complete' || t.status === 'Dropped'
    );

    // Sort by priority
    overdueTasks = sortTasksByPriority(overdueTasks);
    todayTasks = sortTasksByPriority(todayTasks);
    upcomingTasks = sortTasksByPriority(upcomingTasks);

    // Render each section
    renderTaskSection('overdue', overdueTasks);
    renderTaskSection('today', todayTasks);
    renderTaskSection('upcoming', upcomingTasks);
    renderTaskSection('done', doneTasks);

    // Show/hide sections based on filter
    document.getElementById('overdue-section').style.display = currentFilter === 'overdue' ? 'block' : 'none';
    document.getElementById('today-section').style.display = currentFilter === 'today' ? 'block' : 'none';
    document.getElementById('upcoming-section').style.display = currentFilter === 'upcoming' ? 'block' : 'none';
    document.getElementById('done-section').style.display = currentFilter === 'done' ? 'block' : 'none';

    // Show empty state if no tasks
    const hasVisibleTasks =
        (currentFilter === 'overdue' && overdueTasks.length > 0) ||
        (currentFilter === 'today' && todayTasks.length > 0) ||
        (currentFilter === 'upcoming' && upcomingTasks.length > 0) ||
        (currentFilter === 'done' && doneTasks.length > 0);

    // ✅ Context-aware empty messages
    const emptyMessages = {
        'overdue': '🎉 All caught up! No overdue tasks.',
        'today': '☀️ Nothing due today. Enjoy your day!',
        'upcoming': '📅 No upcoming tasks scheduled.',
        'done': '🏁 No completed tasks yet. Get started!'
    };

    const emptyElement = document.getElementById('empty-state');
    if (hasVisibleTasks) {
        emptyElement.style.display = 'none';
    } else {
        emptyElement.innerHTML = `<p>${emptyMessages[currentFilter]}</p>`;
        emptyElement.style.display = 'block';
    }
}

// Render a task section
function renderTaskSection(section, tasks) {
    const container = document.getElementById(`${section}-tasks`);
    container.innerHTML = '';

    tasks.forEach((task, index) => {
        const taskEl = createTaskCard(task, index + 1);
        container.appendChild(taskEl);
    });
}

// Create task card element
function createTaskCard(task, number) {
    const div = document.createElement('div');
    div.className = 'task';
    div.onclick = () => editTask(task.id);

    const today = new Date().toISOString().split('T')[0];
    let badgeClass = 'badge-upcoming';
    let badgeText = task.due_date ? formatDate(task.due_date) : '';

    // Only show overdue for pending tasks
    if (task.status !== 'Complete' && task.status !== 'Dropped') {
        if (task.due_date && task.due_date < today) {
            badgeClass = 'badge-overdue';
            const daysOverdue = Math.floor((new Date() - new Date(task.due_date)) / (1000 * 60 * 60 * 24));
            badgeText = `${daysOverdue}d over`;
        } else if (task.due_date === today) {
            badgeClass = 'badge-today';
            badgeText = 'Due today';
        }
    } else {
        // For completed tasks, just show the date
        if (task.due_date) {
            badgeText = formatDate(task.due_date);
            badgeClass = 'badge-upcoming';
        }
    }

    const titleClass = (task.due_date && task.due_date < today && task.status !== 'Complete' && task.status !== 'Dropped') ? 'task-title overdue' : 'task-title';

    // With checkbox
    div.innerHTML = `
        <div class="task-header">
            <span class="task-num">${number}.</span>
            <div class="task-checkbox" onclick="event.stopPropagation(); completeTaskQuick(${task.id})"></div>
            <span class="task-star">${task.priority ? '★' : '☆'}</span>
            <span class="${titleClass}">${escapeHtml(task.title)}</span>
            ${badgeText ? `<span class="task-badge ${badgeClass}">${badgeText}</span>` : ''}
        </div>
        <div class="task-meta">
            Status: ${task.status}${task.repeat ? ` | repeats ${task.repeat.toLowerCase()}` : ''}${task.remarks ? ` | ${escapeHtml(task.remarks).substring(0, 50)}...` : ''}
        </div>
    `;

    return div;
}

// Update counts in pills
function updateCounts() {
    const today = new Date().toISOString().split('T')[0];

    const overdue = allTasks.filter(t =>
        t.status !== 'Complete' &&
        t.status !== 'Dropped' &&
        t.due_date &&
        t.due_date < today
    ).length;

    const todayCount = allTasks.filter(t =>
        t.status !== 'Complete' &&
        t.status !== 'Dropped' &&
        t.due_date === today
    ).length;

    const upcoming = allTasks.filter(t =>
        t.status !== 'Complete' &&
        t.status !== 'Dropped' &&
        (!t.due_date || t.due_date > today)
    ).length;

    const done = allTasks.filter(t =>
        t.status === 'Complete' || t.status === 'Dropped'
    ).length;

    document.getElementById('count-overdue').textContent = overdue;
    document.getElementById('count-today').textContent = todayCount;
    document.getElementById('count-upcoming').textContent = upcoming;
    document.getElementById('count-done').textContent = done;
}

// Update footer text
function updateFooter() {
    const active = allTasks.filter(t => t.status !== 'Complete' && t.status !== 'Dropped').length;
    document.getElementById('footer-text').textContent = `${active} active task${active !== 1 ? 's' : ''} · auto-archived after 30 days`;
}

// Filter tasks
function filterTasks(filter) {
    currentFilter = filter;

    // Update active pill
    document.querySelectorAll('.pill').forEach(pill => pill.classList.remove('active'));
    event.target.classList.add('active');

    renderTasks();
}

// Chat input handler
function handleChatKeyPress(event) {
    if (event.key === 'Enter') {
        sendChat();
    }
}

function setChat(message) {
    document.getElementById('chat-input').value = message;
    sendChat();
}

async function sendChat() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();

    if (!message) return;

    input.value = '';

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        const data = await response.json();

        if (data.type === 'task_created') {
            showToast('Task created: ' + data.task.title);
            loadTasks();
        } else if (data.type === 'filter') {
            filterTasks(data.filter);
            showToast(data.message);
        } else if (data.message) {
            showToast(data.message);
        }
    } catch (error) {
        console.error('Error sending chat:', error);
        showToast('Failed to process command');
    }
}

// Voice input using Web Speech API
let recognition = null;
let isListening = false;
let currentLang = 'en-IN';  // Default: Indian English

function toggleVoiceLanguage() {
    const langBtn = document.querySelector('.conv-bar button[onclick="toggleVoiceLanguage()"]');
    const chatInput = document.getElementById('chat-input');

    if (currentLang === 'en-IN') {
        currentLang = 'hi-IN';
        langBtn.textContent = '🇮🇳 HI';
        chatInput.placeholder = 'कुछ भी पूछें या आदेश दें...';
        showToast('भाषा: हिंदी');
    } else {
        currentLang = 'en-IN';
        langBtn.textContent = '🇮🇳 EN';
        chatInput.placeholder = 'Ask or command anything...';
        showToast('Language: English');
    }

    if (recognition) {
        recognition.lang = currentLang;
    }
}

function startVoice() {
    // Check browser support
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        showToast('Voice input not supported in this browser. Use Chrome/Edge.');
        return;
    }

    // Initialize recognition
    if (!recognition) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.lang = currentLang;
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = () => {
            isListening = true;
            const voiceBtn = document.querySelector('.voice-btn');
            if (voiceBtn) {
                voiceBtn.classList.add('listening'); // ✅ CHANGED: add class for pulsing animation
            }
            showToast('Listening... Speak now');
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            document.getElementById('chat-input').value = transcript;
            showToast(`Heard: "${transcript}"`);

            setTimeout(() => {
                sendChat();
            }, 1000);
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            if (event.error === 'no-speech') {
                showToast('No speech detected. Try again.');
            } else if (event.error === 'not-allowed') {
                showToast('Microphone access denied. Enable in browser settings.');
            } else {
                showToast('Voice input error. Try again.');
            }
            resetVoiceButton();
        };

        recognition.onend = () => {
            resetVoiceButton();
        };
    }

    recognition.lang = currentLang;

    if (isListening) {
        recognition.stop();
        resetVoiceButton();
    } else {
        try {
            recognition.start();
        } catch (error) {
            console.error('Error starting recognition:', error);
            showToast('Could not start voice input');
            resetVoiceButton();
        }
    }
}

function resetVoiceButton() {
    isListening = false;
    const voiceBtn = document.querySelector('.voice-btn');
    if (voiceBtn) {
        voiceBtn.classList.remove('listening'); // ✅ CHANGED: remove class to stop pulsing
    }
}

// Modal functions
function openAddModal() {
    document.getElementById('modal-title').textContent = 'Add Task';
    document.getElementById('edit-task-id').value = '';
    document.getElementById('task-title').value = '';
    document.getElementById('task-status').value = 'Pending';
    document.getElementById('task-due-date').value = '';
    document.getElementById('task-reminder').value = '';
    document.getElementById('task-repeat').value = '';
    document.getElementById('task-priority').checked = false;
    document.getElementById('task-remarks').value = '';
    document.getElementById('delete-btn').style.display = 'none';
    // ✅ REMOVED: breakdown-btn and stuck-btn references (buttons don't exist in updated HTML)
    document.getElementById('task-modal').style.display = 'flex';
}

function editTask(taskId) {
    const task = allTasks.find(t => t.id === taskId);
    if (!task) return;

    document.getElementById('modal-title').textContent = 'Edit Task';
    document.getElementById('edit-task-id').value = task.id;
    document.getElementById('task-title').value = task.title;
    document.getElementById('task-status').value = task.status;
    document.getElementById('task-due-date').value = task.due_date || '';
    document.getElementById('task-reminder').value = task.reminder_time ? task.reminder_time.slice(0, 16) : '';
    document.getElementById('task-repeat').value = task.repeat || '';
    document.getElementById('task-priority').checked = task.priority;
    document.getElementById('task-remarks').value = task.remarks || '';
    document.getElementById('delete-btn').style.display = 'block';
    // ✅ REMOVED: No longer showing breakdown-btn or stuck-btn
    document.getElementById('task-modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('task-modal').style.display = 'none';
}

async function saveTask() {
    const taskId = document.getElementById('edit-task-id').value;
    const title = document.getElementById('task-title').value.trim();
    const dueDate = document.getElementById('task-due-date').value;

    if (!title) {
        showToast('Title is required');
        return;
    }

    if (!dueDate) {
        showToast('Due date is required');
        return;
    }

    const taskData = {
        title,
        status: document.getElementById('task-status').value,
        due_date: dueDate,
        reminder_time: document.getElementById('task-reminder').value || null,
        repeat: document.getElementById('task-repeat').value || null,
        priority: document.getElementById('task-priority').checked,
        remarks: document.getElementById('task-remarks').value.trim() || null
    };

    try {
        const url = taskId ? `/api/tasks/${taskId}` : '/api/tasks';
        const method = taskId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
        });

        if (response.ok) {
            showToast(taskId ? 'Task updated' : 'Task created');
            closeModal();
            loadTasks(); // ✅ CHANGED: loadSmartBriefing() now called inside loadTasks()
        } else {
            showToast('Failed to save task');
        }
    } catch (error) {
        console.error('Error saving task:', error);
        showToast('Error saving task');
    }
}

async function deleteTask() {
    const taskId = document.getElementById('edit-task-id').value;
    if (!taskId || !confirm('Are you sure you want to delete this task?')) return;

    try {
        const response = await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });

        if (response.ok) {
            showToast('Task deleted');
            closeModal();
            loadTasks(); // ✅ CHANGED: loadSmartBriefing() now called inside loadTasks()
        } else {
            showToast('Failed to delete task');
        }
    } catch (error) {
        console.error('Error deleting task:', error);
        showToast('Error deleting task');
    }
}

// ✅ REMOVED FUNCTION: breakdownTask() - AI feature removed
// ✅ REMOVED FUNCTION: getStuckHelp() - AI feature removed

// Utility functions
function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    if (dateStr === today.toISOString().split('T')[0]) return 'Today';
    if (dateStr === tomorrow.toISOString().split('T')[0]) return 'Tomorrow';

    const month = date.toLocaleDateString('en-US', { month: 'short' });
    const day = date.getDate();
    return `${month} ${day}`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// NEW FUNCTIONS - Added for new features
// ============================================

// Language selection for voice
function selectLanguage(lang) {
    const chatInput = document.getElementById('chat-input');
    const smartPills = document.querySelectorAll('.smart-pills button');
    
    if (lang === 'en') {
        currentLang = 'en-IN';
        document.getElementById('lang-en').classList.add('active');
        document.getElementById('lang-hi').classList.remove('active');
        
        // ✅ Update UI to English
        chatInput.placeholder = "'mark task 2 done' or 'buy milk tomorrow'";
        if (smartPills.length >= 4) {
            smartPills[0].textContent = 'Today';
            smartPills[1].textContent = 'Tomorrow';
            smartPills[3].textContent = '+2d';
        }
        showToast('Language: English');
    } else {
        currentLang = 'hi-IN';
        document.getElementById('lang-hi').classList.add('active');
        document.getElementById('lang-en').classList.remove('active');
        
        // ✅ Update UI to Hindi
        chatInput.placeholder = "कल घर का सामान खरीदना है";
        if (smartPills.length >= 4) {
            smartPills[0].textContent = 'आज';
            smartPills[1].textContent = 'कल';
            smartPills[3].textContent = '+2दिन';
        }
        showToast('भाषा: हिंदी');
    }

    if (recognition) {
        recognition.lang = currentLang;
    }
}

// Smart Pills Handler
function addQuickDate(type) {
    const input = document.getElementById('chat-input');
    let text = input.value.trim().toLowerCase();

    // Check if date already exists
    const dateKeywords = [
        'today', 'tomorrow',
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
        'next week', 'next month',
        'in 2 days', 'in 3 days', 'in 4 days', 'in 5 days',
        'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
    ];

    const hasDateAlready = dateKeywords.some(keyword => text.includes(keyword));

    if (hasDateAlready) {
        showToast('⚠️ Date already mentioned in task');
        return;
    }

    // Add date from pill
    if (type === 'today') {
        input.value = input.value.trim() + ' today';
    } else if (type === 'tomorrow') {
        input.value = input.value.trim() + ' tomorrow';
    } else if (type === 'important') {
        input.value = input.value.trim() + ' urgent';
    } else if (type === '+2days') {
        input.value = input.value.trim() + ' in 2 days';
    }

    sendChat();
}

// Quick Complete via Checkbox
async function completeTaskQuick(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'Complete' })
        });

        if (response.ok) {
            showToast('✓ Task completed');
            loadTasks();
        } else {
            showToast('Failed to complete task');
        }
    } catch (error) {
        console.error('Error completing task:', error);
        showToast('Error completing task');
    }
}

// Sort tasks by priority
function sortTasksByPriority(tasks) {
    return tasks.sort((a, b) => {
        if (a.priority !== b.priority) {
            return b.priority - a.priority;
        }
        if (a.due_date && b.due_date) {
            const dateCompare = new Date(a.due_date) - new Date(b.due_date);
            if (dateCompare !== 0) {
                return dateCompare;
            }
            return a.id - b.id;
        }
        if (a.due_date) return -1;
        if (b.due_date) return 1;
        return a.id - b.id;
    });
}
