async function sendChat() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    input.value = '';
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message: message,
                current_filter: currentFilter
            })
        });
        
        const data = await response.json();
        
        if (data.type === 'task_created') {
            showToast('✓ Task created: ' + data.task.title);
            loadTasks();
        } else if (data.type === 'task_updated') {
            showToast(data.message);
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
