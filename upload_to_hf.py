import os
from huggingface_hub import HfApi, create_repo

# Configuration
REPO_ID = "itzsherlockz/leafora-models"
MODELS_TO_UPLOAD = [
    {"local_path": "m_models/fast_model_1/model.safetensors", "path_in_repo": "fast_model_1/model.safetensors"},
    {"local_path": "m_models/fast_model_2/pytorch_model.bin", "path_in_repo": "fast_model_2/pytorch_model.bin"},
    {"local_path": "m_models/fast_model_3/model.safetensors", "path_in_repo": "fast_model_3/model.safetensors"},
    {"local_path": "detection/best_model.keras", "path_in_repo": "detection/best_model.keras"},
    {"local_path": "detection/best_plant_detector.keras", "path_in_repo": "detection/best_plant_detector.keras"},
    {"local_path": "detection/final_model.keras", "path_in_repo": "detection/final_model.keras"},
    {"local_path": "detection/health.keras", "path_in_repo": "detection/health.keras"},
    {"local_path": "detection/lefora.keras", "path_in_repo": "detection/lefora.keras"},
    {"local_path": "detection/premium.keras", "path_in_repo": "detection/premium.keras"},
]

def upload_models():
    api = HfApi()
    
    # Create repo if it doesn't exist
    try:
        create_repo(repo_id=REPO_ID, repo_type="model", exist_ok=True)
        print(f"Repo {REPO_ID} is ready.")
    except Exception as e:
        print(f"Note: Could not create/verify repo (might already exist or need login): {e}")

    for model in MODELS_TO_UPLOAD:
        local_path = model["local_path"]
        path_in_repo = model["path_in_repo"]
        
        if os.path.exists(local_path):
            print(f"Uploading {local_path} to {path_in_repo}...")
            try:
                api.upload_file(
                    path_or_fileobj=local_path,
                    path_in_repo=path_in_repo,
                    repo_id=REPO_ID,
                    repo_type="model",
                )
                print(f"Successfully uploaded {local_path}")
            except Exception as e:
                print(f"Failed to upload {local_path}: {e}")
        else:
            print(f"Skipping {local_path} (file not found)")

if __name__ == "__main__":
    print("Ensure you have logged in using 'huggingface-cli login'")
    upload_models()
