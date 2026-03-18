"""
Leafora AI - Model Prediction Module
Handles model loading from local files ONLY, preprocessing, and predictions
Automatically selects the largest .keras or .h5 model file
"""
print("DEBUG: predict.py loading...")
import os
print("DEBUG: predict - os imported")
import json
print("DEBUG: predict - json imported")
import logging
print("DEBUG: predict - logging imported")
import traceback
from pathlib import Path
from PIL import Image, ImageOps, ImageFile
print("DEBUG: predict - PIL imported")
import collections
try:
    print("DEBUG: predict - attempting numpy import")
    import numpy as np
    print("DEBUG: predict - numpy imported")
except Exception as e:
    print(f"DEBUG: predict - numpy failed: {e}")
    raise e

# Import tensorflow only when needed to prevent startup hang
tf = None

from download_model import download_model

def get_tf():
    global tf
    if tf is None:
        try:
            import tensorflow as tf
        except ImportError:
            pass
    return tf

try:
    print("DEBUG: predict - attempting requests import")
    import requests
    print("DEBUG: predict - requests imported")
except Exception as e:
    print(f"DEBUG: predict - requests failed: {e}")
    raise e
print("DEBUG: predict - base64 imported")
try:
    print("DEBUG: predict - attempting cv2 import")
    import cv2
    print("DEBUG: predict - cv2 imported")
except Exception as e:
    print(f"DEBUG: predict - cv2 failed: {e}")
    raise e
try:
    print("DEBUG: predict - attempting base64 import")
    import base64
    print("DEBUG: predict - base64 imported")
except Exception as e:
    print(f"DEBUG: predict - base64 failed: {e}")
    raise e

try:
    print("DEBUG: predict - attempting torch import")
    import torch
    print("DEBUG: predict - torch imported")
    import torch.nn as nn
    from torchvision import transforms, models
    print("DEBUG: predict - torchvision imported")
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("Warning: torch/torchvision not available. PyTorch models will be skipped.")
print("DEBUG: predict - torch check done")

try:
    print("DEBUG: predict - attempting transformers import")
    from transformers import AutoConfig, AutoImageProcessor, AutoModelForImageClassification
    TRANSFORMERS_AVAILABLE = True
    print("DEBUG: predict - transformers imported")
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("Warning: transformers not available. HuggingFace directory models will be skipped.")

# Suppress TensorFlow warnings - Maximum suppression
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress all TF logs (ERROR, WARNING, INFO)
os.environ['KERAS_BACKEND'] = 'tensorflow'
os.environ['KERAS_ALLOW_UNSAFE_DESERIALIZATION'] = '1'  # Enable by default for incompatible models

# Suppress ALL warnings comprehensively
import warnings
warnings.filterwarnings('ignore')  # Ignore all warnings
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', module='tensorflow')
warnings.filterwarnings('ignore', module='keras')
warnings.filterwarnings('ignore', message='.*Lambda.*')
warnings.filterwarnings('ignore', message='.*unsafe.*')
warnings.filterwarnings('ignore', message='.*input_shape.*input_dim.*')
warnings.filterwarnings('ignore', message='.*Do not pass an.*input_shape.*')
warnings.filterwarnings('ignore', message='.*deserialization.*')
warnings.filterwarnings('ignore', message='.*compatibility.*')
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s',
    force=True  # Force re-configuration to ensure encoding/handlers are correct if needed
)
# Note: Root logger is configured in app.py with FileHandler(utf-8). 
# We don't need to add another one here, but we ensure basic config is set.
logger = logging.getLogger(__name__)

# --- MONKEYPATCH FOR KERAS 3 COMPATIBILITY ---
def patch_keras_deserialization():
    """
    Monkey-patch Keras deserialization to clean legacy arguments from config.
    This intercepts the config dictionary BEFORE the layer is instantiated.
    """
    try:
        import keras.saving
        
        targets = []
        if hasattr(keras.saving, 'deserialize_keras_object'):
            targets.append((keras.saving, 'deserialize_keras_object'))
        
        try:
            from keras.src.saving import serialization
            if hasattr(serialization, 'deserialize_keras_object'):
                targets.append((serialization, 'deserialize_keras_object'))
        except ImportError:
            pass

        for module, func_name in targets:
            OriginalDeserialize = getattr(module, func_name)
            
            if getattr(OriginalDeserialize, '_is_robust_patch', False):
                continue
                
            def robust_deserialize(config, custom_objects=None, safe_mode=True, **kwargs):
                def clean_config(cfg_wrapper):
                    if isinstance(cfg_wrapper, dict) and 'config' in cfg_wrapper:
                        class_name = cfg_wrapper.get('class_name')
                        cfg = cfg_wrapper['config']
                        
                        if isinstance(cfg, dict):
                            # Fix InputLayer: 'batch_input_shape' -> 'batch_shape', 'input_shape' -> 'shape'
                            if class_name == 'InputLayer':
                                if 'batch_input_shape' in cfg:
                                    cfg['batch_shape'] = cfg.pop('batch_input_shape')
                                if 'input_shape' in cfg:
                                    cfg['shape'] = cfg.pop('input_shape')
                            
                            # Fix RandomRotation: remove 'value_range'
                            if class_name == 'RandomRotation':
                                cfg.pop('value_range', None)
                            
                            # Generic cleanup for all layers
                            keys_to_remove = [
                                'batch_input_shape', 'input_shape', 'batch_shape', 
                                'dim_ordering', 'nb_filter', 'nb_row', 'nb_col', 
                                'value_range', 'dtype' 
                            ]
                            for key in keys_to_remove:
                                # Don't remove 'dtype' from everything, only if it causes issues or specific layers
                                if key == 'dtype':
                                    pass
                                else:
                                    cfg.pop(key, None)
                                
                            if 'layers' in cfg and isinstance(cfg['layers'], list):
                                for layer in cfg['layers']:
                                    clean_config(layer)
                            
                clean_config(config)
                return OriginalDeserialize(config, custom_objects, safe_mode, **kwargs)
            
            robust_deserialize._is_robust_patch = True
            setattr(module, func_name, robust_deserialize)
            
        logger.info(f"Monkey-patched deserialize_keras_object in {len(targets)} locations")
        
    except Exception as e:
        logger.warning(f"Failed to patch deserialization: {e}")

def init_keras_patches():
    try:
        import keras.initializers
        
        # Patch GlorotUniform to accept 'dtype'
        if hasattr(keras.initializers, 'GlorotUniform'):
            original_glorot = keras.initializers.GlorotUniform
            class PatchedGlorotUniform(original_glorot):
                def __init__(self, seed=None, dtype=None, **kwargs):
                    super().__init__(seed=seed)
            keras.initializers.GlorotUniform = PatchedGlorotUniform
            if hasattr(keras.initializers, 'glorot_uniform'):
                 keras.initializers.glorot_uniform = PatchedGlorotUniform

        # Patch Zeros to accept 'dtype'
        if hasattr(keras.initializers, 'Zeros'):
            original_zeros = keras.initializers.Zeros
            class PatchedZeros(original_zeros):
                def __init__(self, dtype=None, **kwargs):
                    super().__init__()
            keras.initializers.Zeros = PatchedZeros
            if hasattr(keras.initializers, 'zeros'):
                 keras.initializers.zeros = PatchedZeros

        # Patch Layers to ignore legacy kwargs
        import keras.layers
        LAYERS_TO_PATCH = [
            'Conv2D', 'Dense', 'MaxPooling2D', 'Flatten', 'Dropout', 
            'BatchNormalization', 'Rescaling', 'Resizing',
            'GlobalAveragePooling2D', 'AveragePooling2D', 'SeparableConv2D',
            'DepthwiseConv2D', 'Activation', 'Concatenate', 'Add', 'Multiply',
            'ZeroPadding2D', 'UpSampling2D', 'LeakyReLU', 'ELU', 'ThresholdedReLU',
            'Softmax', 'ReLU', 'Lambda', 'RandomRotation', 'RandomFlip', 
            'RandomZoom', 'RandomContrast', 'RandomTranslation'
        ]
        # InputLayer removed from list to avoid "must pass shape" error, handled in deserialization patch
        
        for layer_name in LAYERS_TO_PATCH:
            if hasattr(keras.layers, layer_name):
                OriginalLayer = getattr(keras.layers, layer_name)
                class PatchedLayer(OriginalLayer):
                    def __init__(self, *args, **kwargs):
                        # Remove arguments that Keras 3+ doesn't like in __init__
                        kwargs.pop('batch_input_shape', None)
                        kwargs.pop('input_shape', None)
                        kwargs.pop('value_range', None)
                        super().__init__(*args, **kwargs)
                setattr(keras.layers, layer_name, PatchedLayer)
                
        # Apply the deep deserialization patch
        patch_keras_deserialization()
                
        logger.info("Applied Keras 3 compatibility patches for Initializers, Layers, and Deserialization")
    except Exception as e:
        logger.warning(f"Failed to apply Keras patches: {e}")
# ---------------------------------------------

# Global model cache - loads ALL working models ONCE, cached forever
_MODEL_CACHE = {
    'models': [],
    'loaded': False
}

# Configuration
# Get project root directory (where this script is located)
# Use __file__ to get the directory containing predict.py
_script_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = _script_dir
MODEL_DIR = os.getenv("MODEL_DIR", os.path.join(PROJECT_ROOT, "main_models"))
M_MODELS_DIR = os.path.join(PROJECT_ROOT, "m_models")
DETECTION_MODELS_DIR = os.path.join(PROJECT_ROOT, "detection")
DETECTION_ONLY_MODE = os.getenv("DETECTION_ONLY_MODE", "1").strip() != "0"
LABEL_MAP_PATH = os.path.join(MODEL_DIR, "label_map.json")
TOP_K = 5
FINAL_MODELS_DIR = os.path.join(PROJECT_ROOT, "models", "final_models")
_FINAL_CACHE = {
    'loaded': False,
    'plant_model': None,
    'plant_classes': None,
    'plant_threshold': 0.5,
    'disease_models': {}
}
_DETECTION_PLANT_MODEL_CACHE = {
    'loaded': False,
    'model': None
}
_PREMIUM_MODEL_CACHE = {
    'loaded': False,
    'model': None
}


def _load_premium_model():
    if _PREMIUM_MODEL_CACHE['loaded']:
        return _PREMIUM_MODEL_CACHE['model']
    model_path = os.path.join(DETECTION_MODELS_DIR, "premium.keras")
    
    # Auto-download if missing
    if not os.path.exists(model_path):
        logger.info(f"premium.keras missing, attempting download...")
        download_model(model_path)

    if not os.path.exists(model_path):
        logger.warning("premium.keras model not found in detection directory")
        _PREMIUM_MODEL_CACHE['loaded'] = True
        _PREMIUM_MODEL_CACHE['model'] = None
        return None
    try:
        tf = get_tf()
        if not tf:
            raise ImportError("TensorFlow not available")
        init_keras_patches()
        model = tf.keras.models.load_model(model_path, compile=False)
        _PREMIUM_MODEL_CACHE['model'] = model
    except Exception as e:
        logger.error(f"Failed to load premium.keras model: {e}")
        _PREMIUM_MODEL_CACHE['model'] = None
    _PREMIUM_MODEL_CACHE['loaded'] = True
    return _PREMIUM_MODEL_CACHE['model']


def classify_premium_health(image_path):
    model = _load_premium_model()
    if model is None:
        return None
    img_array = preprocess_image(image_path, target_size=(224, 224))
    try:
        preds = model.predict(img_array, verbose=0)
    except Exception as e:
        logger.error(f"premium.keras prediction failed: {e}")
        return None
    if preds is None:
        return None
    preds = preds[0]
    try:
        import numpy as np
        preds = np.array(preds).astype(float).flatten()
        if preds.size == 0:
            return None
        if preds.size == 1:
            unhealthy_prob = float(preds[0])
        else:
            unhealthy_prob = float(preds[1])
        if unhealthy_prob < 0:
            unhealthy_prob = 0.0
        if unhealthy_prob > 1:
            unhealthy_prob = unhealthy_prob / 100.0
    except Exception:
        return None
    confidence_pct = round(unhealthy_prob * 100.0, 2)
    is_unhealthy = confidence_pct >= 74.0
    return {
        "confidence": confidence_pct,
        "is_unhealthy": bool(is_unhealthy)
    }


def load_label_map():
    """Load label map from JSON file"""
    try:
        if os.path.exists(LABEL_MAP_PATH):
            with open(LABEL_MAP_PATH, "r", encoding="utf-8") as f:
                label_map = json.load(f)
            # Handle {"Class_0": 0, ...} format
            if isinstance(label_map, dict):
                # Check if values are integers (index mapping)
                if all(isinstance(v, int) for v in label_map.values()):
                    # Sort by value and get keys
                    sorted_labels = sorted(label_map.items(), key=lambda item: item[1])
                    return [k for k, v in sorted_labels]
                return list(label_map.keys())
            elif isinstance(label_map, list):
                return label_map
    except Exception as e:
        logger.warning(f"Failed to load label_map.json: {e}")
    return None


def _is_hf_model_dir(dir_path):
    """Return True when a directory looks like a local HF image-classification model."""
    try:
        p = Path(dir_path)
        if not p.exists() or not p.is_dir():
            return False
        has_config = (p / "config.json").exists()
        has_preproc = (p / "preprocessor_config.json").exists()
        has_weights = (p / "model.safetensors").exists() or (p / "pytorch_model.bin").exists()
        return bool(has_config and has_preproc and has_weights)
    except Exception:
        return False


def _get_hf_model_size_bytes(dir_path):
    """Estimate size from known HF weight files."""
    total = 0
    try:
        p = Path(dir_path)
        for name in ("model.safetensors", "pytorch_model.bin"):
            wf = p / name
            if wf.exists() and wf.is_file():
                total += wf.stat().st_size
    except Exception:
        return 0
    return total


def find_local_models(model_dir=None):
    """
    Auto-discover models in model/ directory, m_models, and root.
    Prefers .keras format first, then .h5. Prefers largest model when selecting single-model mode.
    Returns sorted list of models by extension priority and size.
    """
    search_dirs = []
    if model_dir:
         search_dirs.append(Path(model_dir))
    elif DETECTION_ONLY_MODE:
         # Strict mode: use detection folder models + explicit fast models in m_models.
         search_dirs.append(Path(DETECTION_MODELS_DIR))
         search_dirs.append(Path(M_MODELS_DIR))
    else:
         # Prefer m_models over main_models
         search_dirs.append(Path(M_MODELS_DIR))
         search_dirs.append(Path(MODEL_DIR))
         search_dirs.append(Path(DETECTION_MODELS_DIR))
    
    web_dir = Path(PROJECT_ROOT) / "web"
    if not DETECTION_ONLY_MODE:
        # Add project root, m_models, and test_models
        # m_models is already included above; keep for robustness
        search_dirs.append(Path(PROJECT_ROOT) / "m_models")
        search_dirs.append(Path(PROJECT_ROOT) / "detection")
        search_dirs.append(Path(PROJECT_ROOT) / "test_models")
        search_dirs.append(Path(PROJECT_ROOT))

        # Add models/extracted
        extracted_dir = Path(PROJECT_ROOT) / "models" / "extracted"
        if extracted_dir.exists():
            search_dirs.append(extracted_dir)

        # Add Web Folder Models (Recursive Search)
        if web_dir.exists():
            search_dirs.append(web_dir)
    
    models = []
    seen_paths = set()

    for d in search_dirs:
        # Use absolute path to handle spaces in directory names
        if not d.is_absolute():
            d = Path(PROJECT_ROOT) / d
        
        # Resolve potentially non-existent paths gracefully
        try:
            d = d.resolve()
        except OSError:
            continue
            
        if not d.exists():
            continue
        
        # Find all model files (recursive if web dir, else shallow)
        if (not DETECTION_ONLY_MODE) and d == web_dir.resolve():
            keras_files = list(d.rglob("*.keras"))
            h5_files = list(d.rglob("*.h5"))
            pt_files = list(d.rglob("*.pt"))
            pth_files = list(d.rglob("*.pth"))
            st_files = list(d.rglob("*.safetensors"))
            bin_files = list(d.rglob("*.bin"))
        else:
            keras_files = list(d.glob("*.keras"))
            h5_files = list(d.glob("*.h5"))
            pt_files = list(d.glob("*.pt"))
            pth_files = list(d.glob("*.pth"))
            st_files = list(d.glob("*.safetensors"))
            bin_files = list(d.glob("*.bin"))
        
        # Check for missing models defined in download_model.py
        from download_model import MODELS_TO_DOWNLOAD
        for local_path_str, repo_path in MODELS_TO_DOWNLOAD.items():
            local_path = Path(PROJECT_ROOT) / local_path_str
            # If the file is supposed to be in this directory but doesn't exist
            if local_path.parent.resolve() == d.resolve() and not local_path.exists():
                # Add it as a placeholder to be downloaded later
                models.append({
                    'path': str(local_path.resolve()),
                    'name': local_path.name,
                    'size': 100 * 1024 * 1024, # Dummy size for sorting (100MB)
                    'ext': local_path.suffix
                })
                seen_paths.add(str(local_path.resolve()))

        for f in keras_files + h5_files + pt_files + pth_files + st_files + bin_files:
            try:
                # Exclude known crashing models
                # if "Plant Disease Detection.h5" in f.name:
                #    continue
                    
                if not f.name.endswith('.crdownload') and f.stat().st_size > 0:
                    path_str = str(f.resolve())
                    if path_str in seen_paths:
                        continue
                    seen_paths.add(path_str)
                    
                    size = f.stat().st_size
                    models.append({
                        'path': path_str,
                        'name': f.name,
                        'size': size,
                        'ext': f.suffix
                    })
            except (OSError, FileNotFoundError):
                continue

        # Add local HuggingFace directory models (fast_model_* folders in m_models)
        hf_dirs = []
        try:
            if _is_hf_model_dir(d):
                hf_dirs.append(d)
            for sub in d.iterdir():
                if sub.is_dir() and _is_hf_model_dir(sub):
                    hf_dirs.append(sub)
        except Exception:
            hf_dirs = []

        for hf_dir in hf_dirs:
            try:
                hf_path = str(hf_dir.resolve())
                if hf_path in seen_paths:
                    continue
                seen_paths.add(hf_path)
                size = _get_hf_model_size_bytes(hf_dir)
                if size <= 0:
                    continue
                models.append({
                    'path': hf_path,
                    'name': hf_dir.name,
                    'size': size,
                    'ext': '.hfdir',
                    'type': 'hf_dir'
                })
            except (OSError, FileNotFoundError):
                continue

    if not models:
        error_msg = (
            f"\nNo model files found in any search directory.\n"
            f"Please ensure at least one .keras or .h5 file exists."
        )
        logger.warning(error_msg)
        return []
    
    # Sort: prefer .keras first, then by size (largest first)
    def sort_key(m):
        # Priority: .keras files first (prefer largest), then .h5, then others
        if m['ext'] == '.keras':
            priority = 0
        elif m['ext'] == '.h5':
            priority = 1
        elif m['ext'] == '.hfdir' or m['ext'] == '.safetensors' or m['ext'] == '.bin':
            priority = 2
        elif m['ext'] in ['.pt', '.pth']:
            priority = 3
        else:
            priority = 4
        return (priority, -m['size'])  # Negative for descending size
    
    models.sort(key=sort_key)
    
    return models


def find_largest_model():
    """
    Backward compatibility: Find the largest model file
    Returns list of (path, filename) tuples sorted by priority
    """
    models = find_local_models()
    return [(m['path'], m['name']) for m in models]


# Label maps for specific models
WEB1_LABELS = [
    "Potato___Early_blight",
    "Potato___healthy",
    "Potato___Late_blight",
    "Tomato_Early_blight",
    "Tomato_healthy"
]

WEB2_LABELS = ['Corn-Common_rust', 'Potato-Early_blight', 'Tomato-Bacterial_spot']

WEB3_LABELS = ['Blight', 'Common_Rust', 'Gray_Leaf_Spot', 'Healthy']

