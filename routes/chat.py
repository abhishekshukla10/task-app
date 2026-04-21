from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Task
import os
import json
from datetime import datetime, timedelta
import requests

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
"call amish tomorrow 3pm urgent" → {"title": "Call Amish at 3pm", "due_date": "2026-04-21", "priority": true, "status": "Pending", "repeat": null}
"submit fees by friday" → {"title": "Submit fees", "due_date": "2026-04-25", "priority": false, "status": "Pending", "repeat": null}
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


@chat_bp.route('/api/chat', methods=['POST'])
@login_required
def chat():
    """Handle conversational input"""
    data = request.get_json()
    user_message = data.get('message', '').strip()

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

    # Priority 2: Status update commands
    action_keywords = ['mark', 'complete', 'done', 'finish', 'set']
    if any(word in lower_msg for word in action_keywords):
        return jsonify({
            'type': 'info',
            'message': 'Status update commands coming soon! Use the task cards to update for now.'
        })

    # Priority 3: Task creation (DEFAULT)
    # If message doesn't match above patterns, assume it's a new task
    parsed = parse_with_groq(user_message)

    if not parsed:
        # Groq failed, create basic task from message
        return jsonify({
            'type': 'info',
            'message': 'I couldn\'t parse that perfectly. Try: "call amish tomorrow 3pm" or use + Add Task button'
        }), 400

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
