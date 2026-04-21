from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, Task
from datetime import datetime, date, timedelta
from sqlalchemy import or_, and_

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard - render the UI"""
    return render_template('dashboard.html', user=current_user)

@tasks_bp.route('/api/tasks', methods=['GET'])
@login_required
def get_tasks():
    """Get all tasks for current user"""
    # Get query parameters
    status_filter = request.args.get('status')  # Pending, In Progress, Completed, Dropped
    search = request.args.get('search', '').strip()
    
    # Base query - only current user's tasks
    query = Task.query.filter_by(user_id=current_user.id)
    
    # Apply filters
    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if search:
        query = query.filter(Task.title.ilike(f'%{search}%'))
    
    # Exclude auto-archived tasks (completed/dropped > 30 days ago)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    query = query.filter(
        or_(
            Task.status.in_(['Pending', 'In Progress']),
            Task.updated_at >= thirty_days_ago
        )
    )
    
    # Get tasks
    tasks = query.order_by(Task.created_at.desc()).all()
    
    # Convert to dict
    tasks_data = [task.to_dict() for task in tasks]
    
    return jsonify({'tasks': tasks_data})

@tasks_bp.route('/api/tasks', methods=['POST'])
@login_required
def create_task():
    """Create a new task"""
    data = request.get_json()
    
    # Validation
    if not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400
    
    try:
        # Create task
        task = Task(
            user_id=current_user.id,
            title=data['title'].strip(),
            status=data.get('status', 'Pending'),
            priority=data.get('priority', False),
            remarks=data.get('remarks', '').strip() if data.get('remarks') else None
        )
        
        # Parse dates
        if data.get('due_date'):
            task.due_date = datetime.fromisoformat(data['due_date']).date()
        
        if data.get('reminder_time'):
            task.reminder_time = datetime.fromisoformat(data['reminder_time'])
        
        if data.get('snoozed_until'):
            task.snoozed_until = datetime.fromisoformat(data['snoozed_until'])
        
        task.repeat = data.get('repeat')
        
        db.session.add(task)
        db.session.commit()
        
        return jsonify({'task': task.to_dict()}), 201
    
    except Exception as e:
        db.session.rollback()
        print(f"Error creating task: {e}")
        return jsonify({'error': 'Failed to create task'}), 500

@tasks_bp.route('/api/tasks/<int:task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    """Update an existing task"""
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first()
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    data = request.get_json()
    
    try:
        # Update fields if provided
        if 'title' in data:
            task.title = data['title'].strip()
        
        if 'status' in data:
            task.status = data['status']
        
        if 'priority' in data:
            task.priority = data['priority']
        
        if 'remarks' in data:
            task.remarks = data['remarks'].strip() if data['remarks'] else None
        
        if 'due_date' in data:
            task.due_date = datetime.fromisoformat(data['due_date']).date() if data['due_date'] else None
        
        if 'reminder_time' in data:
            task.reminder_time = datetime.fromisoformat(data['reminder_time']) if data['reminder_time'] else None
        
        if 'snoozed_until' in data:
            task.snoozed_until = datetime.fromisoformat(data['snoozed_until']) if data['snoozed_until'] else None
        
        if 'repeat' in data:
            task.repeat = data['repeat']
        
        task.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'task': task.to_dict()})
    
    except Exception as e:
        db.session.rollback()
        print(f"Error updating task: {e}")
        return jsonify({'error': 'Failed to update task'}), 500

@tasks_bp.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    """Delete a task"""
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first()
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    try:
        db.session.delete(task)
        db.session.commit()
        return jsonify({'message': 'Task deleted'}), 200
    
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting task: {e}")
        return jsonify({'error': 'Failed to delete task'}), 500

@tasks_bp.route('/api/tasks/bulk', methods=['POST'])
@login_required
def bulk_action():
    """Bulk actions on multiple tasks"""
    data = request.get_json()
    task_ids = data.get('task_ids', [])
    action = data.get('action')  # complete, drop, delete
    
    if not task_ids or not action:
        return jsonify({'error': 'task_ids and action required'}), 400
    
    try:
        tasks = Task.query.filter(
            Task.id.in_(task_ids),
            Task.user_id == current_user.id
        ).all()
        
        if action == 'complete':
            for task in tasks:
                task.status = 'Completed'
                task.updated_at = datetime.utcnow()
        
        elif action == 'drop':
            for task in tasks:
                task.status = 'Dropped'
                task.updated_at = datetime.utcnow()
        
        elif action == 'delete':
            for task in tasks:
                db.session.delete(task)
        
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
        db.session.commit()
        return jsonify({'message': f'{len(tasks)} tasks updated'}), 200
    
    except Exception as e:
        db.session.rollback()
        print(f"Error in bulk action: {e}")
        return jsonify({'error': 'Failed to perform bulk action'}), 500
