
import tensorflow as tf
import os

def inspect_models():
    models_to_check = ['lefora.keras', 'trained_model.h5']
    for model_name in models_to_check:
        print(f"\n--- Inspecting {model_name} ---")
        try:
            model = tf.keras.models.load_model(model_name)
            print(f"Input shape: {model.input_shape}")
            print(f"Output shape: {model.output_shape}")
            
            # Check for class names in config or metadata if possible
            if hasattr(model, 'get_config'):
                config = model.get_config()
                # Often in the last layer (Dense)
                last_layer = config['layers'][-1] if 'layers' in config else None
                if last_layer:
                    print(f"Last layer info: {last_layer.get('class_name')} with {last_layer.get('config', {}).get('units')} units")
        except Exception as e:
            print(f"Error loading {model_name}: {e}")

if __name__ == "__main__":
    inspect_models()
