import os
import tensorflow as tf
from tensorflow.keras.models import load_model
import json

model_path = 'final_model.keras'

try:
    model = load_model(model_path)
    with open("model_details.txt", "w") as f:
        f.write("Model loaded successfully.\n")
        f.write(f"Input shape: {model.input_shape}\n")
        f.write(f"Output shape: {model.output_shape}\n")
        
        # Try to find class names in config
        try:
            config = model.get_config()
            f.write(f"Model Config: {json.dumps(config, indent=2)}\n")
        except Exception as e:
            f.write(f"Could not get config: {e}\n")
            
except Exception as e:
    with open("model_details.txt", "w") as f:
        f.write(f"Error loading model: {e}\n")
    print(f"Error loading model: {e}")