WEB4_LABELS = [
    'Bacterial_spot', 'Healthy', 'Septoria_leaf_spot', 
    'Spider_mites_Two_spotted_spider_mite', 'YellowLeaf__Curl_Virus'
]

# Web14 uses standard PlantVillage classes (0-38)
WEB14_LABELS = [
    'Apple___Apple_scab', 'Apple___Black_rot', 'Apple___Cedar_apple_rust', 'Apple___healthy',
    'Background_without_leaves', 'Blueberry___healthy', 'Cherry___Powdery_mildew', 'Cherry___healthy',
    'Corn___Cercospora_leaf_spot Gray_leaf_spot', 'Corn___Common_rust', 'Corn___Northern_Leaf_Blight', 'Corn___healthy',
    'Grape___Black_rot', 'Grape___Esca_(Black_Measles)', 'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)', 'Grape___healthy',
    'Orange___Haunglongbing_(Citrus_greening)', 'Peach___Bacterial_spot', 'Peach___healthy',
    'Pepper,_bell___Bacterial_spot', 'Pepper,_bell___healthy',
    'Potato___Early_blight', 'Potato___Late_blight', 'Potato___healthy',
    'Raspberry___healthy', 'Soybean___healthy', 'Squash___Powdery_mildew',
    'Strawberry___Leaf_scorch', 'Strawberry___healthy',
    'Tomato___Bacterial_spot', 'Tomato___Early_blight', 'Tomato___Late_blight', 'Tomato___Leaf_Mold',
    'Tomato___Septoria_leaf_spot', 'Tomato___Spider_mites Two-spotted_spider_mite', 'Tomato___Target_Spot',
    'Tomato___Tomato_Yellow_Leaf_Curl_Virus', 'Tomato___Tomato_mosaic_virus', 'Tomato___healthy'
]

DATASET12_LABELS = [
    "apple_alternaria_leaf_spot", "apple_black_rot", "apple_brown_spot", "apple_gray_spot", "apple_healthy",
    "apple_rust", "apple_scab", "bell_pepper_bacterial_spot", "bell_pepper_healthy", "blueberry_healthy",
    "cassava_bacterial_blight", "cassava_brown_streak_disease", "cassava_green_mottle", "cassava_healthy", "cassava_mosaic_disease",
    "cherry_healthy", "cherry_powdery_mildew", "coffee_healthy", "coffee_red_spider_mite", "coffee_rust",
    "corn_common_rust", "corn_gray_leaf_spot", "corn_healthy", "corn_northern_leaf_blight", "grape_black_measles",
    "grape_black_rot", "grape_healthy", "grape_leaf_blight", "not_leaf", "orange_citrus_greening",
    "peach_bacterial_spot", "peach_healthy", "potato_bacterial_wilt", "potato_early_blight", "potato_healthy",
    "potato_late_blight", "potato_leafroll_virus", "potato_mosaic_virus", "potato_nematode", "potato_pests",
    "potato_phytophthora", "raspberry_healthy", "rice_bacterial_blight", "rice_blast", "rice_brown_spot",
    "rice_tungro", "rose_healthy", "rose_rust", "rose_slug_sawfly", "soybean_healthy",
    "squash_powdery_mildew", "strawberry_healthy", "strawberry_leaf_scorch", "sugercane_healthy", "sugercane_mosaic",
    "sugercane_red_rot", "sugercane_rust", "sugercane_yellow_leaf", "tomato_bacterial_spot", "tomato_early_blight",
    "tomato_healthy", "tomato_late_blight", "tomato_leaf_curl", "tomato_leaf_mold", "tomato_mosaic_virus",
    "tomato_septoria_leaf_spot", "tomato_spider_mites", "tomato_target_spot", "watermelon_anthracnose", "watermelon_downy_mildew",
    "watermelon_healthy", "watermelon_mosaic_virus"
]

DATASET16_LABELS = [
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___Cedar_apple_rust",
    "Apple___healthy",
    "Background"
]

DATASET17_LABELS = [
    "Pepper__bell___Bacterial_spot",
    "Pepper__bell___healthy",
    "PlantVillage",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Tomato_Bacterial_spot",
    "Tomato_Early_blight",
    "Tomato_Late_blight",
    "Tomato_Leaf_Mold",
    "Tomato_Septoria_leaf_spot",
    "Tomato_Spider_mites_Two_spotted_spider_mite",
    "Tomato__Target_Spot",
    "Tomato__Tomato_YellowLeaf__Curl_Virus",
    "Tomato__Tomato_mosaic_virus",
    "Tomato_healthy"
]

# Standard PlantVillage 38 classes + Background at the end (Index 38)
DATASET39_LABELS = [
    "Apple___Apple_scab", "Apple___Black_rot", "Apple___Cedar_apple_rust", "Apple___healthy",
    "Background",
    "Blueberry___healthy",
    "Cherry_(including_sour)___Powdery_mildew", "Cherry_(including_sour)___healthy",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot", "Corn_(maize)___Common_rust_", "Corn_(maize)___Northern_Leaf_Blight", "Corn_(maize)___healthy",
    "Grape___Black_rot", "Grape___Esca_(Black_Measles)", "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)", "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)",
    "Peach___Bacterial_spot", "Peach___healthy",
    "Pepper,_bell___Bacterial_spot", "Pepper,_bell___healthy",
    "Potato___Early_blight", "Potato___Late_blight", "Potato___healthy",
    "Raspberry___healthy",
    "Soybean___healthy",
    "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch", "Strawberry___healthy",
    "Tomato___Bacterial_spot", "Tomato___Early_blight", "Tomato___Late_blight", "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot", "Tomato___Spider_mites Two-spotted_spider_mite", "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "Tomato___Tomato_mosaic_virus", "Tomato___healthy",
    # Extended Labels for Rice and others
    "Rice___Blast",                 # 39
    "Rice___Leaf_Smut",             # 40
    "Rice___Tungro",                # 41
    "Rice___Brown_Spot",            # 42
    "Insect___Stem_Fly",            # 43
    "Insect___Pink_Bollworm",       # 44
    "Insect___Whitefly",            # 45
    "Wheat___Black_Rust",           # 46
    "Wheat___Leaf_Blight",          # 47
    "Insect___Army_worm",           # 48
    "Cotton___Aphid",               # 49
    "Cotton___Healthy",             # 50
    "Cotton___Leaf_Curl",           # 51
    "Wheat___Flag_Smut",            # 52
    "Sugarcane___Red_Rot"           # 53
]

DATASET_EXTRA_LABELS = [
    "Army worm",
    "Brownspot",
    "Cotton Aphid",
    "Flag Smut",
    "Healthy cotton",
    "Leaf Curl",
    "Leaf smut",
    "RedRot sugarcane"
]

# detection/streamlit_app.py model labels
DETECTION_BEST_MODEL_LABELS = [
    "Pepper Bell - Bacterial Spot", "Pepper Bell - Healthy",
    "Potato - Early Blight", "Potato - Late Blight", "Potato - Healthy",
    "Tomato - Bacterial Spot", "Tomato - Early Blight", "Tomato - Late Blight",
    "Tomato - Leaf Mold", "Tomato - Septoria Leaf Spot",
    "Tomato - Spider Mites (Two-spotted spider mite)", "Tomato - Target Spot",
    "Tomato - Yellow Leaf Curl Virus", "Tomato - Mosaic Virus", "Tomato - Healthy"
]

DETECTION_LEFORA_LABELS = [
    "Apple___alternaria_leaf_spot", "Apple___black_rot", "Apple___brown_spot", "Apple___gray_spot", "Apple___healthy", "Apple___rust", "Apple___scab",
    "Bell_pepper___bacterial_spot", "Bell_pepper___healthy", "Blueberry___healthy", "Cassava___bacterial_blight", "Cassava___brown_streak_disease",
    "Cassava___green_mottle", "Cassava___healthy", "Cassava___mosaic_disease", "Cherry___healthy", "Cherry___powdery_mildew", "Coffee___healthy",
    "Coffee___red_spider_mite", "Coffee___rust", "Corn___common_rust", "Corn___gray_leaf_spot", "Corn___healthy", "Corn___northern_leaf_blight",
    "Grape___black_measles", "Grape___black_rot", "Grape___healthy", "Grape___Leaf_blight", "Orange___citrus_greening", "Peach___bacterial_spot",
    "Peach___healthy", "Pepper__bell___Bacterial_spot", "Pepper__bell___healthy", "Potato___bacterial_wilt", "Potato___Early_blight", "Potato___healthy",
    "Potato___Late_blight", "Potato___leafroll_virus", "Potato___mosaic_virus", "Potato___nematode", "Potato___pests", "Potato___phytophthora",
    "Raspberry___healthy", "Rice___bacterial_blight", "Rice___blast", "Rice___brown_spot", "Rice___tungro", "Rose___healthy", "Rose___rust",
    "Rose___slug_sawfly", "Soybean___healthy", "Squash___powdery_mildew", "Strawberry___healthy", "Strawberry___leaf_scorch", "Sugercane___healthy",
    "Sugercane___mosaic", "Sugercane___red_rot", "Sugercane___rust", "Sugercane___yellow_leaf", "Tomato_Bacterial_spot", "Tomato_Early_blight",
    "Tomato_healthy", "Tomato_Late_blight", "Tomato_Leaf_Mold", "Tomato_Septoria_leaf_spot", "Tomato_Spider_mites_Two_spotted_spider_mite",
    "Tomato__Target_Spot", "Tomato__Tomato_mosaic_virus", "Tomato__Tomato_YellowLeaf__Curl_Virus", "Tomato___bacterial_spot", "Tomato___early_blight",
    "Tomato___healthy", "Tomato___late_blight", "Tomato___leaf_curl", "Tomato___leaf_mold", "Tomato___mosaic_virus", "Tomato___septoria_leaf_spot",
    "Tomato___spider_mites", "Tomato___target_spot", "Watermelon___anthracnose", "Watermelon___downy_mildew", "Watermelon___healthy", "Watermelon___mosaic_virus"
]

# Match /web/streamlit_app.py behavior exactly
DETECTION_REFERENCE_DISEASE_MODELS = {
    "best_model.keras",
    "lefora.keras",
    "fast_model_1",
    "fast_model_2",
    "fast_model_3",
}
DETECTION_LEFORA_EXCLUDED_PLANTS = {
    'cherry', 'soybean', 'blueberry', 'squash', 'peach', 'grape',
    'coffee', 'sugarcane', 'sugercane', 'watermelon', 'raspberry', 'potato'
}

DATASET1_LABELS = [
    "apple_leaf", "apple_rust_leaf", "apple_scab_leaf", "bell_pepper_leaf", "bell_pepper_leaf_spot",
    "blueberry_leaf", "cherry_leaf", "corn_gray_leaf_spot", "corn_leaf_blight", "corn_rust_leaf",
    "grape_leaf", "grape_leaf_black_rot", "not_leaf", "peach_leaf", "potato_leaf_early_blight",
    "potato_leaf_late_blight", "raspberry_leaf", "soyabean_leaf", "squash_powdery_mildew_leaf",
    "strawberry_leaf", "tomato_early_blight_leaf", "tomato_leaf", "tomato_leaf_bacterial_spot",
    "tomato_leaf_late_blight", "tomato_leaf_mosaic_virus", "tomato_leaf_yellow_virus", "tomato_mold_leaf",
    "tomato_septoria_leaf_spot", "tomato_two_spotted_spider_mites_leaf"
]

DATASET2_LABELS = ["gourd", "hibiscus", "not_leaf", "papaya", "zucchini"]

DATASET4_LABELS = [
    "apple_apple_scab", "apple_black_rot", "apple_cedar_apple_rust", "apple_healthy",
    "background_without_leaves", "blueberry_healthy", "cherry_healthy", "cherry_powdery_mildew",
    "corn_common_rust", "corn_healthy", "corn_northern_leaf_blight", "grape_black_rot", "not_leaf"
]

DATASET5_LABELS = [
    "aloevera", "banana", "bilimbi", "cantaloupe", "cassava", "coconut", "corn", "cucumber",
    "curcuma", "eggplant", "galangal", "ginger", "guava", "kale", "longbeans", "mango",
    "melon", "not_leaf", "orange", "paddy", "papaya", "peper_chili", "pineapple", "pomelo",
    "shallot", "soybeans", "spinach", "sweet_potatoes", "tobacco", "waterapple", "watermelon"
]

DATASET7_LABELS = [
    "diseases", "not_leaf", "tomato_bacterial_spot", "tomato_early_blight", "tomato_healthy",
    "tomato_late_blight", "tomato_leaf_mold", "tomato_septoria_leaf_spot",
    "tomato_spider_mites_two_spotted_spider_mite", "tomato_target_spot",
    "tomato_tomato_mosaic_virus", "tomato_tomato_yellow_leaf_curl_virus"
]

DATASET8_LABELS = [
    "not_leaf", "pepper_bell_bacterial_spot", "pepper_bell_healthy", "potato_early_blight",
    "potato_healthy", "potato_late_blight", "tomato_bacterial_spot", "tomato_early_blight",
    "tomato_healthy", "tomato_late_blight", "tomato_leaf_mold", "tomato_septoria_leaf_spot",
    "tomato_spider_mites_two_spotted_spider_mite", "tomato_target_spot",
    "tomato_tomato_mosaic_virus", "tomato_tomato_yellowleaf_curl_virus"
]

DATASET10_LABELS = ["not_leaf", "plots"]

DATASET13_LABELS = ["non_not_leaf", "not_leaf"]

DATASET14_LABELS = [
    "apple_apple_scab", "apple_black_rot", "apple_cedar_apple_rust",
    "cherry_including_sour_powdery_mildew", "grape_black_rot", "not_leaf",
    "peach_bacterial_spot", "strawberry_leaf_scorch", "tomato_leaf_mold"
]

DATASET15_LABELS = [
    "apple_leaf", "apple_rust_leaf", "apple_scab_leaf", "bell_pepper_leaf", "bell_pepper_leaf_spot",
    "blueberry_leaf", "cherry_leaf", "corn_gray_leaf_spot", "corn_leaf_blight", "corn_rust_leaf",
    "grape_leaf", "grape_leaf_black_rot", "not_leaf", "peach_leaf", "potato_leaf_early_blight",
    "potato_leaf_late_blight", "raspberry_leaf", "soyabean_leaf", "squash_powdery_mildew_leaf",
    "strawberry_leaf", "tomato_early_blight_leaf", "tomato_leaf", "tomato_leaf_bacterial_spot",
    "tomato_leaf_late_blight", "tomato_leaf_mosaic_virus", "tomato_leaf_yellow_virus", "tomato_mold_leaf",
    "tomato_septoria_leaf_spot", "tomato_two_spotted_spider_mites_leaf"
]

DATASET3_LABELS = [
    "apple_apple_scab",
    "apple_black_rot",
    "apple_cedar_apple_rust",
    "cherry_including_sour_powdery_mildew",
    "grape_black_rot",
    "not_leaf",
    "peach_bacterial_spot",
    "strawberry_leaf_scorch",
    "tomato_leaf_mold"
]

RICE_LABELS = [
    "Unknown_0",
    "Unknown_1",
    "Unknown_2",
    "rice_leaf_smut", # 3
    "rice_blast", # 4
    "rice_brown_spot", # 5
    "Unknown_6",
    "Unknown_7",
    "Unknown_8",
    "Unknown_9",
    "Unknown_10",
    "rice_tungro" # 11
]

# Mapping dictionaries for standardizing model outputs to DATASET39_LABELS
DATASET3_MAPPING = {0: 0, 1: 1, 2: 2, 3: 6, 4: 12, 5: 4, 6: 17, 7: 27, 8: 32}
DATASET12_MAPPING = {
    1: 1, 4: 3, 5: 2, 6: 0, 7: 19, 8: 20, 9: 5, 20: 9, 21: 8, 23: 10, 24: 13, 25: 12, 26: 15, 27: 14,
    28: 43, # Stem Fly (Override existing 28:4)
    30: 17, 31: 18, 32: 21, 33: 21, 34: 23, 35: 22, 41: 24, 49: 25, 50: 26, 51: 28, 52: 27, 58: 29, 59: 30,
    60: 38, 61: 31, 63: 32, 64: 37,
    65: 45, # Whitefly (Override existing 65:33)
    66: 34, 67: 35,
    # Extended Mapping from Probe Results
    43: 39, # Blast
    44: 42, # Brown Spot
    45: 41, # Tungro
    40: 44, # Pink Bollworm
    56: 47, # Leaf Blight
}
DATASET16_MAPPING = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}
DATASET17_MAPPING = {0: 19, 1: 20, 2: 4, 3: 21, 4: 22, 5: 23, 6: 29, 7: 30, 8: 31, 9: 32, 10: 33, 11: 34, 12: 35, 13: 36, 14: 37, 15: 38}
RICE_MAPPING = {
    3: 40, # Leaf Smut (Verified with Norm)
    11: 41, # Tungro (Verified with Norm)
    4: 39, # Blast (Verified with Raw)
    5: 42, # Brown Spot (Inferred from model12 agreement on test image)
}

# Web Model Mappings
WEB2_MAPPING = {
    0: 8,   # Corn-Common_rust -> Corn_(maize)___Common_rust_
    1: 21,  # Potato-Early_blight -> Potato___Early_blight
    2: 29   # Tomato-Bacterial_spot -> Tomato___Bacterial_spot
}

WEB3_MAPPING = {
    0: 9,   # Blight -> Corn_(maize)___Northern_Leaf_Blight
    1: 8,   # Common_Rust -> Corn_(maize)___Common_rust_
    2: 7,   # Gray_Leaf_Spot -> Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot
    3: 10   # Healthy -> Corn_(maize)___healthy
}

WEB4_MAPPING = {
    0: 29,  # Bacterial_spot -> Tomato___Bacterial_spot
    1: 38,  # Tomato___healthy
    2: 33,  # Tomato___Septoria_leaf_spot
    3: 34,  # Tomato___Spider_mites Two-spotted_spider_mite
    4: 36   # Tomato___Tomato_Yellow_Leaf_Curl_Virus
}

# Mapping for Plant Disease Detection.h5 (8 classes)
DATASET_EXTRA_MAPPING = {
    0: 48, # Army worm
    1: 42, # Brownspot -> Rice Brown Spot
    2: 49, # Cotton Aphid
    3: 52, # Flag Smut -> Wheat Flag Smut
    4: 50, # Healthy cotton
    5: 51, # Leaf Curl -> Cotton Leaf Curl
    6: 40, # Leaf smut -> Rice Leaf Smut
    7: 53  # RedRot sugarcane
}

import csv

def load_metadata_for_model(model_name):
    """
    Load external metadata (JSON/CSV) for a given model to map class indices to names.
    Looks for files in models/extracted/ matching the model's web prefix.
    """
    try:
        # Extract web prefix (e.g. "web10")
        if not model_name.startswith("web"):
            return None
        
        prefix = model_name.split("_")[0] # "web10"
        extracted_dir = os.path.join(PROJECT_ROOT, "models", "extracted")
        
        # 1. Try JSON (class_indices.json)
        json_path = os.path.join(extracted_dir, f"{prefix}_class_indices.json")
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)
                # Format: {"0": "Apple___Apple_scab", ...}
                # Convert keys to int
                mapping = {}
                for k, v in data.items():
                    try:
                        mapping[int(k)] = v
                    except ValueError:
                        pass
                return mapping

        # 2. Try CSV (disease_info.csv) - web12, web13
        # Assuming index corresponds to row number (ignoring header)
        csv_path = os.path.join(extracted_dir, f"{prefix}_disease_info.csv")
        if os.path.exists(csv_path):
            mapping = {}
            with open(csv_path, 'r', encoding='cp1252', errors='replace') as f: # web12 used cp1252
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    # Prefer 'disease_name' column
                    if 'disease_name' in row:
                        mapping[i] = row['disease_name']
                    elif 'name' in row:
                        mapping[i] = row['name']
            return mapping
            
    except Exception as e:
        logger.warning(f"Failed to load metadata for {model_name}: {e}")
        return None
    
    return None

