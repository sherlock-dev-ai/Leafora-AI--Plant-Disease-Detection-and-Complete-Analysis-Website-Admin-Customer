from app import app, db, User
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    print(f"ADMIN_EMAIL:{admin.email if admin else 'None'}")
