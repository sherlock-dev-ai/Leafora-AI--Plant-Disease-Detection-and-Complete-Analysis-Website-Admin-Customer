"""
Utility Functions for Leafora AI
Helper functions used across modules
"""
import os
import logging
import traceback
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# These will be imported from app.py
app = None
db = None

def init_utils(flask_app, database):
    """Initialize utils with Flask app and database"""
    global app, db
    app = flask_app
    db = database


def validate_image_file(image_path):
    """Validate that the file is a valid, readable image file"""
    try:
        from PIL import Image
        
        logger.info(f"[VALIDATE] Starting validation for: {image_path}")
        
        # Check if file exists
        if not os.path.exists(image_path):
            logger.error(f"[VALIDATE] File does not exist: {image_path}")
            return False, "Image file not found."
        
        # Check file size first (quick check)
        file_size = os.path.getsize(image_path)
        logger.info(f"[VALIDATE] File size: {file_size} bytes")
        if file_size == 0:
            logger.error(f"[VALIDATE] File is empty: {image_path}")
            return False, "Image file is empty. Please upload a valid image file."
        
        # Try to open and validate the image
        try:
            logger.info(f"[VALIDATE] Attempting to open image with PIL: {image_path}")
            img = Image.open(image_path)
            logger.info(f"[VALIDATE] Image opened successfully. Format: {img.format}, Mode: {img.mode}")
            
            # Verify the image can be loaded and has valid dimensions
            try:
                width, height = img.size
                logger.info(f"[VALIDATE] Image dimensions: {width}x{height}")
                
                if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
                    img.close()
                    logger.error(f"[VALIDATE] Invalid dimension types")
                    return False, "Invalid image dimensions. Please upload a valid image file."
                
                if width < 50 or height < 50:
                    img.close()
                    logger.warning(f"[VALIDATE] Image too small: {width}x{height}")
                    return False, "Image is too small. Please upload a larger image (minimum 50x50 pixels)."
                
                if width > 10000 or height > 10000:
                    img.close()
                    logger.warning(f"[VALIDATE] Image too large: {width}x{height}")
                    return False, "Image is too large. Please upload a smaller image (maximum 10000x10000 pixels)."
                
                # Verify the image can be converted to RGB
                try:
                    logger.info(f"[VALIDATE] Attempting RGB conversion from mode: {img.mode}")
                    img_rgb = img.convert('RGB')
                    logger.info(f"[VALIDATE] RGB conversion successful")
                    img_rgb.load()
                    logger.info(f"[VALIDATE] Image loaded successfully")
                    img_rgb.close()
                except Exception as convert_error:
                    img.close()
                    logger.error(f"[VALIDATE] RGB conversion failed: {convert_error}")
                    return False, f"Invalid image format. The image cannot be processed: {str(convert_error)[:100]}. Please upload a valid image file (PNG, JPG, JPEG, GIF, or BMP)."
                
                img.close()
                logger.info(f"[VALIDATE] Validation successful for: {image_path}")
                return True, None
            except Exception as dim_error:
                img.close()
                logger.error(f"[VALIDATE] Dimension check failed: {dim_error}")
                return False, f"Invalid image format. Dimension check failed: {str(dim_error)[:100]}. Please upload a valid image file (PNG, JPG, JPEG, GIF, or BMP)."
        except IOError as e:
            error_msg = str(e).lower()
            logger.error(f"[VALIDATE] IOError: {e}")
            if "cannot identify image file" in error_msg or "cannot open" in error_msg:
                return False, "Invalid image format. The file does not appear to be a valid image file (PNG, JPG, JPEG, GIF, or BMP)."
            elif "truncated" in error_msg or "corrupt" in error_msg:
                return False, "Image file appears to be corrupted or incomplete. Please try uploading again or use a different image."
            else:
                return False, f"Invalid image format. IOError: {str(e)[:100]}. Please upload a valid image file (PNG, JPG, JPEG, GIF, or BMP)."
        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"[VALIDATE] Unexpected error: {error_type}: {error_msg}")
            return False, f"Invalid image format. Error: {error_type}: {str(e)[:100]}. Please upload a valid image file (PNG, JPG, JPEG, GIF, or BMP)."
    except Exception as e:
        logger.error(f"[VALIDATE] Outer exception: {type(e).__name__}: {e}")
        return False, f"Invalid image format. Validation error: {str(e)[:100]}. Please upload a valid image file."


