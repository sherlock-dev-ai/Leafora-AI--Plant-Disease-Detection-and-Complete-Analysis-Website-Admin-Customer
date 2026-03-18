"""
Leafora AI - Deep Learning Crop Disease Detection System
Main Flask Application - Professional Edition
"""
print("DEBUG: app.py is loading...")
import os
import json
import logging
import requests
import base64
import sqlite3
import uuid

# Set Keras backend to TensorFlow (if using TF)
os.environ["KERAS_BACKEND"] = "tensorflow"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"  # Suppress all TensorFlow logs
os.environ['KERAS_ALLOW_UNSAFE_DESERIALIZATION'] = '1'  # Enable unsafe deserialization for incompatible models

# Suppress all warnings
import warnings
warnings.filterwarnings('ignore')

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file, Response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, or_, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine import Engine
from sqlalchemy.orm import joinedload
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app_errors.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import prediction module
try:
    import predict
except ImportError as e:
    logger.error(f"Failed to import predict module: {e}")
    logger.error("Please ensure predict.py exists in the project root")
    raise

from config import Config

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
app.config['TEMPLATES_AUTO_RELOAD'] = True  # Ensure templates reload without server restart
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable static file caching during dev
if str(app.config.get('SQLALCHEMY_DATABASE_URI', '')).startswith('sqlite'):
    engine_opts = dict(app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {}))
    connect_args = dict(engine_opts.get('connect_args', {}))
    connect_args.setdefault('timeout', 30)
    engine_opts['connect_args'] = connect_args
    engine_opts.setdefault('pool_pre_ping', True)
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_opts

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)


def _is_sqlite_disk_io_error(exc):
    """Return True when sqlite reports a transient disk I/O error."""
    return 'disk i/o error' in str(exc).lower()


def _reset_db_connection():
    """Drop potentially stale SQLAlchemy/SQLite connections."""
    try:
        db.session.rollback()
    except Exception:
        pass
    try:
        db.session.remove()
    except Exception:
        pass
    try:
        db.engine.dispose()
    except Exception:
        pass


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    """Set SQLite pragmas that reduce transient I/O and lock errors."""
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()

# Custom Jinja2 filters
@app.template_filter('from_json')
def from_json_filter(value):
    """Parse JSON string to Python object"""
    if not value:
        return None
    try:
        if isinstance(value, str):
            return json.loads(value)
        return value
    except (json.JSONDecodeError, TypeError):
        return value

try:
    with open('disease_info.json', 'r') as f:
        DISEASE_DETAILS = json.load(f)
except Exception as e:
    logger.error(f"Failed to load disease_info.json: {e}")
    DISEASE_DETAILS = {}


def build_disease_recommendations(topk, primary_label, max_items=3):
    results = []
    if not topk:
        return results
    for item in topk[:max_items]:
        try:
            label = item.get('label') or primary_label
        except AttributeError:
            label = primary_label
        base_info = DISEASE_DETAILS.get(label) or DISEASE_DETAILS.get(primary_label) or "Continue monitoring your plant for any changes."
        try:
            conf_val = item.get('confidence')
            if conf_val is None and 'prob' in item:
                conf_val = float(item.get('prob', 0)) * 100.0
        except AttributeError:
            conf_val = 0.0
        try:
            conf_float = float(conf_val) if conf_val is not None else 0.0
        except (TypeError, ValueError):
            conf_float = 0.0
        results.append({
            'label': label,
            'confidence': conf_float,
            'info': base_info
        })
    return results


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_form_bool(value):
    """Parse form values into a strict boolean."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False

    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n", ""}:
        return False

    try:
        return float(text) != 0.0
    except (TypeError, ValueError):
        return False


def _split_crop_and_disease(label):
    text = str(label or '').strip()
    if not text:
        return "Unknown Crop", "Unknown Condition"
    if " - " in text:
        crop, disease = text.split(" - ", 1)
        return crop.strip() or "Unknown Crop", disease.strip() or "Unknown Condition"
    if text.lower().startswith("healthy ") and text.lower().endswith(" leaf"):
        crop = text[len("healthy "):-len(" leaf")].strip()
        return crop or "Unknown Crop", "Healthy"
    return "General Plant", text


def _infer_pathogen_type(disease_name):
    lower = str(disease_name or '').lower()
    if "healthy" in lower:
        return "Non-disease"
    if any(key in lower for key in ("mite", "hispa", "insect", "aphid", "whitefl")):
        return "Pest"
    if any(key in lower for key in ("virus", "mosaic", "curl", "tungro")):
        return "Viral"
    if "bacterial" in lower:
        return "Bacterial"
    if any(key in lower for key in ("rust", "mildew", "spot", "blight", "scab", "rot", "mold", "blast", "scald", "scorch", "measles")):
        return "Fungal"
    return "Plant Stress"


def _infer_risk_level(label, confidence):
    lower = str(label or '').lower()
    conf = _safe_float(confidence, 0.0)
    if "healthy" in lower:
        return "Low"
    if any(key in lower for key in ("unknown", "background", "no plant")):
        return "Unknown"
    if conf >= 90:
        return "High"
    if conf >= 75:
        return "Moderate"
    return "Watchlist"


def _extract_actions_from_info(info, max_items=4):
    if not info:
        return []
    actions = []
    for chunk in str(info).replace(";", ".").split("."):
        action = chunk.strip()
        if action:
            actions.append(action)
        if len(actions) >= max_items:
            break
    return actions


def _infer_symptoms(disease_name):
    lower = str(disease_name or '').lower()
    if "healthy" in lower:
        return [
            "Leaf color and texture appear consistent",
            "No obvious lesion expansion was detected",
            "No rapid tissue decay pattern is visible",
        ]
    symptoms = []
    if any(key in lower for key in ("spot", "scab", "blight", "scorch", "scald")):
        symptoms.append("Discolored spots or lesions on leaf tissue")
    if any(key in lower for key in ("mildew", "mold", "rust")):
        symptoms.append("Powdery, fuzzy, or rust-like surface growth")
    if any(key in lower for key in ("rot", "measles")):
        symptoms.append("Dark necrotic patches and gradual tissue collapse")
    if any(key in lower for key in ("virus", "mosaic", "curl", "tungro")):
        symptoms.append("Leaf distortion, yellowing, or mosaic pattern")
    if any(key in lower for key in ("mite", "hispa", "insect")):
        symptoms.append("Feeding marks, stippling, or scraped leaf surface")
    if not symptoms:
        symptoms = [
            "Localized discoloration on affected areas",
            "Potential spread of lesions over time",
            "Reduced vigor in heavily affected leaves",
        ]
    return symptoms[:3]


def build_disease_description(label, confidence=None):
    confidence_note = ""
    conf_val = _safe_float(confidence, None)
    if conf_val is not None:
        confidence_note = f" (model confidence: {conf_val:.1f}%)."

    if not label:
        return "The detected disease can affect leaf health and yield if not managed." + confidence_note
    lower = str(label).lower()
    if "healthy" in lower:
        return "The model did not detect significant disease symptoms in this leaf." + confidence_note
    parts = str(label).split("-", 1)
    if len(parts) == 2:
        crop = parts[0].strip()
        name = parts[1].strip()
        return f"{name} is a disease of {crop.lower()} that affects leaves and can reduce plant vigor and yield if not treated." + confidence_note
    return f"{label} is a plant disease that affects leaves and overall plant health if not managed in time." + confidence_note


def build_disease_profile(label, confidence=None):
    if not label:
        return None

    crop, disease_name = _split_crop_and_disease(label)
    disease_key = str(label).strip()
    disease_info = (
        DISEASE_DETAILS.get(disease_key)
        or DISEASE_DETAILS.get(disease_name)
        or "Continue monitoring your plant for any changes."
    )

    risk_level = _infer_risk_level(disease_key, confidence)
    pathogen_type = _infer_pathogen_type(disease_name)
    symptoms = _infer_symptoms(disease_name)
    actions = _extract_actions_from_info(disease_info)

    lower = disease_key.lower()
    if "healthy" in lower:
        summary = f"{crop} leaf appears healthy. Maintain routine monitoring and preventive care."
        impact = "Current signs indicate low immediate risk to leaf function and yield."
    elif any(key in lower for key in ("unknown", "background", "no plant")):
        summary = "The image could not be mapped to a known disease class with enough certainty for a specific diagnosis."
        impact = "Disease impact cannot be estimated reliably from this image alone."
        actions = [
            "Retake the image in natural light with one leaf in focus",
            "Avoid motion blur and capture both front and back of affected leaves",
            "Seek field inspection if symptoms are spreading rapidly",
        ]
    else:
        base_summary = build_disease_description(disease_key, confidence=confidence)
        if disease_info and disease_info != "Continue monitoring your plant for any changes.":
            summary = f"{base_summary} Recommended control focus: {disease_info}"
        else:
            summary = base_summary
        if risk_level in ("High", "Moderate"):
            impact = "Without timely control, symptoms may spread and reduce photosynthesis, plant vigor, and yield."
        else:
            impact = "Current impact may be limited, but progression is possible if unmanaged."

    if not actions:
        actions = [
            "Isolate severely affected leaves where practical",
            "Improve canopy airflow and avoid prolonged leaf wetness",
            "Monitor over the next 3 to 5 days and re-scan if symptoms change",
        ]

    return {
        "crop": crop,
        "pathogen_type": pathogen_type,
        "risk_level": risk_level,
        "summary": summary,
        "symptoms": symptoms,
        "impact": impact,
        "actions": actions[:4],
    }

def ensure_timezone_aware(dt):
    """Ensure a datetime object is timezone-aware (UTC)"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


ADMIN_VISUAL_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), 'admin_visual_settings.json')

CURSOR_ANIMATION_OPTIONS = [
    {'id': 'classic_triple', 'name': 'Classic Triple', 'description': 'Default triple-ring cursor with smooth follow.'},
    {'id': 'comet_trail', 'name': 'Comet Trail', 'description': 'Bright leading point with a long trailing motion.'},
    {'id': 'neon_pulse', 'name': 'Neon Pulse', 'description': 'Pulse effect on hover and click events.'},
    {'id': 'magnetic_ring', 'name': 'Magnetic Ring', 'description': 'Outer ring stretches toward interactive items.'},
    {'id': 'minimal_dot', 'name': 'Minimal Dot', 'description': 'Single low-noise precision cursor style.'},
    {'id': 'ripple_click', 'name': 'Ripple Click', 'description': 'Concentric rings on click with subtle decay.'},
    {'id': 'orbit_dual', 'name': 'Orbit Dual', 'description': 'Two orbiting followers around pointer center.'},
    {'id': 'kinetic_spark', 'name': 'Kinetic Spark', 'description': 'Fast micro-spark accents while moving.'},
]

PAGE_ANIMATION_OPTIONS = [
    {'id': 'moving_dots', 'name': 'Moving Dots', 'description': 'Floating particles with curved connection lines.'},
    {'id': 'bio_nodes', 'name': 'Bio Nodes', 'description': 'Organic glowing nodes with pulse movement.'},
    {'id': 'leaf_stream', 'name': 'Leaf Stream', 'description': 'Leaf-like particles drifting diagonally.'},
    {'id': 'aurora_wave', 'name': 'Aurora Wave', 'description': 'Soft layered wave gradients in motion.'},
    {'id': 'matrix_grid', 'name': 'Matrix Grid', 'description': 'Subtle animated technical grid overlay.'},
    {'id': 'nebula_cloud', 'name': 'Nebula Cloud', 'description': 'Smoky cloud motion with dim highlights.'},
    {'id': 'radial_bloom', 'name': 'Radial Bloom', 'description': 'Breathing radial energy blooms.'},
    {'id': 'static_clean', 'name': 'Static Clean', 'description': 'No motion, minimal static themed background.'},
]

PAGE_TARGET_OPTIONS = [
    {'id': 'global', 'name': 'All Pages (Default)'},
    {'id': 'dashboard', 'name': 'Dashboard'},
    {'id': 'upload', 'name': 'Upload'},
    {'id': 'result', 'name': 'Result'},
    {'id': 'history', 'name': 'History'},
    {'id': 'profile', 'name': 'Profile'},
    {'id': 'admin_dashboard', 'name': 'Admin Dashboard'},
    {'id': 'admin_predictions', 'name': 'Admin Predictions'},
    {'id': 'admin_system_logs', 'name': 'Server Management'},
]


def _get_default_admin_visual_settings():
    return {
        'cursor_animation': 'classic_triple',
        'page_animations': {'global': 'moving_dots'}
    }


def _load_admin_visual_settings():
    defaults = _get_default_admin_visual_settings()
    try:
        if not os.path.exists(ADMIN_VISUAL_SETTINGS_PATH):
            return defaults
        with open(ADMIN_VISUAL_SETTINGS_PATH, 'r', encoding='utf-8') as f:
            loaded = json.load(f) or {}
        settings = {
            'cursor_animation': loaded.get('cursor_animation', defaults['cursor_animation']),
            'page_animations': loaded.get('page_animations', defaults['page_animations'])
        }
        if not isinstance(settings['page_animations'], dict):
            settings['page_animations'] = defaults['page_animations']
        return settings
    except Exception as e:
        logger.warning(f"Failed to load admin visual settings: {e}")
        return defaults


def _save_admin_visual_settings(settings):
    try:
        with open(ADMIN_VISUAL_SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save admin visual settings: {e}")
        return False


def _extract_model_names_from_models_used(raw_models_used):
    """Normalize Prediction.models_used into a set of model names."""
    names = set()
    try:
        payload = raw_models_used
        if isinstance(payload, str):
            payload = json.loads(payload) if payload else []
        if not isinstance(payload, list):
            payload = [payload]
        for item in payload:
            if isinstance(item, dict):
                model_name = item.get('name') or item.get('model_name')
                if model_name:
                    names.add(str(model_name))
            elif item:
                names.add(str(item))
    except Exception:
        return set()
    return names


def _collect_model_inventory_and_usage():
    """Build model inventory merged with prediction usage statistics."""
    model_map = {}
    loaded_models = []
    try:
        loaded_models = predict.load_all_models()
    except Exception:
        loaded_models = []

    for model_info in loaded_models:
        model_name = str(model_info.get('name', '')).strip()
        if not model_name:
            continue
        model_map[model_name] = {
            'name': model_name,
            'size_mb': float(model_info.get('size_mb', 0) or 0),
            'classes': len(model_info.get('classes', []) or []),
            'predictions_count': 0,
            'avg_confidence': 0.0
        }

    def _scan_dir_for_models(dir_path):
        if not os.path.isdir(dir_path):
            return
        try:
            for file in os.listdir(dir_path):
                if not file.endswith(('.keras', '.h5')) or file.endswith('.crdownload'):
                    continue
                file_path = os.path.join(dir_path, file)
                try:
                    size_mb = os.path.getsize(file_path) / (1024 * 1024)
                except Exception:
                    size_mb = 0
                if file not in model_map:
                    model_map[file] = {
                        'name': file,
                        'size_mb': size_mb,
                        'classes': 0,
                        'predictions_count': 0,
                        'avg_confidence': 0.0
                    }
                elif not model_map[file].get('size_mb'):
                    model_map[file]['size_mb'] = size_mb
        except Exception as e:
            logger.warning(f"Error scanning model dir {dir_path}: {e}")

    _scan_dir_for_models(getattr(predict, 'MODEL_DIR', os.path.join(os.path.dirname(__file__), 'models')))
    _scan_dir_for_models(os.path.join(os.path.dirname(__file__), 'trained_models'))
    _scan_dir_for_models(os.path.join(os.path.dirname(__file__), 'detection'))

    final_dir = getattr(predict, 'FINAL_MODELS_DIR', os.path.join(os.path.dirname(__file__), 'models', 'final_models'))
    if os.path.isdir(final_dir):
        plant_model_path = os.path.join(final_dir, 'plant_classifier.keras')
        if os.path.exists(plant_model_path):
            try:
                model_map['plant_classifier.keras'] = {
                    'name': 'plant_classifier.keras',
                    'size_mb': os.path.getsize(plant_model_path) / (1024 * 1024),
                    'classes': model_map.get('plant_classifier.keras', {}).get('classes', 0),
                    'predictions_count': 0,
                    'avg_confidence': 0.0
                }
            except Exception:
                pass
        try:
            for entry in os.listdir(final_dir):
                if not entry.startswith('disease_'):
                    continue
                ddir = os.path.join(final_dir, entry)
                if not os.path.isdir(ddir):
                    continue
                for f in os.listdir(ddir):
                    if not f.endswith('_disease_classifier.keras'):
                        continue
                    fpath = os.path.join(ddir, f)
                    try:
                        size_mb = os.path.getsize(fpath) / (1024 * 1024)
                    except Exception:
                        size_mb = 0
                    if f not in model_map:
                        model_map[f] = {
                            'name': f,
                            'size_mb': size_mb,
                            'classes': 0,
                            'predictions_count': 0,
                            'avg_confidence': 0.0
                        }
        except Exception:
            pass

    confidence_sums = {}
    confidence_counts = {}
    all_predictions = Prediction.query.all()
    for prediction in all_predictions:
        used_model_names = _extract_model_names_from_models_used(prediction.models_used)
        for model_name in used_model_names:
            if model_name not in model_map:
                model_map[model_name] = {
                    'name': model_name,
                    'size_mb': 0,
                    'classes': 0,
                    'predictions_count': 0,
                    'avg_confidence': 0.0
                }
            model_map[model_name]['predictions_count'] += 1
            confidence_sums[model_name] = confidence_sums.get(model_name, 0.0) + float(prediction.confidence or 0.0)
            confidence_counts[model_name] = confidence_counts.get(model_name, 0) + 1

    for model_name, stats in model_map.items():
        if confidence_counts.get(model_name):
            stats['avg_confidence'] = round(confidence_sums[model_name] / confidence_counts[model_name], 2)
        else:
            stats['avg_confidence'] = 0.0

    return sorted(
        model_map.values(),
        key=lambda x: (-int(x.get('predictions_count', 0)), x.get('name', '').lower())
    )


# Database Models
class User(db.Model):
    __tablename__ = 'tbl_login'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    theme = db.Column(db.String(10), default='light')
    last_login = db.Column(db.DateTime, nullable=True)

    @property
    def customer(self):
        return db.session.query(Customer).filter_by(customer_id=self.id).first()

    @property
    def is_admin(self):
        c = self.customer
        try:
            return bool(c.is_admin) if c else False
        except AttributeError:
            return False

    @property
    def is_pro(self):
        c = self.customer
        try:
            return bool(c.is_pro) if c else False
        except AttributeError:
            return False

    @property
    def pro_expires_at(self):
        c = self.customer
        try:
            return c.pro_expires_at if c else None
        except AttributeError:
            return None

    @property
    def is_deleted(self):
        c = self.customer
        try:
            return bool(c.is_deleted) if c else False
        except AttributeError:
            return False

    @property
    def created_at(self):
        c = self.customer
        try:
            return c.created_at if c else None
        except AttributeError:
            return None

    def is_pro_active(self):
        c = self.customer
        if not c or not c.is_pro:
            return False
        if c.pro_expires_at:
            expires_at = ensure_timezone_aware(c.pro_expires_at)
            if expires_at and expires_at < datetime.now(timezone.utc):
                return False
        return True

class Customer(db.Model):
    __tablename__ = 'tbl_customer'
    customer_id = db.Column(db.Integer, db.ForeignKey('tbl_login.id'), primary_key=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_pro = db.Column(db.Integer, nullable=False, default=0)
    pro_expires_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_logout_at = db.Column(db.DateTime, nullable=True)
    subscription_purchased_at = db.Column(db.DateTime, nullable=True)
    email = db.Column(db.String(120), nullable=False, default='')
    password_hash = db.Column(db.String(255), nullable=False, default='')

    def __repr__(self):
        return f'<Customer {self.customer_id}>'

    @property
    def id(self):
        return self.customer_id

    @property
    def username(self):
        u = db.session.get(User, self.customer_id)
        return u.username if u else None

    @property
    def gmail(self):
        return self.email

    @property
    def encrypted_pass(self):
        return self.password_hash

    @property
    def subscription_purchased_at_resolved(self):
        try:
            sub = (db.session.query(Subscription)
                   .filter(Subscription.cust_id == self.customer_id)
                   .order_by(Subscription.start_date.desc().nullslast(), Subscription.created_at.desc().nullslast())
                   .first())
            if sub:
                return ensure_timezone_aware(sub.start_date or sub.created_at)
        except Exception:
            pass
        return ensure_timezone_aware(self.subscription_purchased_at) if self.subscription_purchased_at else None

    def is_pro_active(self):
        if not self.is_pro:
            return False
        if self.pro_expires_at:
            expires_at = ensure_timezone_aware(self.pro_expires_at)
            if expires_at and expires_at < datetime.now(timezone.utc):
                return False
        return True


class Prediction(db.Model):
    """Prediction model for storing disease detection results"""
    __tablename__ = 'tbl_prediction'
    
    id = db.Column(db.Integer, primary_key=True)
    cust_id = db.Column(db.Integer, db.ForeignKey('tbl_customer.customer_id'), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    result = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    topk_results = db.Column(db.Text)  # JSON string of top-k predictions
    models_used = db.Column(db.Text)  # JSON list of model names used
    is_unknown = db.Column(db.Boolean, default=False)  # Unknown/out-of-distribution flag
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    customer = db.relationship('Customer', foreign_keys=[cust_id], backref='predictions_rel', lazy=True)
    
    @property
    def prediction_id(self):
        """Backward compatibility property - returns id"""
        return self.id
    
    @property
    def user_id(self):
        """Backward compatibility property - returns cust_id"""
        return self.cust_id
    
    @property
    def user(self):
        """Backward compatibility property - returns customer"""
        return self.customer
    
    def __repr__(self):
        return f'<Prediction {self.id} - {self.result}>'


# Plan and Card models removed - data merged into Subscription and Payment respectively

class Subscription(db.Model):
    """Subscription model - consolidated with plan data"""
    __tablename__ = 'tbl_subscription'
    
    subscription_id = db.Column(db.Integer, primary_key=True)
    cust_id = db.Column(db.Integer, db.ForeignKey('tbl_customer.customer_id'), nullable=True)
    # Plan fields (merged from tbl_plans)
    plan_name = db.Column(db.String(50), nullable=True)
    plan_price = db.Column(db.Numeric(10, 2), nullable=True)
    plan_duration = db.Column(db.Integer, nullable=True)  # Duration in days
    daily_limit = db.Column(db.Integer, nullable=True)  # NULL = unlimited
    plan_features = db.Column(db.Text, nullable=True)  # JSON string
    # Subscription fields
    start_date = db.Column(db.DateTime, nullable=True, default=lambda: datetime.now(timezone.utc))
    end_date = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='active')
    is_active = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, nullable=True, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    customer = db.relationship('Customer', foreign_keys=[cust_id], backref='subscriptions_rel', lazy=True)
    
    def __repr__(self):
        return f'<Subscription {self.subscription_id} - Customer {self.cust_id}>'
    
    @property
    def id(self):
        """Backward compatibility property"""
        return self.subscription_id
    
    def is_active_subscription(self):
        """Check if subscription is currently active"""
        if not self.is_active or self.status != 'active':
            return False
        if self.expires_at:
            expires_at = ensure_timezone_aware(self.expires_at)
            if expires_at and expires_at < datetime.now(timezone.utc):
                return False
        return True


class Payment(db.Model):
    """Payment model - consolidated with card data"""
    __tablename__ = 'tbl_payment'
    
    id = db.Column(db.Integer, primary_key=True)
    cust_id = db.Column(db.Integer, db.ForeignKey('tbl_customer.customer_id'), nullable=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('tbl_subscription.subscription_id'), nullable=True)
    # Card fields (merged from tbl_card)
    card_name = db.Column(db.String(50), nullable=True)
    card_no = db.Column(db.String(20), nullable=True)  # Encrypted
    card_last4 = db.Column(db.String(4), nullable=True)
    card_brand = db.Column(db.String(20), nullable=True)
    card_expiry = db.Column(db.Date, nullable=True)
    is_default = db.Column(db.Integer, default=0)
    # Payment fields
    payment_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    amount_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), default='USD')
    status = db.Column(db.String(20), default='completed')
    receipt_path = db.Column(db.String(255), nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)
    transaction_id = db.Column(db.String(255), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    customer = db.relationship('Customer', foreign_keys=[cust_id], backref='payments_rel', lazy=True)
    subscription = db.relationship('Subscription', foreign_keys=[subscription_id], backref='payments_rel', lazy=True)
    
    @property
    def user_id(self):
        """Backward compatibility property"""
        return self.cust_id
    
    @property
    def user(self):
        """Backward compatibility property"""
        return self.customer
    
    @property
    def payment_id(self):
        """Backward compatibility property"""
        return self.id
    
    def __repr__(self):
        if self.currency == 'INR':
            return f'<Payment {self.id} - ₹{self.amount_cents/100:.2f}>'
        else:
            return f'<Payment {self.id} - ${self.amount_cents/100:.2f}>'


class UsageCounter(db.Model):
    """Usage counter for tracking free tier limits (daily)"""
    __tablename__ = 'tbl_usage_counters'
    
    cust_id = db.Column(db.Integer, db.ForeignKey('tbl_customer.customer_id'), primary_key=True)
    total_predictions = db.Column(db.Integer, default=0)
    today_count = db.Column(db.Integer, default=0)
    daily_reset_at = db.Column(db.DateTime, nullable=True)
    monthly_predictions = db.Column(db.Integer, default=0)
    last_prediction_at = db.Column(db.DateTime, nullable=True)
    month_reset_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    customer = db.relationship('Customer', foreign_keys=[cust_id], backref='usage_counter_rel', uselist=False, lazy=True)
    
    @property
    def user_id(self):
        """Backward compatibility property"""
        return self.cust_id
    
    @property
    def user(self):
        """Backward compatibility property"""
        return self.customer
    
    def __repr__(self):
        return f'<UsageCounter cust_id={self.cust_id} today={self.today_count}>'


class Model(db.Model):
    """Model tracking table"""
    __tablename__ = 'tbl_models'
    
    # Use id as primary key to match existing database schema
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=True)
    backend = db.Column(db.String(10), default='tf')
    classes = db.Column(db.Integer, nullable=True)
    loaded = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=True, default=lambda: datetime.now(timezone.utc))
    
    # Legacy/alternate field names for compatibility
    name = db.Column(db.String(255), nullable=True)  # Some schemas use 'name' instead of filename
    # Note: model_name is NOT a database column - it's a property for backward compatibility
    
    def __repr__(self):
        display_name = self.name if self.name else self.filename
        return f'<Model {display_name}>'
    
    @property
    def model_id(self):
        """Backward compatibility property - returns id"""
        return self.id
    
    @property
    def model_name(self):
        """Backward compatibility property - returns name or filename"""
        return self.name if self.name else self.filename


