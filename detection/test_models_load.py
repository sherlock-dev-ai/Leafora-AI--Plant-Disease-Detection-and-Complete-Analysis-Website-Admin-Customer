
import tensorflow as tf
import os

def test_load():
    try:
        print("Loading disease model...")
        disease_model = tf.keras.models.load_model('best_model.keras')
        print("Disease model loaded successfully.")
        
        print("Loading detector model...")
        detector_model = tf.keras.models.load_model('best_plant_detector.keras')
        print("Detector model loaded successfully.")
        
        print(f"Disease model input: {disease_model.input_shape}, output: {disease_model.output_shape}")
        print(f"Detector model input: {detector_model.input_shape}, output: {detector_model.output_shape}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_load()
