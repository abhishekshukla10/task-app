from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Task
from datetime import datetime, timedelta
import os
import json
import requests

ai_bp = Blueprint('ai', __name__)

def call_groq(system_prompt, user_message, temperature=0.3, max_tokens=300):
    """Helper function to call Groq API"""
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    if not GROQ_API_KEY:
        return None
    
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
                'temperature': temperature,
                'max_tokens': max_tokens
            },
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content'].strip()
            
            # Parse JSON if wrapped in code blocks
            if '```json' in ai_response:
                ai_response = ai_response.split('```json')[1].split('```')[0].strip()
            elif '```' in ai_response:
                ai_response = ai_response.split('```')[1].split('```')[0].strip()
            
            return ai_response
        
        return None
    
    except Exception as e:
        print(f"Groq API error: {e}")
        return None


@ai_bp.route('/api/breakdown', methods=['POST'])
@login_required
def breakdown_task():
    """Break down a task into subtasks"""
    data = request.get_json()
    task_title = data.get('task_title', '').strip()
    
    if not task_title:
        return jsonify({'error': 'Task title required'}), 400
    
    system_prompt = """You are a task breakdown assistant. Break down tasks into 3-5 actionable subtasks.

Rules:
- Each subtask should be specific and actionable
- Keep subtasks short (under 60 characters)
- Order subtasks logically
- Output ONLY a JSON array of strings, nothing else

Example input: "Plan product launch"
Example output: ["Define target audience", "Create marketing timeline", "Design landing page", "Prepare press kit", "Schedule launch email"]
"""
    
    ai_response = call_groq(system_prompt, task_title, temperature=0.3, max_tokens=300)
    
    if ai_response:
        try:
            subtasks = json.loads(ai_response)
            return jsonify({'subtasks': subtasks})
        except:
            return jsonify({'error': 'Failed to parse response'}), 500
    
    return jsonify({'error': 'AI service unavailable'}), 503


@ai_bp.route('/api/stuck-help', methods=['POST'])
@login_required
def stuck_task_help():
    """Get AI coaching for stuck tasks"""
    data = request.get_json()
    task_title = data.get('task_title', '').strip()
    days_stuck = data.get('days_stuck', 0)
    
    if not task_title:
        return jsonify({'error': 'Task title required'}), 400
    
    system_prompt = f"""You are a productivity coach helping someone who's stuck on a task for {days_stuck} days.

Provide 3-4 SHORT, ACTIONABLE suggestions to help them start. Be encouraging but practical.

Format as JSON:
{{
  "suggestions": ["suggestion 1", "suggestion 2", "suggestion 3"],
  "encouragement": "short motivational message"
}}

Keep each suggestion under 50 characters. Keep encouragement under 80 characters.
"""
    
    ai_response = call_groq(system_prompt, f"Task: {task_title}", temperature=0.5, max_tokens=400)
    
    if ai_response:
        try:
            coaching = json.loads(ai_response)
            return jsonify(coaching)
        except:
            return jsonify({'error': 'Failed to parse response'}), 500
    
    return jsonify({'error': 'AI service unavailable'}), 503


@ai_bp.route('/api/tool-suggestions', methods=['POST'])
@login_required
def tool_suggestions():
    """Suggest tools/resources for a task"""
    data = request.get_json()
    task_title = data.get('task_title', '').strip()
    
    if not task_title:
        return jsonify({'error': 'Task title required'}), 400
    
    system_prompt = """You are a productivity expert suggesting helpful tools, tutorials, or resources.

Provide 2-3 specific, practical suggestions for completing this task.

Format as JSON:
{
  "tools": [
    {"name": "tool name", "why": "one sentence why it helps"},
    {"name": "tool name", "why": "one sentence why it helps"}
  ]
}

Keep tool names short (under 30 chars). Keep "why" under 60 chars.
"""
    
    ai_response = call_groq(system_prompt, f"Task: {task_title}", temperature=0.4, max_tokens=400)
    
    if ai_response:
        try:
            tools = json.loads(ai_response)
            return jsonify(tools)
        except:
            return jsonify({'error': 'Failed to parse response'}), 500
    
    return jsonify({'error': 'AI service unavailable'}), 503


@ai_bp.route('/api/reflection', methods=['POST'])
@login_required
def evening_reflection():
    """End-of-day reflection prompt"""
    
    # Get today's completed tasks
    today = datetime.utcnow().date()
    completed_today = Task.query.filter(
        Task.user_id == current_user.id,
        Task.status == 'Complete',
        db.func.date(Task.updated_at) == today
    ).all()
    
    # Get still pending tasks
    pending = Task.query.filter(
        Task.user_id == current_user.id,
        Task.status.in_(['Pending', 'In Progress']),
        Task.due_date <= today
    ).count()
    
    reflection = {
        'completed_count': len(completed_today),
        'completed_tasks': [task.title for task in completed_today[:5]],  # First 5
        'pending_count': pending,
        'prompt': 'What helped you complete these tasks? What blocked you on pending ones?'
    }
    
    return jsonify(reflection)


@ai_bp.route('/api/smart-briefing', methods=['GET'])
@login_required
def smart_briefing():
    """Generate intelligent morning briefing"""
    
    today = datetime.utcnow().date()
    hour = datetime.utcnow().hour
    
    # Get task counts
    overdue = Task.query.filter(
        Task.user_id == current_user.id,
        Task.status.in_(['Pending', 'In Progress']),
        Task.due_date < today
    ).all()
    
    today_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.status.in_(['Pending', 'In Progress']),
        Task.due_date == today
    ).all()
    
    in_progress = Task.query.filter(
        Task.user_id == current_user.id,
        Task.status == 'In Progress'
    ).count()
    
    # Greeting based on time
    if hour < 12:
        greeting = 'Good morning'
    elif hour < 17:
        greeting = 'Good afternoon'
    else:
        greeting = 'Good evening'
    
    # Generate briefing
    briefing = {
        'greeting': greeting,
        'overdue_count': len(overdue),
        'today_count': len(today_tasks),
        'in_progress_count': in_progress,
        'top_priority': None,
        'message': ''
    }
    
    # All caught up
    if len(overdue) == 0 and len(today_tasks) == 0:
        upcoming = Task.query.filter(
            Task.user_id == current_user.id,
            Task.status.in_(['Pending', 'In Progress']),
            Task.due_date > today
        ).order_by(Task.due_date).first()
        
        if upcoming:
            briefing['message'] = f"You're all caught up! Next up: {upcoming.title}"
        else:
            briefing['message'] = "You're all caught up! No pending tasks."
        
        return jsonify(briefing)
    
    # Build message
    parts = []
    
    if len(overdue) > 0:
        top_overdue = sorted(overdue, key=lambda t: t.due_date)[0]
        days_overdue = (today - top_overdue.due_date).days
        briefing['top_priority'] = {
            'title': top_overdue.title,
            'days_overdue': days_overdue
        }
        parts.append(f"⚠️ {len(overdue)} overdue task{'s' if len(overdue) != 1 else ''}")
    
    if len(today_tasks) > 0:
        parts.append(f"{len(today_tasks)} due today")
    
    if in_progress > 0:
        parts.append(f"{in_progress} in progress")
    
    briefing['message'] = '. '.join(parts) + '.'
    
    return jsonify(briefing)
