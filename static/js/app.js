// Global state
let allTasks = [];
let currentFilter = 'overdue';

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (window.location.pathname === '/dashboard') {
        loadTasks();
        generateBriefing();
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

    // Render each section
    renderTaskSection('overdue', overdueTasks);
    renderTaskSection('today', todayTasks);
    renderTaskSection('upcoming', upcomingTasks);

    // Show/hide sections based on filter
    document.getElementById('overdue-section').style.display = currentFilter === 'overdue' ? 'block' : 'none';
    document.getElementById('today-section').style.display = currentFilter === 'today' ? 'block' : 'none';
    document.getElementById('upcoming-section').style.display = currentFilter === 'upcoming' ? 'block' : 'none';

    // Show empty state if no tasks
    const hasVisibleTasks =
        (currentFilter === 'overdue' && overdueTasks.length > 0) ||
        (currentFilter === 'today' && todayTasks.length > 0) ||
        (currentFilter === 'upcoming' && upcomingTasks.length > 0);

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
            Status: ${task.status} › ${task.repeat ? `| repeats ${task.repeat.toLowerCase()}` : ''}
            ${task.remarks ? `| ${escapeHtml(task.remarks).substring(0, 50)}...` : ''}
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

    document.getElementById('count-overdue').textContent = overdue;
    document.getElementById('count-today').textContent = todayCount;
    document.getElementById('count-upcoming').textContent = upcoming;
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

// Generate AI briefing
function generateBriefing() {
    const today = new Date().toISOString().split('T')[0];
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

    if (overdue.length > 0 || todayTasks.length > 0) {
        let briefing = `You have ${overdue.length} overdue task${overdue.length !== 1 ? 's' : ''} and ${todayTasks.length} due today.`;

        if (overdue.length > 0) {
            const topTask = overdue.sort((a, b) => new Date(a.due_date) - new Date(b.due_date))[0];
            const daysOverdue = Math.floor((new Date() - new Date(topTask.due_date)) / (1000 * 60 * 60 * 24));
            briefing += ` Your top priority: ${topTask.title} (overdue ${daysOverdue} day${daysOverdue !== 1 ? 's' : ''}).`;
        }

        document.getElementById('briefing-text').textContent = briefing;
        document.getElementById('briefing-card').style.display = 'block';
    }
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

// Voice input (placeholder for now)
function startVoice() {
    showToast('Voice input coming soon! Use text for now.');
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
        due_date: document.getElementById('task-due-date').value || null,
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
        } else {
            showToast('Failed to delete task');
        }
    } catch (error) {
        console.error('Error deleting task:', error);
        showToast('Error deleting task');
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
