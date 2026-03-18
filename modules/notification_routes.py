"""
Notification Management Module
Handles user notifications, admin notification management, and auto-notifications
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta, timezone

from modules.models import Notification, User

# This will be initialized from app.py
db = None
logger = None

def init_notification_routes(database, app_logger):
    """Initialize notification routes with database and logger"""
    global db, logger
    db = database
    logger = app_logger
    
    notification_bp = Blueprint('notifications', __name__)
    
    @notification_bp.route('/notifications/list')
    def get_notifications_list():
        """Get notifications list for current user (JSON API)"""
        from modules.auth_routes import login_required
        
        @login_required
        def _get_list():
            user = db.session.get(User, session['user_id'])
            
            # Get user-specific unread notifications
            user_notifications = Notification.query.filter_by(
                user_id=user.id, is_read=False
            ).order_by(Notification.created_at.desc()).limit(10).all()
            
            # Get all-user unread notifications
            all_notifications = Notification.query.filter_by(
                user_id=None, is_read=False
            ).order_by(Notification.created_at.desc()).limit(10).all()
            
            # Combine and deduplicate
            seen_ids = set()
            notifications = []
            
            for notif in user_notifications:
                if notif.id not in seen_ids:
                    seen_ids.add(notif.id)
                    notifications.append({
                        'id': notif.id,
                        'title': notif.title,
                        'message': notif.message,
                        'type': notif.notification_type,
                        'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M') if notif.created_at else 'N/A'
                    })
            
            for notif in all_notifications:
                if notif.id not in seen_ids:
                    seen_ids.add(notif.id)
                    notifications.append({
                        'id': notif.id,
                        'title': notif.title,
                        'message': notif.message,
                        'type': notif.notification_type,
                        'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M') if notif.created_at else 'N/A'
                    })
            
            notifications.sort(key=lambda x: x['created_at'], reverse=True)
            return jsonify({'notifications': notifications})
        
        return _get_list()
    
    
    @notification_bp.route('/notifications/count')
    def notification_count():
        """Get unread notification count for current user"""
        from modules.auth_routes import login_required
        
        @login_required
        def _get_count():
            user = db.session.get(User, session['user_id'])
            
            user_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()
            all_count = Notification.query.filter_by(user_id=None, is_read=False).count()
            
            total = user_count + all_count
            return jsonify({'count': total})
        
        return _get_count()
    
    
    @notification_bp.route('/notifications/mark-read/<int:notification_id>', methods=['POST'])
    def mark_notification_read(notification_id):
        """Mark a notification as read"""
        from modules.auth_routes import login_required
        
        @login_required
        def _mark_read():
            user = db.session.get(User, session['user_id'])
            notification = db.session.get(Notification, notification_id)
            
            if not notification:
                return jsonify({'success': False, 'error': 'Notification not found'}), 404
            
            if notification.user_id is None or notification.user_id == user.id:
                notification.is_read = True
                db.session.commit()
                return jsonify({'success': True})
            
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        return _mark_read()
    
    
    @notification_bp.route('/notifications/mark-all-read', methods=['POST'])
    def mark_all_notifications_read():
        """Mark all notifications as read for current user"""
        from modules.auth_routes import login_required
        
        @login_required
        def _mark_all_read():
            user = db.session.get(User, session['user_id'])
            
            Notification.query.filter_by(user_id=user.id, is_read=False).update({'is_read': True})
            db.session.commit()
            
            return jsonify({'success': True})
        
        return _mark_all_read()
    
    
    @notification_bp.route('/admin/notifications', methods=['GET', 'POST'])
    def admin_notifications():
        """Admin - Send notifications to users"""
        from modules.auth_routes import admin_required
        
        @admin_required
        def _admin_notifications():
            if request.method == 'POST':
                title = request.form.get('title', '').strip()
                message = request.form.get('message', '').strip()
                notification_type = request.form.get('type', 'info')
                recipient_type = request.form.get('recipient_type', 'all')
                user_id = request.form.get('user_id', type=int)
                
                if not title or not message:
                    flash('Title and message are required.', 'danger')
                    return redirect(url_for('notifications.admin_notifications'))
                
                try:
                    if recipient_type == 'all':
                        notification = Notification(
                            user_id=None,
                            title=title,
                            message=message,
                            notification_type=notification_type,
                            is_system=False
                        )
                        db.session.add(notification)
                        db.session.commit()
                        flash(f'Notification sent to all users successfully!', 'success')
                    else:
                        if not user_id:
                            flash('Please select a user.', 'danger')
                            return redirect(url_for('notifications.admin_notifications'))
                        
                        user = db.session.get(User, user_id)
                        if not user:
                            flash('User not found.', 'danger')
                            return redirect(url_for('notifications.admin_notifications'))
                        
                        notification = Notification(
                            user_id=user_id,
                            title=title,
                            message=message,
                            notification_type=notification_type,
                            is_system=False
                        )
                        db.session.add(notification)
                        db.session.commit()
                        flash(f'Notification sent to {user.username} successfully!', 'success')
                    
                    return redirect(url_for('notifications.admin_notifications'))
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Error sending notification: {e}")
                    flash('Failed to send notification. Please try again.', 'danger')
                    return redirect(url_for('notifications.admin_notifications'))
            
            # GET request
            all_notifications = Notification.query.order_by(Notification.created_at.desc()).limit(50).all()
            all_users = User.query.filter_by(is_deleted=False).order_by(User.username).all()
            
            return render_template('admin/admin_notifications.html', 
                                 notifications=all_notifications,
                                 users=all_users)
        
        return _admin_notifications()
    
    return notification_bp

