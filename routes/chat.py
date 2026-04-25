from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Task
import os
import json
from datetime import datetime, timedelta
import requests
import re

chat_bp = Blueprint('chat', __name__)


def parse_with_groq(user_message):
    """Parse natural language input using Groq API"""

    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    if not GROQ_API_KEY:
        return None

    # System prompt for task parsing
    system_prompt = """You are a task parser. Convert natural language to task JSON.

Rules:
- Extract: title, due_date, priority, status, repeat
- Due date formats: "tomorrow", "next monday", "25th april", "in 3 days"
- Priority: true if "important", "urgent", "asap", "critical"
- Status: "Pending" (default), "In Progress", "Completed"
- Repeat: "Daily", "Weekly", "Monthly" or null

Output ONLY valid JSON, no explanations:
{
  "title": "task description",
  "due_date": "2026-04-21" or null,
  "priority": true/false,
  "status": "Pending",
  "repeat": null or "Daily"/"Weekly"/"Monthly"
}

Examples:
"call amish tomorrow 3pm urgent" → {"title": "Call Amish at 3pm", "due_date": "2026-04-26", "priority": true, "status": "Pending", "repeat": null}
"submit fees by friday" → {"title": "Submit fees", "due_date": "2026-05-02", "priority": false, "status": "Pending", "repeat": null}
"""

    try:
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'llama-3.1-8b-instant',
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message}
                ],
                'temperature': 0.1,
                'max_tokens': 200
            },
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content'].strip()

            # Parse JSON from response
            if '```json' in ai_response:
                ai_response = ai_response.split(
                    '```json')[1].split('```')[0].strip()
            elif '```' in ai_response:
                ai_response = ai_response.split(
                    '```')[1].split('```')[0].strip()

            parsed = json.loads(ai_response)
            return parsed

        else:
            print(f"Groq API error: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"Error parsing with Groq: {e}")
        return None


def extract_task_number(message):
    """Extract task number from message like 'mark task 2 done' or 'complete 3'"""
    # Match patterns like: "task 2", "task 3", or just "2", "3" after action words
    patterns = [
        r'task\s+(\d+)',  # "task 2"
        r'number\s+(\d+)',  # "number 2"
        r'\s(\d+)\s',  # " 2 " (number with spaces)
        r'^(\d+)\s',  # "2 " (number at start)
        r'\s(\d+)$',  # " 2" (number at end)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message.lower())
        if match:
            return int(match.group(1))
    
    return None


@chat_bp.route('/api/chat', methods=['POST'])
@login_required
def chat():
    """Handle conversational input"""
    data = request.get_json()
    user_message = data.get('message', '').strip()
    current_filter = data.get('current_filter', 'overdue')  # Get current filter context

    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    lower_msg = user_message.lower()

    # Priority 1: View/Filter commands (check FIRST)
    view_keywords = ['show', 'list', 'what', 'whats', 'view', 'see', 'display']
    if any(word in lower_msg for word in view_keywords):
        if 'overdue' in lower_msg:
            return jsonify({
                'type': 'filter',
                'filter': 'overdue',
                'message': 'Showing overdue tasks'
            })
        elif 'today' in lower_msg:
            return jsonify({
                'type': 'filter',
                'filter': 'today',
                'message': 'Showing today\'s tasks'
            })
        elif any(word in lower_msg for word in ['upcoming', 'future', 'later', 'next']):
            return jsonify({
                'type': 'filter',
                'filter': 'upcoming',
                'message': 'Showing upcoming tasks'
            })

    # Priority 2: Drop/Cancel task commands
    drop_keywords = ['drop', 'cancel', 'abandon', 'skip', 'remove']
    if any(word in lower_msg for word in drop_keywords):
        task_num = extract_task_number(user_message)
        
        if task_num:
            # Get tasks based on current filter (what user is viewing)
            today = datetime.utcnow().date()
            
            if current_filter == 'overdue':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Pending', 'In Progress']),
                    Task.due_date < today
                ).order_by(Task.created_at.desc()).all()
            elif current_filter == 'today':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Pending', 'In Progress']),
                    Task.due_date == today
                ).order_by(Task.created_at.desc()).all()
            elif current_filter == 'upcoming':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Pending', 'In Progress']),
                    db.or_(Task.due_date > today, Task.due_date == None)
                ).order_by(Task.created_at.desc()).all()
            elif current_filter == 'done':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Complete', 'Dropped'])
                ).order_by(Task.created_at.desc()).all()
            else:
                # Fallback: all tasks
                tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).all()
            
            if task_num > 0 and task_num <= len(tasks):
                task = tasks[task_num - 1]
                task.status = 'Dropped'
                task.updated_at = datetime.utcnow()
                db.session.commit()
                
                return jsonify({
                    'type': 'task_updated',
                    'message': f'Dropped: {task.title}'
                })
            else:
                return jsonify({
                    'type': 'error',
                    'message': f'Task {task_num} not found in {current_filter} view. There are {len(tasks)} tasks.'
                })
        else:
            return jsonify({
                'type': 'info',
                'message': 'Which task? Try: "drop task 2"'
            })

    # Priority 3: Complete/Done task commands
    complete_keywords = ['mark', 'complete', 'done', 'finish', 'set', 'close', 'tick', 'check', 'did']
    if any(word in lower_msg for word in complete_keywords):
        task_num = extract_task_number(user_message)
        
        if task_num:
            # Get tasks based on current filter (what user is viewing)
            today = datetime.utcnow().date()
            
            if current_filter == 'overdue':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Pending', 'In Progress']),
                    Task.due_date < today
                ).order_by(Task.created_at.desc()).all()
            elif current_filter == 'today':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Pending', 'In Progress']),
                    Task.due_date == today
                ).order_by(Task.created_at.desc()).all()
            elif current_filter == 'upcoming':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Pending', 'In Progress']),
                    db.or_(Task.due_date > today, Task.due_date == None)
                ).order_by(Task.created_at.desc()).all()
            elif current_filter == 'done':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Complete', 'Dropped'])
                ).order_by(Task.created_at.desc()).all()
            else:
                # Fallback: all tasks
                tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).all()
            
            if task_num > 0 and task_num <= len(tasks):
                task = tasks[task_num - 1]
                task.status = 'Complete'
                task.updated_at = datetime.utcnow()
                db.session.commit()
                
                return jsonify({
                    'type': 'task_updated',
                    'message': f'✓ Completed: {task.title}'
                })
            else:
                return jsonify({
                    'type': 'error',
                    'message': f'Task {task_num} not found in {current_filter} view. There are {len(tasks)} tasks.'
                })
        else:
            return jsonify({
                'type': 'info',
                'message': 'Which task? Try: "mark task 2 done"'
            })

    # Priority 4: Task creation (DEFAULT)
    # If message doesn't match above patterns, assume it's a new task
    parsed = parse_with_groq(user_message)

    if not parsed:
        # Groq failed, create basic task from message
        return jsonify({
            'type': 'info',
            'message': 'I couldn\'t parse that perfectly. Try: "call amish tomorrow 3pm" or use + Add Task button'
        }), 400

    # Smart due date defaults
    today = datetime.utcnow().date()
    
    if not parsed.get('due_date'):
        # Check if task has urgency keywords
        urgent_keywords = ['urgent', 'asap', 'important', 'call']
        is_urgent = any(keyword in user_message.lower() for keyword in urgent_keywords)
        
        if is_urgent:
            # Urgent tasks → tomorrow
            parsed['due_date'] = (today + timedelta(days=1)).isoformat()
        else:
            # Regular tasks → 2 days from now
            parsed['due_date'] = (today + timedelta(days=2)).isoformat()

    # Create task from parsed data
    try:
        task = Task(
            user_id=current_user.id,
            title=parsed.get('title', user_message),
            status=parsed.get('status', 'Pending'),
            priority=parsed.get('priority', False),
            repeat=parsed.get('repeat')
        )

        # Parse due date
        if parsed.get('due_date'):
            try:
                task.due_date = datetime.fromisoformat(
                    parsed['due_date']).date()
            except:
                pass

        db.session.add(task)
        db.session.commit()

        return jsonify({
            'type': 'task_created',
            'task': task.to_dict(),
            'message': f'✓ Created: {task.title}'
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error creating task from chat: {e}")
        return jsonify({
            'type': 'error',
            'message': 'Failed to create task'
        }), 500