def get_labels_for_model(model_name):
    """Get the specific label list for a model if available"""
    model_name_l = model_name.lower()

    # Detection folder models
    if 'best_model.keras' in model_name_l or 'final_model.keras' in model_name_l:
        return DETECTION_BEST_MODEL_LABELS
    if 'lefora.keras' in model_name_l:
        return DETECTION_LEFORA_LABELS
    if 'best_plant_detector.keras' in model_name_l:
        return ['plant_score']

    # Strict checking to avoid substring collision (e.g. dataset1 vs dataset10)
    
    # Specific Dataset Models (2-digits)
    if 'dataset10' in model_name: return DATASET10_LABELS
    if 'dataset12' in model_name: return DATASET12_LABELS
    if 'dataset13' in model_name: return DATASET13_LABELS
    if 'dataset14' in model_name: return DATASET14_LABELS
    if 'dataset15' in model_name: return DATASET15_LABELS
    if 'dataset16' in model_name: return DATASET16_LABELS
    if 'dataset17' in model_name: return DATASET17_LABELS
    
    # Specific Dataset Models (1-digit)
    # Check these AFTER 2-digit ones if not using regex anchor
    if 'dataset1' in model_name and 'dataset1' not in model_name.replace('dataset1', ''): # Simple check? No.
         # dataset1 matches dataset10. 
         # But if we already returned for dataset10 above, we are safe?
         # No, 'dataset10' contains 'dataset1'. 
         # So checking 'dataset10' first and returning is NOT enough if we continue.
         # But we return immediately. So yes, order matters.
         pass
    
    # Re-ordering for safety: 
    # Check longer strings first
    
    if 'dataset10' in model_name: return DATASET10_LABELS
    if 'dataset12' in model_name: return DATASET12_LABELS
    if 'dataset13' in model_name: return DATASET13_LABELS
    if 'dataset14' in model_name: return DATASET14_LABELS
    if 'dataset15' in model_name: return DATASET15_LABELS
    if 'dataset16' in model_name: return DATASET16_LABELS
    if 'dataset17' in model_name: return DATASET17_LABELS
    
    # Now check single digits, ensuring they are not part of a larger number
    # But wait, 'dataset1.keras' contains 'dataset1'. 'dataset10.keras' contains 'dataset1' too.
    # If I check 'dataset10' first and return, then 'dataset10' case is handled.
    # But if I have 'dataset1', it won't match 'dataset10'.
    # So if I check 'dataset10' first, I'm good?
    # Yes, because 'dataset10' matches 'dataset10'.
    # 'dataset1' does NOT match 'dataset10' (as a full string check? No, 'dataset1' is in 'dataset10').
    # Wait: 'dataset1' is a substring of 'dataset10'.
    # So if I have model_name='dataset10.keras':
    #   if 'dataset10' in model_name: returns (Correct).
    # If I have model_name='dataset1.keras':
    #   if 'dataset10' in model_name: False.
    #   if 'dataset1' in model_name: True. (Correct).
    
    # What if I have 'dataset1.keras'. 'dataset1' is in it.
    # What if I have 'dataset11.keras'? 'dataset1' is in it.
    # So 'dataset1' check matches 'dataset11'.
    # I should check 'dataset11' before 'dataset1'.
    # I don't have dataset11 labels yet.
    # But generally, I should just trust the order: check specific (longer) first.
    
    if 'dataset1' in model_name: return DATASET1_LABELS
    if 'dataset2' in model_name: return DATASET2_LABELS
    if 'dataset3' in model_name and 'dataset39' not in model_name: return DATASET3_LABELS
    if 'dataset4' in model_name: return DATASET4_LABELS
    if 'dataset5' in model_name: return DATASET5_LABELS
    if 'dataset7' in model_name: return DATASET7_LABELS
    if 'dataset8' in model_name: return DATASET8_LABELS
    
    # Web Models
    if 'web1_' in model_name: return WEB1_LABELS
    if 'web2_' in model_name: return WEB2_LABELS
    if 'web3_' in model_name: return WEB3_LABELS
    if 'web4_' in model_name: return WEB4_LABELS
    if 'web14_' in model_name: return WEB14_LABELS
    
    return None

def get_mapping_for_model(model_name):
    """Get the class index mapping for a specific model"""
    if 'dataset12' in model_name: return DATASET12_MAPPING
    if 'dataset16' in model_name: return DATASET16_MAPPING
    if 'dataset17' in model_name: return DATASET17_MAPPING
    if 'dataset3' in model_name and 'dataset39' not in model_name: return DATASET3_MAPPING
    if 'dataset6' in model_name: return {i:i for i in range(39)}
    if 'dataset39' in model_name or 'plant_disease_recog_model_pwp' in model_name: return {i:i for i in range(39)}
    if 'rice_disease_model' in model_name: return RICE_MAPPING
    if 'trained_model.h5' in model_name: return {i:i for i in range(38)}
    if 'final_model.h5' in model_name: return {i:i for i in range(38)}
    if 'Plant Disease Detection.h5' in model_name: return DATASET_EXTRA_MAPPING
    if 'simple_model.keras' in model_name: return {0:0, 1:1, 2:2}
    
    # Web Models
    if 'plant_disease.h5' in model_name: return WEB2_MAPPING
    if 'model-Corn-Leaf-Diseases-Exception-92.12.h5' in model_name: return WEB3_MAPPING
    if 'tomato_disese_model_V1.keras' in model_name: return WEB4_MAPPING
    
    return None

def get_model_support_mask(model_name, num_classes=None):
    """
    Get a boolean mask of classes supported by this model.
    Returns a numpy array of shape (num_classes,) where 1 means supported.
    """
    if num_classes is None:
        num_classes = len(DATASET39_LABELS)
    
    # dataset6 is a specialist for Apple, Grape, Pepper
    # We restrict its influence to these classes + Background
    # Apple: 0,1,2,3; Background: 4; Grape: 12,13,14,15; Pepper: 19,20
    if 'dataset6' in model_name:
        mask = np.zeros(num_classes, dtype=np.float32)
        specialist_indices = [0, 1, 2, 3, 4, 12, 13, 14, 15, 19, 20]
        for idx in specialist_indices:
            if idx < num_classes:
                mask[idx] = 1.0
        return mask

    mapping = get_mapping_for_model(model_name)
    mask = np.zeros(num_classes, dtype=np.float32)
    
    if mapping:
        # If mapping exists, only mapped targets are supported
        for target_idx in mapping.values():
            if target_idx < num_classes:
                mask[target_idx] = 1.0
    else:
        # If no mapping, assume it supports all classes (e.g. pwp)
        mask[:] = 1.0
        
    return mask

class PyTorchModelWrapper:
    def __init__(self, model, device='cpu'):
        self.model = model
        self.device = device
        if TORCH_AVAILABLE:
            self.model.to(device)
            self.model.eval()

    def predict(self, x, verbose=0):
        # Assume x is numpy array (1, H, W, C) or (1, C, H, W)
        # PyTorch expects (N, C, H, W)
        if not TORCH_AVAILABLE: return np.zeros((1, 1))
        
        with torch.no_grad():
            if isinstance(x, np.ndarray):
                x = torch.from_numpy(x).float().to(self.device)
                # If channel last (N, H, W, C), permute to (N, C, H, W)
                if x.dim() == 4 and x.shape[3] == 3:
                    x = x.permute(0, 3, 1, 2)
            
            output = self.model(x)
            # Apply softmax if logits
            probs = torch.nn.functional.softmax(output, dim=1)
            return probs.cpu().numpy()

def load_specific_models():
    """
    Load ALL discovered models (Core + Extracted + Web).
    Replaces the old restricted loading logic to ensure all available models are used.
    """
    models_dict = {}
    
    # Use auto-discovery to find all model files
    try:
        discovered = find_local_models()
    except FileNotFoundError:
        discovered = []
        logger.warning("No models found via auto-discovery.")

    for m in discovered:
        path = m['path']
        filename = m['name']
        ext = m['ext']
        
        # Auto-download if model is referenced but missing (for specific known models)
        if not os.path.exists(path):
             logger.info(f"Model file {filename} missing, attempting download...")
             download_model(path)

        # Use filename as key. If duplicates exist (e.g. extracted vs web), 
        # the last one loaded wins, or we could append path hash.
        # For now, we assume extracted files might have prefixes like 'web14_' 
        # while original web files might just be 'trained_model.pth'.
        # We want to keep both if possible, or prefer the one that works.
        model_key = filename
        if 'web' in path.lower() and 'web' not in filename.lower():
             # Add prefix to key for web models to avoid collision with generic names
             # e.g. s:\main project\web\web14\...\trained_model.pth -> web14_trained_model.pth
             try:
                 parts = path.split(os.sep)
                 web_part = next((p for p in parts if p.startswith('web') and p != 'web'), 'web_unknown')
                 model_key = f"{web_part}_{filename}"
             except:
                 pass

        try:
            if ext in ['.keras', '.h5']:
                logger.info(f"Loading Keras model: {model_key} from {path}")
                tf_module = get_tf()
                if tf_module:
                    init_keras_patches()
                    models_dict[model_key] = tf_module.keras.models.load_model(path, compile=False)
                else:
                    logger.warning(f"Skipping Keras model {model_key}: TensorFlow not available")
                
            elif ext in ['.pt', '.pth'] and TORCH_AVAILABLE:
                logger.info(f"Loading PyTorch model: {model_key} from {path}")
                try:
                    # Special handling for Web14 ResNet50
                    # Check if it's the web14 model (either in web14 folder or extracted)
                    is_web14 = ('web14' in path.lower() or 'web14' in filename.lower())
                    if is_web14 and ('trained_model.pth' in filename or 'resnet' in filename.lower()):
                        try:
                            # Define ResNet50 architecture
                            # Web14 uses ResNet50 with 39 classes
                            resnet = models.resnet50(weights=None)
                            num_ftrs = resnet.fc.in_features
                            resnet.fc = nn.Linear(num_ftrs, 39) 
                            
                            state_dict = torch.load(path, map_location='cpu')
                            resnet.load_state_dict(state_dict)
                            models_dict[model_key] = PyTorchModelWrapper(resnet)
                            logger.info(f"Successfully loaded Web14 ResNet50 from {path}")
                            continue
                        except Exception as e:
                            logger.warning(f"Failed to load Web14 ResNet logic for {path}, trying standard load: {e}")

                    pt_model = torch.load(path, map_location=torch.device('cpu'))
                    if isinstance(pt_model, dict):
                         logger.warning(f"Skipping {model_key}: Loaded object is a dict (state_dict?), need architecture.")
                    else:
                        models_dict[model_key] = PyTorchModelWrapper(pt_model)
                except Exception as pt_e:
                    logger.error(f"Failed to load PyTorch model {model_key}: {pt_e}")

            elif ext in ['.safetensors', '.bin'] and TRANSFORMERS_AVAILABLE:
                logger.info(f"Loading Transformers model: {model_key} from {path}")
                try:
                    # For Transformers, the path is often the directory containing model.safetensors
                    model_dir = os.path.dirname(path)
                    # Check if it's a known fast_model
                    if 'fast_model' in model_dir.lower():
                        config = AutoConfig.from_pretrained(model_dir)
                        processor = AutoImageProcessor.from_pretrained(model_dir)
                        model = AutoModelForImageClassification.from_pretrained(model_dir)
                        
                        # Wrapper for transformers to match .predict()
                        class TransformersWrapper:
                            def __init__(self, model, processor):
                                self.model = model
                                self.processor = processor
                            def predict(self, x, verbose=0):
                                # x is (1, H, W, 3) numpy array
                                inputs = self.processor(images=x[0], return_tensors="pt")
                                with torch.no_grad():
                                    outputs = self.model(**inputs)
                                    probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
                                    return probs.cpu().numpy()
                        
                        models_dict[model_key] = TransformersWrapper(model, processor)
                        logger.info(f"Successfully loaded Transformers model from {model_dir}")
                except Exception as tr_e:
                    logger.error(f"Failed to load Transformers model {model_key}: {tr_e}")
                    
        except Exception as e:
            logger.error(f"Failed to load {model_key}: {e}")

    return models_dict

