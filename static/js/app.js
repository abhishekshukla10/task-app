// Global state
let allTasks = [];
let currentFilter = 'overdue';

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (window.location.pathname === '/dashboard') {
        loadTasks();
        loadSmartBriefing();
        checkEveningReflection();
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
    } catch (error) {
        console.error('Error loading tasks:', error);
        showToast('Failed to load tasks');
    }
}

// Load AI-powered smart briefing
async function loadSmartBriefing() {
    try {
        const response = await fetch('/api/smart-briefing');
        const data = await response.json();
        
        document.getElementById('briefing-title').textContent = `${data.greeting}! Here's your day`;
        document.getElementById('briefing-text').textContent = data.message;
        
        if (data.top_priority) {
            document.getElementById('briefing-text').textContent += 
                ` Top priority: "${data.top_priority.title}" (${data.top_priority.days_overdue} day${data.top_priority.days_overdue !== 1 ? 's' : ''} overdue).`;
        }
        
        document.getElementById('briefing-card').style.display = 'block';
    } catch (error) {
        console.error('Error loading briefing:', error);
        // Fallback to client-side briefing
        generateClientBriefing();
    }
}

// Fallback client-side briefing
function generateClientBriefing() {
    const today = new Date().toISOString().split('T')[0];
    const hour = new Date().getHours();
    
    const overdue = allTasks.filter(t => 
        t.status !== 'Complete' && 
        t.status !== 'Dropped' && 
        t.due_date && 
        t.due_date < today
    );
    
    const todayTasks = allTasks.filter(t => 
        t.status !== 'Complete' && 
        t.status !== 'Dropped' && 
        t.due_date === today
    );
    
    let greeting = 'Good morning';
    if (hour >= 12 && hour < 17) greeting = 'Good afternoon';
    if (hour >= 17) greeting = 'Good evening';
    
    if (overdue.length > 0 || todayTasks.length > 0) {
        let briefing = `${greeting}! ${overdue.length} overdue, ${todayTasks.length} due today.`;
        document.getElementById('briefing-text').textContent = briefing;
        document.getElementById('briefing-card').style.display = 'block';
    }
}

// Check if evening reflection should show
function checkEveningReflection() {
    const hour = new Date().getHours();
    if (hour >= 20 && hour < 23) {  // 8pm - 11pm
        setTimeout(showReflectionPrompt, 5000);  // Show after 5 seconds
    }
}

// Show evening reflection prompt
async function showReflectionPrompt() {
    try {
        const response = await fetch('/api/reflection', { method: 'POST' });
        const data = await response.json();
        
        if (data.completed_count > 0) {
            const message = `🎉 You completed ${data.completed_count} task${data.completed_count !== 1 ? 's' : ''} today!\n\n${data.prompt}`;
            if (confirm(message)) {
                // Could open a reflection modal here
                console.log('Reflection accepted');
            }
        }
    } catch (error) {
        console.error('Error loading reflection:', error);
    }
}

