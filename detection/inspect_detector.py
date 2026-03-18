import os
import tensorflow as tf
from tensorflow.keras.models import load_model
import json

# Set full absolute path
model_path = r'D:\plant_disease_restart\models\best_plant_detector.keras'
output_file = r"D:\plant_disease_restart\models\detector_info.txt"

print(f"Loading model from: {model_path}")
try:
    model = load_model(model_path)
    print("Model loaded successfully.")
    with open(output_file, "w") as f:
        f.write(f"Model: {model_path}\n")
        f.write(f"Input shape: {model.input_shape}\n")
        f.write(f"Output shape: {model.output_shape}\n")
        try:
            config = model.get_config()
            f.write(f"Model Config: {json.dumps(config, indent=2)}\n")
        except Exception as e:
            f.write(f"Could not get config: {e}\n")
    print(f"Info saved to {output_file}")
except Exception as e:
    with open(output_file, "w") as f:
        f.write(f"Error loading model: {e}")
    print(f"Error: {e}")