def predict_kindwise_api(image_path):
    """
    Call Kindwise Crop Health API for disease identification.
    Returns list of formatted candidate dicts.
    """
    # Use config value or fallback
    api_key = os.getenv('KINDWISE_CROP_API_KEY', 'QXqAt2e7id3VPhzjUKLCOF1bhdvgQNlthNeXY9baQtbdAhquUA')
    url = "https://crop.kindwise.com/api/v1/identification"
    
    try:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
            
        payload = {
            "images": [image_data],
            "similar_images": True
        }
        
        headers = {
            "Api-Key": api_key,
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Kindwise API Error: {response.status_code} - {response.text}")
            return []
            
        data = response.json()
        result = data.get("result", {})
        classification = result.get("classification", {})
        suggestions = classification.get("suggestions", [])
        
        api_candidates = []
        for suggestion in suggestions:
            name = suggestion.get("name", "Unknown")
            probability = suggestion.get("probability", 0.0)
            
            api_candidates.append({
                'model': 'Kindwise API',
                'model_source': 'Kindwise API',
                'label': name,
                'prob': probability,
                'confidence': round(probability * 100, 2),
                'is_primary': False
            })
            
        return api_candidates
        
    except Exception as e:
        logger.error(f"Kindwise API Exception: {e}")
        return []

def predict_image(image_path):
    """
    Predict using ALL available models (Core + Extracted).
    Returns a UNIFIED list of dicts with 'model', 'model_source', 'label', 'prob', 'confidence', 'is_primary'.
    """
    try:
        # Load image
        img = Image.open(image_path).convert('RGB')
        
        # Prepare Image Versions
        # 1. 224x224 Normalized (0-1) - for dataset16, web1
        img_224 = img.resize((224, 224))
        img_arr_224_norm = np.array(img_224) / 255.0
        img_arr_224_norm = np.expand_dims(img_arr_224_norm, axis=0)
        
        # 2. 224x224 Raw (0-255) - for dataset6, dataset17, dataset12, rice, dataset3
        img_arr_224_raw = np.array(img_224).astype(float)
        img_arr_224_raw = np.expand_dims(img_arr_224_raw, axis=0)
        
        # 3. 160x160 Raw (0-255) - for dataset39
        img_160 = img.resize((160, 160))
        img_arr_160_raw = np.array(img_160).astype(float)
        img_arr_160_raw = np.expand_dims(img_arr_160_raw, axis=0)
        
        # 4. 256x256 Raw - for web2, web4
        img_256 = img.resize((256, 256))
        img_arr_256_raw = np.array(img_256).astype(float)
        img_arr_256_raw = np.expand_dims(img_arr_256_raw, axis=0)

        # Load models if not cached
        if not _MODEL_CACHE['loaded']:
            specific_models = load_specific_models()
            if specific_models:
                _MODEL_CACHE['models'] = specific_models
                _MODEL_CACHE['loaded'] = True
            else:
                logger.warning("Specific models not found, falling back to auto-discovery")
                pass
        
        # Unify model list
        all_models = {}
        cache = _MODEL_CACHE.get('models')
        if isinstance(cache, dict):
            all_models = cache
        elif isinstance(cache, list):
            for m in cache:
                all_models[m['name']] = m.get('model')
        
        candidates = []
        
        # Iterate over ALL models
        for name, model in all_models.items():
            try:
                # Default Setup
                input_data = img_arr_224_raw
                label_map_func = None # Optional custom mapping function
                
                # Determine Input Type & Mapping based on Name
                if 'dataset39' in name:
                    input_data = img_arr_160_raw
                elif 'dataset16' in name:
                    input_data = img_arr_224_norm
                elif 'web1_' in name or 'web14_' in name:
                    # PyTorch / Web1 uses 224x224 Norm usually
                    # Check if PyTorch wrapper
                    pass # Handled inside prediction block
                elif 'web2_' in name or 'web4_' in name:
                    input_data = img_arr_256_raw
                
                # Predict
                prob = 0.0
                label = "Unknown"
                
                if (callable(model) and not hasattr(model, 'predict')):
                     # PyTorch / Wrapper Prediction
                     img_resized = img.resize((224, 224))
                     img_arr = np.array(img_resized).astype(float)
                     img_arr = np.expand_dims(img_arr, axis=0)
                     
                     pred = model(img_arr)[0]
                     idx = pred.argmax()
                     prob = float(pred[idx])
                     label = f"Class {idx}"
                elif isinstance(model, type) and 'PyTorchModelWrapper' in str(model): # Legacy check just in case
                     pass 

                else:
                    # Keras/TF Prediction
                    # Check input shape to be safe
                    try:
                        if hasattr(model, 'input_shape'):
                            shape = model.input_shape
                            # (None, H, W, 3)
                            if len(shape) == 4 and shape[1] is not None:
                                h, w = shape[1], shape[2]
                                if h == 160: input_data = img_arr_160_raw
                                elif h == 256: input_data = img_arr_256_raw
                                elif h == 224: 
                                    if 'dataset16' in name: input_data = img_arr_224_norm
                                    else: input_data = img_arr_224_raw
                    except:
                        pass

                    pred = model.predict(input_data, verbose=0)[0]
                    
                    # Softmax for logits
                    if np.max(pred) > 1.0 or np.min(pred) < 0.0:
                        exp_preds = np.exp(pred - np.max(pred))
                        pred = exp_preds / np.sum(exp_preds)

                    idx = pred.argmax()
                    prob = float(pred[idx])
                    label = f"Class {idx}"

                # Label Mapping
                # 0. Try external metadata (JSON/CSV) first - for extracted web models
                metadata_map = load_metadata_for_model(name)
                if metadata_map and idx in metadata_map:
                    label = metadata_map[idx]
                
                # 1. Use get_mapping_for_model if available (internal hardcoded maps)
                else:
                    mapping = get_mapping_for_model(name)
                    if mapping:
                        final_idx = mapping.get(idx, -1)
                        if final_idx != -1 and final_idx < len(DATASET39_LABELS):
                            label = DATASET39_LABELS[final_idx]
                
                # 2. Specific Model Logic (Overrides)
                if 'dataset39' in name:
                    if idx < len(DATASET39_LABELS): label = DATASET39_LABELS[idx]
                    # Raspberry Fix
                    if len(pred) > 24:
                        rasp_prob = float(pred[24])
                        if idx == 4 and rasp_prob > 0.3: # Background -> Raspberry
                            label = DATASET39_LABELS[24]
                            prob = rasp_prob
                elif 'dataset16' in name and idx < len(DATASET16_LABELS):
                    label = DATASET16_LABELS[idx]
                elif 'dataset12' in name and label.startswith("Class"): # Fallback if mapping failed
                    if idx < len(DATASET12_LABELS): label = DATASET12_LABELS[idx]
                
                # 3. Model Specific Label Lists (Web & Datasets)
                if label.startswith("Class"):
                    local_labels = get_labels_for_model(name)
                    if local_labels and idx < len(local_labels):
                        label = local_labels[idx]

                # Clean Label
                label = label.replace("___", " ").replace("_", " ")

                candidates.append({
                    'model': name,
                    'model_source': name.replace('.keras','').replace('.h5','').replace('.pt','').replace('.pth','').replace('web','Web '),
                    'label': label,
                    'prob': prob,
                    'confidence': round(prob * 100, 2),
                    'is_primary': False
                })
                logger.info(f"Predicted {name}: {label} ({prob:.2f})")

            except Exception as e:
                logger.error(f"Prediction failed for {name}: {e}")

        # ---------------------------------------------------------
        # DECISION LOGIC (Identify Primary Detection)
        # ---------------------------------------------------------
        final_result = None
        
        # Helper to find candidate by partial name
        def get_cand(partial_name):
            return next((c for c in candidates if partial_name in c['model']), None)

        c39 = get_cand('dataset39') or get_cand('plant_disease_recog')
        c16 = get_cand('dataset16')
        c6 = get_cand('dataset6')
        c12 = get_cand('dataset12')
        c_rice = get_cand('rice_disease')

        TRUSTED_M39_CROPS = ["Tomato", "Corn", "Squash", "Potato", "Raspberry", "Soybean"]

        # A. Generalist Extension (model12) - High Priority for New Crops
        if c12 and ("Rice" in c12['label'] or "Insect" in c12['label'] or "Wheat" in c12['label']) and c12['prob'] > 0.90:
             final_result = c12

        # B. Rice Specialist
        elif c_rice and "Rice" in c_rice['label'] and c_rice['prob'] > 0.90:
             if c39 and "Rice" not in c39['label'] and "Background" not in c39['label'] and c39['prob'] > 0.6:
                 final_result = c39 # Trust m39 if it sees something else clearly
             elif c16 and "Apple" in c16['label'] and c16['prob'] > 0.80:
                 final_result = c16
             elif c6 and ("Grape" in c6['label'] or "Pepper" in c6['label']) and c6['prob'] > 0.80:
                 final_result = c6
             else:
                 final_result = c_rice

        # C. Generalist (model39)
        elif c39 and any(crop in c39['label'] for crop in TRUSTED_M39_CROPS) and c39['prob'] > 0.80:
            final_result = c39
            
        # D. Apple Specialist (model16)
        elif c16 and "Apple" in c16['label'] and c16['prob'] > 0.85:
            if c39 and "Apple" not in c39['label'] and "Background" not in c39['label'] and c39['prob'] > 0.6:
                 final_result = c39
            else:
                 final_result = c16
                 
        # E. Grape/Pepper Specialist (model6)
        elif c6 and ("Grape" in c6['label'] or "Pepper" in c6['label']) and c6['prob'] > 0.90:
             if c39 and "Grape" not in c39['label'] and "Pepper" not in c39['label'] and "Background" not in c39['label'] and c39['prob'] > 0.6:
                 final_result = c39
             else:
                 final_result = c6

        # F. Fallback
        else:
            # Sort by probability
            sorted_cands = sorted(candidates, key=lambda x: x['prob'], reverse=True)
            # Try to find first non-background
            for cand in sorted_cands:
                if "Background" not in cand['label'] and "Healthy" not in cand['label']:
                    final_result = cand
                    break
            if not final_result and sorted_cands:
                final_result = sorted_cands[0]

        # Mark Primary
        if final_result:
            for c in candidates:
                if c['model'] == final_result['model']:
                    c['is_primary'] = True
                    break
        
        # Sort candidates by confidence (DESC) for the unified list
        candidates.sort(key=lambda x: x['prob'], reverse=True)

        # ---------------------------------------------------------
        # ADD KINDWISE API PREDICTIONS
        # ---------------------------------------------------------
        try:
            api_candidates = predict_kindwise_api(image_path)
            if api_candidates:
                candidates.extend(api_candidates)
                # Re-sort to include API results in order (optional, but good for list display)
                candidates.sort(key=lambda x: x.get('confidence', 0), reverse=True)
                logger.info(f"Added {len(api_candidates)} Kindwise API predictions")
        except Exception as e:
            logger.error(f"Failed to add Kindwise API predictions: {e}")

        return candidates

    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        return []



def generate_label_map(num_classes):
    """Generate label_map.json from model output size"""
    label_map = {f"Class_{i}": i for i in range(num_classes)}
    try:
        with open(LABEL_MAP_PATH, "w", encoding="utf-8") as f:
            json.dump(label_map, f, indent=2)
        logger.info(f"Generated label_map.json with {num_classes} classes")
        return [f"Class_{i}" for i in range(num_classes)]
    except Exception as e:
        logger.error(f"Failed to generate label_map.json: {e}")
        return [f"Class_{i}" for i in range(num_classes)]


def get_enabled_models():
    """Get list of enabled model names from config"""
    config_path = os.path.join(PROJECT_ROOT, "model_config.json")
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                models = config.get('enabled_models', [])
                logger.info(f"Loaded config from {config_path}: {len(models)} models enabled")
                return models
        else:
            logger.warning(f"Config file not found: {config_path}")
    except Exception as e:
        logger.warning(f"Could not read model config: {e}")
    return []  # Empty list means all models enabled

def get_robust_custom_objects():
    """
    Create custom objects dictionary to handle Keras version incompatibilities.
    Specifically patches layers to ignore deprecated arguments like 'batch_input_shape'.
    """
    custom_objects = {}
    try:
        import tensorflow as tf
        layers_module = tf.keras.layers
        
        def robust_layer_factory(LayerClass):
            class RobustLayer(LayerClass):
                def __init__(self, *args, **kwargs):
                    # Remove arguments that Keras 3+ doesn't like in __init__
                    kwargs.pop('batch_input_shape', None)
                    kwargs.pop('input_shape', None)
                    kwargs.pop('batch_shape', None) # Also remove batch_shape
                    kwargs.pop('dim_ordering', None) # Legacy Keras
                    kwargs.pop('nb_filter', None) # Legacy Conv2D
                    kwargs.pop('nb_row', None) # Legacy Conv2D
                    kwargs.pop('nb_col', None) # Legacy Conv2D
                    kwargs.pop('value_range', None) # Legacy Preprocessing
                    super().__init__(*args, **kwargs)

                @classmethod
                def from_config(cls, config):
                    # Clean config before calling __init__
                    config_copy = config.copy()
                    keys_to_remove = [
                        'batch_input_shape', 'input_shape', 'batch_shape', 'dim_ordering', 
                        'nb_filter', 'nb_row', 'nb_col', 'value_range'
                    ]
                    for key in keys_to_remove:
                        config_copy.pop(key, None)
                    
                    # Call parent from_config with cleaned config
                    # This will eventually call cls(**config_copy)
                    return super().from_config(config_copy)

            return RobustLayer

        layer_names = [
            'Conv2D', 'Dense', 'MaxPooling2D', 'Flatten', 'Dropout', 
            'BatchNormalization', 'Rescaling', 'Resizing',
            'GlobalAveragePooling2D', 'AveragePooling2D', 'SeparableConv2D',
            'DepthwiseConv2D', 'Activation', 'Concatenate', 'Add', 'Multiply',
            'ZeroPadding2D', 'UpSampling2D', 'LeakyReLU', 'ELU', 'ThresholdedReLU',
            'Softmax', 'ReLU', 'Lambda', 'RandomRotation', 'RandomFlip', 
            'RandomZoom', 'RandomContrast', 'RandomTranslation'
        ]
        
        for name in layer_names:
            if hasattr(layers_module, name):
                custom_objects[name] = robust_layer_factory(getattr(layers_module, name))
        
        # Initializers
        if hasattr(tf.keras, 'initializers'):
            initializers_module = tf.keras.initializers
            
            def robust_initializer_factory(InitClass):
                class RobustInit(InitClass):
                    def __init__(self, *args, **kwargs):
                        kwargs.pop('dtype', None)
                        super().__init__(*args, **kwargs)
                    
                    @classmethod
                    def from_config(cls, config):
                        config_copy = config.copy()
                        config_copy.pop('dtype', None)
                        return super().from_config(config_copy)
                return RobustInit

            initializer_names = [
                'GlorotUniform', 'GlorotNormal', 'Zeros', 'Ones', 'Constant', 
                'RandomNormal', 'RandomUniform', 'TruncatedNormal', 
                'VarianceScaling', 'Orthogonal', 'Identity', 
                'LecunNormal', 'LecunUniform', 'HeNormal', 'HeUniform'
            ]
            
            for name in initializer_names:
                if hasattr(initializers_module, name):
                    custom_objects[name] = robust_initializer_factory(getattr(initializers_module, name))
                
    except Exception as e:
        logger.warning(f"Error creating custom objects: {e}")
        
    # Add aliases for robustness (handle 'keras.layers.Conv2D' vs 'Conv2D')
    for name, cls in list(custom_objects.items()):
        if '.' not in name:
            custom_objects[f"keras.layers.{name}"] = cls
            custom_objects[f"tf.keras.layers.{name}"] = cls
            # Also add lowercase variants just in case
            custom_objects[name.lower()] = cls
            
    # Add Functional alias for Keras 3 compatibility
    try:
        if hasattr(tf.keras, 'models'):
             # Map Functional to the Model class
             custom_objects['Functional'] = tf.keras.models.Model
             custom_objects['Model'] = tf.keras.models.Model
             # Also add module path variants that might be in the saved config
             custom_objects['keras.src.engine.functional.Functional'] = tf.keras.models.Model
             custom_objects['keras.engine.functional.Functional'] = tf.keras.models.Model
    except:
        pass

    return custom_objects


def patch_keras_layers():
    """
    Monkey-patch Keras layers to handle legacy arguments.
    This is necessary because Keras 3 deserialization can bypass custom_objects
    for standard layers, causing crashes with legacy arguments like 'batch_input_shape'.
    """
    try:
        import tensorflow as tf
        import keras
        import sys
        
        targets = [keras.layers]
        if hasattr(tf, 'keras') and hasattr(tf.keras, 'layers'):
            targets.append(tf.keras.layers)
            
        # Aggressive search for modules containing layers
        for module_name, module in list(sys.modules.items()):
            if 'keras' in module_name:
                 # Check for Conv2D
                 if hasattr(module, 'Conv2D'):
                    if module not in targets:
                        targets.append(module)
                 # Check for RandomRotation (preprocessing)
                 if hasattr(module, 'RandomRotation'):
                    if module not in targets:
                        targets.append(module)

        # Try to explicitly import internal modules
        try:
            import keras.src.layers.convolutional.conv2d
            targets.append(keras.src.layers.convolutional.conv2d)
        except ImportError:
            pass
            
        try:
            import keras.src.layers.preprocessing.image_preprocessing
            targets.append(keras.src.layers.preprocessing.image_preprocessing)
        except ImportError:
            pass

        layers_to_patch = [
            'Conv2D', 'Dense', 'MaxPooling2D', 'Flatten', 'Dropout', 
            'BatchNormalization', 'Rescaling', 'Resizing',
            'GlobalAveragePooling2D', 'AveragePooling2D', 'SeparableConv2D',
            'DepthwiseConv2D', 'Activation', 'Concatenate', 'Add', 'Multiply',
            'ZeroPadding2D', 'UpSampling2D', 'LeakyReLU', 'ELU', 'ThresholdedReLU',
            'Softmax', 'ReLU', 'Lambda', 'RandomRotation', 'RandomFlip', 
            'RandomZoom', 'RandomContrast', 'RandomTranslation'
        ]
        
        count = 0
        for target_module in targets:
            for layer_name in layers_to_patch:
                if not hasattr(target_module, layer_name):
                    continue
                    
                OriginalLayer = getattr(target_module, layer_name)
                
                # Check if already patched
                if getattr(OriginalLayer, '_is_robust_patch', False):
                    continue
                    
                # Create robust subclass
                class RobustLayer(OriginalLayer):
                    _is_robust_patch = True
                    
                    def __init__(self, *args, **kwargs):
                        # Clean kwargs
                        kwargs.pop('batch_input_shape', None)
                        kwargs.pop('input_shape', None)
                        kwargs.pop('batch_shape', None) # Also remove batch_shape
                        kwargs.pop('dim_ordering', None)
                        kwargs.pop('nb_filter', None)
                        kwargs.pop('nb_row', None)
                        kwargs.pop('nb_col', None)
                        kwargs.pop('value_range', None) # Legacy Preprocessing
                        super().__init__(*args, **kwargs)

                    @classmethod
                    def from_config(cls, config):
                        config_copy = config.copy()
                        keys_to_remove = [
                            'batch_input_shape', 'input_shape', 'batch_shape', 'dim_ordering', 
                            'nb_filter', 'nb_row', 'nb_col', 'value_range'
                        ]
                        for key in keys_to_remove:
                            config_copy.pop(key, None)
                        return super().from_config(config_copy)
                
                # Apply patch
                try:
                    setattr(target_module, layer_name, RobustLayer)
                    
                    # Also try to register it as the serializable class
                    if hasattr(keras, 'saving') and hasattr(keras.saving, 'register_keras_serializable'):
                        keras.saving.register_keras_serializable(package='keras.layers', name=layer_name)(RobustLayer)
                        # Register with empty package too just in case
                        keras.saving.register_keras_serializable(name=layer_name)(RobustLayer)
                    
                    count += 1
                except Exception as e:
                    pass
                    
        logger.info(f"Monkey-patched {count} Keras layers for robust loading")
        
    except Exception as e:
        logger.warning(f"Failed to patch Keras layers: {e}")


def patch_keras_initializers():
    """
    Monkey-patch Keras initializers to handle legacy arguments like 'dtype'.
    """
    try:
        import tensorflow as tf
        import keras
        import sys
        from keras.saving import register_keras_serializable
        
        targets = [keras.initializers]
        if hasattr(tf, 'keras') and hasattr(tf.keras, 'initializers'):
            targets.append(tf.keras.initializers)
            
        # Aggressive search for modules containing initializers
        for module_name, module in list(sys.modules.items()):
            if 'keras' in module_name and hasattr(module, 'GlorotUniform'):
                if module not in targets:
                    targets.append(module)
            
        initializers_to_patch = [
            'GlorotUniform', 'GlorotNormal', 'Zeros', 'Ones', 'Constant', 
            'RandomNormal', 'RandomUniform', 'TruncatedNormal', 
            'VarianceScaling', 'Orthogonal', 'Identity', 
            'LecunNormal', 'LecunUniform', 'HeNormal', 'HeUniform'
        ]
        
        count = 0
        for target_module in targets:
            for init_name in initializers_to_patch:
                if not hasattr(target_module, init_name):
                    continue
                    
                OriginalInit = getattr(target_module, init_name)
                
                # Check if already patched
                if getattr(OriginalInit, '_is_robust_patch', False):
                    continue
                    
                # Create robust subclass
                class RobustInit(OriginalInit):
                    _is_robust_patch = True
                    
                    def __init__(self, *args, **kwargs):
                        # Clean kwargs
                        kwargs.pop('dtype', None)
                        try:
                            super().__init__(*args, **kwargs)
                        except TypeError:
                            # Fallback for initializers that don't accept args
                            super().__init__()

                    @classmethod
                    def from_config(cls, config):
                        config_copy = config.copy()
                        config_copy.pop('dtype', None)
                        try:
                            return super().from_config(config_copy)
                        except Exception:
                            # Fallback: create instance with config
                            return cls(**config_copy)
                
                # Apply patch
                try:
                    setattr(target_module, init_name, RobustInit)
                    
                    # Also try to register it
                    if hasattr(keras, 'saving') and hasattr(keras.saving, 'register_keras_serializable'):
                        keras.saving.register_keras_serializable(package='keras.initializers', name=init_name)(RobustInit)
                        # Register with empty package too
                        keras.saving.register_keras_serializable(name=init_name)(RobustInit)
                    
                    count += 1
                except Exception as e:
                    pass
                    
        logger.info(f"Monkey-patched {count} Keras initializers for robust loading")
        
    except Exception as e:
        logger.warning(f"Failed to patch Keras initializers: {e}")


def patch_keras_deserialization():
    """
    Monkey-patch Keras deserialization to clean legacy arguments from config.
    """
    try:
        import keras.saving
        
        targets = []
        if hasattr(keras.saving, 'deserialize_keras_object'):
            targets.append((keras.saving, 'deserialize_keras_object'))
            
        try:
            from keras.src.saving import serialization
            if hasattr(serialization, 'deserialize_keras_object'):
                targets.append((serialization, 'deserialize_keras_object'))
        except ImportError:
            pass

        for module, func_name in targets:
            OriginalDeserialize = getattr(module, func_name)
            if getattr(OriginalDeserialize, '_is_robust_patch', False):
                continue
                
            def robust_deserialize(config, custom_objects=None, safe_mode=True, **kwargs):
                def clean_config(cfg_wrapper):
                    if isinstance(cfg_wrapper, dict) and 'config' in cfg_wrapper:
                        class_name = cfg_wrapper.get('class_name')
                        cfg = cfg_wrapper['config']
                        
                        if isinstance(cfg, dict):
                            # Handle InputLayer specifically
                            if class_name == 'InputLayer':
                                if 'batch_input_shape' in cfg:
                                    cfg['batch_shape'] = cfg.pop('batch_input_shape')
                                if 'input_shape' in cfg:
                                    cfg['shape'] = cfg.pop('input_shape')
                            
                            # Always clean legacy args from ANY layer config to be safe
                            keys_to_remove = [
                                'batch_input_shape', 'input_shape', 'batch_shape', 
                                'dim_ordering', 'nb_filter', 'nb_row', 'nb_col', 
                                'value_range', 'dtype'
                            ]
                            for key in keys_to_remove:
                                # Don't remove batch_shape/shape from InputLayer if we just set them
                                if class_name == 'InputLayer' and key in ['batch_shape', 'shape']:
                                    continue
                                if key in cfg:
                                    cfg.pop(key)
                                    
                            # Recurse into sub-configs (e.g. layers in Sequential/Functional)
                            if 'layers' in cfg and isinstance(cfg['layers'], list):
                                for layer in cfg['layers']:
                                    clean_config(layer)
                                    
                            # Also check for 'build_config' or other nested configs
                            if 'build_config' in cfg and isinstance(cfg['build_config'], dict):
                                if 'input_shape' in cfg['build_config']:
                                    cfg['build_config'].pop('input_shape')
                            
                clean_config(config)
                return OriginalDeserialize(config, custom_objects, safe_mode, **kwargs)
            
            robust_deserialize._is_robust_patch = True
            setattr(module, func_name, robust_deserialize)
            
        logger.info(f"Monkey-patched deserialize_keras_object in {len(targets)} locations")
        
    except Exception as e:
        logger.warning(f"Failed to patch deserialization: {e}")


def load_pytorch_model(path, name):
    """
    Load a PyTorch model (.pt or .pth).
    Supports both full models and state_dicts (assuming ResNet architectures).
    Returns a dict with a 'model' callable that mimics Keras .predict().
    """
    if not TORCH_AVAILABLE:
        return None
    
    try:
        device = torch.device('cpu') # Use CPU for safety
        
        # Load the file
        state_dict_or_model = torch.load(path, map_location=device)
        
        model = None
        num_classes = 0
        
        # Check if it's a state dict
        if isinstance(state_dict_or_model, dict) or isinstance(state_dict_or_model, collections.OrderedDict):
            # Heuristic to detect ResNet variant
            keys = list(state_dict_or_model.keys())
            
            # Determine num_classes from fc.bias or similar
            if 'fc.bias' in state_dict_or_model:
                num_classes = len(state_dict_or_model['fc.bias'])
            elif 'classifier.bias' in state_dict_or_model:
                 num_classes = len(state_dict_or_model['classifier.bias'])
            else:
                # Try to find the last weight/bias
                num_classes = 38 # Default fallback
            
            # Try ResNet50 first (most common)
            try:
                model = models.resnet50(pretrained=False)
                if num_classes != 1000:
                    model.fc = nn.Linear(model.fc.in_features, num_classes)
                model.load_state_dict(state_dict_or_model, strict=False)
            except Exception:
                # Try ResNet18
                try:
                    model = models.resnet18(pretrained=False)
                    if num_classes != 1000:
                        model.fc = nn.Linear(model.fc.in_features, num_classes)
                    model.load_state_dict(state_dict_or_model, strict=False)
                except Exception as e:
                    logger.error(f"Could not match state_dict architecture for {name}: {e}")
                    return None
        else:
            # Full model
            model = state_dict_or_model
            
        model.eval()
        
        # Wrapper function to mimic Keras .predict()
        def predict_wrapper(img_array):
            # img_array is (1, 224, 224, 3)
            # PyTorch expects (1, 3, 224, 224) normalized
            
            # Ensure float32
            img_array = img_array.astype(np.float32)
            
            # Check range and scale if needed (assume [0, 255] if max > 1)
            if img_array.max() > 1.0:
                 img_array = img_array / 255.0
            
            # Transpose to (1, 3, 224, 224)
            tensor = torch.from_numpy(img_array).permute(0, 3, 1, 2)
            
            # Normalize (Standard ImageNet)
            normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            # Apply to each image in batch (though usually batch=1 here)
            tensor_norm = torch.stack([normalize(t) for t in tensor])
            
            with torch.no_grad():
                output = model(tensor_norm)
                probs = torch.nn.functional.softmax(output, dim=1)
                return probs.numpy()
                
        return {
            'model': predict_wrapper,
            'name': name,
            'path': path,
            'type': 'torch',
            'classes': None, # Will be determined later
            'input_shape': (224, 224)
        }

    except Exception as e:
        logger.error(f"Failed to load PyTorch model {name}: {e}")
        return None


def _load_hf_labels_from_config(config_obj):
    """Extract ordered label list from HuggingFace config/id2label metadata."""
    id2label = None
    if isinstance(config_obj, dict):
        id2label = config_obj.get("id2label")
    else:
        id2label = getattr(config_obj, "id2label", None)

    labels = []
    if isinstance(id2label, dict) and id2label:
        try:
            keys = sorted(id2label.keys(), key=lambda x: int(x))
        except Exception:
            keys = sorted(id2label.keys(), key=lambda x: str(x))
        labels = [str(id2label[k]) for k in keys]
    return labels


def _safe_int_dim(value):
    """Convert model dimension objects to a positive int when possible."""
    try:
        dim = int(value)
    except Exception:
        return None
    return dim if dim > 0 else None


def normalize_input_shape(shape, default=(224, 224)):
    """Return a safe (height, width) tuple from arbitrary shape metadata."""
    default_shape = tuple(default) if default else None

    if shape is None:
        return default_shape

    if isinstance(shape, (int, float)):
        dim = _safe_int_dim(shape)
        return (dim, dim) if dim else default_shape

    try:
        dims = list(shape)
    except Exception:
        return default_shape

    # Common forms:
    # (H, W), (None, H, W, C), TensorShape([None, H, W, C])
    candidates = []
    if len(dims) >= 2:
        candidates.append((dims[0], dims[1]))
    if len(dims) >= 3:
        candidates.append((dims[1], dims[2]))
    for dim in dims:
        candidates.append((dim, dim))

    for h_raw, w_raw in candidates:
        h = _safe_int_dim(h_raw)
        w = _safe_int_dim(w_raw)
        if h and w:
            return (h, w)

    return default_shape


def _shape_hints_for_model(model_name):
    """Return model-name based input-size hints."""
    name_l = str(model_name or "").lower()
    hints = []

    if "fast_model_2" in name_l:
        hints.append((256, 256))
    if any(token in name_l for token in ("inception", "xception", "299")):
        hints.append((299, 299))
    if any(token in name_l for token in ("fast_model_1", "fast_model_3", "best_model", "lefora", "mobilenet")):
        hints.append((224, 224))
    if any(token in name_l for token in ("dataset39", "dataset6", "dataset3", "rice_disease_model", "plant_disease_recog_model_pwp")):
        hints.extend([(160, 160), (224, 224)])

    return hints


def build_input_shape_candidates(model_name, configured_shape):
    """Build ordered, unique input-size candidates for model inference retries."""
    candidates = []

    def _append(shape):
        normalized = normalize_input_shape(shape, default=None)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    _append(configured_shape)
    for hint in _shape_hints_for_model(model_name):
        _append(hint)
    for common in ((224, 224), (256, 256), (160, 160), (128, 128), (299, 299), (384, 384)):
        _append(common)

    if not candidates:
        candidates.append((224, 224))
    return candidates


def _is_shape_related_error(exc):
    text = str(exc or "").lower()
    tokens = (
        "expected shape",
        "found shape",
        "input shape",
        "incompatible shape",
        "shape mismatch",
        "dimension",
        "dimensions",
        "cannot reshape",
        "invalid size",
        "size mismatch",
    )
    return any(tok in text for tok in tokens)


def _is_image_read_error(exc):
    text = str(exc or "").lower()
    tokens = (
        "cannot identify image file",
        "cannot open",
        "broken data stream",
        "truncated",
        "corrupt",
        "image file is truncated",
    )
    return any(tok in text for tok in tokens)


def load_hf_directory_model(path, name):
    """Load a local HuggingFace image-classification model from a directory."""
    if not TRANSFORMERS_AVAILABLE:
        logger.warning(f"Skipping HuggingFace model {name}: transformers not available")
        return None
    if not TORCH_AVAILABLE:
        logger.warning(f"Skipping HuggingFace model {name}: torch not available")
        return None

    try:
        processor = AutoImageProcessor.from_pretrained(path, local_files_only=True)
        model = AutoModelForImageClassification.from_pretrained(path, local_files_only=True)
        model.eval()

        cfg = None
        try:
            cfg = AutoConfig.from_pretrained(path, local_files_only=True)
        except Exception:
            cfg = getattr(model, "config", None)

        classes = _load_hf_labels_from_config(cfg if cfg is not None else getattr(model, "config", None))
        if not classes:
            config_path = os.path.join(path, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    classes = _load_hf_labels_from_config(json.load(f))

        num_labels = getattr(getattr(model, "config", None), "num_labels", None)
        if (not classes) and num_labels:
            classes = [f"Class_{i}" for i in range(int(num_labels))]

        input_size = 224
        try:
            size_meta = getattr(processor, "size", None)
            if isinstance(size_meta, dict):
                input_size = int(
                    size_meta.get("height")
                    or size_meta.get("shortest_edge")
                    or size_meta.get("width")
                    or 224
                )
            elif isinstance(size_meta, int):
                input_size = int(size_meta)
        except Exception:
            input_size = 224

        return {
            "model": model,
            "processor": processor,
            "name": name,
            "path": path,
            "backend": "hf",
            "classes": classes,
            "input_shape": normalize_input_shape((input_size, input_size), default=(224, 224)),
            "num_classes": len(classes)
        }
    except Exception as e:
        logger.error(f"Failed to load HuggingFace model {name}: {e}")
        return None


def load_models(models_list=None, safe_mode_override=None):
    """
    Load multiple models from a list of model paths
    Supports unsafe deserialization for Lambda layers with proper warnings
    
    Args:
        models_list: List of model dicts from find_local_models(), or None to auto-discover
        safe_mode_override: If True, enable unsafe deserialization (for local trusted models)
    
    Returns:
        List of loaded model info dicts
    """
    global _MODEL_CACHE
    
    # Return cached models if already loaded
    if _MODEL_CACHE['loaded'] and len(_MODEL_CACHE['models']) > 0:
        logger.debug(f"Using {len(_MODEL_CACHE['models'])} cached models")
        enabled_models = get_enabled_models()
        if enabled_models:
            return [m for m in _MODEL_CACHE['models'] if m['name'] in enabled_models]
        return _MODEL_CACHE['models']
    
    # Auto-discover if no list provided
    if models_list is None:
        models_list = find_local_models()
        
        # Filter by enabled_models from config
        enabled_models = get_enabled_models()
        if enabled_models:
            original_count = len(models_list)
            models_list = [m for m in models_list if m['name'] in enabled_models]
            logger.info(f"Filtered models using config: {len(models_list)}/{original_count} enabled")
    
    # Prepare custom objects for robust loading
    custom_objs = get_robust_custom_objects()
    logger.info(f"Created {len(custom_objs)} custom objects for robust loading: {list(custom_objs.keys())}")

    try:
        import tensorflow as tf
        import warnings
        
        # Register custom objects globally to ensure they are picked up
        try:
            tf.keras.utils.get_custom_objects().update(custom_objs)
            logger.info("Registered custom objects globally")
        except Exception as e:
            logger.warning(f"Failed to register custom objects globally: {e}")

        # Suppress all TensorFlow and Keras warnings
        tf.get_logger().setLevel('ERROR')
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress all TF logs
        
        # Suppress Python warnings
        warnings.filterwarnings('ignore', category=UserWarning)
        warnings.filterwarnings('ignore', category=FutureWarning)
        warnings.filterwarnings('ignore', category=DeprecationWarning)
        warnings.filterwarnings('ignore', module='tensorflow')
        warnings.filterwarnings('ignore', module='keras')
        
        # Import keras with compatibility handling
        try:
            import keras
            # Try to enable unsafe deserialization for incompatible models
            try:
                if hasattr(keras, 'config') and hasattr(keras.config, 'enable_unsafe_deserialization'):
                    keras.config.enable_unsafe_deserialization()
                    unsafe_enabled = True
                else:
                    # Keras 2.x doesn't have this - try alternative approach
                    unsafe_enabled = False
            except (AttributeError, Exception) as e:
                # If enable_unsafe_deserialization doesn't exist, try alternative
                try:
                    # For Keras 3.x, try setting environment variable
                    os.environ['KERAS_ALLOW_UNSAFE_DESERIALIZATION'] = '1'
                    unsafe_enabled = True
                except:
                    unsafe_enabled = False
        except ImportError:
            # Fallback: use tf.keras
            keras = tf.keras
            unsafe_enabled = False
        
        # Apply monkey patch for robust loading
        patch_keras_layers()
        patch_keras_initializers()
        patch_keras_deserialization()
        
        # Register custom objects with keras.saving if available
        if hasattr(keras, 'saving') and hasattr(keras.saving, 'get_custom_objects'):
            try:
                keras.saving.get_custom_objects().update(custom_objs)
                logger.info("Registered custom objects with keras.saving")
            except Exception as e:
                logger.warning(f"Failed to register custom objects with keras.saving: {e}")
        
        import tempfile
        import shutil
        import time
        
        # Enable unsafe deserialization by default for incompatible models
        if safe_mode_override is True or safe_mode_override is None:
            if not unsafe_enabled:
                try:
                    # Try multiple methods to enable unsafe deserialization
                    if hasattr(keras, 'config') and hasattr(keras.config, 'enable_unsafe_deserialization'):
                        keras.config.enable_unsafe_deserialization()
                        unsafe_enabled = True
                    os.environ['KERAS_ALLOW_UNSAFE_DESERIALIZATION'] = '1'
                    unsafe_enabled = True
                except Exception:
                    pass
        
        loaded_models = []
        
        logger.info("=" * 60)
        logger.info(" Model Loader")
        logger.info("=" * 60)
        
        # Print discovered models
        model_info_str = ", ".join([f"{m['name']} ({m['size']/(1024*1024):.1f}MB)" for m in models_list])
        logger.info(f"Found models: {model_info_str}")
        logger.info(f"Loading {len(models_list)} model(s)...")
        if unsafe_enabled:
            logger.info("Enabled unsafe deserialization = True")
        
        # Track compatibility issues for summary
        compatibility_issues = []
        corrupted_models = []
        failed_models = []
        
        # Try loading each model
        for model_info in models_list:
            candidate_path = model_info['path']
            candidate_file = model_info['name']
            candidate_size = model_info['size']
            candidate_type = model_info.get('type', '')
            candidate_ext = model_info.get('ext', '')
            
            try:
                logger.info(f"Trying to load: {candidate_file}")
                
                # Ensure path is absolute and properly formatted
                if not os.path.isabs(candidate_path):
                    candidate_path = os.path.abspath(candidate_path)
                # Normalize path to handle Windows drive letters and spaces correctly
                candidate_path = os.path.normpath(candidate_path)
                candidate_path = os.path.abspath(candidate_path)
                # Convert to string and ensure no double colons or other path issues
                candidate_path = str(candidate_path).replace('::', ':')

                # Local HuggingFace directory model
                if candidate_type == 'hf_dir' or candidate_ext == '.hfdir':
                    if not os.path.exists(candidate_path) or not os.path.isdir(candidate_path):
                        logger.warning(f"Failed to load {candidate_file}: Directory not found: {candidate_path}")
                        failed_models.append(candidate_file)
                        continue
                    hf_result = load_hf_directory_model(candidate_path, candidate_file)
                    if hf_result:
                        hf_result['size_mb'] = candidate_size / (1024 * 1024)
                        hf_result['size_bytes'] = candidate_size
                        loaded_models.append(hf_result)
                        logger.info(f"Successfully loaded {candidate_file} (HuggingFace directory)")
                    else:
                        failed_models.append(candidate_file)
                    continue
                
                if not os.path.exists(candidate_path) or not os.path.isfile(candidate_path):
                    logger.warning(f"⚠️  Failed to load {candidate_file}: File not found: {candidate_path}")
                    failed_models.append(candidate_file)
                    continue
                
                # Check for PyTorch models
                if candidate_file.endswith(('.pt', '.pth')) or candidate_ext in ['.pt', '.pth']:
                    if not TORCH_AVAILABLE:
                        logger.warning(f"Skipping PyTorch model {candidate_file}: torch not available")
                        continue
                        
                    pt_result = load_pytorch_model(candidate_path, candidate_file)
                    if pt_result:
                        pt_result['size'] = candidate_size
                        loaded_models.append(pt_result)
                        logger.info(f"Successfully loaded {candidate_file} (PyTorch)")
                    else:
                        failed_models.append(candidate_file)
                    continue
                else:
                    # Keras/TF Model Loading
                    model = None
                    
                    try:
                        logger.info(f"Attempting load from: {candidate_path}")
                        # Try loading with safe_mode=False (Keras 3 compatibility) and custom objects
                        try:
                            model = tf.keras.models.load_model(candidate_path, compile=False, safe_mode=False, custom_objects=custom_objs)
                        except TypeError:
                            # Fallback for older Keras versions without safe_mode
                            model = tf.keras.models.load_model(candidate_path, compile=False, custom_objects=custom_objs)
                        
                        logger.info(f"Successfully loaded {candidate_file}")
                    
                    except Exception as e:
                        # First failure
                        error_str = str(e).lower()
                        logger.warning(f"Initial load failed for {candidate_file}: {e}")
                        
                        # Check if we should try unsafe deserialization
                        should_retry_unsafe = False
                        if "unsafe" in error_str or "deserialization" in error_str:
                             should_retry_unsafe = True
                        
                        # Enable unsafe deserialization if not already enabled
                        if should_retry_unsafe and not unsafe_enabled:
                            try:
                                if hasattr(keras, 'config') and hasattr(keras.config, 'enable_unsafe_deserialization'):
                                    keras.config.enable_unsafe_deserialization()
                                    os.environ['KERAS_ALLOW_UNSAFE_DESERIALIZATION'] = '1'
                                    unsafe_enabled = True
                                    logger.info("Enabled unsafe deserialization globally")
                            except:
                                pass
                        
                        # Retry if unsafe is enabled (globally or just now)
                        if unsafe_enabled:
                            try:
                                logger.info(f"Retrying {candidate_file} with unsafe deserialization...")
                                try:
                                    model = tf.keras.models.load_model(candidate_path, compile=False, safe_mode=False, custom_objects=custom_objs)
                                except TypeError:
                                    model = tf.keras.models.load_model(candidate_path, compile=False, custom_objects=custom_objs)
                                logger.info(f"Successfully loaded {candidate_file} (unsafe mode)")
                            except Exception as e2:
                                logger.error(f"Final failure loading {candidate_file}: {e2}")
                                failed_models.append(candidate_file)
                                continue
                        else:
                            # Not retrying
                            failed_models.append(candidate_file)
                            continue

                if model is None:
                    # Should have been handled by continue above, but just in case
                    continue
                
                # Try to compile if needed
                try:
                    if not hasattr(model, '_is_compiled') or not model._is_compiled:
                        model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
                except Exception:
                    pass  # Compilation not critical
                
                # Get input shape
                input_shape = None
                try:
                    if hasattr(model, 'input_shape') and model.input_shape:
                        input_shape = model.input_shape[1:3]  # (height, width)
                    elif hasattr(model, 'input') and model.input is not None:
                        input_shape = tuple(model.input.shape[1:3])
                except:
                    pass
                if input_shape is None:
                    input_shape = (160, 160)  # Default
                input_shape = normalize_input_shape(input_shape, default=(160, 160))
                
                # Get number of classes
                num_classes = None
                try:
                    output_shape = model.output_shape
                    if output_shape and len(output_shape) > 1:
                        num_classes = output_shape[-1]
                except:
                    pass
                
                # Load classes/labels
                classes = load_label_map()
                
                # Enforce specific labels for dataset16 and dataset17 and dataset39
                is_known_dataset = False
                if 'dataset16' in candidate_file:
                    classes = DATASET16_LABELS
                    is_known_dataset = True
                    logger.info(f"Using specific labels for {candidate_file}")
                elif 'dataset17' in candidate_file:
                    classes = DATASET17_LABELS
                    is_known_dataset = True
                    logger.info(f"Using specific labels for {candidate_file}")
                elif 'plant_disease_recog_model_pwp' in candidate_file or 'dataset39' in candidate_file:
                    classes = DATASET39_LABELS
                    is_known_dataset = True
                    logger.info(f"Using specific labels for {candidate_file}")
                elif 'dataset3' in candidate_file:
                    classes = DATASET3_LABELS
                    is_known_dataset = True
                    logger.info(f"Using specific labels for {candidate_file}")
                elif 'dataset6' in candidate_file:
                    classes = DATASET39_LABELS
                    is_known_dataset = True
                    logger.info(f"Using specific labels for {candidate_file}")
                elif 'dataset12' in candidate_file:
                    classes = DATASET12_LABELS
                    is_known_dataset = True
                    logger.info(f"Using specific labels for {candidate_file}")
                elif 'rice_disease_model' in candidate_file:
                    classes = RICE_LABELS
                    is_known_dataset = True
                    logger.info(f"Using specific labels for {candidate_file}")
                elif 'Plant Disease Detection.h5' in candidate_file:
                    classes = DATASET_EXTRA_LABELS
                    is_known_dataset = True
                    logger.info(f"Using specific labels for {candidate_file}")
                elif 'trained_model.h5' in candidate_file or 'final_model.h5' in candidate_file:
                    # Assumed to be standard 38 classes
                    classes = DATASET39_LABELS[:38]
                    is_known_dataset = True
                    logger.info(f"Using specific labels for {candidate_file}")
                elif 'simple_model.keras' in candidate_file:
                    # 3 classes - unknown content, use generic
                    classes = ["Class_0", "Class_1", "Class_2"]
                    is_known_dataset = True
                    logger.info(f"Using specific labels for {candidate_file}")
                elif 'best_model.keras' in candidate_file.lower() or 'final_model.keras' in candidate_file.lower():
                    classes = DETECTION_BEST_MODEL_LABELS
                    is_known_dataset = True
                    logger.info(f"Using detection labels for {candidate_file}")
                elif 'lefora.keras' in candidate_file.lower():
                    classes = DETECTION_LEFORA_LABELS
                    is_known_dataset = True
                    logger.info(f"Using detection labels for {candidate_file}")
                elif 'best_plant_detector.keras' in candidate_file.lower():
                    classes = ['plant_score']
                    is_known_dataset = True
                    logger.info(f"Using detector labels for {candidate_file}")
                
                # Web Models Labels
                elif 'plant_disease.h5' in candidate_file: # Web2
                    classes = ['Corn-Common_rust', 'Potato-Early_blight', 'Tomato-Bacterial_spot']
                    is_known_dataset = True
                    logger.info(f"Using specific labels for {candidate_file}")
                elif 'model-Corn-Leaf-Diseases-Exception-92.12.h5' in candidate_file: # Web3
                    classes = ['Blight', 'Common_Rust', 'Gray_Leaf_Spot', 'Healthy']
                    is_known_dataset = True
                    logger.info(f"Using specific labels for {candidate_file}")
                elif 'tomato_disese_model_V1.keras' in candidate_file: # Web4
                    classes = ['Bacterial_spot', 'Healthy', 'Septoria_leaf_spot', 
                               'Spider_mites_Two_spotted_spider_mite', 'YellowLeaf__Curl_Virus']
                    is_known_dataset = True
                    logger.info(f"Using specific labels for {candidate_file}")

                if classes is None or (num_classes and len(classes) != num_classes and not is_known_dataset):
                    # Generate from model output shape
                    if num_classes:
                        classes = generate_label_map(num_classes)
                    else:
                        classes = [f"Class_{i}" for i in range(39)]  # Default
                
                # For known datasets, if mismatch, log it but KEEP the labels (unless completely wrong size)
                if is_known_dataset and num_classes and len(classes) != num_classes:
                    logger.warning(f"Class count mismatch for known dataset {candidate_file}: Labels={len(classes)} vs Model={num_classes}. Keeping specific labels.")
                    # If model has MORE classes than labels, extend labels
                    if num_classes > len(classes):
                        classes.extend([f"Class_{i}" for i in range(len(classes), num_classes)])
                    # If model has FEWER classes, we just won't use the extra labels (safe)

                
                # Verify class count matches model output
                if num_classes and len(classes) != num_classes and not is_known_dataset:
                    logger.warning(f"Class count mismatch: {len(classes)} vs {num_classes}, generating new map")
                    classes = generate_label_map(num_classes)
                
                size_mb = candidate_size / (1024 * 1024)
                model_info_dict = {
                    'model': model,
                    'name': candidate_file,
                    'path': candidate_path,
                    'classes': classes,
                    'input_shape': input_shape,
                    'size_mb': size_mb,
                    'size_bytes': candidate_size,
                    'backend': 'tf',
                    'num_classes': len(classes)
                }
                
                # Check if model is enabled
                enabled_models = get_enabled_models()
                if enabled_models and candidate_file not in enabled_models:
                    logger.info(f"Skipping disabled model: {candidate_file}")
                    continue
                
                # dataset13 (Binary classifier) is now allowed per user request
                if "dataset13" in candidate_file or "dataset13.keras" in candidate_file:
                     logger.info(f"Including binary model: {candidate_file}")

                loaded_models.append(model_info_dict)
                logger.info(f"✅ Loaded: {candidate_file} ({size_mb:.2f} MB, {len(classes)} classes)")
                
            except Exception as e:
                error_str = str(e).lower()
                # Check if it's a compatibility issue
                if ("glorotuniform" in error_str or 
                    "could not be deserialized" in error_str or 
                    "keras 3" in error_str or 
                    "keras3" in error_str):
                    compatibility_issues.append(candidate_file)
                elif "bad marshal" in error_str or "unknown type code" in error_str:
                    corrupted_models.append(candidate_file)
                else:
                    failed_models.append(candidate_file)
                logger.warning(f"Failed to load {candidate_file}: {str(e)[:150]}")
                logger.debug(traceback.format_exc())
                continue
        
        if len(loaded_models) == 0:
            error_msg = (
                f"\n❌ Failed to load any models from {MODEL_DIR}/\n"
                f"   Please ensure at least one valid .keras or .h5 model file exists.\n"
                f"   Some models may be corrupted or incompatible with Keras 3.0."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        _MODEL_CACHE['models'] = loaded_models
        _MODEL_CACHE['loaded'] = True
        
        # Print summary of loading results
        total_attempted = len(models_list)
        total_loaded = len(loaded_models)
        total_failed = total_attempted - total_loaded
        
        if total_failed > 0:
            logger.info("=" * 60)
            logger.info("📊 Model Loading Summary:")
            logger.info(f"   ✅ Successfully loaded: {total_loaded} model(s)")
            if compatibility_issues:
                logger.info(f"   ⚠️  Keras 3.0 incompatible: {len(compatibility_issues)} model(s)")
                for model in compatibility_issues[:3]:  # Show first 3
                    logger.info(f"      - {model}")
                if len(compatibility_issues) > 3:
                    logger.info(f"      ... and {len(compatibility_issues) - 3} more")
            if corrupted_models:
                logger.info(f"   ❌ Corrupted: {len(corrupted_models)} model(s)")
                for model in corrupted_models[:3]:  # Show first 3
                    logger.info(f"      - {model}")
                if len(corrupted_models) > 3:
                    logger.info(f"      ... and {len(corrupted_models) - 3} more")
            if failed_models:
                logger.info(f"   ⚠️  Failed to load: {len(failed_models)} model(s)")
            logger.info("=" * 60)
        
        logger.info(f"✅ Successfully loaded {len(loaded_models)} model(s) (classes: {loaded_models[0]['num_classes'] if loaded_models else 'N/A'})")
        logger.info("=" * 60)
        
        return loaded_models
        
    except Exception as e:
        error_msg = f"Failed to load models: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        raise RuntimeError(error_msg)


def load_all_models():
    """Load ALL working models and cache them globally (backward compatibility)"""
    try:
        return load_models()
    except Exception as e:
        logger.error(f"Error in load_all_models: {e}")
        return []


def load_model_singleton():
    """Backward compatibility: returns first loaded model"""
    models = load_all_models()
    if len(models) == 0:
        raise RuntimeError("No models loaded")
    first_model = models[0]
    return (
        first_model['model'],
        first_model['classes'],
        'tf',
        first_model['name']
    )


def safe_load_model():
    """Public API for model loading - uses singleton cache"""
    return load_model_singleton()


def load_image_rgb(image_path):
    """Open an image safely, apply EXIF orientation, and return an RGB PIL image."""
    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        rgb = img.convert('RGB')
        rgb.load()
    return rgb


def preprocess_image(image_path, target_size=None):
    """
    Preprocess image for model inference
    Automatically detects model input size or uses default
    Enhanced preprocessing for better accuracy
    """
    # Get target size from parameter or use default
    target_size = normalize_input_shape(target_size, default=(224, 224))
    
    # Load and convert to RGB
    img = load_image_rgb(image_path)
    
    # Enhance image quality before resizing
    from PIL import ImageEnhance, ImageFilter
    
    # Slight sharpening to improve edge detection
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
    
    # Enhance contrast slightly
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.1)
    
    # Resize to target size (high-quality resampling)
    img = img.resize(target_size, Image.Resampling.LANCZOS)
    
    # Convert to numpy array
    img_array = np.array(img).astype(np.float32)
    
    # Normalize to [0, 1] by dividing by 255.0 (generic default)
    img_array = img_array / 255.0
    
    # Add batch dimension
    img_array = np.expand_dims(img_array, axis=0)
    
    return img_array


def detect_disease_spots(image_path, max_boxes=8):
    try:
        import cv2
        import numpy as np
    except Exception as e:
        logger.warning(f"OpenCV not available for spot detection: {e}")
        return []
    if not os.path.exists(image_path):
        return []
    img = cv2.imread(image_path)
    if img is None:
        return []
    h, w = img.shape[:2]
    if h == 0 or w == 0:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (11, 11), 0)
    diff = cv2.absdiff(gray, blur)
    _, thresh = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    min_area = (w * h) * 0.002
    for c in cnts:
        x, y, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        if area < min_area:
            continue
        left = (x / float(w)) * 100.0
        top = (y / float(h)) * 100.0
        width = (bw / float(w)) * 100.0
        height = (bh / float(h)) * 100.0
        boxes.append({
            "x": round(left, 2),
            "y": round(top, 2),
            "w": round(width, 2),
            "h": round(height, 2)
        })
    boxes = sorted(boxes, key=lambda b: b["w"] * b["h"], reverse=True)
    return boxes[:max_boxes]

def preprocess_for_model(model_name, image_path, target_size):
    """
    Model-aware preprocessing:
    - RAW (0-255) is handled elsewhere for dataset39/dataset6/dataset3/rice/legacy
    - MobileNetV2-based models (dataset16/dataset17 and similar) use mobilenet_v2.preprocess_input
    - Otherwise use simple 0-1 normalization
    """
    target_size = normalize_input_shape(target_size, default=(224, 224))
    img = load_image_rgb(image_path)
    from PIL import ImageEnhance, ImageFilter
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.1)
    img = img.resize(target_size, Image.Resampling.LANCZOS)
    arr = np.array(img).astype(np.float32)
    try:
        if any(x in model_name for x in ['dataset16', 'dataset17', 'mobilenetv2']):
            import tensorflow as tf
            arr = tf.keras.applications.mobilenet_v2.preprocess_input(arr)
            arr = np.expand_dims(arr, axis=0)
            return arr
    except Exception:
        pass
    arr = arr / 255.0
    arr = np.expand_dims(arr, axis=0)
    return arr


