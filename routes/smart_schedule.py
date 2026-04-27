"""
Smart Reschedule - Python-based task rescheduling
No AI required - pure Python logic based on user patterns
"""

from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from models import db, Task
from datetime import datetime, timedelta
from collections import defaultdict

smart_schedule_bp = Blueprint('smart_schedule', __name__)


def analyze_user_patterns(user_id):
    """
    Analyze user's task completion patterns
    Returns: {
        'best_days': [0-6],  # 0=Monday, 6=Sunday
        'avg_tasks_per_day': float,
        'completion_rate': float
    }
    """
    # Get completed tasks from last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    completed_tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.status == 'Complete',
        Task.updated_at >= thirty_days_ago
    ).all()
    
    if not completed_tasks:
        # No data - return defaults (weekdays preferred)
        return {
            'best_days': [0, 1, 2, 3, 4],  # Monday-Friday
            'avg_tasks_per_day': 3,
            'completion_rate': 0.5
        }
    
    # Count completions by day of week
    day_counts = defaultdict(int)
    for task in completed_tasks:
        day_of_week = task.updated_at.weekday()  # 0=Monday, 6=Sunday
        day_counts[day_of_week] += 1
    
    # Sort days by completion count
    sorted_days = sorted(day_counts.items(), key=lambda x: x[1], reverse=True)
    best_days = [day for day, count in sorted_days[:3]]  # Top 3 days
    
    # Calculate average tasks per day
    total_days = (datetime.utcnow() - thirty_days_ago).days
    avg_tasks_per_day = len(completed_tasks) / total_days if total_days > 0 else 3
    
    return {
        'best_days': best_days if best_days else [0, 1, 2],
        'avg_tasks_per_day': avg_tasks_per_day,
        'completion_rate': 0.6  # Placeholder
    }


def get_workload_per_day(user_id, next_n_days=14):
    """
    Get task count for each upcoming day
    Returns: {date_str: task_count}
    """
    today = datetime.utcnow().date()
    workload = {}
    
    for i in range(next_n_days):
        target_date = today + timedelta(days=i)
        count = Task.query.filter(
            Task.user_id == user_id,
            Task.due_date == target_date,
            Task.status.in_(['Pending', 'In Progress'])
        ).count()
        workload[target_date.isoformat()] = count
    
    return workload


def generate_reschedule_suggestions(user_id):
    """
    Generate smart reschedule suggestions for overdue tasks
    Pure Python logic - no AI
    """
    today = datetime.utcnow().date()
    
    # Get all overdue tasks
    overdue_tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.status.in_(['Pending', 'In Progress']),
        Task.due_date < today
    ).order_by(Task.priority.desc(), Task.due_date).all()
    
    if not overdue_tasks:
        return []
    
    # Analyze user patterns
    patterns = analyze_user_patterns(user_id)
    workload = get_workload_per_day(user_id)
    
    # Max tasks per day (based on user average + 20% buffer)
    max_tasks_per_day = int(patterns['avg_tasks_per_day'] * 1.2) + 1
    if max_tasks_per_day < 3:
        max_tasks_per_day = 3
    
    suggestions = []
    
    for task in overdue_tasks:
        # Find best day to reschedule this task
        best_date = None
        best_reason = ""
        
        # Start from tomorrow
        for days_ahead in range(1, 15):
            candidate_date = today + timedelta(days=days_ahead)
            candidate_str = candidate_date.isoformat()
            current_load = workload.get(candidate_str, 0)
            day_of_week = candidate_date.weekday()
            
            # Prefer lighter days
            if current_load < max_tasks_per_day:
                # Priority 1: User's best days with light load
                if day_of_week in patterns['best_days'] and current_load < 2:
                    best_date = candidate_date
                    best_reason = f"Light day ({current_load} tasks) on your productive day"
                    break
                
                # Priority 2: Any light day
                if not best_date and current_load < 2:
                    best_date = candidate_date
                    best_reason = f"Light day with only {current_load} task{'s' if current_load != 1 else ''}"
                
                # Priority 3: Moderately loaded day
                if not best_date and current_load < max_tasks_per_day:
                    best_date = candidate_date
                    best_reason = f"Balanced day ({current_load} tasks)"
        
        # Fallback: if no good day found, just use tomorrow
        if not best_date:
            best_date = today + timedelta(days=1)
            best_reason = "Rescheduled to tomorrow"
        
        # Update workload for next iteration
        workload[best_date.isoformat()] = workload.get(best_date.isoformat(), 0) + 1
        
        suggestions.append({
            'task_id': task.id,
            'task_title': task.title,
            'old_date': task.due_date.isoformat(),
            'new_date': best_date.isoformat(),
            'reason': best_reason
        })
    
    return suggestions


@smart_schedule_bp.route('/api/smart-reschedule', methods=['POST'])
@login_required
def smart_reschedule():
    """
    Generate smart reschedule suggestions for overdue tasks
    """
    try:
        suggestions = generate_reschedule_suggestions(current_user.id)
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'count': len(suggestions)
        }), 200
    
    except Exception as e:
        print(f"Error in smart reschedule: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate suggestions'
        }), 500
