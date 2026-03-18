
import os
import sys

print("Starting check_models.py", flush=True)

try:
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    print("Importing tensorflow...", flush=True)
    import tensorflow as tf
    print("Tensorflow imported.", flush=True)
    # import keras
    # print("Keras imported.", flush=True)
except Exception as e:
    print(f"Import failed: {e}", flush=True)
    sys.exit(1)

models_to_check = ["best_model.keras", "best_plant_detector.keras", "lefora.keras"]

def check_model(model_name):
    print(f"\n--- Checking {model_name} ---", flush=True)
    try:
        model_path = os.path.join("detection", model_name)
        if not os.path.exists(model_path):
             model_path = model_name 
        
        if not os.path.exists(model_path):
            print(f"File not found: {model_path}", flush=True)
            return

        print(f"Loading model from {model_path}...", flush=True)
        model = tf.keras.models.load_model(model_path, compile=False)
        print("Model loaded.", flush=True)
        
        # Check for specific architecture hints
        layers = [l.name for l in model.layers[:10]]
        print(f"First 10 layers: {layers}", flush=True)
        
        # Check input shape
        if hasattr(model, 'input_shape'):
            print(f"Input shape: {model.input_shape}", flush=True)
            
        # Check number of params
        print(f"Total params: {model.count_params()}", flush=True)
        
        # Simple heuristic
        layer_str = " ".join(layers).lower()
        if "resnet" in layer_str or "res" in layer_str:
            print("Architecture hint: ResNet-like", flush=True)
        elif "mobilenet" in layer_str or "block_" in layer_str or "expanded_conv" in layer_str: 
             print("Architecture hint: MobileNet-like", flush=True)
        elif "conv2d" in layer_str:
             print("Architecture hint: CNN (Custom or Generic)", flush=True)
        else:
             print("Architecture hint: Unknown/Custom", flush=True)
             
    except Exception as e:
        print(f"Error checking {model_name}: {e}", flush=True)

if __name__ == "__main__":
    for m in models_to_check:
        check_model(m)