def load_disease_names():
    """Load disease names from JSON file with caching"""
    global _DISEASE_NAMES
    if '_DISEASE_NAMES' not in globals():
        _DISEASE_NAMES = None
        
    if _DISEASE_NAMES is not None:
        return _DISEASE_NAMES
    
    # Try m_models first (preferred location)
    paths = [
        os.path.join(M_MODELS_DIR, "disease_names.json"),
        os.path.join(MODEL_DIR, "disease_names.json")
    ]
    
    for path in paths:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    _DISEASE_NAMES = json.load(f)
                return _DISEASE_NAMES
        except Exception as e:
            logger.warning(f"Failed to load disease_names.json from {path}: {e}")
    
    _DISEASE_NAMES = {}
    return _DISEASE_NAMES


NON_PLANT_LABEL_TOKENS = {
    "invalid",
    "not_leaf",
    "not leaf",
    "background_without_leaves",
    "background without leaves",
    "non_leaf",
}


def _is_non_plant_label(label):
    token = str(label or "").strip().lower().replace("-", " ")
    return token in NON_PLANT_LABEL_TOKENS


def _extract_plant_token(class_label):
    """Match /web streamlit extraction logic for supported plants."""
    c = str(class_label or "")
    if " - " in c:
        plant = c.split(" - ")[0]
    elif "___" in c:
        plant = c.split("___")[0]
    else:
        plant = c.split("_")[0]
    return plant.strip()


