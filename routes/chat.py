from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Task
import os
import json
from datetime import datetime, timedelta
import requests
import re

chat_bp = Blueprint('chat', __name__)


def try_simple_parse(user_message):
    """
    ✅ NEW: Try simple regex parsing first (no AI, instant, preserves all text)
    
    Handles 90% of cases:
    - "task today" → Due today
    - "task tomorrow urgent" → Due tomorrow, priority
    - "how to cook learn today" → Preserves "how to"
    
    Returns parsed dict or None if complex (needs AI)
    """
    text = user_message.strip()
    text_lower = text.lower()
    
    # Check for complex patterns that need AI
    complex_keywords = [
        'next', 'in ', 'after', 'before', 'this ', 'coming', 'following',
        'week', 'month', 'monday', 'tuesday', 'wednesday', 'thursday', 
        'friday', 'saturday', 'sunday', 'jan', 'feb', 'mar', 'apr', 
        'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
    ]
    
    # If contains complex date patterns, use AI
    for keyword in complex_keywords:
        if re.search(rf'\b{keyword}\b', text_lower):
            return None  # Too complex, use AI
    
    # Simple date extraction
    due_date = None
    date_keyword = None
    
    # Check for today
    if re.search(r'\btoday\b', text_lower):
        due_date = datetime.utcnow().date().isoformat()
        date_keyword = 'today'
    # Check for tomorrow
    elif re.search(r'\btomorrow\b', text_lower):
        due_date = (datetime.utcnow().date() + timedelta(days=1)).isoformat()
        date_keyword = 'tomorrow'
    # Check for day after tomorrow
    elif re.search(r'\bday after tomorrow\b', text_lower):
        due_date = (datetime.utcnow().date() + timedelta(days=2)).isoformat()
        date_keyword = 'day after tomorrow'
    
    # Priority extraction
    priority = False
    priority_keywords = []
    
    for keyword in ['urgent', 'important', 'asap', 'critical']:
        if re.search(rf'\b{keyword}\b', text_lower):
            priority = True
            priority_keywords.append(keyword)
    
    # Clean title (remove date and priority keywords)
    title = text
    
    # Remove date keyword
    if date_keyword:
        title = re.sub(rf'\b{date_keyword}\b', '', title, flags=re.IGNORECASE)
    
    # Remove priority keywords
    for keyword in priority_keywords:
        title = re.sub(rf'\b{keyword}\b', '', title, flags=re.IGNORECASE)
    
    # Clean up extra whitespace
    title = ' '.join(title.split())
    
    # If title is empty or too short after cleaning, return None (let AI handle)
    if not title.strip() or len(title.strip()) < 2:
        return None
    
    # Return parsed result
    return {
        'title': title.strip(),
        'due_date': due_date,
        'priority': priority,
        'status': 'Pending',
        'repeat': None
    }


