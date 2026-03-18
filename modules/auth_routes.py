"""
Customer Registration Module
Handles user registration, login, and logout
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone

from modules.models import User, UsageCounter
from modules.utils import generate_customer_id

# This will be initialized from app.py
db = None

def init_auth_routes(database, flask_app):
    """Initialize auth routes with database and app"""
    global db
    db = database
    
    auth_bp = Blueprint('auth', __name__)
    
    @auth_bp.route('/register', methods=['GET', 'POST'])
    def register():
        """User registration"""
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            # Validation
            if not username or not email or not password:
                flash('All fields are required.', 'danger')
                return render_template('auth/register.html')
            
            if password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return render_template('auth/register.html')
            
            if len(password) < 6:
                flash('Password must be at least 6 characters long.', 'danger')
                return render_template('auth/register.html')
            
            # Check if user exists
            if User.query.filter_by(email=email).first():
                flash('Email already registered. Please login.', 'warning')
                return redirect(url_for('login'))
            
            if User.query.filter_by(username=username).first():
                flash('Username already taken. Please choose another.', 'danger')
                return render_template('auth/register.html')
            
            # Create new user with customer ID
            password_hash = generate_password_hash(password)
            customer_id = generate_customer_id()
            new_user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                customer_id=customer_id
            )
            
            db.session.add(new_user)
            db.session.commit()
            
            # Create usage counter with daily reset
            tomorrow = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            counter = UsageCounter(
                user_id=new_user.id, 
                total_predictions=0,
                today_count=0,
                daily_reset_at=tomorrow,
                monthly_predictions=0
            )
            db.session.add(counter)
            db.session.commit()
            
            flash('Registration successful! Welcome to Leafora AI. You have 3 detections per day on the Basic plan.', 'success')
            session['show_usage_info'] = True
            session['new_user_id'] = new_user.id
            return redirect(url_for('login'))
        
        return render_template('auth/register.html')
    
    
    @auth_bp.route('/login', methods=['GET', 'POST'])
    def login():
        """User login"""
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            
            if not email or not password:
                flash('Please enter both email and password.', 'danger')
                return render_template('auth/login.html')
            
            user = User.query.filter_by(email=email).first()
            
            if not user:
                flash('Invalid email or password.', 'danger')
                return render_template('auth/login.html')
            
            # Check if user is deleted/banned
            try:
                if hasattr(user, 'is_deleted') and user.is_deleted:
                    flash('User has been banned from the session. Please contact administrator.', 'danger')
                    return render_template('auth/login.html')
            except Exception:
                pass
            
            if check_password_hash(user.password_hash, password):
                session['user_id'] = user.id
                session['username'] = user.username
                session['is_admin'] = user.is_admin
                
                # Show usage info if new user just registered
                if session.get('show_usage_info') and session.get('new_user_id') == user.id:
                    counter = UsageCounter.query.filter_by(user_id=user.id).first()
                    today_usage = counter.today_count if counter else 0
                    remaining = max(0, 3 - today_usage)
                    flash(f'Welcome, {user.username}! You have {remaining}/3 detections remaining today on the Basic plan.', 'info')
                    session.pop('show_usage_info', None)
                    session.pop('new_user_id', None)
                else:
                    # Show usage for existing users
                    counter = UsageCounter.query.filter_by(user_id=user.id).first()
                    now = datetime.now(timezone.utc)
                    if counter and counter.daily_reset_at:
                        from modules.utils import ensure_timezone_aware
                        reset_at = ensure_timezone_aware(counter.daily_reset_at)
                        if reset_at and reset_at < now:
                            counter.today_count = 0
                            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                            counter.daily_reset_at = tomorrow
                            db.session.commit()
                    today_usage = counter.today_count if counter else 0
                    is_pro = user.is_pro_active()
                    # Removed welcome back messages

                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password.', 'danger')
                return render_template('auth/login.html')
        
        return render_template('auth/login.html')
    
    
    @auth_bp.route('/logout')
    def logout():
        """User logout"""
        session.clear()
        flash('You have been logged out successfully.', 'info')
        return redirect(url_for('index'))
    
    return auth_bp