def _normalize_plant_name(plant):
    p = str(plant or "").replace("_", " ").strip()
    return " ".join(w.capitalize() for w in p.split())


def _load_local_hf_model_labels(model_dir_name):
    """Read labels directly from local HF config to avoid loading model weights."""
    cfg_path = os.path.join(M_MODELS_DIR, model_dir_name, "config.json")
    try:
        if not os.path.exists(cfg_path):
            return []
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        labels = _load_hf_labels_from_config(cfg)
        return labels
    except Exception as e:
        logger.warning(f"Could not read labels from {cfg_path}: {e}")
        return []


def get_detection_supported_plants():
    """
    Return supported plant names for the active detection model family.
    """
    model1 = sorted({_normalize_plant_name(_extract_plant_token(c)) for c in DETECTION_BEST_MODEL_LABELS if c})
    model2 = sorted({
        _normalize_plant_name(_extract_plant_token(c))
        for c in DETECTION_LEFORA_LABELS
        if c and _extract_plant_token(c).lower() not in DETECTION_LEFORA_EXCLUDED_PLANTS
    })
    fast1_labels = _load_local_hf_model_labels("fast_model_1")
    fast2_labels = _load_local_hf_model_labels("fast_model_2")
    fast3_labels = _load_local_hf_model_labels("fast_model_3")

    fast1_plants = sorted({
        _normalize_plant_name(_extract_plant_token(c))
        for c in fast1_labels
        if c and not _is_non_plant_label(_extract_plant_token(c))
    })
    fast2_plants = sorted({
        _normalize_plant_name(_extract_plant_token(c))
        for c in fast2_labels
        if c and not _is_non_plant_label(_extract_plant_token(c))
    })
    fast3_plants = sorted({
        _normalize_plant_name(_extract_plant_token(c))
        for c in fast3_labels
        if c and not _is_non_plant_label(_extract_plant_token(c))
    })

    return {
        "best_model": model1,
        "lefora": model2,
        "fast_model_1": fast1_plants,
        "fast_model_2": fast2_plants,
        "fast_model_3": fast3_plants,
    }


def format_label(label):
    """Format class label for display"""
    if label is None:
        return "Unknown"
    if _is_non_plant_label(label):
        return "Unknown"
    
    # Check for Class_X format
    if label.startswith('Class_'):
        disease_names = load_disease_names()
        if label in disease_names:
            return disease_names[label] # Assuming value is the name or description? 
            # Wait, disease_names.json maps Name -> Description.
            # If label is Class_0, it might map Class_0 -> "Apple - Apple Scab".
            # But the JSON I read earlier mapped "Apple - Apple Scab" -> "Description".
            # So looking up Class_X in THAT json won't work unless it ALSO contains Class_X keys.
            # I should assume Class_X lookup might need a DIFFERENT file (label_map.json?)
            # But existing code checked disease_names.json for Class_X. 
            # If disease_names.json ONLY has "Name"->"Description", then the existing code for Class_X lookup was WRONG or checking the wrong file.
            pass
            
        class_num = label.replace('Class_', '')
        return f"Class {class_num}"
    
    # Check for old format (Plant - Disease)
    if ' - ' in label:
        return label
    
    # Otherwise, format generic class names
    formatted = label.replace('___', ' - ').replace('_', ' ')
    # Capitalize first letter of each word
    formatted = ' '.join(word.capitalize() for word in formatted.split())
    
    # Validate against disease_names.json keys
    disease_names = load_disease_names()
    if disease_names and formatted in disease_names:
        return formatted
        
    return formatted


def predict_with_model(model_info, image_path, k=TOP_K):
    """Predict with a single model"""
    try:
        model = model_info['model']
        classes = model_info['classes']
        model_name = model_info['name']
        input_shape = normalize_input_shape(model_info.get('input_shape', (160, 160)), default=(160, 160))
        input_shape_candidates = build_input_shape_candidates(model_name, input_shape)
        
        if model is None or not classes:
            logger.error(f"Model or classes missing for {model_name}")
            return None
        
        # Check if image file exists
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        backend = str(model_info.get('backend', 'tf')).lower()

        if backend == 'hf':
            if not TORCH_AVAILABLE:
                raise RuntimeError(f"torch is required for HuggingFace model inference: {model_name}")
            processor = model_info.get('processor')
            if processor is None:
                raise RuntimeError(f"Missing processor for HuggingFace model: {model_name}")
            try:
                img = load_image_rgb(image_path)
                inputs = processor(images=img, return_tensors="pt")
                with torch.no_grad():
                    outputs = model(**inputs)
                    logits = outputs.logits
                    predictions = torch.nn.functional.softmax(logits, dim=-1).cpu().numpy()
            except Exception as e:
                logger.error(f"HuggingFace prediction failed for {model_name}: {e}")
                raise
        else:
            # TensorFlow/Keras path with model-specific size fallbacks.
            raw_input_models = (
                'dataset39',
                'dataset6',
                'dataset3',
                'rice_disease_model',
                'plant_disease_recog_model_pwp',
                'trained_model',
                'final_model',
                'Plant Disease Detection',
            )
            predictions = None

            for idx, candidate_shape in enumerate(input_shape_candidates):
                try:
                    if any(x in model_name for x in raw_input_models):
                        img = load_image_rgb(image_path)
                        img = img.resize(candidate_shape, Image.Resampling.LANCZOS)
                        img_array = np.array(img).astype(np.float32)
                        img_array = np.expand_dims(img_array, axis=0)
                    else:
                        img_array = preprocess_for_model(model_name, image_path, candidate_shape)

                    print(f"DEBUG: calling model.predict for {model_name} (shape={candidate_shape})...", flush=True)
                    predictions = model.predict(img_array, verbose=0)
                    print(f"DEBUG: model.predict returned for {model_name}", flush=True)
                    if idx > 0:
                        logger.info(f"Recovered {model_name} prediction using fallback shape {candidate_shape}")
                    break
                except Exception as e:
                    if _is_image_read_error(e):
                        logger.error(f"Image read failed for {model_name}: {e}")
                        raise

                    can_retry = _is_shape_related_error(e) and idx < (len(input_shape_candidates) - 1)
                    if can_retry:
                        logger.warning(
                            f"Input size mismatch for {model_name} at {candidate_shape}: {type(e).__name__}: {e}. "
                            f"Retrying next candidate."
                        )
                        continue

                    logger.error(f"Model prediction failed for {model_name}: {type(e).__name__}: {e}")
                    raise

            if predictions is None:
                raise RuntimeError(f"No predictions returned for {model_name}")

        # Model uses sigmoid activation, outputs are probabilities [0,1] per class
        raw_probs = predictions[0].astype(np.float32)
        
        # Check if outputs look like logits (negative values) or probabilities
        if np.any(raw_probs < 0) or np.max(raw_probs) > 1.0:
            tf_module = get_tf()
            if tf_module:
                raw_probs = tf_module.nn.sigmoid(raw_probs).numpy()
            else:
                # Fallback to numpy sigmoid
                raw_probs = 1 / (1 + np.exp(-raw_probs))
        
        # Calculate adjusted probabilities for display
        max_prob = np.max(raw_probs)
        high_conf_count = np.sum(raw_probs > 0.9)
        prob_sum = np.sum(raw_probs)
        num_classes = len(raw_probs)
        
        # Default probability vector
        probs = raw_probs.copy() if prob_sum > 0 else raw_probs
        
        # Domain-specific handling for Rice models
        formatted_labels = [format_label(lbl if i < len(classes) else f"Class_{i}") for i, lbl in enumerate(classes)]
        if 'rice_disease_model' in model_name:
            # Filter for Rice classes only (case-insensitive) but allow explicit unknowns if confidence is high
            rice_indices = [i for i, fl in enumerate(formatted_labels) if 'rice' in fl.lower() and 'unknown' not in fl.lower()]
            
            # If explicit RICE_MAPPING exists, trust it more than string matching
            mapping = get_mapping_for_model(model_name)
            if mapping:
                 mapped_rice_indices = [k for k, v in mapping.items() if v in [39, 40, 41, 42] or (v < 39 and "rice" in DATASET39_LABELS[v].lower())]
                 # Combine with string matching results
                 rice_indices = list(set(rice_indices + mapped_rice_indices))

            if len(rice_indices) > 0:
                # Restrict to rice-only classes
                # DO NOT re-normalize probabilities to prevent hallucinations (e.g. boosting 1% -> 100%)
                # If the model predicts a non-rice class (Unknown_X) with high confidence, 
                # the rice classes will have low confidence, resulting in a correct "Unknown" output.
                
                sel = np.array(rice_indices, dtype=int)
                rice_probs = probs[sel]
                
                # Zero out everything
                probs = np.zeros_like(probs)
                
                # Restore only rice probabilities (unscaled)
                probs[sel] = rice_probs
            else:
                # No rice classes found in labels map; force unknown with low confidence
                probs = np.zeros_like(probs)
        else:
            # Generic uncertainty handling
            if high_conf_count > 3 and prob_sum > 8.0:
                top_idx = np.argmax(raw_probs)
                second_max = np.partition(raw_probs, -2)[-2] if len(raw_probs) > 1 else max_prob
                uncertainty_penalty = min(0.6, (high_conf_count - 1) / num_classes)
                if max_prob - second_max > 0.3:
                    uncertainty_penalty *= 0.5
                probs[top_idx] = raw_probs[top_idx] * (1.0 - uncertainty_penalty)
                high_mask = raw_probs > 0.9
                probs[high_mask] = raw_probs[high_mask] * (1.0 - uncertainty_penalty * 0.8)
            elif max_prob <= 0.3 and prob_sum > 0:
                probs = raw_probs / prob_sum

        # Match /web behavior: Lefora excludes specific plant groups entirely.
        if 'lefora.keras' in model_name.lower():
            for i, raw_label in enumerate(classes):
                plant = _extract_plant_token(raw_label).lower()
                if plant in DETECTION_LEFORA_EXCLUDED_PLANTS:
                    probs[i] = 0.0
        
        # Get top-k
        topk_indices = np.argsort(probs)[::-1][:k]
        topk_results = []
        
        for idx in topk_indices:
            label = classes[idx] if idx < len(classes) else f"Class_{idx}"
            prob = float(probs[idx])
            confidence = round(prob * 100, 2)
            formatted_label = format_label(label)
            topk_results.append({
                "label": formatted_label,
                "raw_label": label,
                "prob": prob,
                "confidence": confidence
            })
        
        top1_confidence = topk_results[0]["confidence"] if topk_results else 0
        # Stricter unknown threshold for rice models
        if 'rice_disease_model' in model_name:
            is_unknown = top1_confidence < 50
            # Clamp overly-confident Healthy predictions to moderate confidence
            if topk_results and 'healthy' in topk_results[0]['label'].lower() and top1_confidence > 80:
                topk_results[0]['confidence'] = 55.0
                topk_results[0]['prob'] = round(topk_results[0]['confidence'] / 100.0, 4)
        else:
            is_unknown = top1_confidence < 30
        if topk_results and str(topk_results[0].get('label', '')).strip().lower() == 'unknown':
            is_unknown = True
        confidence_message = "Please upload a clearer leaf image. Model is unsure." if is_unknown else None
        
        # Format model source for display
        model_source = model_name.replace('.keras','').replace('.h5','').replace('.pt','').replace('.pth','')
        model_source = model_source.replace('_', ' ').replace('-', ' ')
        model_source = model_source.replace('web', 'Web ').replace('dataset', 'Dataset ')
        model_source = model_source.title().strip()
        
        return {
            "model_name": model_name,
            "model_source": model_source,
            "topk": topk_results,
            "unknown": is_unknown,
            "confidence_message": confidence_message,
        }
    except Exception as e:
        logger.error(f"Error in predict_with_model for {model_info.get('name', 'unknown')}: {type(e).__name__}: {str(e)}")
        logger.error(traceback.format_exc())
        raise



