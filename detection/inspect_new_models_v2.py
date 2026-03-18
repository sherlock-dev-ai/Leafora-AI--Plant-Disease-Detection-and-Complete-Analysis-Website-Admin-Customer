
import tensorflow as tf
import os
import json

def inspect_models():
    models_to_check = ['lefora.keras', 'trained_model.h5']
    results = []
    for model_name in models_to_check:
        info = {"model": model_name}
        try:
            model = tf.keras.models.load_model(model_name)
            info["input_shape"] = str(model.input_shape)
            info["output_shape"] = str(model.output_shape)
            
            if hasattr(model, 'get_config'):
                config = model.get_config()
                layers = config.get('layers', [])
                if layers:
                    last_layer = layers[-1]
                    info["last_layer"] = {
                        "class_name": last_layer.get('class_name'),
                        "units": last_layer.get('config', {}).get('units')
                    }
            results.append(info)
        except Exception as e:
            results.append({"model": model_name, "error": str(e)})
    
    with open('model_inspection_results.json', 'w') as f:
        json.dump(results, f, indent=4)
    print("Results saved to model_inspection_results.json")

if __name__ == "__main__":
    inspect_models()