class Notification(db.Model):
    """Notification model for user notifications"""
    __tablename__ = 'tbl_notification'
    
    id = db.Column(db.Integer, primary_key=True)
    cust_id = db.Column(db.Integer, db.ForeignKey('tbl_customer.customer_id'), nullable=True)  # None = all users
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), default='info')
    is_read = db.Column(db.Boolean, default=False)
    is_system = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    customer = db.relationship('Customer', foreign_keys=[cust_id], backref='notifications_rel', lazy=True)
    
    @property
    def user_id(self):
        """Backward compatibility property"""
        return self.cust_id
    
    def __repr__(self):
        recipient = f"Customer {self.cust_id}" if self.cust_id else "All Users"
        return f'<Notification {self.id} - {recipient} - {self.title}>'


# Helper Functions
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
        # Simply opening with PIL validates that it's a valid image file
        try:
            # Open the image - PIL will raise an error if it's not a valid image format
            # This works for JPEG, PNG, GIF, BMP, and other PIL-supported formats
            logger.info(f"[VALIDATE] Attempting to open image with PIL: {image_path}")
            img = Image.open(image_path)
            logger.info(f"[VALIDATE] Image opened successfully. Format: {img.format}, Mode: {img.mode}")
            
            # Verify the image can be loaded and has valid dimensions
            # This is more reliable than checking format, as some valid images
            # might not have format metadata but can still be processed
            try:
                # Try to get dimensions - this will fail if image is truly invalid
                width, height = img.size
                logger.info(f"[VALIDATE] Image dimensions: {width}x{height}")
                
                # Verify dimensions are valid numbers
                if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
                    img.close()
                    logger.error(f"[VALIDATE] Invalid dimension types: width={type(width)}, height={type(height)}")
                    return False, "Invalid image dimensions. Please upload a valid image file."
                
                # Check image dimensions (should be reasonable)
                if width < 50 or height < 50:
                    img.close()
                    logger.warning(f"[VALIDATE] Image too small: {width}x{height}")
                    return False, "Image is too small. Please upload a larger image (minimum 50x50 pixels)."
                
                if width > 10000 or height > 10000:
                    img.close()
                    logger.warning(f"[VALIDATE] Image too large: {width}x{height}")
                    return False, "Image is too large. Please upload a smaller image (maximum 10000x10000 pixels)."
                
                # Verify the image can be converted to RGB (required for preprocessing)
                # This is the actual test - if it can be converted, it's valid
                try:
                    logger.info(f"[VALIDATE] Attempting RGB conversion from mode: {img.mode}")
                    img_rgb = img.convert('RGB')
                    logger.info(f"[VALIDATE] RGB conversion successful")
                    img_rgb.load()  # Force loading to catch any corruption issues
                    logger.info(f"[VALIDATE] Image loaded successfully")
                    img_rgb.close()
                except Exception as convert_error:
                    img.close()
                    logger.error(f"[VALIDATE] RGB conversion failed: {convert_error} (type: {type(convert_error).__name__})")
                    logger.error(f"[VALIDATE] Full error: {traceback.format_exc()}")
                    return False, f"Invalid image format. The image cannot be processed: {str(convert_error)[:100]}. Please upload a valid image file (PNG, JPG, JPEG, GIF, or BMP)."
                
                # Close the image to free memory
                img.close()
                logger.info(f"[VALIDATE] Validation successful for: {image_path}")
                return True, None
            except Exception as dim_error:
                img.close()
                logger.error(f"[VALIDATE] Dimension check failed: {dim_error} (type: {type(dim_error).__name__})")
                logger.error(f"[VALIDATE] Full error: {traceback.format_exc()}")
                return False, f"Invalid image format. Dimension check failed: {str(dim_error)[:100]}. Please upload a valid image file (PNG, JPG, JPEG, GIF, or BMP)."
        except IOError as e:
            error_msg = str(e).lower()
            logger.error(f"[VALIDATE] IOError: {e} (file: {image_path})")
            logger.error(f"[VALIDATE] Full error: {traceback.format_exc()}")
            if "cannot identify image file" in error_msg or "cannot open" in error_msg:
                return False, "Invalid image format. The file does not appear to be a valid image file (PNG, JPG, JPEG, GIF, or BMP)."
            elif "truncated" in error_msg or "corrupt" in error_msg:
                return False, "Image file appears to be corrupted or incomplete. Please try uploading again or use a different image."
            else:
                return False, f"Invalid image format. IOError: {str(e)[:100]}. Please upload a valid image file (PNG, JPG, JPEG, GIF, or BMP)."
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            logger.error(f"[VALIDATE] Unexpected error: {error_type}: {error_msg} (file: {image_path})")
            logger.error(f"[VALIDATE] Full traceback:\n{traceback.format_exc()}")
            return False, f"Invalid image format. Error: {error_type}: {str(error_msg)[:100]}. Please upload a valid image file (PNG, JPG, JPEG, GIF, or BMP)."
    except Exception as e:
        logger.error(f"[VALIDATE] Outer exception: {type(e).__name__}: {e}")
        return False, f"An unexpected error occurred during validation: {str(e)[:100]}"
        logger.error(f"[VALIDATE] Full traceback:\n{traceback.format_exc()}")
        return False, f"Invalid image format. Validation error: {str(e)[:100]}. Please upload a valid image file."