def parse_with_groq(user_message):
    """
    ✅ UPDATED: Hybrid parsing - try simple parse first, use AI as fallback
    
    Flow:
    1. Try simple regex parse (90% of cases) → Instant, preserves text
    2. If complex, use Groq AI (10% of cases) → Handles "next friday", etc.
    """
    
    # ✅ STEP 1: Try simple parse first
    simple_result = try_simple_parse(user_message)
    if simple_result:
        return simple_result  # No AI needed! ⚡
    
    # ✅ STEP 2: Complex case - use AI
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    if not GROQ_API_KEY:
        return None

    # System prompt for task parsing
    system_prompt = """You are a task parser. Convert natural language to task JSON.

Rules:
- Extract: title, due_date, priority, status, repeat
- PRESERVE all words in title including "how to", "I need to", "want to", etc.
- Only remove date keywords (today, tomorrow, etc.) and priority keywords (urgent, important) from title
- Due date formats: "tomorrow", "next monday", "25th april", "in 3 days"
- Priority: true if "important", "urgent", "asap", "critical"
- Status: "Pending" (default), "In Progress", "Completed"
- Repeat: "Daily", "Weekly", "Monthly" or null

Output ONLY valid JSON, no explanations:
{
  "title": "task description",
  "due_date": "today" or "tomorrow" or "day after tomorrow" or null,
  "priority": true/false,
  "status": "Pending",
  "repeat": null or "Daily"/"Weekly"/"Monthly"
}

Examples:
"call amish tomorrow 3pm urgent" → {"title": "Call Amish at 3pm", "due_date": "tomorrow", "priority": true, "status": "Pending", "repeat": null}
"how to cook pasta next friday" → {"title": "How to cook pasta", "due_date": "next friday", "priority": false, "status": "Pending", "repeat": null}
"I need to submit fees in 3 days" → {"title": "I need to submit fees", "due_date": "in 3 days", "priority": false, "status": "Pending", "repeat": null}
"gym today" → {"title": "Gym", "due_date": "today", "priority": false, "status": "Pending", "repeat": null}
"meeting day after tomorrow" → {"title": "Meeting", "due_date": "day after tomorrow", "priority": false, "status": "Pending", "repeat": null}
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


def preprocess_hindi_dates(message):
    """
    ✅ NEW: Convert Hindi date keywords to English before LLM processing
    Critical for Indian users: aaj=today, kal=tomorrow, parso=day after tomorrow
    """
    # Hindi to English date mappings (case-insensitive)
    replacements = {
        # Core date keywords (CRITICAL for Indian users)
        r'\baaj\b': 'today',
        r'\baaj ka\b': 'today',
        r'\bkal\b': 'tomorrow',
        r'\bkl\b': 'tomorrow',
        r'\bparso\b': 'day after tomorrow',
        r'\bparsoo\b': 'day after tomorrow',
        
        # Week references
        r'\bis hafte\b': 'this week',
        r'\bis week\b': 'this week',
        r'\bagle hafte\b': 'next week',
        r'\bagla hafta\b': 'next week',
        
        # Month references
        r'\bis mahine\b': 'this month',
        r'\bis month\b': 'this month',
        r'\bagle mahine\b': 'next month',
        r'\bagla month\b': 'next month',
        
        # Days of week (Hindi)
        r'\bsomwar\b': 'monday',
        r'\bsomvaar\b': 'monday',
        r'\bmangalwar\b': 'tuesday',
        r'\bmangalvaar\b': 'tuesday',
        r'\bbudhwar\b': 'wednesday',
        r'\bbudhvaar\b': 'wednesday',
        r'\bguruwaar\b': 'thursday',
        r'\bguruvaar\b': 'thursday',
        r'\bshukrawaar\b': 'friday',
        r'\bshukravar\b': 'friday',
        r'\bshaniwar\b': 'saturday',
        r'\bshanivaar\b': 'saturday',
        r'\braviwar\b': 'sunday',
        r'\bravivaar\b': 'sunday',
    }
    
    # Apply all replacements (case-insensitive)
    processed = message
    for hindi_pattern, english_word in replacements.items():
        processed = re.sub(hindi_pattern, english_word, processed, flags=re.IGNORECASE)
    
    return processed


def convert_relative_date(date_string):
    """
    ✅ NEW: Convert relative date strings to ISO format dates
    Handles: 'today', 'tomorrow', 'day after tomorrow'
    Returns ISO date string or original if already in ISO format
    """
    if not date_string:
        return None
    
    today = datetime.utcnow().date()
    date_lower = date_string.lower().strip()
    
    # Convert relative dates to ISO
    if date_lower == 'today':
        return today.isoformat()
    elif date_lower == 'tomorrow':
        return (today + timedelta(days=1)).isoformat()
    elif 'day after tomorrow' in date_lower:
        return (today + timedelta(days=2)).isoformat()
    
    # Already an ISO date or other format - return as is
    return date_string


def sort_tasks_by_priority(tasks):
    """
    ✅ FIXED: Sort tasks by priority first, then by due_date, then by ID
    This MATCHES the frontend sorting in app.js sortTasksByPriority()

    Sorting logic:
    1. Priority tasks (★) first
    2. Then by due date (oldest first)
    3. Then by task ID (ensures consistent order when priority+date are same)
    """
    return sorted(tasks, key=lambda t: (
        # False (priority=True) comes before True (priority=False)
        not t.priority,
        t.due_date if t.due_date else datetime.max.date(),  # Tasks with dates first
        t.id  # ✅ FIX: ID as tie-breaker for tasks with same priority & date
    ))


@chat_bp.route('/api/chat', methods=['POST'])
@login_required
def chat():
    """Handle conversational input"""
    data = request.get_json()
    user_message = data.get('message', '').strip()
    # Get current filter context
    current_filter = data.get('current_filter', 'overdue')

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
                ).all()
            elif current_filter == 'today':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Pending', 'In Progress']),
                    Task.due_date == today
                ).all()
            elif current_filter == 'upcoming':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Pending', 'In Progress']),
                    db.or_(Task.due_date > today, Task.due_date == None)
                ).all()
            elif current_filter == 'done':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Complete', 'Dropped'])
                ).all()
            else:
                # Fallback: all tasks
                tasks = Task.query.filter_by(user_id=current_user.id).all()

            # ✅ FIX: Sort by priority to match frontend
            tasks = sort_tasks_by_priority(tasks)

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
    complete_keywords = ['mark', 'complete', 'done',
                         'finish', 'set', 'close', 'tick', 'check', 'did']
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
                ).all()
            elif current_filter == 'today':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Pending', 'In Progress']),
                    Task.due_date == today
                ).all()
            elif current_filter == 'upcoming':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Pending', 'In Progress']),
                    db.or_(Task.due_date > today, Task.due_date == None)
                ).all()
            elif current_filter == 'done':
                tasks = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(['Complete', 'Dropped'])
                ).all()
            else:
                # Fallback: all tasks
                tasks = Task.query.filter_by(user_id=current_user.id).all()

            # ✅ FIX: Sort by priority to match frontend
            tasks = sort_tasks_by_priority(tasks)

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
    
    # ✅ NEW: Preprocess Hindi dates before sending to LLM
    preprocessed_message = preprocess_hindi_dates(user_message)
    parsed = parse_with_groq(preprocessed_message)

    if not parsed:
        # ✅ FIX: Groq failed, but create task anyway with raw text
        try:
            task = Task(
                user_id=current_user.id,
                title=user_message,  # Use raw message as title
                status='Pending',
                priority=False,
                # Default: 2 days from now
                due_date=(datetime.utcnow().date() + timedelta(days=2))
            )

            db.session.add(task)
            db.session.commit()

            return jsonify({
                'type': 'task_created',
                'task': task.to_dict(),
                # Truncate long titles in toast
                'message': f'✓ Created: {task.title[:50]}...'
            }), 201

        except Exception as e:
            db.session.rollback()
            print(f"Error creating fallback task: {e}")
            return jsonify({
                'type': 'info',
                'message': 'Couldn\'t create task. Try: "call amish tomorrow" or use + Add Task'
            }), 400

    # Smart due date defaults
    today = datetime.utcnow().date()

    # ✅ NEW: Convert relative dates from Groq to ISO format FIRST
    if parsed.get('due_date'):
        parsed['due_date'] = convert_relative_date(parsed['due_date'])

    # ✅ THEN apply +2 days fallback if STILL no date
    if not parsed.get('due_date'):
        # Check if task has urgency keywords
        urgent_keywords = ['urgent', 'asap', 'important', 'call']
        is_urgent = any(keyword in user_message.lower()
                        for keyword in urgent_keywords)

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