// Render tasks based on current filter
function renderTasks() {
    const today = new Date().toISOString().split('T')[0];
    
    const overdueTasks = allTasks.filter(t => 
        t.status !== 'Complete' && 
        t.status !== 'Dropped' && 
        t.due_date && 
        t.due_date < today
    );
    
    const todayTasks = allTasks.filter(t => 
        t.status !== 'Complete' && 
        t.status !== 'Dropped' && 
        t.due_date === today
    );
    
    const upcomingTasks = allTasks.filter(t => 
        t.status !== 'Complete' && 
        t.status !== 'Dropped' && 
        (!t.due_date || t.due_date > today)
    );
    
    const doneTasks = allTasks.filter(t => 
        t.status === 'Complete' || t.status === 'Dropped'
    );
    
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
    
    document.getElementById('empty-state').style.display = hasVisibleTasks ? 'none' : 'block';
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
    
    if (task.due_date && task.due_date < today) {
        badgeClass = 'badge-overdue';
        const daysOverdue = Math.floor((new Date() - new Date(task.due_date)) / (1000 * 60 * 60 * 24));
        badgeText = `${daysOverdue} day${daysOverdue !== 1 ? 's' : ''} overdue`;
    } else if (task.due_date === today) {
        badgeClass = 'badge-today';
        badgeText = 'Due today';
    }
    
    const titleClass = task.due_date && task.due_date < today ? 'task-title overdue' : 'task-title';
    
    div.innerHTML = `
        <div class="task-header">
            <span class="task-num">${number}.</span>
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
    
    if (currentLang === 'en-IN') {
        currentLang = 'hi-IN';  // Switch to Hindi
        langBtn.textContent = '🇮🇳 HI';
        showToast('Voice language: Hindi');
    } else {
        currentLang = 'en-IN';  // Switch to English
        langBtn.textContent = '🇮🇳 EN';
        showToast('Voice language: English');
    }
    
    // Reset recognition with new language
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
            document.querySelector('.voice-btn[onclick="startVoice()"]').style.background = '#E24B4A';
            document.querySelector('.voice-btn[onclick="startVoice()"]').textContent = '🔴';
            showToast('Listening... Speak now');
        };
        
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            document.getElementById('chat-input').value = transcript;
            showToast(`Heard: "${transcript}"`);
            
            // Auto-send after 1 second
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
    
    // Update language before starting
    recognition.lang = currentLang;
    
    // Toggle listening
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
    const voiceBtn = document.querySelector('.voice-btn[onclick="startVoice()"]');
    if (voiceBtn) {
        voiceBtn.style.background = '#E6F1FB';
        voiceBtn.textContent = '🎤';
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
    document.getElementById('breakdown-btn').style.display = 'none';
    document.getElementById('stuck-btn').style.display = 'none';
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
    document.getElementById('breakdown-btn').style.display = 'inline-block';
    
    // Show stuck help button if task is old
    const today = new Date();
    const created = new Date(task.created_at);
    const daysOld = Math.floor((today - created) / (1000 * 60 * 60 * 24));
    if (daysOld >= 5 && task.status !== 'Complete') {
        document.getElementById('stuck-btn').style.display = 'inline-block';
    } else {
        document.getElementById('stuck-btn').style.display = 'none';
    }
    
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
            loadTasks();
            loadSmartBriefing();  // Refresh briefing
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
            loadTasks();
            loadSmartBriefing();  // Refresh briefing
        } else {
            showToast('Failed to delete task');
        }
    } catch (error) {
        console.error('Error deleting task:', error);
        showToast('Error deleting task');
    }
}

// AI Feature: Task Decomposition
async function breakdownTask() {
    const taskTitle = document.getElementById('task-title').value.trim();
    
    if (!taskTitle) {
        showToast('Please enter a task title first');
        return;
    }
    
    const btn = document.getElementById('breakdown-btn');
    const originalText = btn.textContent;
    btn.textContent = '⏳ Breaking down...';
    btn.disabled = true;
    
    try {
        const response = await fetch('/api/breakdown', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_title: taskTitle })
        });
        
        const data = await response.json();
        
        if (data.subtasks && data.subtasks.length > 0) {
            const subtasksText = data.subtasks.map((st, i) => `${i + 1}. ${st}`).join('\n');
            const currentRemarks = document.getElementById('task-remarks').value;
            document.getElementById('task-remarks').value = 
                `Subtasks:\n${subtasksText}\n\n${currentRemarks}`;
            
            showToast(`Broke down into ${data.subtasks.length} subtasks!`);
        } else {
            showToast('Could not break down task');
        }
    } catch (error) {
        console.error('Error breaking down task:', error);
        showToast('Failed to break down task');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// AI Feature: Stuck Task Coaching
async function getStuckHelp() {
    const taskId = document.getElementById('edit-task-id').value;
    const taskTitle = document.getElementById('task-title').value.trim();
    
    if (!taskTitle) {
        showToast('Please enter a task title first');
        return;
    }
    
    const task = allTasks.find(t => t.id == taskId);
    const daysStuck = task ? Math.floor((new Date() - new Date(task.created_at)) / (1000 * 60 * 60 * 24)) : 5;
    
    const btn = document.getElementById('stuck-btn');
    const originalText = btn.textContent;
    btn.textContent = '⏳ Getting help...';
    btn.disabled = true;
    
    try {
        const response = await fetch('/api/stuck-help', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_title: taskTitle, days_stuck: daysStuck })
        });
        
        const data = await response.json();
        
        if (data.suggestions && data.suggestions.length > 0) {
            let helpText = `💡 AI Coaching (stuck for ${daysStuck} days):\n\n`;
            data.suggestions.forEach((s, i) => {
                helpText += `${i + 1}. ${s}\n`;
            });
            if (data.encouragement) {
                helpText += `\n${data.encouragement}`;
            }
            
            const currentRemarks = document.getElementById('task-remarks').value;
            document.getElementById('task-remarks').value = 
                `${helpText}\n\n${currentRemarks}`;
            
            showToast('AI coaching added to notes!');
        } else {
            showToast('Could not generate coaching');
        }
    } catch (error) {
        console.error('Error getting stuck help:', error);
        showToast('Failed to get coaching');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

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