# Removed duplicate mappings and get_mapping_for_model that were shadowing the correct ones at the top of the file

def predict_ensemble(image_path, models_list, k=TOP_K):
    """
    Run ensemble prediction across multiple models
    Averages softmax probabilities and returns ensemble + per-model results
    Uses weighted averaging based on model support to handle sparse classes (e.g. Raspberry)
    Includes 'Context-Aware' weighting to suppress specialist hallucinations.
    """
    import tensorflow as tf
    print("DEBUG: Starting predict_ensemble", flush=True)
    
    excluded_models = []  # Models to exclude from ensemble averaging
    
    all_model_results = []
    rice_gate = False
    use_gen_fallback = False
    
    # 1. Collect all predictions first
    # Store tuples of (model_name, probs_39_class, support_mask, raw_top_label, raw_top_prob)
    ensemble_candidates = []
    
    # Define model weights for ensemble
    # Specialist models get higher weight in their domain
    MODEL_WEIGHTS = {
        'dataset16': 3.0,  # Apple specialist - Highly reliable for Apple Rust
        'dataset3': 1.5,   # Apple/Grape/Tomato specialist
        'dataset6': 1.0,   # Grape/Pepper specialist (but sometimes confuses Apple)
        'dataset17': 0.8,  # Potato/Tomato/Pepper
        'dataset12': 0.5,  # Large dataset but often predicts Background/not_leaf
        'plant_disease_recog_model_pwp': 1.0,
        'dataset39': 1.0,  # Alias for pwp
        'rice_disease_model': 0.5 # Rice specialist - Lower default weight to prevent hallucination on non-rice
    }
    
    NUM_CLASSES = len(DATASET39_LABELS)
    
    # First Pass: Run all models and collect predictions
    for idx, model_info in enumerate(models_list):
        try:
            model_name = model_info['name']
            print(f"DEBUG: Processing {model_name} for ensemble", flush=True)
            
            # 1. Standard Prediction (Top-K) for per-model reporting
            result = predict_with_model(model_info, image_path, k)
            if result:
                top_entry = result['topk'][0] if result.get('topk') else None
                all_model_results.append({
                "model": model_name,
                "model_name": model_name,  # Add model_name key for compatibility
                "top": result.get('topk', []),
                "top_label": (top_entry or {}).get('label', 'Unknown'),
                "top_prob": float((top_entry or {}).get('prob', 0.0))
            })
                
                # 2. Prepare for Ensemble
                if model_name not in excluded_models:
                    model = model_info['model']
                    # Determine input shape based on model name if not provided
                    if 'input_shape' in model_info:
                        input_shape = normalize_input_shape(model_info['input_shape'], default=(224, 224))
                    elif any(x in model_name for x in ['dataset39', 'plant_disease_recog_model_pwp']):
                        input_shape = (160, 160)
                    else:
                        input_shape = (224, 224) # Default for dataset6, 12, 16, 17
                    
                    # Preprocess with model-specific logic
                    # dataset39 (pwp), dataset6, and rice_disease_model use Raw input (0-255)
                    # Web4 (tomato_disese_model_V1.keras) also uses Raw input
                    if any(x in model_name for x in ['dataset39', 'dataset6', 'plant_disease_recog_model_pwp', 'rice_disease_model', 'tomato_disese_model_V1.keras']):
                         img = load_image_rgb(image_path)
                         img = img.resize(input_shape, Image.Resampling.LANCZOS)
                         img_array = np.array(img).astype(np.float32)
                         img_array = np.expand_dims(img_array, axis=0)
                         # Note: No division by 255.0 (Raw input)
                    else:
                         img_array = preprocess_image(image_path, target_size=input_shape)
                    
                    predictions = model.predict(img_array, verbose=0)
                    raw_output = predictions[0].astype(np.float32)
                    
                    # Check if output is logits or probabilities
                    is_probability = (np.min(raw_output) >= 0 and np.max(raw_output) <= 1.0)
                    
                    if is_probability:
                        probs = raw_output
                        if np.sum(probs) > 1.5:
                             probs = probs / (np.sum(probs) + 1e-7)
                    else:
                        tf_module = get_tf()
                        if tf_module:
                            probs = tf_module.nn.softmax(raw_output).numpy()
                        else:
                            # Numpy softmax fallback
                            e_x = np.exp(raw_output - np.max(raw_output))
                            probs = e_x / e_x.sum(axis=0)
                    
                    # Map to standardized 39-class vector
                    mapping = get_mapping_for_model(model_name)
                    print(f"DEBUG: Mapping for {model_name}: {mapping is not None}")
                    standard_probs = np.zeros(NUM_CLASSES, dtype=np.float32)
                    
                    if mapping:
                        for src_idx, target_idx in mapping.items():
                            if src_idx < len(probs) and target_idx < NUM_CLASSES:
                                standard_probs[target_idx] += probs[src_idx]
                    else:
                        # Safety: If no mapping and dimension mismatch, exclude from ensemble average
                        # This prevents models with incompatible labels (e.g. Rice, Binary) from corrupting the result
                        if len(probs) != NUM_CLASSES:
                            logger.info(f"Excluding {model_name} from ensemble average: Class count mismatch ({len(probs)} vs {NUM_CLASSES})")
                            continue
                            
                        limit = min(len(probs), NUM_CLASSES)
                        standard_probs[:limit] = probs[:limit]
                    
                    # Get support mask for this model
                    support_mask = get_model_support_mask(model_name, NUM_CLASSES)
                    
                    # Get raw top label for heuristic checks
                    top_idx = np.argmax(standard_probs)
                    top_label = DATASET39_LABELS[top_idx] if top_idx < len(DATASET39_LABELS) else "Unknown"
                    top_prob = float(np.max(standard_probs))
                    
                    ensemble_candidates.append({
                        'name': model_name,
                        'probs': standard_probs,
                        'mask': support_mask,
                        'top_label': top_label,
                        'top_prob': top_prob
                    })
                    
        except Exception as e:
            logger.warning(f"Prediction failed for {model_info['name']}: {e}")
            continue
    
    if not ensemble_candidates:
        return {
            "ensemble_top": [],
            "per_model": all_model_results,
            "entropy": 0.0,
            "is_ood": True,
            "warning": "No models contributed to ensemble"
        }

    # 3. Dynamic Weight Adjustment (Anti-Hallucination)
    
    # Find Generalist Model (dataset39 / pwp)
    gen_cand = next((c for c in ensemble_candidates if 'plant_disease_recog_model_pwp' in c['name'] or 'dataset39' in c['name']), None)
    
    if gen_cand:
        logger.info(f"Ensemble Context: Generalist thinks it is {gen_cand['top_label']} ({gen_cand['top_prob']:.2f})")
        print(f"DEBUG: Gen cand found: {gen_cand['top_label']}")
        gen_display = next((r for r in all_model_results if ('plant_disease_recog_model_pwp' in r['model'] or 'dataset39' in r['model']) and r.get('top')), None)
        gen_top_conf = 0.0
        gen_top_label_fmt = gen_cand['top_label']
        if gen_display:
            try:
                gen_top_conf = float(gen_display['top'][0].get('prob', gen_display['top'][0].get('confidence', 0.0) / 100.0))
                gen_top_label_fmt = gen_display['top'][0].get('label', gen_top_label_fmt)
            except Exception:
                pass
        if gen_top_conf > 0.5:
            MODEL_WEIGHTS['plant_disease_recog_model_pwp'] = 2.0
            MODEL_WEIGHTS['dataset39'] = 2.0
        
        # Heuristic 1: If Generalist is confident it's NOT Apple, suppress Apple Specialist (dataset16)
        # Increased threshold to 0.5 to prevent over-suppression
        if "Apple" not in gen_top_label_fmt and "Background" not in gen_top_label_fmt and gen_top_conf > 0.5:
            logger.info("-> Suppressing Apple Specialist (dataset16) due to Generalist disagreement")
            MODEL_WEIGHTS['dataset16'] = 0.5  # Reduced weight, not zero
            
        # Heuristic 2: If Generalist is confident it's NOT Grape/Pepper, suppress Grape/Pepper Specialist (dataset6)
        if "Grape" not in gen_top_label_fmt and "Pepper" not in gen_top_label_fmt and "Background" not in gen_top_label_fmt and gen_top_conf > 0.5:
            logger.info("-> Suppressing Grape/Pepper Specialist (dataset6) due to Generalist disagreement")
            MODEL_WEIGHTS['dataset6'] = 0.5

        # Heuristic 3: If Generalist is confident it's NOT Potato/Tomato/Pepper, suppress dataset17
        if not any(x in gen_top_label_fmt for x in ["Potato", "Tomato", "Pepper"]) and "Background" not in gen_top_label_fmt and gen_top_conf > 0.5:
             logger.info("-> Suppressing Potato/Tomato Specialist (dataset17) due to Generalist disagreement")
             MODEL_WEIGHTS['dataset17'] = 0.5

        # Heuristic 4: If Generalist is confident it's NOT Rice, suppress Rice Specialist
        # Note: gen_cand['top_label'] is formatted (e.g. "Rice - Blast"), so checking "Rice" works.
        if "Rice" not in gen_top_label_fmt and "Background" not in gen_top_label_fmt and gen_top_conf > 0.5:
            logger.info("-> Suppressing Rice Specialist (rice_disease_model) due to Generalist disagreement")
            MODEL_WEIGHTS['rice_disease_model'] = 0.5
            rice_gate = True
            if gen_top_conf > 0.7:
                use_gen_fallback = True
    print(f"DEBUG: rice_gate={rice_gate}", flush=True)
             
    # 4. Calculate Weighted Average
    weighted_sum_probs = np.zeros(NUM_CLASSES, dtype=np.float32)
    support_counts = np.zeros(NUM_CLASSES, dtype=np.float32)
    
    for cand in ensemble_candidates:
        model_name = cand['name']
        probs = cand['probs']
        mask = cand['mask']
        
        # Determine weight
        weight = 1.0
        for k_name, w in MODEL_WEIGHTS.items():
            if k_name in model_name:
                weight = w
                break
        
        if weight > 0.05:
            logger.info(f"   + {model_name} (Wt: {weight:.2f}) votes for {cand['top_label']}")
        
        weighted_sum_probs += probs * weight
        support_counts += mask * weight

    if 'rice_gate' in locals() and rice_gate:
        print("DEBUG: Rice gating applied", flush=True)
        rice_indices = [39, 40, 41, 42]
        for idx in rice_indices:
            if idx < NUM_CLASSES:
                weighted_sum_probs[idx] = 0.0
                support_counts[idx] = 0.0

    # Calculate Weighted Average: Sum(Probs) / SupportCount
    ensemble_probs = np.zeros(NUM_CLASSES, dtype=np.float32)
    np.divide(weighted_sum_probs, support_counts, out=ensemble_probs, where=support_counts > 0)
    
    if use_gen_fallback and gen_cand:
        print("DEBUG: Applying generalist fallback", flush=True)
        # Prefer the generalist candidate distribution
        prob_sum = np.sum(gen_cand['probs'])
        if prob_sum > 0:
            ensemble_probs = gen_cand['probs'] / prob_sum
    
    # Renormalize to sum to 1 (do NOT fabricate distribution if empty)
    prob_sum = np.sum(ensemble_probs)
    if prob_sum > 0:
        ensemble_probs = ensemble_probs / prob_sum
    else:
        ensemble_probs = np.zeros(NUM_CLASSES, dtype=np.float32)
    
    # Get top-k
    topk_indices = np.argsort(ensemble_probs)[::-1][:k]
    # Use DATASET39_LABELS as the master label set
    classes = DATASET39_LABELS
    
    ensemble_top = []
    for idx in topk_indices:
        label = classes[idx] if idx < len(classes) else f"Class_{idx}"
        prob = float(ensemble_probs[idx])
        confidence = round(prob * 100, 2)
        formatted_label = format_label(label)
        ensemble_top.append({
            "label": formatted_label,
            "prob": prob,
            "confidence": confidence,
            "prob_percent": prob * 100,
            "model": "Ensemble"
        })
    
    # Calculate entropy for OOD detection
    entropy = -np.sum(ensemble_probs * np.log(ensemble_probs + 1e-10))
    is_ood = True if len(ensemble_top) == 0 else (entropy > 3.3 or ensemble_top[0]['prob'] < 0.20)
    
    return {
        "ensemble_top": ensemble_top,
        "per_model": all_model_results,
        "entropy": float(entropy),
        "is_ood": is_ood,
        "model_used": "Ensemble (Top-5 Avg)"
    }