def validate_leaf_image(image_path):
    """Basic validation to check if image appears to be a leaf/plant"""
    try:
        from PIL import Image
        import numpy as np
        
        logger.info(f"[LEAF_VALIDATE] Starting leaf validation for: {image_path}")
        
        # First validate it's a valid image file
        is_valid, error_msg = validate_image_file(image_path)
        if not is_valid:
            logger.warning(f"[LEAF_VALIDATE] Image file validation failed: {error_msg}")
            return False, error_msg
        
        logger.info(f"[LEAF_VALIDATE] Image file validation passed, checking leaf content...")
        
        try:
            img = Image.open(image_path).convert('RGB')
            logger.info(f"[LEAF_VALIDATE] Image opened and converted to RGB")
            
            img_array = np.array(img)
            logger.info(f"[LEAF_VALIDATE] Converted to numpy array, shape: {img_array.shape}")
            
            if len(img_array.shape) < 2:
                logger.error(f"[LEAF_VALIDATE] Invalid array shape: {img_array.shape}")
                return False, "Invalid image format. Image dimensions are invalid."
            
            height, width = img_array.shape[:2]
            logger.info(f"[LEAF_VALIDATE] Image dimensions: {width}x{height}")
            
            if width < 50 or height < 50:
                logger.warning(f"[LEAF_VALIDATE] Image too small: {width}x{height}")
                return False, "Image is too small. Please upload a larger image."
            
            logger.info(f"[LEAF_VALIDATE] Leaf validation passed")
            return True, None
        except Exception as img_error:
            logger.error(f"[LEAF_VALIDATE] Error processing image: {img_error}")
            return False, f"Invalid image format. Error processing image: {str(img_error)[:100]}. Please upload a valid image file."
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"[LEAF_VALIDATE] Outer exception: {error_type}: {e}")
        return False, f"Invalid image format. Validation error: {error_type}: {str(e)[:100]}. Please upload a valid image file."


def allowed_file(filename):
    """Check if file extension is allowed"""
    if app is None:
        return False
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def luhn_checksum(card_number):
    """Validate card number using Luhn algorithm"""
    digits = [int(x) for x in card_number if x.isdigit()]
    
    if len(digits) < 13 or len(digits) > 19:
        return False
    
    checksum = 0
    dbl = False
    for d in digits[::-1]:
        if dbl:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
        dbl = not dbl
    
    return checksum % 10 == 0


def validate_card(card_number, expiry_mm_yy, cvv, cardholder_name):
    """Validate card details"""
    errors = []
    
    if not luhn_checksum(card_number):
        errors.append("Invalid card number")
    
    try:
        month, year = expiry_mm_yy.split('/')
        month = int(month)
        year = int(year)
        if month < 1 or month > 12:
            errors.append("Invalid expiry month")
        else:
            current_year = datetime.now().year
            full_year = 2000 + year if year < 100 else year
            expiry_date = datetime(full_year, month, 1)
            if expiry_date < datetime.now().replace(day=1):
                errors.append("Card has expired")
    except (ValueError, AttributeError):
        errors.append("Invalid expiry format (use MM/YY)")
    
    if not cvv or not cvv.isdigit() or len(cvv) != 3:
        errors.append("CVV must be exactly 3 digits")
    
    if not cardholder_name or len(cardholder_name.strip()) < 2:
        errors.append("Cardholder name is required")
    
    return len(errors) == 0, errors


def get_card_brand(card_number):
    """Detect card brand from card number"""
    digits = ''.join([x for x in card_number if x.isdigit()])
    if digits.startswith('4'):
        return 'Visa'
    elif digits.startswith('5') or digits.startswith('2'):
        return 'Mastercard'
    elif digits.startswith('3'):
        return 'American Express'
    elif digits.startswith('6'):
        return 'Discover'
    else:
        return 'Unknown'


def generate_customer_id():
    """Generate formatted customer ID (for display purposes only)
    Note: customer_id in database is now user.id (INTEGER)
    This function returns a formatted string like CUST-YYYYMMDD-####
    """
    from modules.models import User
    from sqlalchemy import func
    
    # Customer ID is now just user.id, but we can generate a display format
    date_str = datetime.now().strftime('%Y%m%d')
    # Get next user ID
    max_id = db.session.query(func.max(User.id)).scalar() or 0
    next_id = max_id + 1
    return f"CUST-{date_str}-{next_id:04d}"