def normalize_uploaded_image(image_path):
    """Normalize uploaded images to stable RGB encodings for downstream model reads."""
    tmp_path = f"{image_path}.normalized"
    try:
        from PIL import Image, ImageOps, ImageFile

        ImageFile.LOAD_TRUNCATED_IMAGES = True
        ext = os.path.splitext(image_path)[1].lower()
        rewrite_formats = {
            '.jpg': ('JPEG', {'quality': 95, 'optimize': True}),
            '.jpeg': ('JPEG', {'quality': 95, 'optimize': True}),
            '.png': ('PNG', {'optimize': True}),
        }

        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
            normalized = img.convert('RGB')
            normalized.load()

        # Keep GIF/BMP as-is to avoid format/extension mismatch.
        if ext not in rewrite_formats:
            return True, None

        save_format, save_kwargs = rewrite_formats[ext]
        normalized.save(tmp_path, format=save_format, **save_kwargs)
        os.replace(tmp_path, image_path)
        return True, None
    except Exception as e:
        logger.error(f"[NORMALIZE] Failed for {image_path}: {type(e).__name__}: {e}")
        logger.error(f"[NORMALIZE] Full traceback:\n{traceback.format_exc()}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return False, "Image normalization failed. Please try uploading a different image."


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
            
            # Check image dimensions (should be reasonable)
            if len(img_array.shape) < 2:
                logger.error(f"[LEAF_VALIDATE] Invalid array shape: {img_array.shape}")
                return False, "Invalid image format. Image dimensions are invalid."
            
            height, width = img_array.shape[:2]
            logger.info(f"[LEAF_VALIDATE] Image dimensions: {width}x{height}")
            
            if width < 50 or height < 50:
                logger.warning(f"[LEAF_VALIDATE] Image too small: {width}x{height}")
                return False, "Image is too small. Please upload a larger image."
            
            # Check if image has significant green content (leaves are typically green)
            # Simple check: count green-ish pixels
            green_pixels = 0
            total_pixels = width * height
            
            # Check RGB values for green dominance
            sample_step_y = max(1, height // 20)
            sample_step_x = max(1, width // 20)
            logger.info(f"[LEAF_VALIDATE] Sampling pixels with step: {sample_step_x}x{sample_step_y}")
            
            sampled_pixels = 0
            for y in range(0, height, sample_step_y):
                for x in range(0, width, sample_step_x):
                    if len(img_array.shape) == 3 and img_array.shape[2] >= 3:
                        r, g, b = img_array[y, x][:3]
                        # Green is dominant if G > R and G > B
                        if g > r and g > b and g > 50:  # Some green threshold
                            green_pixels += 1
                        sampled_pixels += 1
                    else:
                        logger.warning(f"[LEAF_VALIDATE] Unexpected array shape at pixel [{y}, {x}]: {img_array[y, x]}")
            
            if sampled_pixels == 0:
                logger.error(f"[LEAF_VALIDATE] No pixels sampled!")
                return False, "Invalid image format. Cannot analyze image content."
            
            green_ratio = green_pixels / sampled_pixels if sampled_pixels > 0 else 0
            logger.info(f"[LEAF_VALIDATE] Green ratio: {green_ratio:.3f} ({green_pixels}/{sampled_pixels} pixels)")
            
            # If less than 5% green, likely not a leaf
            if green_ratio < 0.05:
                logger.info(f"[LEAF_VALIDATE] Low green content, but allowing (might be diseased leaf)")
                # Actually, let's be more lenient - diseased leaves might not be green
                # return False, "The uploaded image does not appear to be a plant leaf. Please upload a clear image of a crop leaf."
            
            logger.info(f"[LEAF_VALIDATE] Leaf validation passed")
            return True, None
        except Exception as img_error:
            logger.error(f"[LEAF_VALIDATE] Error processing image: {img_error} (type: {type(img_error).__name__})")
            logger.error(f"[LEAF_VALIDATE] Full traceback:\n{traceback.format_exc()}")
            return False, f"Invalid image format. Error processing image: {str(img_error)[:100]}. Please upload a valid image file."
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"[LEAF_VALIDATE] Outer exception: {error_type}: {e}")
        logger.error(f"[LEAF_VALIDATE] Full traceback:\n{traceback.format_exc()}")
        return False, f"Invalid image format. Validation error: {error_type}: {str(e)[:100]}. Please upload a valid image file."


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def build_unique_upload_filename(original_filename):
    """Generate a collision-resistant filename for uploaded images."""
    safe_name = secure_filename(original_filename or "")
    stem, ext = os.path.splitext(safe_name)
    stem = (stem or "upload")[:60]
    ext = ext.lower() if ext else ".jpg"
    ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    token = uuid.uuid4().hex[:8]
    return f"{ts}_{token}_{stem}{ext}"


def luhn_checksum(card_number):
    """Validate card number using Luhn algorithm"""
    # Remove spaces and non-digits
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
    
    # Validate expiry (MM/YY format, must be future date)
    try:
        month, year = expiry_mm_yy.split('/')
        month = int(month)
        year = int(year)
        if month < 1 or month > 12:
            errors.append("Invalid expiry month")
        else:
            # Convert YY to full year
            current_year = datetime.now().year
            full_year = 2000 + year if year < 100 else year
            expiry_date = datetime(full_year, month, 1)
            if expiry_date < datetime.now().replace(day=1):
                errors.append("Card has expired")
    except (ValueError, AttributeError):
        errors.append("Invalid expiry format (use MM/YY)")
    
    # Validate CVV (exactly 3 digits)
    if not cvv or not cvv.isdigit() or len(cvv) != 3:
        errors.append("CVV must be exactly 3 digits")
    
    # Validate cardholder name
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
    """Generate formatted customer ID from user ID"""
    # Customer ID is now just a formatted version of user.id
    # This is for display purposes only
    from sqlalchemy import func
    # Get next user ID
    max_id = db.session.query(func.max(User.id)).scalar() or 0
    next_id = max_id + 1
    date_str = datetime.now().strftime('%Y%m%d')
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
    if user.is_pro_active():
        return True, None  # Pro users have unlimited
    
    # Get or create usage counter
    counter = UsageCounter.query.filter_by(cust_id=user.id).first()
    now = datetime.now(timezone.utc)
    
    if not counter:
        # Set daily reset to tomorrow at midnight
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        counter = UsageCounter(
            cust_id=user.id, 
            total_predictions=0,
            today_count=0,
            daily_reset_at=tomorrow
        )
        db.session.add(counter)
        db.session.commit()
    
    # Check if day has passed - reset daily count
    if counter.daily_reset_at:
        reset_at = ensure_timezone_aware(counter.daily_reset_at)
        if reset_at and reset_at < now:
            counter.today_count = 0
            # Set next day reset (tomorrow at midnight)
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            counter.daily_reset_at = tomorrow
            db.session.commit()
    
    # Check daily limit (3 per day for free users)
    if counter.today_count >= 3:
        return False, "You have reached the free tier limit of 3 detections per day. Please upgrade to Pro for unlimited detections."
    
    return True, None


def increment_usage(user):
    """Increment usage counter for user (daily and total predictions)"""
    counter = UsageCounter.query.filter_by(cust_id=user.id).first()
    now = datetime.now(timezone.utc)
    
    if not counter:
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        counter = UsageCounter(
            cust_id=user.id, 
            total_predictions=0,
            today_count=0,
            daily_reset_at=tomorrow
        )
        db.session.add(counter)
    
    # Check if day has passed - reset daily count
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
    if user.is_pro and user.pro_expires_at:
        expires_at = ensure_timezone_aware(user.pro_expires_at)
        now = datetime.now(timezone.utc)
        
        # Check if plan expired (expired but user.is_pro is still True)
        if expires_at and expires_at < now and user.is_pro:
            # Check if we already sent an expiration notification (within last 24 hours)
            recent_notification = Notification.query.filter_by(
                cust_id=user.id,
                notification_type='warning',
                is_system=True
            ).filter(
                Notification.message.like('%Pro subscription has expired%'),
                Notification.created_at > (now - timedelta(days=1))
            ).first()
            
            if not recent_notification:
                # Create expiration notification
                notification = Notification(
                    cust_id=user.id,
                    title='Pro Plan Expired',
                    message=f'Your Pro subscription expired on {expires_at.strftime("%B %d, %Y")}. Upgrade to Pro to continue enjoying unlimited disease detections!',
                    notification_type='warning',
                    is_system=True
                )
                db.session.add(notification)
                
                # Update user Pro status in customer table
                if user.customer:
                    user.customer.is_pro = 0
                    db.session.commit()


def _notification_visible_after(user):
    """Return the timestamp from which notifications should be visible for this user."""
    try:
        joined_at = user.created_at if user else None
    except Exception:
        joined_at = None
    return ensure_timezone_aware(joined_at) if joined_at else None


def generate_receipt_pdf(payment):
    """Generate receipt PDF for payment"""
    try:
        from reportlab.lib.pagesizes import letter  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore
        from reportlab.lib.units import inch  # type: ignore
        
        receipts_dir = os.path.join(app.config['UPLOAD_FOLDER'], '..', 'receipts')
        os.makedirs(receipts_dir, exist_ok=True)
        
        receipt_path = os.path.join(receipts_dir, f'receipt_{payment.id}.pdf')
        
        c = canvas.Canvas(receipt_path, pagesize=letter)
        width, height = letter
        
        # Header
        c.setFont("Helvetica-Bold", 20)
        c.drawString(100, height - 50, "Leafora AI - Payment Receipt")
        
        # Payment details
        y = height - 100
        c.setFont("Helvetica", 12)
        c.drawString(100, y, f"Payment ID: {payment.id}")
        y -= 20
        c.drawString(100, y, f"Date: {payment.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        y -= 20
        c.drawString(100, y, f"Customer: {payment.user.username} ({payment.user.email})")
        y -= 20
        # Format amount with currency symbol
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
        
        # Footer
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


# Model loading and prediction are handled by predict.py module


# Authentication Decorators
def login_required(f):
    """Decorator to require login for routes"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin access for routes"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        
        user = db.session.get(User, session['user_id'])
        if not user or not user.is_admin:
            flash('Access denied. Admin privileges required.', 'danger')
            # Redirect non-admin users to member dashboard to avoid admin redirect loops.
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function


def member_only(f):
    """Decorator to restrict admin users from member features"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        
        user = db.session.get(User, session['user_id'])
        if user and user.is_admin:
            flash('This feature is only available for regular members. Admins should use the Admin Panel.', 'info')
            return redirect(url_for('admin_dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function


def _format_prediction_label(raw_label):
    """Format model labels for clean homepage display."""
    label = str(raw_label or "").strip()
    if not label:
        return "Unknown"
    label = label.replace("___", " - ").replace("_", " ")
    return " ".join(label.split())


def _landing_fallback_top_diseases(limit=3):
    palette = [
        ("success", "bi-bug-fill"),
        ("warning", "bi-exclamation-triangle-fill"),
        ("info", "bi-droplet-fill"),
    ]
    placeholders = [
        "No recent detections",
        "Upload leaf images to build stats",
        "Live detection trends appear here",
    ]

    items = []
    for i in range(limit):
        tone, icon = palette[i % len(palette)]
        items.append({
            "label": placeholders[i % len(placeholders)],
            "confidence": 0,
            "tone": tone,
            "icon": icon,
            "bar_class": f"bar-fluctuate-{(i % 3) + 1}",
            "count": 0,
        })
    return items


def get_landing_top_diseases(limit=3):
    """Return top detected diseases for homepage hero card."""
    palette = [
        ("success", "bi-bug-fill"),
        ("warning", "bi-exclamation-triangle-fill"),
        ("info", "bi-droplet-fill"),
    ]

    def _query_top_diseases(since=None):
        lowered = func.lower(Prediction.result)
        query = (
            db.session.query(
                Prediction.result.label("label"),
                func.count(Prediction.id).label("hits"),
                func.avg(Prediction.confidence).label("avg_confidence"),
            )
            .filter(Prediction.result.isnot(None))
            .filter(func.length(func.trim(Prediction.result)) > 0)
            .filter(~lowered.like("%healthy%"))
            .filter(~lowered.like("%unknown%"))
            .filter(~lowered.like("%no plant%"))
            .filter(~lowered.like("%background%"))
        )
        if since is not None:
            query = query.filter(Prediction.timestamp >= since)
        return (
            query.group_by(Prediction.result)
            .order_by(func.count(Prediction.id).desc(), func.avg(Prediction.confidence).desc())
            .limit(limit)
            .all()
        )

    try:
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        rows = _query_top_diseases(since=thirty_days_ago)
        if not rows:
            rows = _query_top_diseases()

        has_live_data = bool(rows)
        items = []
        for idx, row in enumerate(rows):
            tone, icon = palette[idx % len(palette)]
            confidence_raw = _safe_float(getattr(row, "avg_confidence", 0.0), 0.0)
            confidence = int(max(0, min(100, round(confidence_raw))))
            items.append({
                "label": _format_prediction_label(getattr(row, "label", "")),
                "confidence": confidence,
                "tone": tone,
                "icon": icon,
                "bar_class": f"bar-fluctuate-{(idx % 3) + 1}",
                "count": int(getattr(row, "hits", 0) or 0),
            })

        if len(items) < limit:
            filler = _landing_fallback_top_diseases(limit=limit - len(items))
            for idx, item in enumerate(filler):
                if idx >= (limit - len(items)):
                    break
                item["bar_class"] = f"bar-fluctuate-{((len(items) + idx) % 3) + 1}"
            items.extend(filler)

        return items[:limit], has_live_data
    except Exception as e:
        logger.warning(f"Failed to build landing top diseases data: {e}")
        logger.warning(traceback.format_exc())
        return _landing_fallback_top_diseases(limit=limit), False


# Routes
@app.route('/images/logo.png')
def logo():
    """Serve logo from images folder"""
    basedir = os.path.dirname(__file__)
    logo_path = os.path.join(basedir, 'images', 'logo.png')
    
    if os.path.exists(logo_path):
        return send_file(logo_path, mimetype='image/png')
    
    # Fallback to static logo if images/logo.png doesn't exist
    static_logo = os.path.join(basedir, 'static', 'img', 'logo.svg')
    if os.path.exists(static_logo):
        return send_file(static_logo, mimetype='image/svg+xml')
    
    from flask import abort
    abort(404)

@app.route('/')
def index():
    """Homepage"""
    try:
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        top_detected_diseases, has_live_top_data = get_landing_top_diseases(limit=3)
        return render_template(
            'index.html',
            top_detected_diseases=top_detected_diseases,
            has_live_top_data=has_live_top_data,
        )
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        logger.error(traceback.format_exc())
        # Return a simple error page if template fails
        return f"<h1>Error loading homepage</h1><p>{str(e)}</p>", 500


@app.route('/supported-plants')
def supported_plants():
    try:
        supported = {}
        try:
            supported = predict.get_detection_supported_plants() or {}
        except Exception as _sp_err:
            logger.warning(f"Could not read model plant support from predict.py: {_sp_err}")

        best_model_plants = sorted(list(set(supported.get('best_model', []))))
        lefora_plants = sorted(list(set(supported.get('lefora', []))))
        fast_model_1_plants = sorted(list(set(supported.get('fast_model_1', []))))
        fast_model_2_plants = sorted(list(set(supported.get('fast_model_2', []))))
        fast_model_3_plants = sorted(list(set(supported.get('fast_model_3', []))))

        basic_plants = lefora_plants if lefora_plants else (best_model_plants if best_model_plants else ["Pepper Bell", "Potato", "Tomato"])
        pro_union = set(best_model_plants + fast_model_1_plants + fast_model_2_plants + fast_model_3_plants)
        pro_plants = sorted([p for p in pro_union if p not in set(basic_plants)])
        beta_plants = ["Orange", "Rose", "Strawberry", "Sugercane"]

        model_supported_plants = [
            {"name": "best_model.keras", "plants": best_model_plants},
            {"name": "lefora.keras", "plants": lefora_plants},
            {"name": "fast_model_1", "plants": fast_model_1_plants},
            {"name": "fast_model_2", "plants": fast_model_2_plants},
            {"name": "fast_model_3", "plants": fast_model_3_plants},
        ]
        return render_template('supported_plants.html',
                               basic_plants=basic_plants,
                               pro_plants=pro_plants,
                               beta_plants=beta_plants,
                               num_basic=len(basic_plants),
                               num_pro=len(pro_plants),
                               model_supported_plants=model_supported_plants)
    except Exception as e:
        logger.error(f"Error loading supported plants: {e}")
        return render_template('supported_plants.html',
                               basic_plants=[],
                               pro_plants=[],
                               beta_plants=[],
                               num_basic=0,
                               num_pro=0,
                               model_supported_plants=[])


@app.route('/register', methods=['GET', 'POST'])
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
        
        # Check if user exists (retry once for transient SQLite errors)
        for attempt in range(2):
            try:
                if User.query.filter_by(email=email).first():
                    flash('Email already registered. Please login.', 'warning')
                    return redirect(url_for('login'))
                
                if User.query.filter_by(username=username).first():
                    flash('Username already taken. Please choose another.', 'danger')
                    return render_template('auth/register.html')
                break
            except OperationalError as e:
                if attempt == 0 and _is_sqlite_disk_io_error(e):
                    logger.warning("SQLite disk I/O error during registration lookup; retrying once.")
                    _reset_db_connection()
                    continue
                logger.error(f"Registration lookup failed: {e}")
                flash('Database is temporarily unavailable. Please try again in a few seconds.', 'danger')
                return render_template('auth/register.html')
        
        # Create new user
        password_hash = generate_password_hash(password)
        new_user_id = None
        for attempt in range(2):
            try:
                new_user = User(
                    username=username,
                    email=email,
                    password_hash=password_hash
                )
                
                db.session.add(new_user)
                db.session.flush()  # Flush to get user.id
                
                # Create customer record in tbl_customers (customer_id = user.id)
                customer = Customer(
                    customer_id=new_user.id,
                    is_admin=False,
                    is_pro=0,
                    is_deleted=False,
                    created_at=datetime.now(timezone.utc)
                )
                db.session.add(customer)
                
                # Create usage counter with daily reset
                tomorrow = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                counter = UsageCounter(
                    cust_id=new_user.id, 
                    total_predictions=0,
                    today_count=0,
                    daily_reset_at=tomorrow,
                    monthly_predictions=0
                )
                db.session.add(counter)
                db.session.commit()
                new_user_id = new_user.id
                break
            except OperationalError as e:
                db.session.rollback()
                if attempt == 0 and _is_sqlite_disk_io_error(e):
                    logger.warning("SQLite disk I/O error during registration commit; retrying once.")
                    _reset_db_connection()
                    continue
                logger.error(f"Registration failed with database error: {e}")
                flash('Database is temporarily unavailable. Please try again in a few seconds.', 'danger')
                return render_template('auth/register.html')
            except Exception as e:
                db.session.rollback()
                logger.error(f"Registration failed: {e}")
                flash('Registration failed. Please try again.', 'danger')
                return render_template('auth/register.html')
        
        flash('Registration successful! Welcome to Leafora AI. You have 3 detections per day on the Basic plan.', 'success')
        # Show usage info after registration
        session['show_usage_info'] = True
        session['new_user_id'] = new_user_id
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')


@app.route('/login', methods=['GET', 'POST'])
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
        
        # Check if user exists first
        if not user:
            flash('Invalid email or password.', 'danger')
            return render_template('auth/login.html')
        
        # Check if user is deleted/banned
        try:
            if hasattr(user, 'is_deleted') and user.is_deleted:
                flash('User has been banned from the session. Please contact administrator.', 'danger')
                return render_template('auth/login.html')
        except Exception:
            # If is_deleted column doesn't exist, continue normally
            pass
        
        if check_password_hash(user.password_hash, password):
            # Update last_login in tbl_login
            login_time = datetime.now(timezone.utc)
            user.last_login = login_time
            
            # Create customer record if missing
            if not user.customer:
                customer = Customer(
                    customer_id=user.id,
                    is_admin=False,
                    is_pro=0,
                    is_deleted=False,
                    created_at=login_time,
                    last_login_at=login_time
                )
                db.session.add(customer)
            else:
                # Update last_login_at in customer table
                user.customer.last_login_at = login_time
            
            db.session.commit()
            
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            
            # Show usage info if new user just registered
            if session.get('show_usage_info') and session.get('new_user_id') == user.id:
                counter = UsageCounter.query.filter_by(cust_id=user.id).first()
                today_usage = counter.today_count if counter else 0
                remaining = max(0, 3 - today_usage)
                flash(f'Welcome, {user.username}! You have {remaining}/3 detections remaining today on the Basic plan.', 'info')
                session.pop('show_usage_info', None)
                session.pop('new_user_id', None)
            else:
                # Show usage for existing users
                counter = UsageCounter.query.filter_by(cust_id=user.id).first()
                now = datetime.now(timezone.utc)
                if counter and counter.daily_reset_at:
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
            # Don't reveal if user exists or not (security best practice)
            flash('Invalid email or password.', 'danger')
            return render_template('auth/login.html')
    
    return render_template('auth/login.html')


@app.route('/logout')
@login_required
def logout():
    """User logout"""
    # Log logout time
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user and user.customer:
            user.customer.last_logout_at = datetime.now(timezone.utc)
            db.session.commit()
    
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
@member_only
def dashboard():
    """User dashboard"""
    from datetime import timedelta as _timedelta
    uid = session.get('user_id')
    user = db.session.get(User, uid) if uid else None
    if not user:
        flash('Your session has expired. Please log in again.', 'warning')
        return redirect(url_for('logout'))
    cust_id = user.customer.customer_id if user and user.customer else None
    if not cust_id:
        flash('Customer record not found. Please contact support.', 'danger')
        return redirect(url_for('logout'))
    
    recent_predictions = Prediction.query.filter_by(cust_id=cust_id)\
        .order_by(Prediction.timestamp.desc()).limit(5).all()
    
    # Statistics
    total_predictions = Prediction.query.filter_by(cust_id=cust_id).count()
    healthy_count = Prediction.query.filter_by(cust_id=cust_id, result='Healthy').count()
    disease_count = total_predictions - healthy_count
    
    # Dashboard Stats object for the new UI
    stats = {
        'total': total_predictions,
        'healthy': healthy_count,
        'issues': disease_count
    }
    print(f"DEBUG: Dashboard called. Stats: {stats}")
    
    # Prepare recent analyses with enriched data for the timeline
    recent_analyses = []
    for p in recent_predictions:
        # Get extra info from DISEASE_DETAILS if available
        details = DISEASE_DETAILS.get(p.result, {})
        
        # Handle cases where details might be a string (from disease_info.json) or dict
        description = ""
        treatment = ""
        
        if isinstance(details, dict):
            description = details.get('description', '')
            treatment = details.get('treatment', '')
        elif isinstance(details, str):
            treatment = details
            
        recent_analyses.append({
            'id': p.id,
            'image_path': p.filename,
            'disease_name': p.result,
            'confidence': p.confidence,
            'created_at': p.timestamp.strftime('%Y-%m-%d %H:%M'),
            'description': description,
            'treatment': treatment
        })
    
    # Recent activity
    recent_activity = Prediction.query.filter_by(cust_id=cust_id)\
        .order_by(Prediction.timestamp.desc()).limit(10).all()
    
    # Get usage counter for limit display
    counter = UsageCounter.query.filter_by(cust_id=user.id).first()
    now = datetime.now(timezone.utc)
    
    # Reset daily count if needed
    if counter and counter.daily_reset_at:
        reset_at = ensure_timezone_aware(counter.daily_reset_at)
        if reset_at and reset_at < now:
            counter.today_count = 0
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + _timedelta(days=1)
            counter.daily_reset_at = tomorrow
            db.session.commit()
    
    today_usage = counter.today_count if counter else 0
    is_pro = user.is_pro_active()
    remaining = max(0, 3 - today_usage) if not is_pro else "Unlimited"
    
    # Check for expired Pro plan and send notification
    check_and_notify_expired_plan(user)
    
    visible_after = _notification_visible_after(user)

    # Get unread notifications
    unread_query = Notification.query.filter_by(cust_id=user.id, is_read=False)
    if visible_after:
        unread_query = unread_query.filter(Notification.created_at >= visible_after)
    unread_notifications = unread_query.order_by(Notification.created_at.desc()).limit(10).all()
    
    # Also get notifications for all users (cust_id is None)
    all_user_query = Notification.query.filter_by(cust_id=None, is_read=False)
    if visible_after:
        all_user_query = all_user_query.filter(Notification.created_at >= visible_after)
    all_user_notifications = all_user_query.order_by(Notification.created_at.desc()).limit(10).all()
    # Optimized chart data: Last 30 days predictions for THIS user only
    chart_dates = []
    chart_counts = []
    chart_healthy = []
    chart_diseased = []
    try:
        from collections import defaultdict
        
        thirty_days_ago = datetime.now(timezone.utc) - _timedelta(days=30)
        
        # Query grouped counts by day and result in one pass.
        results = (
            db.session.query(
                db.func.date(Prediction.timestamp).label('date'),
                Prediction.result.label('result'),
                db.func.count(Prediction.id).label('count')
            )
            .filter(Prediction.cust_id == user.customer.customer_id)
            .filter(Prediction.timestamp >= thirty_days_ago)
            .group_by(db.func.date(Prediction.timestamp), Prediction.result)
            .order_by(db.func.date(Prediction.timestamp))
            .all()
        )

        daily_counts = {}
        for r in results:
            raw_date = r.date
            if hasattr(raw_date, 'isoformat'):
                date_key = raw_date.isoformat()
            else:
                date_key = str(raw_date)

            if date_key not in daily_counts:
                daily_counts[date_key] = {'healthy': 0, 'diseased': 0, 'total': 0}

            c = int(r.count or 0)
            daily_counts[date_key]['total'] += c
            if (r.result or '').strip().lower() == 'healthy':
                daily_counts[date_key]['healthy'] += c
            else:
                daily_counts[date_key]['diseased'] += c

        for date_key in sorted(daily_counts.keys()):
            try:
                date_obj = datetime.fromisoformat(date_key)
                chart_dates.append(date_obj.strftime('%m/%d'))
                chart_counts.append(daily_counts[date_key]['total'])
                chart_healthy.append(daily_counts[date_key]['healthy'])
                chart_diseased.append(daily_counts[date_key]['diseased'])
            except (ValueError, TypeError):
                continue
                
    except Exception as e:
        logger.error(f"Error generating dashboard chart data: {e}")

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
                         all_user_notifications=all_user_notifications,
                         chart_dates=chart_dates,
                         chart_counts=chart_counts,
                         chart_healthy=chart_healthy,
                         chart_diseased=chart_diseased)


@app.route('/upload', methods=['GET', 'POST'])
@login_required
@member_only
def upload():
    """Image upload and disease prediction"""
    user = db.session.get(User, session['user_id'])
    
    if request.method == 'POST':
        # Check usage limit for free users
        can_predict, limit_message = check_usage_limit(user)
        if not can_predict:
            flash(limit_message, 'warning')
            return redirect(url_for('plans'))
        
        if 'file' not in request.files:
            logger.warning("[UPLOAD] No 'file' key in request.files")
            flash('No file selected.', 'danger')
            return redirect(url_for('upload'))
        
        file = request.files['file']
        logger.info(f"[UPLOAD] File received: filename='{file.filename}', content_type='{file.content_type if hasattr(file, 'content_type') else 'N/A'}'")
        
        if file.filename == '':
            logger.warning("[UPLOAD] Empty filename")
            flash('No file selected.', 'danger')
            return redirect(url_for('upload'))
        
        # Check file extension
        is_allowed = allowed_file(file.filename)
        logger.info(f"[UPLOAD] File extension check: {is_allowed} for '{file.filename}'")
        
        if file and is_allowed:
            # Secure filename and save
            unique_filename = build_unique_upload_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            # Create uploads directory if it doesn't exist
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            try:
                file.save(filepath)
                logger.info(f"File saved successfully: {filepath} (size: {os.path.getsize(filepath)} bytes)")
            except Exception as e:
                logger.error(f"Error saving file: {e}")
                flash('Error saving file. Please try again.', 'danger')
                return redirect(url_for('upload'))
            
            # First validate that it's a valid image file
            logger.info(f"Validating image file: {filepath}")
            is_valid_image, validation_error = validate_image_file(filepath)
            if not is_valid_image:
                logger.warning(f"Image validation failed: {validation_error} (file: {filepath})")
                flash(validation_error, 'danger')
                # Clean up invalid image
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except:
                    pass
                return redirect(url_for('upload'))
            logger.info(f"Image validation passed: {filepath}")

            # Normalize image bytes for consistent model preprocessing across formats/devices.
            normalized_ok, normalize_error = normalize_uploaded_image(filepath)
            if not normalized_ok:
                flash(normalize_error, 'danger')
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception:
                    pass
                return redirect(url_for('upload'))
            logger.info(f"Image normalization passed: {filepath}")
            
            # Legacy non-leaf check kept as advisory only.
            # Final leaf/not-leaf decision is made by best_plant_detector.keras in predict.py.
            is_valid_leaf, validation_error = validate_leaf_image(filepath)
            if not is_valid_leaf:
                logger.info(f"[UPLOAD] Legacy leaf heuristic flagged image, proceeding to detector model: {validation_error}")
            
            # Initialize upgrade_prompt and premium health / visualization info
            upgrade_prompt = None
            premium_health = None
            premium_healthy = False
            show_premium_button = False
            disease_spots = []
            
            try:
                # Beta toggle controls model scope: off=lefora only, on=all detection models.
                use_all_models = True
                use_ensemble = False
                rice_enabled_flag = request.form.get('rice_enabled')
                enable_rice_models = _as_form_bool(rice_enabled_flag) and user.is_pro_active()
                beta_enabled_raw = request.form.get('enable_beta')
                beta_enabled = _as_form_bool(beta_enabled_raw) and user.is_pro_active()
                session['beta_enabled'] = beta_enabled
                logger.info(
                    f"[UPLOAD] enable_beta raw='{beta_enabled_raw}' parsed={beta_enabled} "
                    f"is_pro={user.is_pro_active()} disable_best_model={not beta_enabled}"
                )
                result = predict.predict_topk(
                    filepath,
                    k=predict.TOP_K,
                    use_all_models=use_all_models,
                    use_ensemble=use_ensemble,
                    enable_rice_models=enable_rice_models,
                    disable_best_model=(not beta_enabled)
                )

                # Streamlit-style gate: if detector says non-leaf, stop here and show confidence.
                non_leaf_conf = result.get('non_leaf_confidence')
                if non_leaf_conf is None and result.get('detector_score') is not None:
                    non_leaf_conf = round(100.0 - float(result.get('detector_score')), 2)
                detector_non_leaf = (
                    ('best_plant_detector.keras' in str(result.get('model_used', '')).lower() and bool(result.get('unknown')))
                    or (
                        non_leaf_conf is not None
                        and bool(result.get('unknown'))
                        and len(result.get('all_models') or []) == 0
                        and (result.get('topk') or [{}])[0].get('label', '').lower() == 'unknown'
                    )
                )
                if detector_non_leaf:
                    image = url_for('static', filename=f'uploads/{unique_filename}')
                    non_conf = non_leaf_conf if non_leaf_conf is not None else 0.0
                    info_msg = 'No disease analysis is available because this does not appear to be a plant leaf.'
                    return render_template(
                        'user/result.html',
                        label='Not a plant image',
                        confidence=non_conf,
                        image=image,
                        info=info_msg,
                        topk=[],
                        model_used='Plant detector',
                        models_used=[],
                        is_unknown=True,
                        confidence_message=None,
                        all_models=[],
                        ensemble_top=[],
                        per_model=[],
                        kindwise_results=[],
                        is_pro=user.is_pro_active(),
                        upgrade_prompt=None,
                        prediction_id=None,
                        filename=unique_filename,
                        rice_enabled=False,
                        disease_spots=[],
                        is_non_plant=True,
                        non_leaf_confidence=non_leaf_conf
                    )
                
                # Detect plant type first from all predictions
                from modules.plant_detector import detect_plant_type, filter_predictions_by_plant
                detected_plant = detect_plant_type(result['topk'])
                # Enforce discovered ready plants
                try:
                    import json
                    ready = []
                    with open(os.path.join(os.getcwd(), 'artifacts', 'discovered_plants.json'), 'r', encoding='utf-8') as f:
                        dj = json.load(f)
                        ready = [p for p, info in (dj.get('by_plant') or {}).items() if (info or {}).get('status') in ['ready', 'beta']]
                    mu = str(result.get('model_used', ''))
                    if mu.startswith('disease_'):
                        plant_from_model = mu.replace('disease_', '').strip()
                    else:
                        plant_from_model = detected_plant
                    logger.info(f"DEBUG PLANT GATING: Plant='{plant_from_model}', Ready={ready}")
                    if ready and plant_from_model:
                        ready_lower = [r.lower() for r in ready]
                        if plant_from_model.lower() not in ready_lower:
                            flash('Plant may be unsupported yet. Proceeding with best-guess diagnosis.', 'warning')
                except Exception:
                    pass
                
                # Keep per-model Top-5 display intact (one result per model).
                if detected_plant:
                    logger.info(f"Detected plant type: {detected_plant}")

                # Detect disease spots (returns percentage-based bounding boxes)
                try:
                    disease_spots = getattr(predict, "detect_disease_spots", lambda p, max_boxes=8: [])(filepath, max_boxes=8)
                except Exception as _ds_err:
                    logger.warning(f"disease spot detection failed: {_ds_err}")
                    disease_spots = []
                
                # Get top prediction (already formatted by predict.py)
                # Double-check: Ensure crop_model.h5 results are not in topk
                model_used = result.get('model_used', '')
                if 'crop_model' in model_used.lower() or 'crop_model.h5' in model_used.lower():
                    logger.error(f"ERROR: crop_model.h5 is being used as primary model: {model_used}")
                    if 'all_models' in result:
                        non_excluded = [m for m in result['all_models'] if 'crop_model' not in m.get('model_name', '').lower()]
                        if non_excluded and non_excluded[0].get('topk'):
                            logger.info(f"Using alternative model: {non_excluded[0]['model_name']}")
                            result['topk'] = non_excluded[0]['topk']
                            result['model_used'] = non_excluded[0]['model_name']
                        else:
                            raise ValueError("crop_model.h5 is excluded from primary predictions. No alternative models available.")
                
                top1 = result['topk'][0] if result['topk'] else None
                if not top1:
                    raise ValueError("No valid predictions available")
                _unknown_flag = bool(result.get('unknown'))
                label = top1['label']  # Already formatted
                # Handle both 'confidence' (single model) and 'prob' (ensemble) formats
                if 'confidence' in top1:
                    confidence = top1['confidence']
                elif 'prob' in top1:
                    # Convert probability (0-1) to confidence percentage (0-100)
                    confidence = round(top1['prob'] * 100, 2)
                else:
                    # Fallback: try to get any numeric value
                    confidence = top1.get('prob', top1.get('confidence', 0.0))
                    if confidence < 1.0:  # If it's a probability, convert to percentage
                        confidence = round(confidence * 100, 2)
                    else:
                        confidence = round(float(confidence), 2)
                if _unknown_flag and confidence < 20.0:
                    msg = result.get('confidence_message') or 'Model is unsure. Please upload a clearer leaf image or a supported crop.'
                    flash(msg, 'warning')
                
                # Check which model was used and capture detailed breakdown
                models_used_list = []
                if 'per_model' in result:
                    # Capture full details from ensemble per-model results (use actual top entry if present)
                    for m in result['per_model']:
                        top = (m.get('top') or [])
                        if top:
                            t0 = top[0]
                            conf = t0.get('confidence', t0.get('prob', 0.0) * 100.0)
                            entry = {
                                'name': m.get('model', 'Unknown'),
                                'conf': float(conf),
                                'label': t0.get('label', 'Unknown')
                            }
                        else:
                            entry = {
                                'name': m.get('model', 'Unknown'),
                                'conf': float(m.get('top_prob', 0.0)) * 100.0,
                                'label': m.get('top_label', 'Unknown')
                            }
                        models_used_list.append(entry)
                elif 'all_models' in result:
                    # Fallback for non-ensemble path or legacy
                    for m in result['all_models']:
                        # m is result from predict_with_model, has 'topk'
                        top1 = m.get('topk', [{}])[0] if m.get('topk') else {}
                        entry = {
                            'name': m.get('model_name', 'Unknown'),
                            'conf': top1.get('confidence', 0.0),
                            'label': top1.get('label', 'Unknown')
                        }
                        models_used_list.append(entry)
                else:
                    models_used_list = [{'name': result.get('model_used', 'unknown'), 'conf': confidence, 'label': label}]
                
                # Check if predicted plant is in the new model (42 classes) - Basic plan support
                # New model supports: Cotton, Rice, Wheat, Maize, Sugarcane
                new_model_crops = ['cotton', 'rice', 'wheat', 'maize', 'sugarcane']
                label_lower = label.lower()
                is_in_new_model = any(crop in label_lower for crop in new_model_crops)
                
                # Check if old model was used (39 classes) and plant is not in new model
                old_model_names = ['plant_disease_recog_model_pwp.keras', 'crop_model.h5']
                used_old_model = any(any(old_name in str(m) for old_name in old_model_names) for m in models_used_list)
                
                # If free user used old model and plant is not in new model, show upgrade message
                if not user.is_pro_active() and used_old_model and not is_in_new_model:
                    # Extract plant name from prediction
                    if ' - ' in label:
                        plant_name = label.split(' - ')[0].strip()
                    elif '___' in label:
                        plant_name = label.split('___')[0].strip()
                    else:
                        plant_name = label
                    upgrade_prompt = f'"{plant_name}" is not available in the Basic plan. Upgrade to Pro to access all models and detect diseases in this plant type.'
                
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                logger.error(f"Prediction failed: {error_type}: {error_msg}")
                logger.error(f"Full traceback:\n{traceback.format_exc()}")
                
                # Clean error message for user - never expose technical details
                if "Model not loaded" in error_msg or "No model" in error_msg or "Failed to load" in error_msg:
                    user_msg = "Model is not available. Please contact administrator."
                elif "All model predictions failed" in error_msg:
                    user_msg = "Unable to process image. Please try a different image or contact support."
                elif "FileNotFoundError" in error_type or "No such file" in error_msg:
                    user_msg = "Image file not found. Please try uploading again."
                elif "ValueError" in error_type:
                    # Check for specific ValueError cases
                    err_lower = error_msg.lower()
                    if "Invalid" in error_msg or "cannot identify image file" in err_lower or "cannot open" in err_lower:
                        user_msg = "Invalid image format. Please upload a valid image file (PNG, JPG, JPEG, GIF, or BMP)."
                    elif any(tok in err_lower for tok in ["expected shape", "found shape", "input shape", "shape mismatch", "dimension", "size mismatch"]):
                        user_msg = "Model input-size mismatch detected. We retried model-specific image sizes but prediction still failed. Please try another image."
                    elif "inhomogeneous" in err_lower or "array element" in err_lower:
                        user_msg = "Model compatibility issue detected. Please try again or contact support if the problem persists."
                    else:
                        user_msg = f"Prediction error: {str(error_msg)[:100]}. Please try again or contact support."
                elif "OSError" in error_type or "IOError" in error_type:
                    err_lower = error_msg.lower()
                    if "cannot identify image file" in err_lower or "cannot open" in err_lower:
                        user_msg = "Invalid image format. The file may be corrupted or is not a valid image. Please try uploading again."
                    elif "truncated" in err_lower or "corrupt" in err_lower or "broken data stream" in err_lower:
                        user_msg = "Image file appears corrupted or incomplete. Please re-upload the original image."
                    elif any(tok in err_lower for tok in ["expected shape", "found shape", "input shape", "shape mismatch", "dimension", "size mismatch"]):
                        user_msg = "Model input-size mismatch detected. Please try another image."
                    else:
                        user_msg = "Error reading image file. Please try uploading again."
                elif "PIL" in error_msg or "Pillow" in error_msg or "Image" in error_type:
                    user_msg = "Invalid image format. Please upload a valid image file (PNG, JPG, JPEG, GIF, or BMP)."
                elif "Invalid" in error_msg:
                    user_msg = "Invalid image format. Please upload a valid image file."
                else:
                    user_msg = f"An error occurred during prediction. Please try again or contact support."
                    # Log more details for debugging
                    logger.error(f"Unexpected prediction error: {error_type}: {error_msg}")
                
                flash(user_msg, 'danger')
                # Clean up on error
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except:
                        pass
                return redirect(url_for('upload'))
            
            # Increment usage counter
            increment_usage(user)
            
            # models_used_list already set above
            
            # Save prediction to database with top-k results
            try:
                # Use cust_id instead of user_id (user_id is a property, not a DB column)
                cust_id = user.customer.customer_id if user.customer else None
                if not cust_id:
                    flash('Customer record not found. Prediction saved but may not appear in history.', 'warning')
                
                prediction = Prediction(
                    cust_id=cust_id,
                    filename=unique_filename,
                    result=label,
                    confidence=confidence,
                    topk_results=json.dumps(result['topk']),
                    models_used=json.dumps(models_used_list),
                    is_unknown=result['unknown']
                )
                db.session.add(prediction)
                db.session.commit()
                logger.info(f"✅ Prediction saved to database: {prediction.id}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"❌ Database commit failed: {e}")
                logger.error(traceback.format_exc())
                flash('Prediction completed but failed to save to database. Please check logs.', 'warning')
            
            if confidence < 30:
                info = DISEASE_DETAILS.get(label, "Please consult with an agricultural expert for tailored treatment advice.")
            else:
                info = DISEASE_DETAILS.get(label, "Continue monitoring your plant for any changes.")
            image = url_for('static', filename=f'uploads/{unique_filename}')
            
            all_models_results = result.get('all_models', [])
            ensemble_top = result.get('ensemble_top', [])
            per_model_raw = result.get('per_model', [])
            models_used_list = []
            unified_results = result.get('unified_results', [])

            topk_display = result.get('topk', []) or unified_results
            
            if unified_results:
                for item in unified_results:
                    models_used_list.append({
                        'model_source': item.get('model_source', 'Unknown'),
                        'model_name': item.get('model_name', 'Unknown'), # Fallback
                        'topk': [item] # The item itself has 'label' and 'confidence'
                    })
            else:
                if per_model_raw:
                    for pm in per_model_raw:
                        top_list = pm.get('top') or pm.get('topk')
                        if top_list:
                            top_pred = top_list[0]
                            conf_val = top_pred.get('confidence', top_pred.get('prob', 0) * 100)
                            models_used_list.append({
                                'name': pm.get('model_name') or pm.get('model', 'Unknown'),
                                'label': top_pred.get('label', 'Unknown'),
                                'conf': float(conf_val)
                            })
            
            for model_result in all_models_results:
                if 'model_name' not in model_result:
                    model_result['model_name'] = model_result.get('model', 'Unknown Model')
            
            for item in ensemble_top:
                if 'confidence' not in item and 'prob' in item:
                    item['confidence'] = round(item['prob'] * 100, 2)
                elif 'confidence' not in item:
                    item['confidence'] = 0.0
            
            prediction_id = prediction.id if prediction else None
            disease_recommendations = build_disease_recommendations(topk_display, label)
            disease_profile = build_disease_profile(label, confidence=confidence)
            disease_description = build_disease_description(label, confidence=confidence)
            
            kindwise_results = []
            try:
                # Extract from prediction result if available (already called in predict.py)
                for m in result.get('all_models', []):
                    if m.get('model_name') == 'Kindwise API' and 'kindwise_details' in m:
                        details = m['kindwise_details']
                        suggestions = []
                        if isinstance(details, dict):
                            suggestions = details.get('suggestions', [])
                        elif isinstance(details, list):
                            suggestions = details
                        
                        for s in suggestions[:5]:
                            name = s.get('name') or s.get('disease', {}).get('name') or 'Unknown'
                            # Try to find crop info if available
                            crop = "Detected Crop"
                            if 'plant' in s:
                                 crop = s['plant'].get('name', crop)
                            
                            conf = s.get('probability') or s.get('confidence') or 0.0
                            details_obj = s.get('details') or {}
                            images = []
                            
                            similar_images = s.get('similar_images', [])
                            for sim in similar_images:
                                if isinstance(sim, dict) and sim.get('url'):
                                    images.append(sim['url'])
                                elif isinstance(sim, str):
                                    images.append(sim)
                            
                            citations = []
                            if details_obj.get('url'):
                                 citations.append({"source": "Reference", "url": details_obj['url']})
                            
                            kindwise_results.append({
                                "crop": crop,
                                "disease": name,
                                "confidence": round(float(conf) * 100, 2),
                                "images": images[:3], # Limit to 3 images
                                "citations": citations
                            })
                        logger.info(f"Kindwise API Results Extracted: {len(kindwise_results)} results")
                        break
            except Exception as e:
                logger.warning(f"Kindwise API extraction failed: {e}")
                logger.error(traceback.format_exc())
            
            return render_template('user/result.html',
                                 label=label,
                                 confidence=confidence,
                                 image=image,
                                 info=info,
                                 topk=topk_display,
                                 disease_description=disease_description,
                                 disease_profile=disease_profile,
                                 disease_recommendations=disease_recommendations,
                                 model_used=result.get('model_used', 'ensemble' if use_ensemble else 'single'),
                                 models_used=models_used_list,
                                 is_unknown=result['unknown'],
                                 confidence_message=result.get('confidence_message', None),
                                 all_models=all_models_results,
                                 ensemble_top=ensemble_top,
                                 per_model=per_model_raw,
                                 kindwise_results=kindwise_results,
                                 is_pro=user.is_pro_active(),
                                 upgrade_prompt=upgrade_prompt,
                                 prediction_id=prediction_id,
                                 filename=unique_filename,
                                 rice_enabled=False,
                                 disease_spots=disease_spots,
                                 is_non_plant=False,
                                 non_leaf_confidence=None)
        else:
            logger.warning(f"[UPLOAD] File extension not allowed: '{file.filename}'")
            logger.warning(f"[UPLOAD] Allowed extensions: {app.config['ALLOWED_EXTENSIONS']}")
            flash('Invalid file type. Please upload an image (PNG, JPG, JPEG, GIF, BMP).', 'danger')
            return redirect(url_for('upload'))
    
    # Show usage info on GET
    counter = UsageCounter.query.filter_by(cust_id=user.id).first()
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
    beta_enabled = bool(session.get('beta_enabled', False))
    
    return render_template('user/upload.html', 
                         usage_count=today_usage, 
                         remaining=remaining, 
                         is_pro=is_pro,
                         beta_enabled=beta_enabled)


@app.route('/predict', methods=['POST'])
@login_required
def predict_api():
    """API endpoint for predictions"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Please upload an image (PNG, JPG, JPEG, GIF, BMP).'}), 400
    
    try:
        # Save temporary file
        unique_filename = build_unique_upload_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        try:
            file.save(filepath)
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return jsonify({'error': 'Error saving file. Please try again.'}), 400
        
        # Validate that it's a valid image file
        is_valid_image, validation_error = validate_image_file(filepath)
        if not is_valid_image:
            # Clean up invalid image
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except:
                pass
            return jsonify({'error': validation_error}), 400

        normalized_ok, normalize_error = normalize_uploaded_image(filepath)
        if not normalized_ok:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass
            return jsonify({'error': normalize_error}), 400
        
        # Use beta toggle state for model gating: off=lefora only, on=all detection models.
        user = db.session.get(User, session.get('user_id'))
        beta_enabled = bool(session.get('beta_enabled', False)) and bool(user and user.is_pro_active())
        result = predict.predict_topk(filepath, k=predict.TOP_K, use_ensemble=False, disable_best_model=(not beta_enabled))
        
        # Streamlit-style gate for API consumers too
        non_leaf_conf = result.get('non_leaf_confidence')
        if non_leaf_conf is None and result.get('detector_score') is not None:
            non_leaf_conf = round(100.0 - float(result.get('detector_score')), 2)
        detector_non_leaf = (
            ('best_plant_detector.keras' in str(result.get('model_used', '')).lower() and bool(result.get('unknown')))
            or (
                non_leaf_conf is not None
                and bool(result.get('unknown'))
                and len(result.get('all_models') or []) == 0
                and (result.get('topk') or [{}])[0].get('label', '').lower() == 'unknown'
            )
        )
        if detector_non_leaf:
            return jsonify({
                'is_leaf': False,
                'message': 'Not a leaf image',
                'confidence': non_leaf_conf if non_leaf_conf is not None else 0.0
            }), 200

        top1 = result['topk'][0]
        
        # Return in requested format: {disease_name, confidence}
        return jsonify({
            'is_leaf': True,
            'disease_name': top1['label'].replace('_', ' ').replace('___', ' - '),
            'confidence': top1['confidence']
        })
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        logger.error(f"API prediction error: {error_type}: {error_msg}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        
        # Clean up on error
        try:
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass
        
        # Clean error message for API - never expose technical details
        if "Model not loaded" in error_msg or "No model" in error_msg:
            user_error = "Model is not available. Please contact administrator."
        elif "ValueError" in error_type or "OSError" in error_type or "IOError" in error_type:
            err_lower = error_msg.lower()
            if "cannot identify image file" in err_lower or "cannot open" in err_lower or "invalid" in err_lower:
                user_error = "Invalid image format. Please upload a valid image file (PNG, JPG, JPEG, GIF, or BMP)."
            elif "truncated" in err_lower or "corrupt" in err_lower or "broken data stream" in err_lower:
                user_error = "Image file appears corrupted or incomplete. Please re-upload the original image."
            else:
                user_error = "Invalid image format. Please upload a valid image file."
        elif "FileNotFoundError" in error_type:
            user_error = "Image file not found. Please try uploading again."
        else:
            user_error = "An error occurred during prediction. Please try again."
        
        return jsonify({'error': user_error}), 500


@app.route('/history')
@login_required
@member_only
def history():
    """User prediction history"""
    user = db.session.get(User, session['user_id'])
    # Use cust_id instead of user_id (user_id is a property, not a DB column)
    cust_id = user.customer.customer_id if user.customer else None
    if not cust_id:
        flash('Customer record not found. Please contact support.', 'danger')
        return redirect(url_for('logout'))
    
    predictions = Prediction.query.filter_by(cust_id=cust_id)\
        .order_by(Prediction.timestamp.desc()).all()
    
    return render_template('user/history.html', predictions=predictions)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
@member_only
def profile():
    """User profile settings"""
    user = db.session.get(User, session['user_id'])

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()

        if not username or not email:
            flash('Username and email are required.', 'danger')
            return redirect(url_for('profile'))

        # Update basic fields
        user.username = username
        user.email = email

        # Handle profile image upload (stored as file only, not in DB)
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
        return redirect(url_for('profile'))

    # Determine profile image URL if exists
    profile_image_url = None
    for ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp']:
        candidate = os.path.join(app.config['UPLOAD_FOLDER'], f"profile_{user.id}.{ext}")
        if os.path.exists(candidate):
            profile_image_url = url_for('static', filename=f"uploads/profile_{user.id}.{ext}")
            break

    # Check Pro status for display
    is_pro = user.is_pro_active()
    total_predictions = Prediction.query.filter_by(cust_id=user.id).count()
    return render_template('user/profile.html', user=user, profile_image_url=profile_image_url, is_pro=is_pro, total_predictions=total_predictions)


@app.route('/plans')
@login_required
def plans():
    """Show Pro plan pricing and features"""
    user = db.session.get(User, session['user_id'])
    counter = UsageCounter.query.filter_by(cust_id=user.id).first()
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
    
    return render_template('plans.html', 
                         user=user, 
                         usage_count=today_usage, 
                         is_pro=is_pro)


@app.route('/subscribe', methods=['GET', 'POST'])
@login_required
@member_only
def subscribe():
    """Pro subscription payment page"""
    user = db.session.get(User, session['user_id'])
    
    if user.is_pro_active():
        flash('You already have an active Pro subscription.', 'info')
        return redirect(url_for('dashboard'))
    
    plan = request.args.get('plan', 'pro')
    
    if request.method == 'POST':
        payment_type = request.form.get('payment_type', 'qr')
        if payment_type == 'card':
            card_number = request.form.get('card_number', '')
            expiry = request.form.get('expiry', '')
            cvv = request.form.get('cvv', '')
            card_name = request.form.get('card_name', '')
            valid, errors = validate_card(card_number, expiry, cvv, card_name)
            if not valid:
                for err in errors:
                    flash(err, 'danger')
                return render_template('subscribe.html', plan=plan, user=user)
            amount = 149900
            brand = get_card_brand(card_number)
            last4 = ''.join([x for x in card_number if x.isdigit()])[-4:]
            try:
                month, year = expiry.split('/')
                month = int(month)
                year = 2000 + int(year) if int(year) < 100 else int(year)
                card_expiry = datetime(year, month, 1)
            except Exception:
                card_expiry = None
            payment = Payment(
                cust_id=user.id,
                amount_cents=amount,
                currency='INR',
                card_name=card_name,
                card_last4=last4,
                card_brand=brand,
                card_expiry=card_expiry,
                status='completed',
                payment_method='Card',
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(payment)
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            if not user.customer:
                customer = Customer(
                    customer_id=user.id,
                    is_admin=False,
                    is_pro=0,
                    is_deleted=False,
                    created_at=datetime.now(timezone.utc)
                )
                db.session.add(customer)
                db.session.flush()
            user.customer.is_pro = 1
            user.customer.pro_expires_at = expires_at
            user.customer.subscription_purchased_at = datetime.now(timezone.utc)
            payment.expires_at = expires_at
            receipt_path = generate_receipt_pdf(payment)
            if receipt_path:
                payment.receipt_path = receipt_path
            db.session.commit()
            receipt_url = url_for('receipt', payment_id=payment.id) if payment.receipt_path else None
            if receipt_url:
                message = f'Your Pro subscription has been activated for 30 days. <a href="{receipt_url}" style="color: #4CAF50; text-decoration: underline;">Download receipt here</a>'
            else:
                message = f'Your Pro subscription has been activated for 30 days. Your plan expires on {expires_at.strftime("%B %d, %Y")}.'
            notification = Notification(
                cust_id=user.id,
                title='Pro Plan Activated',
                message=message,
                notification_type='success',
                is_system=True
            )
            db.session.add(notification)
            db.session.commit()
            flash('Payment successful! Your Pro subscription is now active.', 'success')
            return redirect(url_for('receipt', payment_id=payment.id))
        else:
            try:
                import hashlib
                import base64
                import json
                import requests
                MERCHANT_ID = "PGTESTPAYUAT143"
                SALT_KEY = "ab3ab177-b468-4791-8071-275c404d8ab0"
                SALT_INDEX = 1
                ENVIRONMENT = "UAT"
                merchant_transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{user.id}"
                amount = 149900
                payment = Payment(
                    cust_id=user.id,
                    amount_cents=amount,
                    currency='INR',
                    card_last4=None,
                    card_brand='PhonePe',
                    status='pending',
                    payment_method='PhonePe',
                    transaction_id=merchant_transaction_id,
                    expires_at=None,
                    created_at=datetime.now(timezone.utc)
                )
                db.session.add(payment)
                db.session.commit()
                payload = {
                    "merchantId": MERCHANT_ID,
                    "merchantTransactionId": merchant_transaction_id,
                    "merchantUserId": str(user.id),
                    "amount": amount,
                    "redirectUrl": request.url_root.rstrip('/') + url_for('payment_callback', payment_id=payment.id),
                    "redirectMode": "REDIRECT",
                    "callbackUrl": request.url_root.rstrip('/') + url_for('payment_webhook'),
                    "mobileNumber": "9999999999",
                    "paymentInstrument": {"type": "PAY_PAGE"}
                }
                payload_str = json.dumps(payload)
                payload_base64 = base64.b64encode(payload_str.encode()).decode()
                string_to_hash = payload_base64 + "/pg/v1/pay" + SALT_KEY
                sha256_hash = hashlib.sha256(string_to_hash.encode()).hexdigest()
                x_verify = sha256_hash + "###" + str(SALT_INDEX)
                phonepe_url = "https://api-preprod.phonepe.com/apis/pg-sandbox/pg/v1/pay"
                headers = {"Content-Type": "application/json", "X-VERIFY": x_verify, "Accept": "application/json"}
                response = requests.post(phonepe_url, json={"request": payload_base64}, headers=headers, timeout=10)
                if response.status_code == 200:
                    response_data = response.json()
                    if response_data.get('success') and response_data.get('data'):
                        redirect_url = response_data['data'].get('instrumentResponse', {}).get('redirectInfo', {}).get('url')
                        if redirect_url:
                            session['payment_id'] = payment.id
                            session['merchant_transaction_id'] = merchant_transaction_id
                            return redirect(redirect_url)
                        else:
                            flash('Failed to get payment URL from PhonePe. Please try again.', 'danger')
                    else:
                        flash('PhonePe payment initiation failed. Please try again.', 'danger')
                else:
                    flash('PhonePe API error. Please try again later.', 'danger')
            except Exception as e:
                db.session.rollback()
                logger.error(f"Payment processing error: {e}")
                flash('Payment processing failed. Please try again.', 'danger')
            return render_template('subscribe.html', plan=plan, user=user)
    
    return render_template('subscribe.html', plan=plan, user=user)


@app.route('/payment/callback/<int:payment_id>')
@login_required
def payment_callback(payment_id):
    """Handle PhonePe payment callback after user returns from payment page"""
    user = db.session.get(User, session['user_id'])
    payment = db.session.get(Payment, payment_id)
    
    if not payment or payment.user_id != user.id:
        flash('Invalid payment.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check payment status with PhonePe
    try:
        import hashlib
        import requests
        
        MERCHANT_ID = "PGTESTPAYUAT143"
        SALT_KEY = "ab3ab177-b468-4791-8071-275c404d8ab0"
        SALT_INDEX = 1
        ENVIRONMENT = "UAT"
        
        merchant_transaction_id = session.get('merchant_transaction_id', f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{user.id}")
        
        # Check payment status
        if ENVIRONMENT == "PRODUCTION":
            status_url = f"https://api.phonepe.com/apis/hermes/pg/v1/status/{MERCHANT_ID}/{merchant_transaction_id}"
        else:
            status_url = f"https://api-preprod.phonepe.com/apis/pg-sandbox/pg/v1/status/{MERCHANT_ID}/{merchant_transaction_id}"
        
        # Create X-VERIFY header
        string_to_hash = f"/pg/v1/status/{MERCHANT_ID}/{merchant_transaction_id}" + SALT_KEY
        sha256_hash = hashlib.sha256(string_to_hash.encode()).hexdigest()
        x_verify = sha256_hash + "###" + str(SALT_INDEX)
        
        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": x_verify,
            "X-MERCHANT-ID": MERCHANT_ID,
            "Accept": "application/json"
        }
        
        response = requests.get(status_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success') and response_data.get('data'):
                payment_info = response_data['data']
                code = payment_info.get('code', '')
                
                if code == "PAYMENT_SUCCESS":
                    # Payment successful
                    payment.status = 'completed'
                    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                    payment.expires_at = expires_at
                    
                    # Update user Pro status in customer table
                    if not user.customer:
                        # Create customer if doesn't exist
                        customer = Customer(
                            customer_id=user.id,
                            is_admin=False,
                            is_pro=0,
                            is_deleted=False,
                            created_at=datetime.now(timezone.utc)
                        )
                        db.session.add(customer)
                        db.session.flush()
                    user.customer.is_pro = 1
                    user.customer.pro_expires_at = expires_at
                    user.customer.subscription_purchased_at = datetime.now(timezone.utc)
                    
                    # Generate receipt first
                    receipt_path = generate_receipt_pdf(payment)
                    if receipt_path:
                        payment.receipt_path = receipt_path
                        db.session.commit()
                    
                    # Create auto-notification for plan purchase with receipt link
                    receipt_url = url_for('receipt', payment_id=payment.id) if receipt_path else None
                    if receipt_url:
                        message = f'Your Pro subscription has been activated for 30 days. <a href="{receipt_url}" style="color: #4CAF50; text-decoration: underline;">Download receipt here</a>'
                    else:
                        message = f'Your Pro subscription has been activated for 30 days. Your plan expires on {expires_at.strftime("%B %d, %Y")}.'
                    
                    notification = Notification(
                        cust_id=user.id,
                        title='Pro Plan Activated',
                        message=message,
                        notification_type='success',
                        is_system=True
                    )
                    db.session.add(notification)
                    db.session.commit()
                    
                    flash('Payment successful! Your Pro subscription is now active.', 'success')
                    return redirect(url_for('receipt', payment_id=payment.id))
                else:
                    payment.status = 'failed'
                    db.session.commit()
                    flash('Payment failed or was cancelled.', 'danger')
            else:
                flash('Unable to verify payment status. Please contact support.', 'warning')
        else:
            flash('Payment verification error. Please contact support.', 'warning')
    except Exception as e:
        logger.error(f"Payment callback error: {e}")
        logger.error(traceback.format_exc())
        flash('Payment verification error. Please contact support.', 'warning')
    
    return redirect(url_for('dashboard'))


@app.route('/payment/webhook', methods=['POST'])
def payment_webhook():
    """Handle PhonePe webhook for payment status updates"""
    try:
        import hashlib
        import base64
        import json
        
        MERCHANT_ID = "PGTESTPAYUAT143"
        SALT_KEY = "ab3ab177-b468-4791-8071-275c404d8ab0"
        SALT_INDEX = 1
        
        # Get webhook data
        data = request.get_json()
        x_verify_header = request.headers.get('X-VERIFY', '')
        
        # Verify webhook signature
        response_data = data.get('response', '')
        string_to_hash = response_data + "/pg/v1/webhook" + SALT_KEY
        sha256_hash = hashlib.sha256(string_to_hash.encode()).hexdigest()
        expected_verify = sha256_hash + "###" + str(SALT_INDEX)
        
        if x_verify_header != expected_verify:
            logger.warning("Invalid webhook signature")
            return jsonify({'success': False}), 400
        
        # Decode response
        decoded_response = base64.b64decode(response_data).decode()
        webhook_data = json.loads(decoded_response)
        
        merchant_transaction_id = webhook_data.get('merchantTransactionId', '')
        code = webhook_data.get('code', '')
        
        # Find payment by transaction ID (extract payment ID from transaction ID)
        # Transaction ID format: TXN{timestamp}{user_id}
        if 'TXN' in merchant_transaction_id:
            try:
                # Extract user_id from transaction ID (last part after timestamp)
                user_id_str = merchant_transaction_id.split('TXN')[1][14:]  # Skip timestamp (14 chars)
                user_id = int(user_id_str)
                # Find latest pending payment for this user
                payment = Payment.query.filter(
                    Payment.cust_id == user_id,
                    Payment.status == 'pending'
                ).order_by(Payment.id.desc()).first()
            except:
                payment = None
        else:
            payment = None
        
        if payment and code == "PAYMENT_SUCCESS":
            payment.status = 'completed'
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            payment.expires_at = expires_at
            
            user = db.session.get(User, payment.user_id)
            if user:
                if not user.customer:
                    # Create customer if doesn't exist
                    customer = Customer(
                        customer_id=user.id,
                        is_admin=False,
                        is_pro=0,
                        is_deleted=False,
                        created_at=datetime.now(timezone.utc)
                    )
                    db.session.add(customer)
                    db.session.flush()
                user.customer.is_pro = 1
                user.customer.pro_expires_at = expires_at
                user.customer.subscription_purchased_at = datetime.now(timezone.utc)
            
            db.session.commit()
        
        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False}), 500


@app.route('/receipt/<int:payment_id>')
@login_required
def receipt(payment_id):
    """Show receipt page with download link"""
    user = db.session.get(User, session['user_id'])
    payment = db.session.get(Payment, payment_id)
    if not payment:
        from flask import abort
        abort(404)
    
    # Verify payment belongs to user (unless admin)
    if payment.user_id != user.id and not user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('receipt.html', payment=payment, user=user)


@app.route('/receipt/<int:payment_id>/download')
@login_required
def download_receipt(payment_id):
    """Download receipt PDF"""
    user = db.session.get(User, session['user_id'])
    payment = db.session.get(Payment, payment_id)
    if not payment:
        from flask import abort
        abort(404)
    
    # Verify payment belongs to user (unless admin)
    if payment.user_id != user.id and not user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    if payment.receipt_path and os.path.exists(payment.receipt_path):
        return send_file(payment.receipt_path, as_attachment=True, 
                        download_name=f'receipt_{payment.id}.pdf')
    else:
        flash('Receipt not found.', 'warning')
        return redirect(url_for('receipt', payment_id=payment_id))


@app.route('/prediction/<int:prediction_id>/download-pdf')
@login_required
def download_prediction_pdf(prediction_id):
    """Download prediction result as PDF"""
    from modules.pdf_generator import generate_prediction_pdf
    
    user = db.session.get(User, session['user_id'])
    prediction = db.session.get(Prediction, prediction_id)
    
    if not prediction:
        from flask import abort
        abort(404)
    
    # Verify prediction belongs to user (unless admin)
    if prediction.user_id != user.id and not user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get image path
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], prediction.filename)
    if not os.path.exists(image_path):
        flash('Image file not found.', 'warning')
        return redirect(url_for('history'))
    
    # Parse topk results
    try:
        topk_results = json.loads(prediction.topk_results) if prediction.topk_results else []
    except:
        topk_results = [{'label': prediction.result, 'confidence': prediction.confidence}]
    
    # Parse models used
    try:
        models_used = json.loads(prediction.models_used) if prediction.models_used else []
    except:
        models_used = []
    
    # Generate PDF
    try:
        pdf_path = generate_prediction_pdf(
            prediction=prediction,
            user=user,
            image_path=image_path,
            topk_results=topk_results,
            all_models=None,  # Could be enhanced to store this in DB
            ensemble_top=None  # Could be enhanced to store this in DB
        )
        
        if pdf_path and os.path.exists(pdf_path):
            return send_file(pdf_path, as_attachment=True,
                            download_name=f'prediction_{prediction.id}.pdf')
        else:
            logger.warning(f"PDF generation returned None or file doesn't exist: {pdf_path}")
            flash('PDF generation failed. Please ensure reportlab is installed.', 'warning')
            return redirect(url_for('history'))
    except Exception as e:
        logger.error(f"Error in download_prediction_pdf: {e}")
        logger.error(traceback.format_exc())
        flash(f'PDF generation error: {str(e)[:100]}. Please try again.', 'warning')
        return redirect(url_for('history'))


@app.route('/toggle-theme', methods=['POST'])
@login_required
def toggle_theme():
    """Toggle user theme preference"""
    user = db.session.get(User, session['user_id'])
    current_theme = user.theme or 'light'
    new_theme = 'dark' if current_theme == 'light' else 'light'
    user.theme = new_theme
    db.session.commit()
    session['theme'] = new_theme
    return jsonify({'theme': new_theme})


# Admin Routes
@app.route('/notifications/list')
@login_required
def get_notifications_list():
    """Get notifications list for current user (JSON API)"""
    user = db.session.get(User, session['user_id'])
    visible_after = _notification_visible_after(user)
    
    # Get user-specific unread notifications
    user_query = Notification.query.filter_by(cust_id=user.id, is_read=False)
    if visible_after:
        user_query = user_query.filter(Notification.created_at >= visible_after)
    user_notifications = user_query.order_by(Notification.created_at.desc()).limit(10).all()
    
    # Get all-user unread notifications (broadcast notifications)
    all_query = Notification.query.filter_by(cust_id=None, is_read=False)
    if visible_after:
        all_query = all_query.filter(Notification.created_at >= visible_after)
    all_notifications = all_query.order_by(Notification.created_at.desc()).limit(10).all()
    
    # Combine and deduplicate (in case same notification appears in both)
    seen_ids = set()
    notifications = []
    
    # Add user-specific notifications first
    for notif in user_notifications:
        if notif.id not in seen_ids:
            seen_ids.add(notif.id)
            notifications.append({
                'id': notif.id,
                'title': notif.title,
                'message': notif.message,
                'type': notif.notification_type,
                'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M') if notif.created_at else 'N/A',
                '_created_ts': notif.created_at.timestamp() if notif.created_at else 0
            })
    
    # Add all-user notifications
    for notif in all_notifications:
        if notif.id not in seen_ids:
            seen_ids.add(notif.id)
            notifications.append({
                'id': notif.id,
                'title': notif.title,
                'message': notif.message,
                'type': notif.notification_type,
                'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M') if notif.created_at else 'N/A',
                '_created_ts': notif.created_at.timestamp() if notif.created_at else 0
            })
    
    # Sort by created_at descending
    notifications.sort(key=lambda x: x.get('_created_ts', 0), reverse=True)
    for item in notifications:
        item.pop('_created_ts', None)
    
    return jsonify({'notifications': notifications})


@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard with comprehensive stats"""
    try:
        total_users = Customer.query.filter(Customer.is_deleted == False).count()
        total_predictions = (
            Prediction.query.join(Customer, Prediction.cust_id == Customer.customer_id)
            .filter(Customer.is_deleted == False)
            .count()
        )
        recent_predictions = (
            Prediction.query.join(Customer, Prediction.cust_id == Customer.customer_id)
            .filter(Customer.is_deleted == False)
            .order_by(Prediction.timestamp.desc())
            .limit(10)
            .all()
        )
        uploaded_images_count = total_predictions
        
        # Pro members stats (only count active subscriptions with future expiry)
        pro_members = Customer.query.filter(
            Customer.is_deleted == False,
            Customer.is_pro == 1,
            Customer.pro_expires_at.isnot(None),
            Customer.pro_expires_at > datetime.now(timezone.utc)
        ).count()
        active_pro = pro_members
        
        # Payments stats
        try:
            total_payments = Payment.query.count()
            total_revenue = db.session.query(db.func.sum(Payment.amount_cents)).filter(Payment.status == 'completed').scalar() or 0
            total_revenue_dollars = total_revenue / 100.0  # Will be displayed as ₹ in template
        except Exception as payment_error:
            logger.warning(f"Error querying payments: {payment_error}")
            total_payments = 0
            total_revenue_dollars = 0.0
        
        # Expiring Pro (within 30 days)
        thirty_days_from_now = datetime.now(timezone.utc).replace(day=1) + timedelta(days=30)
        expiring_pro = Customer.query.filter(
            Customer.is_deleted == False,
            Customer.is_pro == 1,
            Customer.pro_expires_at.isnot(None),
            Customer.pro_expires_at <= thirty_days_from_now,
            Customer.pro_expires_at > datetime.now(timezone.utc)
        ).count()
        
        disease_counts = (
            db.session.query(Prediction.result, db.func.count(Prediction.id))
            .join(Customer, Prediction.cust_id == Customer.customer_id)
            .filter(Customer.is_deleted == False)
            .group_by(Prediction.result)
            .all()
        )
    except Exception as e:
        logger.error(f"Error in admin dashboard: {e}")
        # Fallback - try with Customer join, or use basic queries
        try:
            total_users = Customer.query.filter(Customer.is_deleted == False).count()
            total_predictions = Prediction.query.count()
            recent_predictions = Prediction.query.order_by(Prediction.timestamp.desc()).limit(10).all()
            uploaded_images_count = Prediction.query.count()
            pro_members = Customer.query.filter(Customer.is_deleted == False, Customer.is_pro == 1).count()
            active_pro = pro_members
        except:
            total_users = Customer.query.count()
            total_predictions = Prediction.query.count()
            recent_predictions = Prediction.query.order_by(Prediction.timestamp.desc()).limit(10).all()
            uploaded_images_count = Prediction.query.count()
            pro_members = 0
            active_pro = 0
        try:
            total_payments = Payment.query.count()
        except Exception as payment_error:
            logger.warning(f"Error querying payments in fallback: {payment_error}")
            total_payments = 0
        total_revenue_dollars = 0.0
        expiring_pro = 0
        disease_counts = (db.session.query(Prediction.result, db.func.count(Prediction.id))
                          .group_by(Prediction.result).all())
    
    most_common_disease = None
    most_common_count = 0
    if disease_counts:
        most_common = max(disease_counts, key=lambda x: x[1])
        most_common_disease = most_common[0]
        most_common_count = most_common[1]
    
    # Disease distribution
    disease_distribution = dict(disease_counts[:10])  # Top 10
    
    # Load model accuracy data
    model_accuracy = {}
    try:
        accuracy_path = os.path.join(os.path.dirname(__file__), 'model_accuracy.json')
        if os.path.exists(accuracy_path):
            with open(accuracy_path, 'r') as f:
                model_accuracy = json.load(f)
    except Exception as e:
        logger.error(f"Error loading model accuracy: {e}")

    return render_template('admin/admin_dashboard.html',
                         total_users=total_users,
                         total_predictions=total_predictions,
                         recent_predictions=recent_predictions,
                         most_common_disease=most_common_disease,
                         most_common_count=most_common_count,
                         uploaded_images_count=uploaded_images_count,
                         disease_distribution=disease_distribution,
                         pro_members=pro_members,
                         active_pro=active_pro,
                         total_payments=total_payments,
                         total_revenue_dollars=total_revenue_dollars,
                         expiring_pro=expiring_pro,
                         model_accuracy=model_accuracy)


@app.route('/admin/model-performance')
@admin_required
def admin_model_performance():
    """Admin - Model performance statistics"""
    try:
        model_stats = _collect_model_inventory_and_usage()
        return render_template('admin/admin_model_performance.html', model_stats=model_stats)
    except Exception as e:
        logger.error(f"Error loading model performance: {e}")
        flash('Error loading model performance data.', 'danger')
        return redirect(url_for('admin_dashboard'))


@app.route('/admin/models', methods=['GET', 'POST'])
@admin_required
def admin_model_management():
    """Admin - Manage model enable/disable"""
    config_path = os.path.join(os.path.dirname(__file__), 'model_config.json')

    def _load_enabled_model_list():
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return list((json.load(f) or {}).get('enabled_models', []))
        except Exception as e:
            logger.warning(f"Could not load model config: {e}")
        return []

    def _save_enabled_model_list(enabled_models):
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump({'enabled_models': sorted(list(set(enabled_models)))}, f, indent=2)

    enabled_models = _load_enabled_model_list()
    models = []

    # Get all available models from model directory
    try:
        model_dir = predict.MODEL_DIR
        loaded_model_classes = {}
        loaded_name_set = set()
        loaded_models_available = False
        try:
            loaded_models = predict.load_all_models()
            for lm in loaded_models:
                lm_name = str(lm.get('name', '')).strip()
                if lm_name:
                    loaded_name_set.add(lm_name)
                    loaded_model_classes[lm_name] = len(lm.get('classes', []) or [])
            loaded_models_available = bool(loaded_name_set)
        except Exception:
            loaded_models_available = False

        models = []

        def _add_dir_models(dir_path):
            try:
                if os.path.exists(dir_path):
                    for file in os.listdir(dir_path):
                        if file.endswith(('.keras', '.h5')) and not file.endswith('.crdownload'):
                            file_path = os.path.join(dir_path, file)
                            try:
                                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                                classes = loaded_model_classes.get(file, 0)
                                models.append({
                                    'name': file,
                                    'path': file_path,
                                    'size_mb': size_mb,
                                    'classes': classes,
                                    'enabled': (file in enabled_models) if enabled_models else True
                                })
                            except Exception as e:
                                logger.warning(f"Error getting info for {file}: {e}")
            except Exception as e:
                logger.warning(f"Error scanning {dir_path}: {e}")
        _add_dir_models(model_dir)
        trained_dir = os.path.join(os.path.dirname(__file__), 'trained_models')
        _add_dir_models(trained_dir)
        detection_dir = os.path.join(os.path.dirname(__file__), 'detection')
        _add_dir_models(detection_dir)
        predict_detection_dir = getattr(predict, 'DETECTION_MODELS_DIR', None)
        if predict_detection_dir and os.path.abspath(predict_detection_dir) != os.path.abspath(detection_dir):
            _add_dir_models(predict_detection_dir)
        final_dir = getattr(predict, 'FINAL_MODELS_DIR', os.path.join(os.path.dirname(__file__), 'models', 'final_models'))
        try:
            if os.path.isdir(final_dir):
                plant_model = os.path.join(final_dir, 'plant_classifier.keras')
                if os.path.exists(plant_model):
                    try:
                        size_mb = os.path.getsize(plant_model) / (1024 * 1024)
                        models.append({
                            'name': 'plant_classifier.keras',
                            'path': plant_model,
                            'size_mb': size_mb,
                            'classes': 0,
                            'enabled': ('plant_classifier.keras' in enabled_models) if enabled_models else True
                        })
                    except:
                        pass
                for entry in os.listdir(final_dir):
                    if entry.startswith('disease_'):
                        ddir = os.path.join(final_dir, entry)
                        for f in os.listdir(ddir):
                            if f.endswith('_disease_classifier.keras'):
                                fpath = os.path.join(ddir, f)
                                try:
                                    size_mb = os.path.getsize(fpath) / (1024 * 1024)
                                    models.append({
                                        'name': f,
                                        'path': fpath,
                                        'size_mb': size_mb,
                                        'classes': 0,
                                        'enabled': (f in enabled_models) if enabled_models else True
                                    })
                                except:
                                    pass
        except Exception:
            pass
        backups_dir = os.path.join(os.path.dirname(__file__), 'models', 'backups_old')
        try:
            if os.path.isdir(backups_dir):
                subs = [os.path.join(backups_dir, d) for d in os.listdir(backups_dir) if os.path.isdir(os.path.join(backups_dir, d))]
                if subs:
                    subs.sort(reverse=True)
                    latest = subs[0]
                    _add_dir_models(latest)
                    for entry in os.listdir(latest):
                        if entry.startswith('disease_'):
                            ddir = os.path.join(latest, entry)
                            for f in os.listdir(ddir):
                                if f.endswith('_disease_classifier.keras'):
                                    fpath = os.path.join(ddir, f)
                                    try:
                                        size_mb = os.path.getsize(fpath) / (1024 * 1024)
                                        models.append({
                                            'name': f,
                                            'path': fpath,
                                            'size_mb': size_mb,
                                            'classes': 0,
                                            'enabled': (f in enabled_models) if enabled_models else True
                                        })
                                    except:
                                        pass
        except Exception:
            pass

        # Deduplicate and filter to only valid, loadable models
        dedup = {}
        for m in models:
            dedup[m['name']] = m
        models = list(dedup.values())
        valid_names = set()
        valid_names.update(loaded_name_set)
        # Always include final two-stage models even if not in loaded list
        try:
            if os.path.isdir(final_dir):
                if os.path.exists(os.path.join(final_dir, 'plant_classifier.keras')):
                    valid_names.add('plant_classifier.keras')
                for entry in os.listdir(final_dir):
                    if entry.startswith('disease_'):
                        ddir = os.path.join(final_dir, entry)
                        for f in os.listdir(ddir):
                            if f.endswith('_disease_classifier.keras'):
                                valid_names.add(f)
        except Exception:
            pass

        # Filter out unknown models only when model loader is available
        if loaded_models_available and valid_names:
            models = [m for m in models if m['name'] in valid_names]
        models.sort(key=lambda x: x['name'])
    except Exception as e:
        logger.error(f"Error loading models: {e}")
        flash('Error loading model information from directories. Using model stats fallback.', 'warning')

    model_stats = _collect_model_inventory_and_usage()
    # Guaranteed fallback for UI: if scan/listing fails, use stats-derived names.
    if not models and model_stats:
        models = [{
            'name': s.get('name'),
            'path': '',
            'size_mb': float(s.get('size_mb', 0) or 0),
            'classes': int(s.get('classes', 0) or 0),
            'enabled': True
        } for s in model_stats if s.get('name')]
        models.sort(key=lambda x: x['name'])

    # Ensure explicitly-enabled models always appear in management list.
    if enabled_models:
        stats_map = {s.get('name'): s for s in model_stats if s.get('name')}
        existing_names = {m.get('name') for m in models}
        for enabled_name in enabled_models:
            if enabled_name in existing_names:
                continue
            s = stats_map.get(enabled_name, {})
            models.append({
                'name': enabled_name,
                'path': '',
                'size_mb': float(s.get('size_mb', 0) or 0),
                'classes': int(s.get('classes', 0) or 0),
                'enabled': True
            })
        models.sort(key=lambda x: x['name'])

    model_names = [m['name'] for m in models]

    if request.method == 'POST':
        action = (request.form.get('action') or 'bulk_save').strip()
        quick_toggle = (request.form.get('quick_toggle') or '').strip()
        model_name_override = None
        if '|' in quick_toggle:
            toggle_action, toggle_model = quick_toggle.split('|', 1)
            if toggle_action == 'enable':
                action = 'enable_model'
            elif toggle_action == 'disable':
                action = 'disable_model'
            model_name_override = toggle_model
        current_enabled = set(enabled_models if enabled_models else model_names)
        try:
            if action == 'enable_model':
                model_name = (model_name_override or request.form.get('model_name') or '').strip()
                if model_name in model_names:
                    current_enabled.add(model_name)
                    _save_enabled_model_list(list(current_enabled))
                    flash(f'Model enabled: {model_name}', 'success')
                else:
                    flash('Selected model was not found.', 'warning')
            elif action == 'disable_model':
                model_name = (model_name_override or request.form.get('model_name') or '').strip()
                if model_name in model_names:
                    current_enabled.discard(model_name)
                    _save_enabled_model_list(list(current_enabled))
                    flash(f'Model disabled: {model_name}', 'success')
                else:
                    flash('Selected model was not found.', 'warning')
            elif action == 'enable_all':
                _save_enabled_model_list(model_names)
                flash('All models enabled.', 'success')
            elif action == 'disable_all':
                _save_enabled_model_list([])
                flash('All models disabled.', 'warning')
            else:
                selected = request.form.getlist('enabled_models')
                _save_enabled_model_list(selected)
                flash('Model settings updated successfully. Changes are applied automatically.', 'success')

            try:
                predict._MODEL_CACHE['loaded'] = False
                predict._MODEL_CACHE['models'] = []
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error saving model config: {e}")
            flash('Error saving model settings.', 'danger')
        return redirect(url_for('admin_model_management'))

    enabled_set = set(enabled_models if enabled_models else model_names)
    for m in models:
        m['enabled'] = m['name'] in enabled_set

    return render_template(
        'admin/admin_model_management.html',
        models=models,
        model_stats=model_stats,
        enabled_model_names=sorted(list(enabled_set))
    )


@app.route('/admin/system-logs', methods=['GET', 'POST'])
@admin_required
def admin_system_logs():
    """Admin - System logs"""
    settings = _load_admin_visual_settings()
    valid_cursor_ids = {item['id'] for item in CURSOR_ANIMATION_OPTIONS}
    valid_page_ids = {item['id'] for item in PAGE_TARGET_OPTIONS}
    valid_animation_ids = {item['id'] for item in PAGE_ANIMATION_OPTIONS}

    selected_page = (request.args.get('page') or request.form.get('selected_page') or 'global').strip()
    if selected_page not in valid_page_ids:
        selected_page = 'global'

    if request.method == 'POST':
        action = (request.form.get('action') or '').strip()
        if action == 'save_cursor':
            selected_cursor = (request.form.get('cursor_animation') or '').strip()
            if selected_cursor in valid_cursor_ids:
                settings['cursor_animation'] = selected_cursor
                if _save_admin_visual_settings(settings):
                    flash('Cursor animation preference saved. No live animation changed yet.', 'success')
                else:
                    flash('Could not save cursor animation setting.', 'danger')
            else:
                flash('Invalid cursor animation option selected.', 'warning')
        elif action == 'save_page_animation':
            page_target = (request.form.get('selected_page') or 'global').strip()
            page_animation = (request.form.get('page_animation') or '').strip()
            if page_target not in valid_page_ids:
                page_target = 'global'
            if page_animation in valid_animation_ids:
                page_map = settings.get('page_animations') or {}
                page_map[page_target] = page_animation
                settings['page_animations'] = page_map
                if _save_admin_visual_settings(settings):
                    flash(f'Page animation preference saved for "{page_target}". Live background stays unchanged.', 'success')
                else:
                    flash('Could not save page animation setting.', 'danger')
            else:
                flash('Invalid page animation option selected.', 'warning')
        return redirect(url_for('admin_system_logs', page=selected_page))

    current_cursor = settings.get('cursor_animation', 'classic_triple')
    page_map = settings.get('page_animations') or {}
    current_page_animation = page_map.get(selected_page) or page_map.get('global') or 'moving_dots'
    cursor_options = sorted(CURSOR_ANIMATION_OPTIONS, key=lambda x: 0 if x['id'] == current_cursor else 1)
    page_animation_options = sorted(PAGE_ANIMATION_OPTIONS, key=lambda x: 0 if x['id'] == current_page_animation else 1)

    # Get recent activity from database
    try:
        recent_predictions = (
            Prediction.query
            .join(Customer, Prediction.cust_id == Customer.customer_id)
            .filter(Customer.is_deleted == False)
            .order_by(Prediction.timestamp.desc())
            .limit(50)
            .all()
        )
        recent_users = (
            Customer.query
            .filter(Customer.is_deleted == False)
            .order_by(Customer.created_at.desc())
            .limit(20)
            .all()
        )
    except Exception as e:
        logger.error(f"Error loading system logs: {e}")
        recent_predictions = Prediction.query.order_by(Prediction.timestamp.desc()).limit(50).all()
        recent_users = Customer.query.order_by(Customer.created_at.desc()).limit(20).all()
    
    return render_template('admin/admin_system_logs.html', 
                         recent_predictions=recent_predictions,
                         recent_users=recent_users,
                         cursor_options=cursor_options,
                         page_animation_options=page_animation_options,
                         page_targets=PAGE_TARGET_OPTIONS,
                         selected_page=selected_page,
                         current_cursor=current_cursor,
                         current_page_animation=current_page_animation)


@app.route('/admin/database')
@admin_required
def admin_database():
    """Admin - View database tables and data"""
    import sqlite3
    from pathlib import Path
    
    # Find database file
    db_path = Path('instance') / 'database.sqlite'
    if not db_path.exists():
        db_path = Path('database') / 'instance' / 'database.sqlite'
    
    if not db_path.exists():
        flash('Database file not found.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Only show these tables in admin dashboard
    allowed_tables = [
        'tbl_customer',
        'tbl_payment',
        'tbl_subscription',
        'tbl_prediction',
        'tbl_usage_counters',
        'tbl_models',
        'tbl_notification'
    ]
    
    tables_info = {}
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        all_tables = [row[0] for row in cursor.fetchall()]
        
        # Filter to only allowed tables; if singular tables missing, include plural equivalents
        tables = []
        for table in all_tables:
            if table in allowed_tables:
                tables.append(table)
        # Include plural equivalents if present
        plural_map = {
            'tbl_customer': 'tbl_customers',
            'tbl_prediction': 'tbl_predictions',
            'tbl_notification': 'tbl_notifications'
        }
        for singular, plural in plural_map.items():
            if singular not in tables and plural in all_tables and singular in allowed_tables:
                tables.append(plural)
        
        for table_name in tables:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            fk_rows = cursor.fetchall()
            fk_map = {}
            for fk in fk_rows:
                from_col = fk[3]
                ref_table = fk[2]
                ref_col = fk[4]
                fk_map[from_col] = f"Foreign Key → {ref_table}({ref_col})"

            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 10")
            sample_rows = [dict(row) for row in cursor.fetchall()]
            
            # Augment tbl_customer data with gmail, encrypted_pass, subscription_purchased_at
            try:
                if table_name in ('tbl_customer', 'tbl_customers') and sample_rows:
                    # Build index for login and subscription lookups
                    for r in sample_rows:
                        cid = r.get('customer_id') or r.get('cust_id')
                        if cid is None:
                            continue
                        # Fetch email and password_hash from tbl_login
                        cursor.execute("SELECT email, password_hash FROM tbl_login WHERE id = ?", (cid,))
                        login_row = cursor.fetchone()
                        if login_row:
                            r['gmail'] = login_row[0]
                            r['encrypted_pass'] = login_row[1]
                        # Fetch latest subscription dates
                        cursor.execute("SELECT start_date, created_at FROM tbl_subscription WHERE cust_id = ? ORDER BY COALESCE(start_date, created_at) DESC LIMIT 1", (cid,))
                        sub_row = cursor.fetchone()
                        if sub_row:
                            r['subscription_purchased_at'] = sub_row[0] or sub_row[1]
            except Exception as _e:
                pass

            def describe(col_name: str) -> str:
                mapping = {
                    'cust_id': 'Customer ID - Unique identifier for the customer',
                    'customer_id': 'Customer ID - Unique identifier for the customer',
                    'user_id': 'User ID - Links to the login email',
                    'cust_fname': 'First Name - Customer\'s first name',
                    'cust_lname': 'Last Name - Customer\'s last name',
                    'cust_username': 'Username - Unique username for the customer',
                    'cust_phone': 'Phone Number - Customer\'s contact number',
                    'cust_city': 'City - Customer\'s city',
                    'cust_district': 'District - Customer\'s district',
                    'cust_state': 'State - Customer\'s state',
                    'cust_pincode': 'Pincode - Customer\'s postal code',
                    'cust_country': 'Country - Customer\'s country',
                    'is_pro': 'Is Pro - 1 if Pro subscriber, 0 otherwise',
                    'pro_expires_at': 'Pro Expiry - Date when Pro subscription expires',
                    'theme': 'Theme - UI theme preference (light/dark)',
                    'is_deleted': 'Is Deleted - 1 if account is deleted/banned',
                    'created_at': 'Created At - Account creation timestamp',
                    'subscription_id': 'Subscription ID - ID of the active subscription',
                    'gmail': 'Email - Customer\'s email address',
                    'encrypted_pass': 'Password Hash - Encrypted password',
                    'subscription_purchased_at': 'Subscription Date - Date of latest subscription',
                    'payment_id': 'Payment ID - Unique identifier for the payment',
                    'card_id': 'Card ID - Links to the payment card',
                    'payment_date': 'Payment Date - Date and time of payment',
                    'amount_cents': 'Amount (Cents) - Payment amount in cents',
                    'currency': 'Currency - Payment currency (e.g., USD)',
                    'status': 'Status - Current status',
                    'receipt_path': 'Receipt Path - Path to the payment receipt file',
                    'plan_id': 'Plan ID - Links to the subscription plan',
                    'start_date': 'Start Date - Subscription start date',
                    'end_date': 'End Date - Subscription end date',
                    'expires_at': 'Expiry Date - When the subscription expires',
                    'is_active': 'Is Active - 1 if currently active',
                    'updated_at': 'Updated At - Last update timestamp',
                    'prediction_id': 'Prediction ID - Unique identifier for the prediction',
                    'filename': 'Filename - Name of the file',
                    'result': 'Result - Disease prediction result',
                    'confidence': 'Confidence - Confidence score of the prediction',
                    'topk_results': 'Top-K Results - JSON of top K predictions',
                    'models_used': 'Models Used - List of models used for prediction',
                    'is_unknown': 'Is Unknown - 1 if disease is unknown',
                    'timestamp': 'Timestamp - Date and time of event',
                    'total_predictions': 'Total Predictions - Total number of predictions made',
                    'today_count': 'Today\'s Count - Predictions made today',
                    'daily_reset_at': 'Reset Time - Time when daily count resets',
                    'last_prediction_at': 'Last Prediction - Timestamp of last prediction',
                    'model_id': 'Model ID - Unique identifier for the model',
                    'model_name': 'Model Name - Name of the model',
                    'size_bytes': 'Size (Bytes) - Size of the model file',
                    'backend': 'Backend - Framework used (e.g., tf, pytorch)',
                    'classes': 'Classes - Number of classes the model can detect',
                    'loaded': 'Loaded - 1 if model is loaded in memory',
                    'notification_id': 'Notification ID - Unique identifier',
                    'title': 'Title - Notification title',
                    'message': 'Message - Notification content',
                    'type': 'Type - Notification type (info, warning, etc.)',
                    'is_read': 'Is Read - 1 if read, 0 if unread',
                    'is_system': 'Is System - 1 if system notification',
                    'notification_type': 'Notification Type - Category of notification',
                    'recipient_type': 'Recipient Type - Target audience',
                    'id': 'ID - Unique identifier'
                }
                if col_name in mapping:
                    return mapping[col_name]
                # Fallback for unmapped columns
                parts = col_name.replace('_id', ' ID').split('_')
                return ' '.join(p.capitalize() for p in parts) + f" - {col_name.replace('_', ' ')}"

            cols_transformed = []
            for col in columns:
                name = col[1]
                dtype = col[2]
                notnull = col[3]
                pk = col[5]
                has_pk = (pk == 1)
                has_fk = (name in fk_map)
                constraint = ''
                if has_pk and has_fk:
                    constraint = 'PRIMARY KEY; FOREIGN KEY'
                elif has_pk:
                    constraint = 'PRIMARY KEY'
                elif has_fk:
                    constraint = 'FOREIGN KEY'
                if notnull == 1:
                    constraint = (constraint + ('; ' if constraint else '') + 'NOT NULL')
                cols_transformed.append({
                    'field': name,
                    'data_type': dtype,
                    'constraint': constraint,
                    'description': describe(name)
                })

            # Synthetic FK: subscription_id in tbl_customer
            try:
                if table_name in ('tbl_customer', 'tbl_customers'):
                    cols_transformed.append({
                        'field': 'subscription_id',
                        'data_type': 'INTEGER',
                        'constraint': 'FOREIGN KEY',
                        'description': describe('subscription_id')
                    })
            except Exception:
                pass

            # Transform sample rows keys to descriptions
            sample_rows_transformed = []
            for row in sample_rows:
                new_row = {}
                for key, value in row.items():
                    new_key = describe(key)
                    new_row[new_key] = value
                sample_rows_transformed.append(new_row)

            tables_info[table_name] = {
                'columns': cols_transformed,
                'row_count': row_count,
                'sample_data': sample_rows_transformed
            }
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error reading database: {e}")
        flash(f'Error reading database: {e}', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Add table descriptions
    table_descriptions = {
        'tbl_login': 'Login Details - User credentials and authentication',
        'tbl_customer': 'Customer Details - Personal and profile information',
        'tbl_customers': 'Customer Details - Personal and profile information',
        'tbl_plans': 'Subscription Plans - Available pricing tiers',
        'tbl_card': 'Card Details - Saved payment methods',
        'tbl_subscription': 'Subscription Details - User subscription status',
        'tbl_payment': 'Payment Details - Transaction history',
        'tbl_predictions': 'Disease Prediction Results - AI analysis history',
        'tbl_usage_counters': 'Usage Counters - Tracks API/Service usage',
        'tbl_models': 'AI Models - Registered machine learning models',
        'tbl_notification': 'Notifications - User alerts and messages',
        'tbl_notifications': 'Notifications - User alerts and messages'
    }
    
    for t_name, t_info in tables_info.items():
        t_info['description'] = table_descriptions.get(t_name, '')

    return render_template('admin/admin_database.html', 
                         tables_info=tables_info,
                         db_path=str(db_path))


@app.route('/admin/users')
@admin_required
def admin_users():
    """Admin - View all users with Pro status"""
    show_deleted = request.args.get('show_deleted', 'false') == 'true'
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    download = request.args.get('download') == '1'
    download_pdf = request.args.get('download_pdf') == '1'
    try:
        base_query = Customer.query.filter(Customer.is_deleted == True) if show_deleted else Customer.query.filter(Customer.is_deleted == False)
        if start_date_str:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            base_query = base_query.filter(Customer.created_at >= start_dt)
        if end_date_str:
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            base_query = base_query.filter(Customer.created_at < end_dt)
        users = base_query.order_by(Customer.created_at.desc()).all()
        deleted_count = Customer.query.filter(Customer.is_deleted == True).count()
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        users = Customer.query.order_by(Customer.customer_id.desc()).all()
        deleted_count = 0
    
    # Get usage counters for all users
    for user in users:
        counter = UsageCounter.query.filter_by(cust_id=user.id).first()
        user.usage_count = counter.total_predictions if counter else 0
    
    if download_pdf:
        from flask import Response as FlaskResponse
        from modules.pdf_generator import generate_admin_table_pdf
        rows = []
        for u in users:
            rows.append([
                u.id,
                u.username,
                u.email,
                'Admin' if u.is_admin else 'Member',
                u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else ''
            ])
        subtitle = f"Date range: {start_date_str or 'Any'} to {end_date_str or 'Any'} | View: {'Deleted Users' if show_deleted else 'Active Users'}"
        pdf_bytes = generate_admin_table_pdf(
            title='Leafora AI - Users Report',
            columns=['ID', 'Username', 'Email', 'Role', 'Created'],
            rows=rows,
            subtitle=subtitle
        )
        if pdf_bytes:
            filename = f"users_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            resp = FlaskResponse(pdf_bytes, mimetype='application/pdf')
            resp.headers['Content-Disposition'] = f'attachment; filename={filename}'
            return resp
    if download:
        from flask import Response as FlaskResponse
        import csv, io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Username', 'Email', 'Admin', 'Created'])
        for u in users:
            writer.writerow([u.id, u.username, u.email, 1 if u.is_admin else 0, u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else ''])
        resp = FlaskResponse(output.getvalue(), mimetype='text/csv')
        resp.headers['Content-Disposition'] = 'attachment; filename=users.csv'
        return resp
    return render_template('admin/admin_users.html', 
                         users=users, 
                         show_deleted=show_deleted, 
                         deleted_count=deleted_count,
                         start_date=start_date_str,
                         end_date=end_date_str)


@app.route('/admin/payments')
@admin_required
def admin_payments():
    """Admin - View all payments"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    download = request.args.get('download') == '1'
    download_pdf = request.args.get('download_pdf') == '1'
    payments_query = Payment.query.options(joinedload(Payment.subscription), joinedload(Payment.customer))
    if start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            payments_query = payments_query.filter(Payment.payment_date >= start_dt)
        except Exception:
            pass
    if end_date_str:
        try:
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            payments_query = payments_query.filter(Payment.payment_date < end_dt)
        except Exception:
            pass
    payments = payments_query.order_by(Payment.payment_date.desc()).all()
    search_customer = request.args.get('customer_id', '')
    if search_customer:
        # Search by user ID (customer_id is same as user.id)
        try:
            search_id = int(search_customer.replace('CUST-', '').replace('-', ''))
            payments = (
                Payment.query
                .options(joinedload(Payment.subscription), joinedload(Payment.customer))
                .filter(Payment.cust_id == search_id)
                .order_by(Payment.payment_date.desc())
                .all()
            )
        except (ValueError, AttributeError):
            # If not a valid ID, search by formatted customer_id
            payments = (
                Payment.query
                .options(joinedload(Payment.subscription), joinedload(Payment.customer))
                .filter(db.cast(Payment.cust_id, db.String).like(f'%{search_customer}%'))
                .order_by(Payment.payment_date.desc())
                .all()
            )
    if download_pdf:
        from flask import Response as FlaskResponse
        from modules.pdf_generator import generate_admin_table_pdf
        rows = []
        for p in payments:
            rows.append([
                p.id,
                p.user.customer_id if p.user else '',
                f"{p.amount_cents/100:.2f}",
                p.currency,
                p.card_last4 or '',
                p.card_brand or '',
                p.status,
                (p.created_at or p.payment_date).strftime('%Y-%m-%d %H:%M') if (p.created_at or p.payment_date) else ''
            ])
        subtitle = f"Customer filter: {search_customer or 'None'} | Date range: {start_date_str or 'Any'} to {end_date_str or 'Any'}"
        pdf_bytes = generate_admin_table_pdf(
            title='Leafora AI - Payments Report',
            columns=['ID', 'Customer', 'Amount', 'Currency', 'Card Last4', 'Brand', 'Status', 'Date'],
            rows=rows,
            subtitle=subtitle
        )
        if pdf_bytes:
            filename = f"payments_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            resp = FlaskResponse(pdf_bytes, mimetype='application/pdf')
            resp.headers['Content-Disposition'] = f'attachment; filename={filename}'
            return resp
    if download:
        from flask import Response as FlaskResponse
        import csv, io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Customer', 'Amount', 'Currency', 'Card Last4', 'Brand', 'Status', 'Date'])
        for p in payments:
            writer.writerow([p.id, p.user.customer_id if p.user else '', f"{p.amount_cents/100:.2f}", p.currency, p.card_last4 or '', p.card_brand or '', p.status, (p.created_at or p.payment_date).strftime('%Y-%m-%d %H:%M') if (p.created_at or p.payment_date) else ''])
        resp = FlaskResponse(output.getvalue(), mimetype='text/csv')
        resp.headers['Content-Disposition'] = 'attachment; filename=payments.csv'
        return resp
    return render_template('admin/admin_payments.html', payments=payments, search_customer=search_customer, start_date=start_date_str, end_date=end_date_str)


@app.route('/admin/notifications', methods=['GET', 'POST'])
@admin_required
def admin_notifications():
    """Admin - Send notifications to users"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        notification_type = request.form.get('type', 'info')
        recipient_type = request.form.get('recipient_type', 'all')  # 'all' or 'individual'
        user_id = request.form.get('user_id', type=int)
        
        if not title or not message:
            flash('Title and message are required.', 'danger')
            return redirect(url_for('admin_notifications'))
        
        try:
            if recipient_type == 'all':
                # Send to all users
                notification = Notification(
                    cust_id=None,  # None = all users
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    is_system=False
                )
                db.session.add(notification)
                db.session.commit()
                flash(f'Notification sent to all users successfully!', 'success')
            else:
                # Send to individual user
                if not user_id:
                    flash('Please select a user.', 'danger')
                    return redirect(url_for('admin_notifications'))
                
                user = db.session.get(User, user_id)
                if not user:
                    flash('User not found.', 'danger')
                    return redirect(url_for('admin_notifications'))
                
                notification = Notification(
                    cust_id=user_id,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    is_system=False
                )
                db.session.add(notification)
                db.session.commit()
                flash(f'Notification sent to {user.username} successfully!', 'success')
            
            return redirect(url_for('admin_notifications'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error sending notification: {e}")
            flash('Failed to send notification. Please try again.', 'danger')
            return redirect(url_for('admin_notifications'))
    
    # GET request - show form and notification history
    all_notifications = Notification.query.order_by(Notification.created_at.desc()).limit(50).all()
    all_users = User.query.join(Customer).filter(Customer.is_deleted == False).order_by(User.username).all()
    
    return render_template('admin/admin_notifications.html', 
                         notifications=all_notifications,
                         users=all_users)


def _clear_all_data_and_recreate_admin():
    from sqlalchemy import text
    from pathlib import Path
    db.session.remove()
    try:
        db.engine.dispose()
    except Exception:
        pass
    candidates = []
    try:
        candidates.append(Path(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')))
    except Exception:
        pass
    candidates.append(Path('instance') / 'database.sqlite')
    candidates.append(Path('database') / 'instance' / 'database.sqlite')
    removed = False
    for p in candidates:
        try:
            if p.exists():
                os.remove(p)
                removed = True
        except Exception:
            pass
    if not removed:
        with db.engine.connect() as conn:
            conn.execute(text('PRAGMA foreign_keys=OFF'))
            for t in db.inspect(db.engine).get_table_names():
                if not t.startswith('sqlite_'):
                    conn.execute(text(f'DROP TABLE IF EXISTS {t}'))
            conn.execute(text('PRAGMA foreign_keys=ON'))
    
    # Recreate schema
    db.create_all()
    admin = User(email='admin@admin.com', username='admin', password_hash=generate_password_hash('admin123'))
    db.session.add(admin)
    db.session.commit()
    admin_customer = Customer(customer_id=admin.id, is_admin=True, is_pro=1, is_deleted=False, created_at=datetime.now(timezone.utc))
    db.session.add(admin_customer)
    db.session.commit()

@app.route('/admin/clear_all', methods=['POST'])
@admin_required
def admin_clear_all():
    try:
        _clear_all_data_and_recreate_admin()
        flash('All data cleared. Admin user recreated.', 'success')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error clearing data: {e}')
        flash('Failed to clear data.', 'danger')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/logs')
@admin_required
def admin_logs():
    """Admin - View user activity logs (login, logout, subscription purchases)"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    download = request.args.get('download') == '1'
    download_pdf = request.args.get('download_pdf') == '1'
    customers = Customer.query.order_by(Customer.customer_id.desc()).all()
    
    # Build activity log entries
    activity_logs = []
    for customer in customers:
        user = User.query.get(customer.customer_id)
        if not user:
            continue
            
        # Login activity
        if customer.last_login_at:
            activity_logs.append({
                'type': 'login',
                'user': user,
                'timestamp': customer.last_login_at,
                'description': f'{user.username} logged in'
            })
        
        # Logout activity
        if customer.last_logout_at:
            activity_logs.append({
                'type': 'logout',
                'user': user,
                'timestamp': customer.last_logout_at,
                'description': f'{user.username} logged out'
            })
        
        # Subscription purchase
        if customer.subscription_purchased_at:
            activity_logs.append({
                'type': 'subscription',
                'user': user,
                'timestamp': customer.subscription_purchased_at,
                'description': f'{user.username} purchased Pro subscription'
            })
    
    if start_date_str or end_date_str:
        try:
            if start_date_str:
                start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                activity_logs = [l for l in activity_logs if l['timestamp'] and l['timestamp'] >= start_dt]
            if end_date_str:
                end_dt = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
                activity_logs = [l for l in activity_logs if l['timestamp'] and l['timestamp'] < end_dt]
        except Exception:
            pass
    activity_logs.sort(key=lambda x: x['timestamp'] if x['timestamp'] else datetime.min, reverse=True)
    
    # Limit to last 500 entries
    activity_logs = activity_logs[:500]
    
    # Filter by type if requested
    filter_type = request.args.get('type', '')
    if filter_type:
        activity_logs = [log for log in activity_logs if log['type'] == filter_type]
    
    if download_pdf:
        from flask import Response as FlaskResponse
        from modules.pdf_generator import generate_admin_table_pdf
        rows = []
        for l in activity_logs:
            rows.append([
                l['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if l['timestamp'] else '',
                l['type'],
                l['user'].username if l['user'] else '',
                l['user'].email if l['user'] else '',
                l['description']
            ])
        subtitle = f"Type filter: {filter_type or 'All'} | Date range: {start_date_str or 'Any'} to {end_date_str or 'Any'}"
        pdf_bytes = generate_admin_table_pdf(
            title='Leafora AI - Activity Logs Report',
            columns=['Timestamp', 'Type', 'Username', 'Email', 'Description'],
            rows=rows,
            subtitle=subtitle
        )
        if pdf_bytes:
            filename = f"activity_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            resp = FlaskResponse(pdf_bytes, mimetype='application/pdf')
            resp.headers['Content-Disposition'] = f'attachment; filename={filename}'
            return resp
    if download:
        from flask import Response as FlaskResponse
        import csv, io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Timestamp', 'Type', 'Username', 'Email', 'Description'])
        for l in activity_logs:
            writer.writerow([
                l['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if l['timestamp'] else '',
                l['type'],
                l['user'].username if l['user'] else '',
                l['user'].email if l['user'] else '',
                l['description']
            ])
        resp = FlaskResponse(output.getvalue(), mimetype='text/csv')
        resp.headers['Content-Disposition'] = 'attachment; filename=activity_logs.csv'
        return resp
    return render_template('admin/admin_logs.html', 
                         activity_logs=activity_logs,
                         filter_type=filter_type,
                         start_date=start_date_str,
                         end_date=end_date_str)


@app.route('/notifications/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    user = db.session.get(User, session['user_id'])
    notification = db.session.get(Notification, notification_id)
    
    if not notification:
        return jsonify({'success': False, 'error': 'Notification not found'}), 404
    
    # Check if notification belongs to user or is for all users
    if notification.cust_id is None or notification.cust_id == user.id:
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Unauthorized'}), 403


@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read for current user"""
    user = db.session.get(User, session['user_id'])
    
    # Mark user-specific notifications
    Notification.query.filter_by(cust_id=user.id, is_read=False).update({'is_read': True})
    
    # Mark all-user notifications (we'll track this per user in a separate way)
    # For simplicity, we'll just mark user-specific ones
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/notifications/count')
@login_required
def notification_count():
    """Get unread notification count for current user"""
    user = db.session.get(User, session['user_id'])
    visible_after = _notification_visible_after(user)
    
    # Count user-specific unread notifications
    user_count_query = Notification.query.filter_by(cust_id=user.id, is_read=False)
    if visible_after:
        user_count_query = user_count_query.filter(Notification.created_at >= visible_after)
    user_count = user_count_query.count()
    
    # Count all-user unread notifications visible for this user only
    all_count_query = Notification.query.filter_by(cust_id=None, is_read=False)
    if visible_after:
        all_count_query = all_count_query.filter(Notification.created_at >= visible_after)
    all_count = all_count_query.count()
    
    total = user_count + all_count
    return jsonify({'count': total})


@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    """Admin - Soft delete user"""
    if user_id == session['user_id']:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin_users'))
    
    user = db.session.get(User, user_id)
    if not user:
        from flask import abort
        abort(404)
    try:
        if user.customer:
            user.customer.is_deleted = True
            db.session.commit()
            flash(f'User {user.username} has been removed. They can be restored from the deleted users list.', 'success')
        else:
            raise AttributeError("Customer record not found")
    except Exception as e:
        # If is_deleted column doesn't exist, use hard delete
        logger.warning(f"Soft delete failed, using hard delete: {e}")
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.username} has been deleted.', 'success')
    return redirect(url_for('admin_users', show_deleted='false'))


@app.route('/admin/users/restore/<int:user_id>', methods=['POST'])
@admin_required
def admin_restore_user(user_id):
    """Admin - Restore deleted user"""
    user = db.session.get(User, user_id)
    if not user:
        from flask import abort
        abort(404)
    try:
        if user.customer:
            user.customer.is_deleted = False
            db.session.commit()
            flash(f'User {user.username} has been restored. They can now login again.', 'success')
        else:
            raise AttributeError("Customer record not found")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error restoring user: {e}")
        flash(f'Error restoring user: {e}', 'danger')
    return redirect(url_for('admin_users', show_deleted='true'))


@app.route('/admin/predictions')
@admin_required
def admin_predictions():
    """Admin - View all predictions"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    range_key = request.args.get('range', '30d')
    download = request.args.get('download') == '1'
    download_pdf = request.args.get('download_pdf') == '1'
    valid_ranges = {
        '7d': 7,
        '30d': 30,
        '90d': 90,
        '365d': 365,
        'all': None
    }
    if range_key not in valid_ranges:
        range_key = '30d'
    max_age_days = valid_ranges[range_key]
    try:
        base_query = (
            Prediction.query
            .join(Customer, Prediction.cust_id == Customer.customer_id)
            .filter(Customer.is_deleted == False)
        )
    except Exception:
        base_query = Prediction.query
    try:
        if start_date_str:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            base_query = base_query.filter(Prediction.timestamp >= start_dt)
        if end_date_str:
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            base_query = base_query.filter(Prediction.timestamp < end_dt)
    except Exception:
        pass
    predictions = base_query.order_by(Prediction.timestamp.desc()).all()
    from collections import defaultdict
    predictions_by_date = defaultdict(int)
    today = datetime.now(timezone.utc).date()
    for pred in predictions:
        if not getattr(pred, 'timestamp', None):
            continue
        pred_date = pred.timestamp.date()
        age_days = (today - pred_date).days
        if age_days < 0:
            continue
        if max_age_days is not None and age_days > max_age_days:
            continue
        predictions_by_date[pred_date.isoformat()] += 1
    sorted_dates = sorted(predictions_by_date.keys())
    chart_dates = []
    chart_counts = []
    for date_str in sorted_dates:
        date_obj = datetime.fromisoformat(date_str).date()
        chart_dates.append(date_obj.strftime('%m/%d'))
        chart_counts.append(predictions_by_date[date_str])
    if not chart_dates:
        chart_dates = []
        chart_counts = []
    disease_counts = defaultdict(int)
    for pred in predictions:
        base_label = pred.result.split(' - ')[0] if pred.result else 'Unknown'
        disease_counts[base_label] += 1
    sorted_diseases = sorted(disease_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    disease_names = [d[0] for d in sorted_diseases]
    disease_values = [int(d[1]) for d in sorted_diseases]
    total_predictions = len(predictions)
    today_predictions = sum(1 for pred in predictions if pred.timestamp.date() == today)
    week_predictions = sum(1 for pred in predictions if (today - pred.timestamp.date()).days <= 7)
    month_predictions = sum(1 for pred in predictions if (today - pred.timestamp.date()).days <= 30)
    if download_pdf:
        from flask import Response as FlaskResponse
        from modules.pdf_generator import generate_admin_table_pdf
        rows = []
        for p in predictions:
            rows.append([
                p.id,
                p.user.username if p.user else '',
                p.timestamp.strftime('%Y-%m-%d %H:%M:%S') if p.timestamp else '',
                p.result,
                f"{p.confidence:.2f}",
                p.filename
            ])
        subtitle = f"Date range: {start_date_str or 'Any'} to {end_date_str or 'Any'} | Total: {len(predictions)}"
        pdf_bytes = generate_admin_table_pdf(
            title='Leafora AI - Predictions Report',
            columns=['ID', 'User', 'Timestamp', 'Result', 'Confidence', 'Filename'],
            rows=rows,
            subtitle=subtitle
        )
        if pdf_bytes:
            filename = f"predictions_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            resp = FlaskResponse(pdf_bytes, mimetype='application/pdf')
            resp.headers['Content-Disposition'] = f'attachment; filename={filename}'
            return resp
    if download:
        from flask import Response as FlaskResponse
        import csv, io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'User', 'Timestamp', 'Result', 'Confidence', 'Filename'])
        for p in predictions:
            writer.writerow([p.id, p.user.username if p.user else '', p.timestamp.strftime('%Y-%m-%d %H:%M:%S'), p.result, f"{p.confidence:.2f}", p.filename])
        resp = FlaskResponse(output.getvalue(), mimetype='text/csv')
        resp.headers['Content-Disposition'] = 'attachment; filename=predictions.csv'
        return resp
    return render_template('admin/admin_predictions.html', 
                         predictions=predictions,
                         chart_dates=chart_dates,
                         chart_counts=chart_counts,
                         disease_names=disease_names,
                         disease_values=disease_values,
                         total_predictions=total_predictions,
                         today_predictions=today_predictions,
                         week_predictions=week_predictions,
                         month_predictions=month_predictions,
                         start_date=start_date_str,
                         end_date=end_date_str,
                         time_range=range_key)


@app.route('/admin/predictions/delete/<int:prediction_id>', methods=['POST'])
@admin_required
def admin_delete_prediction(prediction_id):
    """Admin - Delete prediction"""
    prediction = db.session.get(Prediction, prediction_id)
    if not prediction:
        from flask import abort
        abort(404)
    
    # Delete associated file
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], prediction.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    
    db.session.delete(prediction)
    db.session.commit()
    flash('Prediction deleted successfully.', 'success')
    return redirect(url_for('admin_predictions'))


def initialize_app():
    """Initialize database, admin user, and load model with self-healing checks"""
    with app.app_context():
        # Run database migrations first
        try:
            from database.migrate import migrate_database
            migrations_applied = migrate_database()
            
            # Add logging columns to tbl_customers if they don't exist
            try:
                import sqlite3
                from pathlib import Path
                db_path = Path('instance') / 'database.sqlite'
                if not db_path.exists():
                    db_path = Path('database') / 'instance' / 'database.sqlite'
                
                if db_path.exists():
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    
                    # Check if tbl_customers exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tbl_customers'")
                    if cursor.fetchone():
                        # Check and add logging columns
                        cursor.execute("PRAGMA table_info(tbl_customers)")
                        columns = [row[1] for row in cursor.fetchall()]
                        
                        if 'last_login_at' not in columns:
                            cursor.execute("ALTER TABLE tbl_customers ADD COLUMN last_login_at DATETIME NULL")
                            logger.info("✅ Added last_login_at column to tbl_customers")
                        
                        if 'last_logout_at' not in columns:
                            cursor.execute("ALTER TABLE tbl_customers ADD COLUMN last_logout_at DATETIME NULL")
                            logger.info("✅ Added last_logout_at column to tbl_customers")
                        
                        if 'subscription_purchased_at' not in columns:
                            cursor.execute("ALTER TABLE tbl_customers ADD COLUMN subscription_purchased_at DATETIME NULL")
                            logger.info("✅ Added subscription_purchased_at column to tbl_customers")
                    
                    # Fix tbl_models schema if needed - ensure it has 'id' column as primary key
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tbl_models'")
                    if cursor.fetchone():
                        cursor.execute("PRAGMA table_info(tbl_models)")
                        columns = [row[1] for row in cursor.fetchall()]
                        
                        # If table has model_id column but not id, we need to handle it
                        # Model class uses 'id' as primary key, so we'll use a property for compatibility
                        if 'model_id' in columns and 'id' not in columns:
                            logger.info("⚠️ tbl_models uses model_id - Model class uses id (property will map model_id to id)")
                    
                    conn.commit()
                    conn.close()
            except Exception as e:
                logger.warning(f"Could not add logging columns or check model schema: {e}")
            logger.info(f"✅ Database migrations completed: {len(migrations_applied)} applied")
        except Exception as e:
            logger.warning(f"Migration script failed: {e}, continuing with direct schema check...")
        
        # Self-healing: Check and fix database schema
        logger.info("=" * 60)
        logger.info("🔍 Checking database schema...")
        logger.info("=" * 60)
        
        try:
            # Check if migrations folder exists
            migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
            if not os.path.exists(migrations_dir):
                logger.info("📁 Migrations folder not found. Initializing migrations...")
                from flask_migrate import init as migrate_init
                migrate_init()
                logger.info("✅ Migrations folder created")
            
            # Database version check and schema verification
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            DB_VERSION = 3  # Increment when schema changes
            
            if os.path.exists(db_path):
                # Check if predictions table has required columns
                try:
                    from sqlalchemy import inspect, text
                    inspector = inspect(db.engine)
                    
                    # Check database version
                    db_version = 1
                    try:
                        with db.engine.connect() as conn:
                            result = conn.execute(text("SELECT version FROM alembic_version LIMIT 1"))
                            row = result.fetchone()
                            if row:
                                # Try to get version from metadata or use migration number
                                db_version = DB_VERSION  # Assume latest if migrations exist
                    except:
                        pass
                    
                    # Check users table for is_deleted column (support both old and new table names)
                    table_name_users = 'tbl_login' if 'tbl_login' in inspector.get_table_names() else 'users'
                    if table_name_users in inspector.get_table_names():
                        user_columns = [col['name'] for col in inspector.get_columns(table_name_users)]
                        if 'is_deleted' not in user_columns:
                            logger.info(f"🔄 Adding is_deleted column to {table_name_users} table...")
                            try:
                                with db.engine.connect() as conn:
                                    conn.execute(text(f"ALTER TABLE {table_name_users} ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
                                    conn.commit()
                                logger.info(f"✅ Added is_deleted column to {table_name_users} table")
                            except Exception as e:
                                logger.warning(f"Could not add is_deleted column: {e}")
                    
                    # Check predictions table (support both old and new table names)
                    table_name_predictions = 'tbl_predictions' if 'tbl_predictions' in inspector.get_table_names() else 'predictions'
                    if table_name_predictions in inspector.get_table_names():
                        columns = [col['name'] for col in inspector.get_columns(table_name_predictions)]
                        required_columns = ['topk_results', 'models_used', 'is_unknown']
                        missing_columns = [col for col in required_columns if col not in columns]
                        
                        if missing_columns:
                            logger.warning(f"⚠️ Missing columns in {table_name_predictions} table: {missing_columns}")
                            logger.info("🔄 Adding missing columns directly...")
                            try:
                                # Direct SQLite ALTER TABLE (faster than migrations)
                                from sqlalchemy import text
                                with db.engine.connect() as conn:
                                    for col in missing_columns:
                                        if col == 'topk_results':
                                            conn.execute(text(f"ALTER TABLE {table_name_predictions} ADD COLUMN topk_results TEXT DEFAULT '[]'"))
                                        elif col == 'models_used':
                                            conn.execute(text(f"ALTER TABLE {table_name_predictions} ADD COLUMN models_used TEXT DEFAULT '[]'"))
                                        elif col == 'is_unknown':
                                            conn.execute(text(f"ALTER TABLE {table_name_predictions} ADD COLUMN is_unknown INTEGER DEFAULT 0"))
                                    conn.commit()
                                logger.info("✅ Database schema updated")
                            except Exception as e:
                                logger.warning(f"Direct migration failed: {e}. Trying Flask-Migrate...")
                                try:
                                    from flask_migrate import migrate as migrate_migrate, upgrade as migrate_upgrade
                                    migrate_migrate(message="Add missing columns to predictions")
                                    migrate_upgrade()
                                    logger.info("✅ Database schema updated via Flask-Migrate")
                                except Exception as e2:
                                    logger.warning(f"Migration failed: {e2}. Recreating database...")
                                    os.remove(db_path)
                                    db.create_all()
                                    logger.info("✅ Database recreated with correct schema")
                        else:
                            logger.info("✅ Database schema is correct (version check passed)")
                    else:
                        logger.info("📊 Creating database tables...")
                        db.create_all()
                except Exception as e:
                    logger.warning(f"Schema check failed: {e}. Recreating database...")
                    if os.path.exists(db_path):
                        os.remove(db_path)
                    db.create_all()
                    logger.info("✅ Database recreated")
            else:
                logger.info("📊 Creating new database...")
                db.create_all()
            
            # Check if we need to migrate table names (old -> new)
            try:
                from sqlalchemy import inspect, text
                inspector = inspect(db.engine)
                existing_tables = inspector.get_table_names()
                
                # Check if old table names exist but new ones don't
                needs_migration = False
                if 'users' in existing_tables and 'tbl_login' not in existing_tables:
                    needs_migration = True
                    logger.info("🔄 Detected old table names. Migrating to new naming convention...")
                    
                    # Rename tables
                    table_mappings = {
                        'users': 'tbl_login',
                        'predictions': 'tbl_predictions',
                        'payments': 'tbl_payments',
                        'usage_counters': 'tbl_usage_counters',
                        'models': 'tbl_models'
                    }
                    
                    with db.engine.connect() as conn:
                        for old_name, new_name in table_mappings.items():
                            if old_name in existing_tables and new_name not in existing_tables:
                                logger.info(f"   Renaming: {old_name} -> {new_name}")
                                conn.execute(text(f"ALTER TABLE {old_name} RENAME TO {new_name}"))
                        conn.commit()
                    logger.info("✅ Table names migrated successfully!")

                # Migrate plural table names to singular to match configuration
                try:
                    singular_mappings = {
                        'tbl_customers': 'tbl_customer',
                        'tbl_predictions': 'tbl_prediction',
                        'tbl_notifications': 'tbl_notification'
                    }
                    with db.engine.connect() as conn:
                        for old_name, new_name in singular_mappings.items():
                            if old_name in existing_tables and new_name not in existing_tables:
                                logger.info(f"   Renaming: {old_name} -> {new_name}")
                                conn.execute(text(f"ALTER TABLE {old_name} RENAME TO {new_name}"))
                        conn.commit()
                    logger.info("✅ Plural-to-singular table names migrated successfully!")
                except Exception as e2:
                    logger.warning(f"Plural-to-singular table migration failed: {e2}")
            except Exception as e:
                logger.warning(f"Table name migration check failed: {e}")

            # Ensure required columns exist on critical tables (SQLite ALTER TABLE)
            try:
                from sqlalchemy import text, inspect
                inspector = inspect(db.engine)
                # tbl_payment: expires_at
                if 'tbl_payment' in inspector.get_table_names():
                    cols = [c['name'] for c in inspector.get_columns('tbl_payment')]
                    if 'expires_at' not in cols:
                        logger.info("🔧 Adding missing column tbl_payment.expires_at")
                        with db.engine.connect() as conn:
                            conn.execute(text("ALTER TABLE tbl_payment ADD COLUMN expires_at DATETIME"))
                            conn.commit()
                        logger.info("✅ Added tbl_payment.expires_at")
                # tbl_customer: email, password_hash
                if 'tbl_customer' in inspector.get_table_names():
                    cols = [c['name'] for c in inspector.get_columns('tbl_customer')]
                    with db.engine.connect() as conn:
                        if 'email' not in cols:
                            logger.info("🔧 Adding missing column tbl_customer.email")
                            conn.execute(text("ALTER TABLE tbl_customer ADD COLUMN email VARCHAR(120) NOT NULL DEFAULT ''"))
                            logger.info("✅ Added tbl_customer.email")
                        if 'password_hash' not in cols:
                            logger.info("🔧 Adding missing column tbl_customer.password_hash")
                            conn.execute(text("ALTER TABLE tbl_customer ADD COLUMN password_hash VARCHAR(255) NOT NULL DEFAULT ''"))
                            logger.info("✅ Added tbl_customer.password_hash")
                        # Backfill from tbl_login
                        try:
                            logger.info("↻ Backfilling tbl_customer email/password_hash from tbl_login")
                            conn.execute(text(
                                """
                                UPDATE tbl_customer
                                SET email = (
                                    SELECT email FROM tbl_login WHERE tbl_login.id = tbl_customer.customer_id
                                ),
                                password_hash = (
                                    SELECT password_hash FROM tbl_login WHERE tbl_login.id = tbl_customer.customer_id
                                )
                                WHERE customer_id IN (SELECT id FROM tbl_login)
                                """
                            ))
                            conn.commit()
                            logger.info("✅ Backfill complete")
                        except Exception as e2:
                            logger.warning(f"Backfill failed: {e2}")
            except Exception as e:
                logger.warning(f"Column migration failed: {e}")
            
            # Create admin user if it doesn't exist
            admin_email = 'admin@admin.com'
            try:
                admin = User.query.filter_by(email=admin_email).first()
            except Exception as e:
                # If table doesn't exist yet, create it
                logger.warning(f"User table query failed: {e}. Creating tables...")
                db.create_all()
                admin = None
            
            if not admin:
                admin = User(
                    username='admin',
                    email=admin_email,
                    password_hash=generate_password_hash('admin123')
                )
                db.session.add(admin)
                db.session.flush()  # Get admin.id
                
                # Create customer record for admin
                admin_customer = Customer(
                    customer_id=admin.id,
                    is_admin=True,
                    is_pro=1,  # Admin gets Pro by default
                    is_deleted=False,
                    created_at=datetime.now(timezone.utc)
                )
                db.session.add(admin_customer)
                db.session.commit()
                logger.info("✅ Admin user created: admin@admin.com / admin123")
            else:
                # Ensure admin has customer record
                if not admin.customer:
                    admin_customer = Customer(
                        customer_id=admin.id,
                        is_admin=True,
                        is_pro=1,
                        is_deleted=False,
                        created_at=datetime.now(timezone.utc)
                    )
                    db.session.add(admin_customer)
                    db.session.commit()
                # Ensure admin password is set to admin123
                try:
                    admin.password_hash = generate_password_hash('admin123')
                    db.session.commit()
                    logger.info("✅ Admin password updated to admin123")
                except Exception as e:
                    logger.warning(f"Could not update admin password: {e}")
                logger.info("✅ Admin user already exists")
                
        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}")
            logger.info("🔄 Attempting to recreate database...")
            try:
                db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
                if os.path.exists(db_path):
                    db.session.remove()
                    db.engine.dispose()
                    os.remove(db_path)
                db.create_all()
                # Recreate admin
                admin = User(
                    username='admin',
                    email='admin@admin.com',
                    password_hash=generate_password_hash('admin123')
                )
                db.session.add(admin)
                db.session.commit()
                logger.info("✅ Database recreated successfully")
            except Exception as e2:
                logger.error(f"❌ Failed to recreate database: {e2}")
                raise
        
        # Self-healing: Check model directory and label_map.json
        logger.info("=" * 60)
        logger.info("🔍 Checking model directory...")
        logger.info("=" * 60)
        
        model_dir = app.config['MODEL_PATH']
        if not os.path.exists(model_dir):
            os.makedirs(model_dir, exist_ok=True)
            logger.info(f"✅ Created model directory: {model_dir}")
        
        # Model selection is now automatic (largest file)
        # Check if model directory exists
        if os.path.exists(model_dir):
            model_files = [f for f in os.listdir(model_dir) if f.endswith(('.keras', '.h5')) and not f.endswith('.crdownload')]
            if model_files:
                logger.info(f"✅ Found {len(model_files)} model file(s) in {model_dir}/")
            else:
                logger.warning("⚠️ No model files found. Will attempt to load during startup.")
        else:
            logger.warning(f"⚠️ Model directory not found: {model_dir}")
        
        # Check label_map.json
        label_map_path = app.config.get('LABEL_MAP_PATH', os.path.join(model_dir, 'label_map.json'))
        if os.path.exists(label_map_path):
            logger.info(f"✅ Found label_map.json")
        else:
            logger.warning("⚠️ label_map.json not found. Will be auto-generated if needed.")
        
        # Load models at startup using predict module
        # This MUST succeed - raise error if it fails
        try:
            logger.info("=" * 60)
            logger.info("🚀 Initializing Leafora AI Model System")
            logger.info("=" * 60)
            
            # Load all models
            try:
                # models = predict.load_all_models()
                models = []
                import threading
                def _bg_loader():
                    with app.app_context():
                        try:
                            logger.info("⏳ Starting background model loading...")
                            _loaded = predict.load_all_models()
                            logger.info(f"✅ Background model loading complete: {len(_loaded)} models")
                        except Exception as e:
                            logger.error(f"❌ Background loading failed: {e}")
                threading.Thread(target=_bg_loader, daemon=True).start()
                logger.info("ℹ️ Model loading deferred to background thread")
                # logger.info("Skipping model loading for UI demo speedup")
                # models = []
                
                # Store model metadata in database
                for model_info in models:
                    try:
                        # Rollback any previous failed transaction
                        db.session.rollback()
                        
                        # Query using id as primary key (matches existing DB schema)
                        existing = Model.query.filter_by(filename=model_info['name']).first()
                    except Exception as query_error:
                        # If query fails due to schema mismatch, try raw SQL
                        logger.warning(f"Query failed: {query_error}")
                        db.session.rollback()  # Rollback before retry
                        try:
                            from sqlalchemy import text
                            result = db.session.execute(
                                text("SELECT id, filename, name, size_bytes, backend, classes, loaded FROM tbl_models WHERE filename = :filename LIMIT 1"),
                                {"filename": model_info['name']}
                            ).first()
                            # If we got a result from raw SQL, fetch the actual Model object by ID
                            if result:
                                model_id = result[0]  # First column is id
                                existing = Model.query.get(model_id)
                            else:
                                existing = None
                        except Exception as e2:
                            logger.warning(f"Raw SQL query also failed: {e2}")
                            db.session.rollback()
                            existing = None
                    
                    try:
                        if not existing:
                            # Create model record - use id as primary key (matches existing DB schema)
                            # Note: Do NOT include model_name - it's not a database column
                            model_record = Model(
                                name=model_info['name'],  # Use name field (matches DB schema)
                                filename=model_info['name'],
                                size_bytes=model_info.get('size_bytes', int(model_info.get('size_mb', 0) * 1024 * 1024)),
                                backend='tf',
                                classes=model_info.get('num_classes', len(model_info.get('classes', []))),
                                loaded=True
                            )
                            db.session.add(model_record)
                            db.session.commit()
                        else:
                            # Update existing model record (existing is now a Model object, not a Row)
                            existing.loaded = True
                            existing.classes = model_info.get('num_classes', len(model_info.get('classes', [])))
                            # Also update name if it's different
                            if existing.name != model_info['name']:
                                existing.name = model_info['name']
                            db.session.commit()
                    except Exception as save_error:
                        logger.warning(f"Failed to save model record for {model_info['name']}: {save_error}")
                        db.session.rollback()
                        continue  # Skip this model and continue with next
                
                logger.info("=" * 60)
                logger.info(f"✅ Models loaded successfully!")
                logger.info(f"   Models: {len(models)}")
                if models:
                    model_names = [m['name'] for m in models]
                    model_sizes = [f"{m['name']} ({m.get('size_mb', 0):.1f}MB)" for m in models]
                    logger.info(f"   Using models: {', '.join(model_sizes)}")
                    first_model = models[0]
                    num_classes = first_model.get('num_classes') or len(first_model.get('classes', []))
                    logger.info(f"   Classes: {num_classes}")
                logger.info("=" * 60)
                
                # Verify label_map.json matches model (if we have models)
                if models and os.path.exists(label_map_path):
                    try:
                        with open(label_map_path, 'r', encoding='utf-8') as f:
                            label_data = json.load(f)
                        if isinstance(label_data, dict):
                            label_count = len(label_data)
                        elif isinstance(label_data, list):
                            label_count = len(label_data)
                        else:
                            label_count = 0
                        
                        first_model = models[0]
                        model_classes_count = first_model.get('num_classes') or len(first_model.get('classes', []))
                        if label_count != model_classes_count:
                            logger.warning(f"⚠️ Label count mismatch: {label_count} in file vs {model_classes_count} in model")
                            logger.info("   Label map will be regenerated to match model")
                    except Exception as e:
                        logger.warning(f"Error checking label map: {e}")
            except Exception as load_error:
                logger.error(f"❌ Critical Error loading models: {load_error}")
                # Continue without models - do not crash
                models = []
            
            logger.info("=" * 60)
            logger.info("🌐 Flask server ready at http://127.0.0.1:5000")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"❌ CRITICAL: Model loading failed: {e}")
            logger.error("💡 The application cannot run without a model.")
            logger.error("   Please ensure at least one .keras or .h5 file exists in model/ directory.")
            logger.error("   The app will automatically select the largest model file.")
            logger.error("=" * 60)
            raise


@app.route('/result/<int:prediction_id>')
@login_required
@member_only
def result(prediction_id):
    """View individual prediction result"""
    user = db.session.get(User, session['user_id'])
    
    # Verify ownership
    cust_id = user.customer.customer_id if user and user.customer else None
    if not cust_id:
        flash('Customer record not found.', 'danger')
        return redirect(url_for('dashboard'))
        
    prediction = Prediction.query.filter_by(id=prediction_id, cust_id=cust_id).first()
    
    if not prediction:
        flash('Prediction not found or access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    image = url_for('static', filename=f'uploads/{prediction.filename}')
    info = DISEASE_DETAILS.get(prediction.result, "Continue monitoring your plant for any changes.")
    
    try:
        topk = json.loads(prediction.topk_results) if prediction.topk_results else []
        models_used = json.loads(prediction.models_used) if prediction.models_used else []
    except (json.JSONDecodeError, TypeError):
        topk = []
        models_used = []
        
    if not isinstance(models_used, list):
        models_used = [str(models_used)]
    
    if models_used and isinstance(models_used[0], dict):
         model_used_str = 'ensemble' if len(models_used) > 1 else models_used[0].get('name', 'unknown')
    else:
         model_used_str = 'ensemble' if len(models_used) > 1 else (models_used[0] if models_used else 'unknown')
    
    label_lower = str(prediction.result or '').strip().lower()
    is_non_plant = ('not a plant' in label_lower) or ('no plant leaf' in label_lower)
    non_leaf_confidence = float(prediction.confidence) if is_non_plant else None
    kindwise_results = []
    disease_spots = []

    if is_non_plant:
        topk = []
        disease_recommendations = []
        disease_profile = None
        disease_description = None
    else:
        disease_recommendations = build_disease_recommendations(topk, prediction.result)
        disease_profile = build_disease_profile(prediction.result, confidence=prediction.confidence)
        disease_description = build_disease_description(prediction.result, confidence=prediction.confidence)

    return render_template('user/result.html',
                           label=prediction.result,
                           confidence=prediction.confidence,
                           image=image,
                           info=info,
                           topk=topk,
                           disease_description=disease_description,
                           disease_profile=disease_profile,
                           disease_recommendations=disease_recommendations,
                           models_used=models_used,
                           model_used=model_used_str,
                           is_unknown=prediction.is_unknown,
                           prediction_id=prediction.id,
                           filename=prediction.filename,
                           is_pro=user.is_pro_active(),
                           all_models=[], 
                           ensemble_top=[], 
                           per_model=[],
                           confidence_message=None,
                           upgrade_prompt=None,
                           rice_enabled=False,
                           kindwise_results=kindwise_results,
                           disease_spots=disease_spots,
                           is_non_plant=is_non_plant,
                           non_leaf_confidence=non_leaf_confidence
                           )


@app.route('/reprocess', methods=['POST'])
@login_required
@member_only
def reprocess():
    """Re-run prediction on an already uploaded image with options (e.g., rice toggle)"""
    user = db.session.get(User, session['user_id'])
    filename = request.form.get('filename', '').strip()
    rice_enabled_flag = request.form.get('rice_enabled')
    rice_enabled = _as_form_bool(rice_enabled_flag)
    
    if not filename:
        flash('Missing image reference for reprocessing.', 'danger')
        return redirect(url_for('upload'))
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        flash('Image file not found for reprocessing.', 'danger')
        return redirect(url_for('upload'))
    
    try:
        use_all_models = True
        use_ensemble = False
        beta_enabled = bool(session.get('beta_enabled', False)) and user.is_pro_active()
        result = predict.predict_topk(
            filepath,
            k=predict.TOP_K,
            use_all_models=use_all_models,
            use_ensemble=use_ensemble,
            enable_rice_models=rice_enabled,
            disable_best_model=(not beta_enabled)
        )

        # Streamlit-style gate: non-leaf should not continue to disease report.
        non_leaf_conf = result.get('non_leaf_confidence')
        if non_leaf_conf is None and result.get('detector_score') is not None:
            non_leaf_conf = round(100.0 - float(result.get('detector_score')), 2)
        detector_non_leaf = (
            ('best_plant_detector.keras' in str(result.get('model_used', '')).lower() and bool(result.get('unknown')))
            or (
                non_leaf_conf is not None
                and bool(result.get('unknown'))
                and len(result.get('all_models') or []) == 0
                and (result.get('topk') or [{}])[0].get('label', '').lower() == 'unknown'
            )
        )
        if detector_non_leaf:
            flash(
                f'Not a leaf image (confidence: {non_leaf_conf}%). Please upload a clear leaf image.'
                if non_leaf_conf is not None
                else 'Not a leaf image. Please upload a clear leaf image.',
                'warning'
            )
            return redirect(url_for('upload'))
        
        from modules.plant_detector import detect_plant_type, filter_predictions_by_plant
        detected_plant = detect_plant_type(result['topk'])
        if detected_plant:
            logger.info(f"Detected plant type during reprocess: {detected_plant}")
        
        top1 = result['topk'][0] if result['topk'] else None
        if not top1:
            raise ValueError('No valid predictions available')
        label = top1['label']
        confidence = top1.get('confidence', round(top1.get('prob', 0.0) * 100, 2))
        image = url_for('static', filename=f'uploads/{filename}')
        
        models_used_list = []
        if 'per_model' in result:
            # Capture full details: name, confidence, top_label from ensemble per-model results
            for m in result['per_model']:
                entry = {
                    'name': m['model'],
                    'conf': float(m.get('top_prob', 0.0)) * 100,
                    'label': m.get('top_label', 'Unknown')
                }
                models_used_list.append(entry)
        elif 'all_models' in result:
            # Pass full model results including model_source and topk
            models_used_list = result['all_models']
        else:
            models_used_list = [{'name': result.get('model_used', 'unknown'), 'conf': confidence, 'label': label}]
        
        info = DISEASE_DETAILS.get(label, "Continue monitoring your plant for any changes.")
        all_models_results = result.get('all_models', [])
        ensemble_top = result.get('ensemble_top', [])
        per_model = result.get('per_model', [])
        kindwise_results = []

        # Keep visual disease spots consistent with the upload flow.
        try:
            disease_spots = getattr(predict, "detect_disease_spots", lambda p, max_boxes=8: [])(filepath, max_boxes=8)
        except Exception as _ds_err:
            logger.warning(f"disease spot detection failed during reprocess: {_ds_err}")
            disease_spots = []

        disease_recommendations = build_disease_recommendations(result['topk'], label)
        disease_profile = build_disease_profile(label, confidence=confidence)
        disease_description = build_disease_description(label, confidence=confidence)

        if len(models_used_list) > 1:
            model_used_value = 'ensemble'
        elif models_used_list:
            single_model = models_used_list[0]
            if isinstance(single_model, dict):
                model_used_value = (
                    single_model.get('model_source')
                    or single_model.get('model_name')
                    or single_model.get('name')
                    or 'unknown'
                )
            else:
                model_used_value = str(single_model)
        else:
            model_used_value = result.get('model_used', 'unknown')

        # Save updated prediction
        is_unknown = label.lower() == 'unknown'
        
        prediction = Prediction(
            cust_id=user.customer.customer_id,
            filename=filename,
            result=label,
            confidence=confidence,
            is_correct=False, # Reset verification
            timestamp=datetime.now(timezone.utc),
            topk_results=json.dumps(result['topk']),
            models_used=json.dumps(models_used_list),
            is_unknown=is_unknown
        )
        db.session.add(prediction)
        
        # Update Usage
        counter = UsageCounter.query.filter_by(cust_id=user.id).first()
        if not counter:
            counter = UsageCounter(cust_id=user.id, total_predictions=0)
            db.session.add(counter)
        counter.total_predictions += 1
        counter.last_prediction_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return render_template('user/result.html',
                           label=label,
                           confidence=confidence,
                           image=image,
                           info=info,
                           topk=result['topk'],
                           disease_description=disease_description,
                           disease_profile=disease_profile,
                           disease_recommendations=disease_recommendations,
                           models_used=models_used_list,
                           model_used=model_used_value,
                           is_unknown=is_unknown,
                           prediction_id=prediction.id,
                           filename=filename,
                           is_pro=user.is_pro_active(),
                           all_models=all_models_results,
                           ensemble_top=ensemble_top,
                           per_model=per_model,
                           kindwise_results=kindwise_results,
                           confidence_message=None,
                           upgrade_prompt=None,
                           rice_enabled=rice_enabled,
                           disease_spots=disease_spots,
                           is_non_plant=False,
                           non_leaf_confidence=None
                           )

    except Exception as e:
        logger.error(f"Error reprocessing image: {e}")
        flash(f'Error analyzing image: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/demo-animations')
def demo_animations():
    """Demo page for animations"""
    return render_template('demo_animations.html')


@app.errorhandler(OperationalError)
def handle_operational_error(e):
    """Gracefully handle transient database operational failures."""
    logger.error(f"Database OperationalError: {e}")
    if _is_sqlite_disk_io_error(e):
        _reset_db_connection()
        try:
            flash('Database is temporarily unavailable. Please try again in a few seconds.', 'danger')
        except Exception:
            pass
        if request.endpoint == 'register':
            return render_template('auth/register.html'), 503
        if request.endpoint == 'login':
            return render_template('auth/login.html'), 503
        return "Database is temporarily unavailable. Please retry.", 503
    return "Database operation failed.", 500


@app.errorhandler(500)
def handle_500(e):
    logger.error(f"Internal Server Error: {e}")
    logger.error(traceback.format_exc())
    return "Internal Server Error (Logged)", 500

if __name__ == '__main__':
    print("DEBUG: Starting app.py __main__")
    import sys
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['MODEL_PATH'], exist_ok=True)
    os.makedirs('instance', exist_ok=True)
    print("DEBUG: Directories created")
    try:
        initialize_app()
        print("DEBUG: App initialized")
    except Exception as e:
        print(f"DEBUG: Initialization failed: {e}")
    
    if '--clear-db' in sys.argv:
        try:
            _clear_all_data_and_recreate_admin()
        except Exception:
            pass
        import sys as _sys
        _sys.exit(0)
    print("DEBUG: Starting app.run")
    try:
        app.run(debug=True, host='127.0.0.1', port=5001, use_reloader=False)
    except Exception as e:
        print(f"DEBUG: app.run failed: {e}")
    print("DEBUG: app.run returned")
