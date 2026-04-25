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
- Due date logic:
  * If explicit date mentioned ("tomorrow", "friday") → use that date
  * If task contains "urgent", "ASAP", "important", or "call" → due_date = tomorrow
  * Otherwise → due_date = 2 days from now
- Priority: true if "important", "urgent", "asap", "critical"
- Status: "Pending" (default)

Current date: {today's date in YYYY-MM-DD format}

Output ONLY valid JSON, no explanations:
{
  "title": "task description",
  "due_date": "2026-04-21" or null,
  "priority": true/false,
  "status": "Pending",
  "repeat": null or "Daily"/"Weekly"/"Monthly"
}

Examples:
"call sachin" → {{"title": "Call Sachin", "due_date": "{(today + timedelta(days=1)).isoformat()}", "priority": false, "status": "Pending", "repeat": null}}
"buy groceries" → {{"title": "Buy groceries", "due_date": "{(today + timedelta(days=2)).isoformat()}", "priority": false, "status": "Pending", "repeat": null}}
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

    import re

    # ============================================
    # Priority 1: Drop task commands
    # ============================================

    drop_keywords = ['drop', 'cancel', 'abandon', 'skip']

    if any(word in lower_msg for word in drop_keywords):
        patterns = [
            r'task\s+(\d+)',
            r'drop\s+(\d+)',
            r'cancel\s+(\d+)',
            r'skip\s+(\d+)',
        ]

        task_number = None
        for pattern in patterns:
            match = re.search(pattern, lower_msg)
            if match:
                task_number = int(match.group(1))
                break

        if task_number:
            tasks = Task.query.filter_by(user_id=current_user.id).order_by(
                Task.created_at.desc()).all()

            if 1 <= task_number <= len(tasks):
                task = tasks[task_number - 1]
                task.status = 'Dropped'
                task.updated_at = datetime.utcnow()

                try:
                    db.session.commit()
                    return jsonify({
                        'type': 'task_updated',
                        'task': task.to_dict(),
                        'message': f'⛔ Dropped: {task.title}'
                    }), 200
                except Exception as e:
                    db.session.rollback()
                    print(f"Error dropping task: {e}")
                    return jsonify({'type': 'error', 'message': 'Failed to drop task'}), 500
            else:
                return jsonify({
                    'type': 'error',
                    'message': f'Task {task_number} not found. You have {len(tasks)} tasks.'
                }), 400
        else:
            return jsonify({
                'type': 'info',
                'message': 'Which task? Try: "drop task 2"'
            }), 400

    # ============================================
    # Priority 2: Complete task commands
    # ============================================

    action_keywords = ['mark', 'complete', 'done',
                       'finish', 'set', 'close', 'tick', 'check', 'did']

    if any(word in lower_msg for word in action_keywords):
        patterns = [
            r'task\s+(\d+)',
            r'mark\s+(\d+)',
            r'complete\s+(\d+)',
            r'finish\s+(\d+)',
            r'close\s+(\d+)',
            r'tick\s+(\d+)',
            r'check\s+(\d+)',
            r'did\s+(\d+)',
        ]

        task_number = None
        for pattern in patterns:
            match = re.search(pattern, lower_msg)
            if match:
                task_number = int(match.group(1))
                break

        if task_number:
            tasks = Task.query.filter_by(user_id=current_user.id).order_by(
                Task.created_at.desc()).all()

            if 1 <= task_number <= len(tasks):
                task = tasks[task_number - 1]
                task.status = 'Complete'
                task.updated_at = datetime.utcnow()

                try:
                    db.session.commit()
                    return jsonify({
                        'type': 'task_updated',
                        'task': task.to_dict(),
                        'message': f'✓ Marked as complete: {task.title}'
                    }), 200
                except Exception as e:
                    db.session.rollback()
                    print(f"Error updating task: {e}")
                    return jsonify({'type': 'error', 'message': 'Failed to update task'}), 500
            else:
                return jsonify({
                    'type': 'error',
                    'message': f'Task {task_number} not found. You have {len(tasks)} tasks.'
                }), 400
        else:
            return jsonify({
                'type': 'info',
                'message': 'Which task? Try: "mark task 2 done"'
            }), 400

    # ============================================
    # Priority 3: Task creation via LLM
    # ============================================

    parsed = parse_with_groq(user_message)

    if not parsed:
        return jsonify({
            'type': 'info',
            'message': 'I couldn\'t parse that. Try: "call Sachin tomorrow 3pm" or "mark task 2 done"'
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
        return jsonify({'type': 'error', 'message': 'Failed to create task'}), 500