def ensure_timezone_aware(dt):
    """Ensure datetime is timezone-aware (assume UTC if naive)"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def check_usage_limit(user):
    """Check if user has reached free tier limit (3 predictions per day)"""
    from modules.models import UsageCounter
    
    if user.is_pro_active():
        return True, None
    
    counter = UsageCounter.query.filter_by(user_id=user.id).first()
    now = datetime.now(timezone.utc)
    
    if not counter:
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        counter = UsageCounter(
            user_id=user.id, 
            total_predictions=0,
            today_count=0,
            daily_reset_at=tomorrow
        )
        db.session.add(counter)
        db.session.commit()
    
    if counter.daily_reset_at:
        reset_at = ensure_timezone_aware(counter.daily_reset_at)
        if reset_at and reset_at < now:
            counter.today_count = 0
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            counter.daily_reset_at = tomorrow
            db.session.commit()
    
    if counter.today_count >= 3:
        return False, "You have reached the free tier limit of 3 detections per day. Please upgrade to Pro for unlimited detections."
    
    return True, None


def increment_usage(user):
    """Increment usage counter for user (daily and total predictions)"""
    from modules.models import UsageCounter
    
    counter = UsageCounter.query.filter_by(user_id=user.id).first()
    now = datetime.now(timezone.utc)
    
    if not counter:
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        counter = UsageCounter(
            user_id=user.id, 
            total_predictions=0,
            today_count=0,
            daily_reset_at=tomorrow
        )
        db.session.add(counter)
    
    if counter.daily_reset_at:
        reset_at = ensure_timezone_aware(counter.daily_reset_at)
        if reset_at and reset_at < now:
            counter.today_count = 0
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            counter.daily_reset_at = tomorrow
    
    counter.total_predictions += 1
    counter.today_count += 1
    counter.last_prediction_at = now
    db.session.commit()


def check_and_notify_expired_plan(user):
    """Check if user's Pro plan has expired and send notification if needed"""
    from modules.models import Notification
    
    if user.is_pro and user.pro_expires_at:
        expires_at = ensure_timezone_aware(user.pro_expires_at)
        now = datetime.now(timezone.utc)
        
        if expires_at and expires_at < now and user.is_pro:
            recent_notification = Notification.query.filter_by(
                user_id=user.id,
                notification_type='warning',
                is_system=True
            ).filter(
                Notification.message.like('%Pro subscription has expired%'),
                Notification.created_at > (now - timedelta(days=1))
            ).first()
            
            if not recent_notification:
                notification = Notification(
                    user_id=user.id,
                    title='Pro Plan Expired',
                    message=f'Your Pro subscription expired on {expires_at.strftime("%B %d, %Y")}. Upgrade to Pro to continue enjoying unlimited disease detections!',
                    notification_type='warning',
                    is_system=True
                )
                db.session.add(notification)
                user.is_pro = False
                db.session.commit()


def generate_receipt_pdf(payment):
    """Generate receipt PDF for payment"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        
        receipts_dir = os.path.join(app.config['UPLOAD_FOLDER'], '..', 'receipts')
        os.makedirs(receipts_dir, exist_ok=True)
        
        receipt_path = os.path.join(receipts_dir, f'receipt_{payment.id}.pdf')
        
        c = canvas.Canvas(receipt_path, pagesize=letter)
        width, height = letter
        
        c.setFont("Helvetica-Bold", 20)
        c.drawString(100, height - 50, "Leafora AI - Payment Receipt")
        
        y = height - 100
        c.setFont("Helvetica", 12)
        c.drawString(100, y, f"Payment ID: {payment.id}")
        y -= 20
        c.drawString(100, y, f"Date: {payment.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        y -= 20
        c.drawString(100, y, f"Customer: {payment.user.username} ({payment.user.email})")
        y -= 20
        
        if payment.currency == 'INR':
            amount_str = f"₹{payment.amount_cents / 100:.2f} {payment.currency}"
        else:
            amount_str = f"${payment.amount_cents / 100:.2f} {payment.currency}"
        c.drawString(100, y, f"Amount: {amount_str}")
        y -= 20
        c.drawString(100, y, f"Card: **** **** **** {payment.card_last4} ({payment.card_brand})")
        y -= 20
        c.drawString(100, y, f"Status: {payment.status.upper()}")
        if payment.expires_at:
            y -= 20
            c.drawString(100, y, f"Pro expires: {payment.expires_at.strftime('%Y-%m-%d')}")
        
        y = 100
        c.setFont("Helvetica", 10)
        c.drawString(100, y, "Thank you for your purchase!")
        y -= 15
        c.drawString(100, y, "Leafora AI - Plant Disease Detection System")
        
        c.save()
        return receipt_path
    except ImportError:
        logger.warning("reportlab not installed, cannot generate PDF receipt")
        return None
    except Exception as e:
        logger.error(f"Error generating receipt PDF: {e}")
        return None

