"""
Configuration file for Leafora AI Flask Application
"""
import os

# Base directory
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Application configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'leafora-ai-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'database.sqlite')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload settings
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
    
    # Model settings
    MODEL_PATH = os.path.join(basedir, 'm_models')  # Directory containing model files
    LABEL_MAP_PATH = os.path.join(basedir, 'm_models', 'label_map.json')
    IMAGE_SIZE = (224, 224)  # MobileNetV2/ViT standard: 224x224 images
    
    # API Keys
    KINDWISE_CROP_API_KEY = os.environ.get('KINDWISE_CROP_API_KEY') or 'QXqAt2e7id3VPhzjUKLCOF1bhdvgQNlthNeXY9baQtbdAhquUA'

