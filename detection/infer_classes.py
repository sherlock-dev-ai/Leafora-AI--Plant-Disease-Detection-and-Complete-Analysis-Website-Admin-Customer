import os
import sys
import traceback

# Setup logging to file
LOG_FILE = "debug_v2.log"

def log(msg):
    print(msg)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
            f.flush()
    except:
        pass

# Clear log file
try:
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("Starting inference script v2...\n")
except Exception as e:
    print(f"Failed to create log file: {e}")

try:
    log("Importing numpy...")
    import numpy as np
    log("Importing tensorflow...")
    import tensorflow as tf
    log("Importing keras models...")
    from tensorflow.keras.models import load_model
    log("Importing PIL...")
    from PIL import Image
    # log("Importing keras preprocessing...")
    # from tensorflow.keras.preprocessing import image
    
    # Suppress TensorFlow logs
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

    MODEL_PATH = 'best_model.keras'
    # Use absolute paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATASETS = [
        # os.path.join(BASE_DIR, "dataset1"),
        # os.path.join(BASE_DIR, "dataset2"),
        os.path.join(BASE_DIR, "dataset3")
    ]
    OUTPUT_FILE = "inferred_classes.txt"

    log(f"Base Dir: {BASE_DIR}")
    log(f"Model Path: {os.path.abspath(MODEL_PATH)}")

    def load_and_preprocess_image(img_path):
        try:
            # img = image.load_img(img_path, target_size=(224, 224))
            # img_array = image.img_to_array(img)
            
            # Use PIL directly
            img = Image.open(img_path)
            img = img.resize((224, 224))
            img_array = np.array(img)
            
            # Handle grayscale or RGBA
            if img_array.ndim == 2: # Grayscale
                 img_array = np.stack((img_array,)*3, axis=-1)
            elif img_array.shape[2] == 4: # RGBA
                 img_array = img_array[:, :, :3]
                 
            img_array = img_array.astype('float32')
            img_array = np.expand_dims(img_array, axis=0)
            img_array /= 255.0
            return img_array
        except Exception as e:
            log(f"Error processing image {img_path}: {e}")
            return None

    def main():
        try:
            log("Loading model...")
            if not os.path.exists(MODEL_PATH):
                log(f"CRITICAL: Model file not found at {os.path.abspath(MODEL_PATH)}")
                return
                
            model = load_model(MODEL_PATH)
            log("Model loaded successfully.")
            
            input_shape = model.input_shape
            output_shape = model.output_shape
            log(f"Input: {input_shape}, Output: {output_shape}")
            
        except Exception as e:
            log(f"Error loading model: {e}")
            log(traceback.format_exc())
            return

        results = {}  # Map class_index -> list of (folder_name, confidence)

        log(f"Checking datasets: {DATASETS}")
        for dataset in DATASETS:
            if not os.path.exists(dataset):
                log(f"Dataset not found: {dataset}")
                continue
                
            log(f"Scanning {dataset}...")
            try:
                class_folders = os.listdir(dataset)
            except Exception as e:
                log(f"Error listing dataset {dataset}: {e}")
                continue

            for class_folder in class_folders:
                # Only check Potato folders
                if "Potato" not in class_folder:
                    continue

                folder_path = os.path.join(dataset, class_folder)
                if not os.path.isdir(folder_path):
                    continue
                    
                # Get first valid image
                try:
                    images = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                except Exception as e:
                    continue

                if not images:
                    continue
                    
                # Test up to 3 images per folder to be sure
                for img_name in images[:3]:
                    img_path = os.path.join(folder_path, img_name)
                    img_array = load_and_preprocess_image(img_path)
                    
                    if img_array is None:
                        continue
                        
                    try:
                        prediction = model.predict(img_array, verbose=0)
                        predicted_index = np.argmax(prediction)
                        confidence = prediction[0][predicted_index]
                        
                        log(f"  Img: {class_folder}/{img_name} -> Class {predicted_index} ({confidence:.2f})")
                        
                        if confidence > 0.5: # Only consider confident predictions
                            if predicted_index not in results:
                                results[predicted_index] = []
                            results[predicted_index].append(f"{confidence:.2f} - {class_folder}")
                    except Exception as e:
                        log(f"Prediction error: {e}")

        # Write results
        try:
            abs_output_path = os.path.abspath(OUTPUT_FILE)
            log(f"Writing results to: {abs_output_path}")
            
            with open(abs_output_path, "w", encoding="utf-8") as f:
                f.write("Inferred Class Mapping:\n")
                f.write("=======================\n")
                for i in range(15):
                    f.write(f"\nClass {i}:\n")
                    if i in results:
                        # Get unique folder names to avoid duplicates
                        unique_hits = sorted(list(set(results[i])))
                        for hit in unique_hits:
                            f.write(f"  - {hit}\n")
                    else:
                        f.write("  (No high confidence matches found)\n")
            log("Done. Results written.")
        except Exception as e:
            log(f"Error writing results: {e}")

    if __name__ == "__main__":
        main()

except Exception as e:
    with open("fatal_error.log", "w") as f:
        f.write(str(e))
        f.write(traceback.format_exc())