def predict_with_kindwise(image_path):
    """
    Predict using Kindwise Crop Health API
    """
    api_key = "QXqAt2e7id3VPhzjUKLCOF1bhdvgQNlthNeXY9baQtbdAhquUA"
    api_url = "https://crop.kindwise.com/api/v1/identification" # Correct endpoint for identification

    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

        payload = {
            "images": [encoded_string],
            "similar_images": True
        }
        headers = {
            "Content-Type": "application/json",
            "Api-Key": api_key
        }

        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # Parse result
            # Check for 'result' wrapper which might be present depending on API version
            result_data = data.get('result', data)
            classification = result_data.get('classification', result_data)
            suggestions = classification.get('suggestions', [])
            
            if suggestions:
                top_suggestion = suggestions[0]
                
                label = top_suggestion.get('name') or top_suggestion.get('disease', {}).get('name') or 'Unknown'
                probability = top_suggestion.get('probability', 0.0)
                
                # Extract similar images if available
                similar_images = top_suggestion.get('similar_images', [])
                
                import datetime
                return {
                    "model_name": "Kindwise API",
                    "model_source": "Kindwise API",
                    "topk": [{
                        "label": label,
                        "raw_label": label,
                        "prob": probability,
                        "confidence": round(probability * 100, 2),
                        "model_name": "Kindwise API",
                        "model_source": "Kindwise API"
                    }],
                    "unknown": False,
                    "confidence_message": None,
                    "kindwise_details": {
                        "suggestions": suggestions,
                        "similar_images": similar_images,
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "model_sources_used": ["Kindwise Crop Health API", "Similar Images Database"]
                    }
                }
            else:
                logger.warning(f"Kindwise API response format unexpected: {data}")
        else:
            logger.warning(f"Kindwise API failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.warning(f"Kindwise API Exception: {e}")
    
    return None


def _is_auxiliary_detector_model(model_name):
    """Models used for gating only; not included in disease ranking."""
    name_l = str(model_name).lower()
    return 'best_plant_detector.keras' in name_l


def _load_detection_plant_detector(models):
    """Get detector model from loaded models and cache for quick plant gating."""
    global _DETECTION_PLANT_MODEL_CACHE

    if _DETECTION_PLANT_MODEL_CACHE.get('loaded') and _DETECTION_PLANT_MODEL_CACHE.get('model') is not None:
        return _DETECTION_PLANT_MODEL_CACHE['model']

    detector = next((m.get('model') for m in models if _is_auxiliary_detector_model(m.get('name'))), None)
    _DETECTION_PLANT_MODEL_CACHE['model'] = detector
    _DETECTION_PLANT_MODEL_CACHE['loaded'] = True
    return detector


def _predict_plant_score(image_path, detector_model):
    """Run best_plant_detector model and return a plant score in [0,1]."""
    if detector_model is None:
        return None
    try:
        img = Image.open(image_path).convert('RGB')
        img = ImageOps.fit(img, (224, 224), Image.Resampling.LANCZOS)
        arr = np.asarray(img).astype(np.float32)
        if arr.ndim == 2:
            arr = np.stack((arr,) * 3, axis=-1)
        elif arr.shape[2] == 4:
            arr = arr[:, :, :3]
        arr = arr / 255.0
        arr = np.expand_dims(arr, axis=0)

        pred = detector_model.predict(arr, verbose=0)
        if pred is None:
            return None

        pred = np.asarray(pred).reshape(-1)
        if pred.size == 0:
            return None
        if pred.size == 1:
            score = float(pred[0])
        else:
            # Supports both [non_plant, plant] and [plant, non_plant] layouts by taking max confidence.
            score = float(np.max(pred))

        return max(0.0, min(1.0, score))
    except Exception as e:
        logger.warning(f"Plant detector check failed: {e}")
        return None


def predict_topk(image_path, k=TOP_K, use_all_models=True, use_ensemble=False, enable_rice_models=True, disable_best_model=False):
    """
    Predict top-k classes with all available models
    Supports ensemble mode (averages probabilities) or per-model mode
    """
    logger.info(f"DEBUG: predict_topk called for {image_path}")
    try:
        try:
            img = Image.open(image_path).convert('RGB')
            arr = np.asarray(img)
            h, w = arr.shape[0], arr.shape[1]
            uniq = len({tuple(x) for x in arr.reshape(-1, 3)})
            logger.info(f"DEBUG: Image stats - size: {w}x{h}, unique colors: {uniq}")
            if uniq < 800 and (h * w < 150000):
                logger.info("DEBUG: Image rejected by precheck_ood")
                topk = [{'label': 'Unknown', 'raw_label': 'Unknown', 'prob': 0.0, 'confidence': 0.0}]
                return {
                    "model_used": "precheck_ood",
                    "backend": "tf",
                    "topk": topk,
                    "unknown": True,
                    "confidence_message": "Image appears non-leaf or synthetic",
                    "all_models": [],
                    "unified_results": []
                }
        except Exception as e:
            logger.error(f"DEBUG: Precheck failed: {e}")
            pass
        
        if os.path.isdir(FINAL_MODELS_DIR) and not use_all_models:
            logger.info("DEBUG: Using final models only")
            _maybe_load_final_models()
            if _FINAL_CACHE['loaded'] and _FINAL_CACHE['plant_model'] is not None:
                return _predict_two_stage(image_path, k)
    except Exception as e:
        logger.error(f"DEBUG: Error in early checks: {e}")
        pass
    
    if True: # Always run all models logic if we passed the check above
        # Load all models
        logger.info("DEBUG: Loading all models...")
        models = load_all_models()
        logger.info(f"DEBUG: Loaded {len(models)} models")

        if DETECTION_ONLY_MODE:
            disease_allowed = set(DETECTION_REFERENCE_DISEASE_MODELS)
            if disable_best_model and "best_model.keras" in disease_allowed:
                disease_allowed.remove("best_model.keras")
                logger.info("DEBUG: best_model.keras disabled (beta toggle is off)")
            allowed = disease_allowed | {'best_plant_detector.keras'}
            models = [m for m in models if str(m.get('name', '')).lower() in allowed]
            logger.info(f"DEBUG: Detection parity model set active: {[m.get('name') for m in models]}")

        # Strict gate: when beta toggle is off, only lefora + plant detector are allowed.
        if disable_best_model:
            models = [
                m for m in models
                if _is_auxiliary_detector_model(m.get('name'))
                or 'lefora.keras' in str(m.get('name', '')).lower()
            ]
            logger.info(f"DEBUG: Beta off strict model set active: {[m.get('name') for m in models]}")

        detector_model = _load_detection_plant_detector(models)
        plant_score = _predict_plant_score(image_path, detector_model)
        if plant_score is not None:
            logger.info(f"DEBUG: Detection plant score: {plant_score:.3f}")
            if plant_score < 0.50:
                non_leaf_confidence = round((1.0 - plant_score) * 100, 2)
                topk = [{'label': 'Unknown', 'raw_label': 'Unknown', 'prob': 0.0, 'confidence': 0.0}]
                return {
                    "model_used": "best_plant_detector.keras",
                    "backend": "tf",
                    "topk": topk,
                    "unknown": True,
                    "confidence_message": f"Not a leaf image (confidence: {non_leaf_confidence}%). Please upload a clear leaf photo.",
                    "all_models": [],
                    "unified_results": [],
                    "detector_score": round(plant_score * 100, 2),
                    "non_leaf_confidence": non_leaf_confidence
                }

        disease_models = [m for m in models if not _is_auxiliary_detector_model(m.get('name'))]
        if DETECTION_ONLY_MODE:
            disease_allowed = set(DETECTION_REFERENCE_DISEASE_MODELS)
            if disable_best_model and "best_model.keras" in disease_allowed:
                disease_allowed.remove("best_model.keras")
            disease_models = [m for m in disease_models if str(m.get('name', '')).lower() in disease_allowed]
        logger.info(f"DEBUG: Disease models after detector filtering: {len(disease_models)}")
        
        # Optional filter: exclude rice-specific models when disabled
        if not enable_rice_models:
            disease_models = [m for m in disease_models if 'rice_disease_model' not in m['name'].lower()]
        
        # Optional filter: when beta toggle is off, use only lefora.keras as disease model
        if disable_best_model:
            disease_models = [
                m for m in disease_models
                if 'lefora.keras' in str(m.get('name', '')).lower()
            ]
        
        if use_ensemble and len(disease_models) > 1:
            logger.info("DEBUG: Running ensemble mode")
            # Ensemble mode: average probabilities across all models (excluding crop_model.h5)
            ensemble_result = predict_ensemble(image_path, disease_models, k)
            
            # Format for backward compatibility
            top1 = ensemble_result['ensemble_top'][0] if ensemble_result['ensemble_top'] else None
            if top1:
                # Reuse per-model results from ensemble instead of re-running
                all_models_display = ensemble_result.get('per_model', [])
                
                # Ensure ensemble_top doesn't come from crop_model.h5
                ensemble_topk = ensemble_result['ensemble_top']
                
                # Safety fallback: if ensemble is empty or low confidence/disagreement, select a verified-good single model
                primary_fallback = False
                primary_model_name = None
                primary_topk = ensemble_topk
                
                # Check for low confidence or disagreement
                low_conf = not ensemble_topk or (ensemble_topk and ensemble_topk[0].get('confidence', 0.0) < 40.0)
                
                if low_conf:
                    # Explicitly prefer dataset6 (verified good model)
                    candidates = []
                    for m in all_models_display:
                        top = m.get('top') or []
                        if top:
                            name = m.get('model', '')
                            # Get confidence of top prediction
                            conf = top[0].get('confidence', top[0].get('prob', 0.0) * 100.0)
                            candidates.append((name, conf, top))
                    
                    # Sort by rank: dataset6 is gold standard fallback
                    def rank(name):
                        nl = name.lower()
                        if 'dataset6' in nl: return 0
                        if 'plant_disease_recog_model_pwp' in nl: return 1
                        if 'dataset39' in nl: return 2
                        return 3
                        
                    if candidates:
                        candidates.sort(key=lambda x: (rank(x[0]), -float(x[1])))
                        primary_model_name, primary_conf, primary_topk = candidates[0]
                        
                        # Only use fallback if it's reasonably confident
                        if primary_conf > 10.0:
                             primary_fallback = True
                             logger.info(f"Ensemble low confidence. Falling back to {primary_model_name} ({primary_conf:.2f}%)")
                
                # Generate unified_results for ensemble mode too
                unified_results = []
                for m in all_models_display:
                    m_name = m.get('model_name') or m.get('model') or ''
                    if disable_best_model and 'best_model.keras' in str(m_name).lower():
                        continue
                    m_source = m.get('model_source', m_name or 'Unknown Model')
                    for p in m.get('topk', m.get('top', [])):
                        pred = p.copy()
                        pred['model_source'] = m_source
                        pred['model_name'] = m_source
                        if 'confidence' not in pred:
                            pred['confidence'] = pred.get('prob', 0) * 100
                        unified_results.append(pred)
                unified_results.sort(key=lambda x: float(x.get('confidence', 0)), reverse=True)

                return {
                    "model_used": (f"Primary ({primary_model_name})" if primary_fallback and primary_model_name else ensemble_result.get('model_used', 'ensemble')),
                    "backend": "tf",
                    "topk": primary_topk if primary_topk else [],
                    "unknown": ensemble_result['is_ood'] and not primary_fallback,
                    "confidence_message": ("Primary model result (safety fallback applied)" if primary_fallback else ("Please upload a clearer leaf image. Model is unsure." if ensemble_result['is_ood'] else None)),
                    "all_models": all_models_display,
                    "ensemble_top": ensemble_result['ensemble_top'],
                    "per_model": ensemble_result['per_model'],
                    "entropy": ensemble_result['entropy'],
                    "primary_fallback": primary_fallback,
                    "primary_model": primary_model_name,
                    "unified_results": unified_results
                }
        
        # Per-model mode: run each model separately
        print("DEBUG: Running per-model mode", flush=True)
        all_results = []
        excluded_models = ['crop_model.h5']  # Models to exclude from primary prediction
        
        for model_info in disease_models:
            try:
                print(f"DEBUG: Predicting with {model_info['name']}", flush=True)
                result = predict_with_model(model_info, image_path, k)
                if result:
                    # Ensure model_name is set correctly
                    result['model_name'] = model_info['name']
                    result['model_source'] = model_info['name']
                    all_results.append(result)
                    print(f"DEBUG: Success for {model_info['name']}", flush=True)
                else:
                    print(f"DEBUG: No result for {model_info['name']}", flush=True)
            except Exception as e:
                print(f"DEBUG: Prediction failed for {model_info['name']}: {e}", flush=True)
                logger.warning(f"Prediction failed for {model_info['name']}: {e}")
                all_results.append({
                    'model_name': model_info['name'],
                    'model_source': model_info['name'],
                    'topk': [{'label': 'Unknown', 'raw_label': 'Unknown', 'prob': 0.0, 'confidence': 0.0}],
                    'unknown': True,
                    'confidence_message': f"Model failed: {model_info['name']}",
                })
                continue
        
        print(f"DEBUG: Total results collected: {len(all_results)}", flush=True)
        
        # When beta toggle is off, hard-remove best_model.keras from per-model results
        if disable_best_model:
            all_results = [
                r for r in all_results
                if 'best_model.keras' not in str(r.get('model_name', '')).lower()
            ]
        
        # Add Kindwise API Prediction (disabled in detection-only mode)
        if not DETECTION_ONLY_MODE:
            try:
                kindwise_result = predict_with_kindwise(image_path)
                if kindwise_result:
                    all_results.append(kindwise_result)
            except Exception as e:
                logger.warning(f"Kindwise prediction failed: {e}")

        if len(all_results) == 0:
            raise RuntimeError("All model predictions failed")
        
        # Plant gating across per-model outputs
        try:
            from modules.plant_detector import detect_plant_type, filter_predictions_by_plant
            agg = []
            for r in all_results:
                if r.get('topk'):
                    agg.extend(r['topk'][:3])
            detected_plant = detect_plant_type(agg) if agg else None
            if detected_plant:
                for r in all_results:
                    topk = r.get('topk') or []
                    filtered = filter_predictions_by_plant(topk, detected_plant)
                    if filtered:
                        r['topk'] = filtered
                    else:
                        r['unknown'] = True
                        damped = []
                        for p in topk[:k]:
                            c = p.get('confidence', p.get('prob', 0) * 100)
                            c2 = 40.0 if c > 40.0 else c
                            damped.append({
                                'label': p.get('label', 'Unknown'),
                                'raw_label': p.get('raw_label', p.get('label', 'Unknown')),
                                'prob': round(c2 / 100.0, 4),
                                'confidence': c2
                            })
                        r['topk'] = damped if damped else [{'label': 'Unknown', 'raw_label': 'Unknown', 'prob': 0.05, 'confidence': 5.0}]
        except Exception:
            pass
        
        # Global aggregation: keep one top prediction per model for final Top-K display.
        global_predictions = []
        model_top_predictions = []
        for res in all_results:
            m_source = res.get('model_source', res.get('model_name', 'Unknown Model'))

            topk_items = res.get('topk', [])
            for idx, p in enumerate(topk_items):
                pred = p.copy()
                pred['model_source'] = m_source
                pred['model_name'] = m_source
                if 'confidence' not in pred:
                    pred['confidence'] = pred.get('prob', 0) * 100
                global_predictions.append(pred)
                if idx == 0:
                    model_top_predictions.append(pred)

        # Sort by confidence (descending)
        global_predictions.sort(key=lambda x: float(x.get('confidence', 0)), reverse=True)
        model_top_predictions.sort(key=lambda x: float(x.get('confidence', 0)), reverse=True)

        # Top-K where each item is the best prediction from one model
        topk_per_model = model_top_predictions[:max(1, int(k or TOP_K))]
        
        # Extract Kindwise results for template display
        kindwise_display = []
        for res in all_results:
            if res.get('model_name') == 'Kindwise API':
                details = res.get('kindwise_details', {})
                suggestions = details.get('suggestions', [])
                if not suggestions and res.get('topk'):
                    # Fallback if suggestions missing but topk exists
                    for item in res['topk']:
                        kindwise_display.append({
                            'disease': item.get('label'),
                            'crop': 'Analyzed Crop',
                            'confidence': item.get('confidence', 0),
                            'images': [],
                            'citations': []
                        })
                else:
                    for s in suggestions:
                        # Extract similar images
                        sim_imgs = []
                        if 'similar_images' in s:
                            sim_imgs = [img.get('url') for img in s['similar_images'] if img.get('url')]
                        elif 'similar_images' in details:
                             # Sometimes similar_images are at top level
                             sim_imgs = [img.get('url') for img in details['similar_images'] if img.get('url')]
                        
                        kindwise_display.append({
                            'disease': s.get('name'),
                            'crop': 'Analyzed Crop',
                            'confidence': s.get('probability', 0) * 100,
                            'images': sim_imgs[:4], # Limit to 4 images
                            'citations': [],
                            'details': details # Pass full details including timestamp
                        })

        # Determine Primary Detection (Top 1 from per-model Top-K)
        if topk_per_model:
            primary_pred = topk_per_model[0]
            primary_model_name = primary_pred['model_name']
            
            # Format model name
            prefix = "DL_" if any(x in primary_model_name.lower() for x in ['keras', 'h5', 'tensorflow', 'dataset']) else "ML_"
            if "kindwise" in primary_model_name.lower():
                final_model_name = primary_model_name
            elif not primary_model_name.startswith(("DL_", "ML_")):
                 final_model_name = f"{prefix}{primary_model_name}"
            else:
                 final_model_name = primary_model_name
                 
            confidence_message = res.get('confidence_message') # Might be stale, but acceptable
        else:
            primary_pred = {'label': 'Unknown', 'confidence': 0.0}
            final_model_name = "None"
            confidence_message = "No confident predictions found"

        return {
            "model_used": final_model_name,
            "backend": "tf",
            "topk": topk_per_model,
            "unknown": primary_pred.get('label') == 'Unknown',
            "confidence_message": confidence_message,
            "all_models": all_results,  # Include all models for display
            "unified_results": model_top_predictions,
            "kindwise_results": kindwise_display
        }
    else:
        # Backward compatibility: use first model only
        try:
            model, classes, backend, model_name = load_model_singleton()
            model_info = {
                'model': model,
                'classes': classes,
                'name': model_name,
                'input_shape': _MODEL_CACHE.get('input_shape', (160, 160))
            }
            result = predict_with_model(model_info, image_path, k)
            if not result:
                raise RuntimeError("Prediction failed - no result returned")
            if 'topk' not in result:
                raise RuntimeError("Prediction failed - missing topk in result")
            return {
                "model_used": result.get("model_name", model_name),
                "backend": backend,
                "topk": result["topk"],
                "unknown": result.get("unknown", False),
                "confidence_message": result.get("confidence_message", None),
            }
        except Exception as e:
            logger.error(f"Single model prediction failed: {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            raise

def _maybe_load_final_models():
    if _FINAL_CACHE['loaded']:
        return
    fm_dir = FINAL_MODELS_DIR
    plant_map = os.path.join(fm_dir, "plant_label_map.json")
    plant_model_path = os.path.join(fm_dir, "plant_classifier.keras")
    if not (os.path.exists(plant_map) and os.path.exists(plant_model_path)):
        backups_dir = os.path.join(PROJECT_ROOT, "models", "backups_old")
        try:
            if os.path.isdir(backups_dir):
                subs = [os.path.join(backups_dir, d) for d in os.listdir(backups_dir)]
                subs = [d for d in subs if os.path.isdir(d)]
                if subs:
                    subs.sort(reverse=True)
                    fm_dir = subs[0]
                    plant_map = os.path.join(fm_dir, "plant_label_map.json")
                    plant_model_path = os.path.join(fm_dir, "plant_classifier.keras")
        except Exception:
            pass
        if not (os.path.exists(plant_map) and os.path.exists(plant_model_path)):
            return
    import tensorflow as tf
    try:
        import keras
        try:
            keras.config.enable_unsafe_deserialization()
        except Exception:
            pass
    except Exception:
        pass
    try:
        pm = tf.keras.models.load_model(plant_model_path, compile=False)
        classes = None
        try:
            with open(plant_map, "r", encoding="utf-8") as f:
                classes = json.load(f)
        except Exception:
            classes = None
        thr = 0.5
        try:
            with open(os.path.join(PROJECT_ROOT, "artifacts", "plant_calibration.json"), "r", encoding="utf-8") as f:
                j = json.load(f)
                thr = float(j.get("threshold", thr))
        except Exception:
            pass
        try:
            thr = min(float(thr), 0.40)
        except Exception:
            pass
        _FINAL_CACHE['plant_model'] = pm
        _FINAL_CACHE['plant_classes'] = classes
        _FINAL_CACHE['plant_threshold'] = thr
        _FINAL_CACHE['disease_models'] = {}
        for entry in os.listdir(fm_dir):
            if entry.startswith("disease_"):
                plant = entry.replace("disease_", "")
                ddir = os.path.join(fm_dir, entry)
                label_map_path = os.path.join(ddir, "label_map.json")
                model_path = os.path.join(ddir, f"{plant}_disease_classifier.keras")
                if os.path.exists(model_path) and os.path.exists(label_map_path):
                    try:
                        dm = tf.keras.models.load_model(model_path, compile=False)
                        with open(label_map_path, "r", encoding="utf-8") as f:
                            dclasses = json.load(f)
                        dthr = 0.5
                        calib_path = os.path.join(PROJECT_ROOT, "artifacts", f"{plant}_disease_calibration.json")
                        try:
                            with open(calib_path, "r", encoding="utf-8") as f:
                                j = json.load(f)
                                dthr = float(j.get("threshold", dthr))
                        except Exception:
                            pass
                        try:
                            dthr = min(float(dthr), 0.25)
                        except Exception:
                            pass
                        _FINAL_CACHE['disease_models'][plant] = {'model': dm, 'classes': dclasses, 'threshold': dthr}
                    except Exception:
                        continue
        _FINAL_CACHE['loaded'] = True
    except Exception:
        _FINAL_CACHE['loaded'] = False

def _predict_two_stage(image_path, k=TOP_K):
    import numpy as np
    import tensorflow as tf
    from modules.plant_detector import detect_plant_type
    # Enforce ready status gating from discovered_plants.json
    ready_set = None
    try:
        with open(os.path.join(PROJECT_ROOT, "artifacts", "discovered_plants.json"), "r", encoding="utf-8") as f:
            dj = json.load(f)
            ready_set = {p for p, info in (dj.get("by_plant") or {}).items() if (info or {}).get("status") == "ready"}
            if not ready_set:
                ready_set = None
    except Exception:
        ready_set = None
    pm = _FINAL_CACHE['plant_model']
    pclasses = _FINAL_CACHE['plant_classes'] or []
    pthr = _FINAL_CACHE['plant_threshold']
    img_array = preprocess_image(image_path, target_size=(224, 224))
    p = pm.predict(img_array, verbose=0)[0].astype(np.float32)
    pi = int(np.argmax(p))
    pc = float(np.max(p))
    if pc < pthr or pi >= len(pclasses):
        topk = [{'label': 'Unknown', 'raw_label': 'Unknown', 'prob': 0.0, 'confidence': 0.0, 'model': 'two_stage'}]
        return {
            "model_used": "two_stage",
            "backend": "tf",
            "topk": topk,
            "unknown": True,
            "confidence_message": "Low plant confidence",
            "all_models": [{"model_name": "plant_classifier.keras"}]
        }
    plant_name = str(pclasses[pi]).lower()
    plant_name = plant_name.strip().replace(" ", "_")
    # Cross-check plant via aggregated per-model predictions; override if mismatch and alternative is ready
    try:
        agg_detected = None
        models = load_all_models()
        agg = []
        for model_info in models:
            try:
                result = predict_with_model(model_info, image_path, k)
                if result and result.get('topk'):
                    agg.extend(result['topk'][:3])
            except Exception:
                continue
        if agg:
            agg_detected = detect_plant_type(agg)
        if agg_detected and agg_detected != plant_name and (ready_set is None or agg_detected in ready_set):
            if agg_detected in _FINAL_CACHE['disease_models']:
                plant_name = agg_detected
    except Exception:
        pass
    if ready_set is not None and plant_name not in ready_set:
        topk = [{'label': 'Unknown', 'raw_label': 'Unknown', 'prob': 0.0, 'confidence': 0.0, 'model': 'two_stage'}]
        return {
            "model_used": "two_stage",
            "backend": "tf",
            "topk": topk,
            "unknown": True,
            "confidence_message": "Plant not enabled",
            "all_models": [{"model_name": "plant_classifier.keras"}]
        }
    if plant_name not in _FINAL_CACHE['disease_models']:
        topk = [{'label': 'Unknown', 'raw_label': 'Unknown', 'prob': 0.0, 'confidence': 0.0, 'model': 'two_stage'}]
        return {
            "model_used": "two_stage",
            "backend": "tf",
            "topk": topk,
            "unknown": True,
            "confidence_message": "No disease model for plant",
            "all_models": [{"model_name": "plant_classifier.keras"}]
        }
    dinfo = _FINAL_CACHE['disease_models'][plant_name]
    dm = dinfo['model']
    dclasses = dinfo['classes'] or []
    dthr = float(dinfo.get('threshold', 0.5))
    q = dm.predict(img_array, verbose=0)[0].astype(np.float32)
    idxs = np.argsort(q)[::-1][:k]
    results = []
    for idx in idxs:
        lbl = dclasses[idx] if idx < len(dclasses) else f"Class_{idx}"
        prob = float(q[idx])
        conf = round(prob * 100.0, 2)
        results.append({
            "label": format_label(lbl),
            "raw_label": lbl,
            "prob": prob,
            "confidence": conf,
            "model": f"disease_{plant_name}"
        })
    unknown = (q.max() < dthr)
    all_models_list = [{"model_name": "plant_classifier.keras"}, {"model_name": f"{plant_name}_disease_classifier.keras", "topk": results}]
    try:
        models = load_all_models()
        for model_info in models:
            try:
                res = predict_with_model(model_info, image_path, k)
                if res and res.get("topk"):
                    all_models_list.append({"model_name": model_info["name"], "topk": res["topk"]})
            except Exception:
                continue
    except Exception:
        pass
    return {
        "model_used": f"disease_{plant_name}",
        "backend": "tf",
        "topk": results,
        "unknown": bool(unknown),
        "confidence_message": "Model is unsure." if unknown else None,
        "all_models": all_models_list
    }
