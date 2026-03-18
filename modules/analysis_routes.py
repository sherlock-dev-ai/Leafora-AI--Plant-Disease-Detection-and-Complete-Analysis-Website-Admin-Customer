"""
Disease Analysis Management Module
Handles user dashboard, prediction history, and profile management
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, url_for as flask_url_for
from datetime import datetime, timedelta, timezone
import os

from modules.models import User, Prediction, UsageCounter, Notification
from modules.utils import ensure_timezone_aware, check_and_notify_expired_plan, allowed_file

# This will be initialized from app.py
db = None
app = None
logger = None

def init_analysis_routes(database, flask_app, app_logger):
    """Initialize analysis routes with database, app, and logger"""
    global db, app, logger
    db = database
    app = flask_app
    logger = app_logger
    
    analysis_bp = Blueprint('analysis', __name__)
    
    @analysis_bp.route('/dashboard')
    def dashboard():
        """User dashboard with statistics"""
        from modules.auth_routes import login_required, member_only
        
        @login_required
        @member_only
        def _dashboard():
            user = db.session.get(User, session['user_id'])
            
            # Check for expired Pro plan and send notification
            check_and_notify_expired_plan(user)
            
            # Get recent predictions
            recent_predictions = Prediction.query.filter_by(user_id=user.id)\
                .order_by(Prediction.timestamp.desc()).limit(5).all()
            
            # Statistics
            total_predictions = Prediction.query.filter_by(user_id=user.id).count()
            healthy_count = Prediction.query.filter_by(user_id=user.id, result='Healthy').count()
            disease_count = total_predictions - healthy_count
            
            # Dashboard Stats object for the new UI
            stats = {
                'total': total_predictions,
                'healthy': healthy_count,
                'issues': disease_count
            }
            
            # Prepare recent analyses with enriched data for the timeline
            recent_analyses = []
            for p in recent_predictions:
                recent_analyses.append({
                    'id': p.id,
                    'image_path': p.filename,
                    'disease_name': p.result,
                    'confidence': p.confidence,
                    'created_at': p.timestamp.strftime('%Y-%m-%d %H:%M'),
                    'description': '', # Details not easily available here
                    'treatment': ''
                })
            
            # Recent activity
            recent_activity = Prediction.query.filter_by(user_id=user.id)\
                .order_by(Prediction.timestamp.desc()).limit(10).all()
            
            # Get usage counter for limit display
            counter = UsageCounter.query.filter_by(user_id=user.id).first()
            now = datetime.now(timezone.utc)
            
            # Reset daily count if needed
            if counter and counter.daily_reset_at:
                reset_at = ensure_timezone_aware(counter.daily_reset_at)
                if reset_at and reset_at < now:
                    counter.today_count = 0
                    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    counter.daily_reset_at = tomorrow
                    db.session.commit()
            
            today_usage = counter.today_count if counter else 0
            is_pro = user.is_pro_active()
            remaining = max(0, 3 - today_usage) if not is_pro else "Unlimited"
            
            # Get unread notifications
            unread_notifications = Notification.query.filter_by(
                user_id=user.id, is_read=False
            ).order_by(Notification.created_at.desc()).limit(10).all()
            
            # Also get notifications for all users
            all_user_notifications = Notification.query.filter_by(
                user_id=None, is_read=False
            ).order_by(Notification.created_at.desc()).limit(10).all()
            
            return render_template('user/dashboard.html', 
                                 user=user, 
                                 stats=stats,
                                 recent_analyses=recent_analyses,
                                 recent_predictions=recent_predictions,
                                 total_predictions=total_predictions,
                                 healthy_count=healthy_count,
                                 disease_count=disease_count,
                                 recent_activity=recent_activity,
                                 today_usage=today_usage,
                                 remaining=remaining,
                                 is_pro=is_pro,
                                 unread_notifications=unread_notifications,
                                 all_user_notifications=all_user_notifications)
        
        return _dashboard()
    
    
    @analysis_bp.route('/history')
    def history():
        """User prediction history"""
        from modules.auth_routes import login_required, member_only
        
        @login_required
        @member_only
        def _history():
            user = db.session.get(User, session['user_id'])
            predictions = Prediction.query.filter_by(user_id=user.id)\
                .order_by(Prediction.timestamp.desc()).all()
            
            return render_template('user/history.html', predictions=predictions)
        
        return _history()
    
    
    @analysis_bp.route('/profile', methods=['GET', 'POST'])
    def profile():
        """User profile settings"""
        from modules.auth_routes import login_required, member_only
        
        @login_required
        @member_only
        def _profile():
            user = db.session.get(User, session['user_id'])
            
            if request.method == 'POST':
                username = request.form.get('username', '').strip()
                email = request.form.get('email', '').strip().lower()
                
                if not username or not email:
                    flash('Username and email are required.', 'danger')
                    return redirect(url_for('analysis.profile'))
                
                # Update basic fields
                user.username = username
                user.email = email
                
                # Handle profile image upload
                file = request.files.get('profile_image')
                if file and file.filename and allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = f"profile_{user.id}.{ext}"
                    profile_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(profile_path)
                
                db.session.commit()
                session['username'] = user.username
                flash('Profile updated successfully.', 'success')
                return redirect(url_for('analysis.profile'))
            
            # Determine profile image URL if exists
            profile_image_url = None
            for ext in ['png', 'jpg', 'jpeg', 'gif']:
                candidate = os.path.join(app.config['UPLOAD_FOLDER'], f"profile_{user.id}.{ext}")
                if os.path.exists(candidate):
                    profile_image_url = flask_url_for('static', filename=f"uploads/profile_{user.id}.{ext}")
                    break
            
            is_pro = user.is_pro_active()
            total_predictions = Prediction.query.filter_by(cust_id=user.id).count()
            return render_template('user/profile.html', user=user, profile_image_url=profile_image_url, is_pro=is_pro, total_predictions=total_predictions)
        
        return _profile()
    
    return analysis_bp

