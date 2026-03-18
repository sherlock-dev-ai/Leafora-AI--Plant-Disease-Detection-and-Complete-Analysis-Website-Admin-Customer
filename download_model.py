import os
from huggingface_hub import hf_hub_download

REPO_ID = "itzsherlockz/leafora-models"

# Mapping of model files to their local paths
MODELS_TO_DOWNLOAD = {
    "m_models/fast_model_1/model.safetensors": "fast_model_1/model.safetensors",
    "m_models/fast_model_2/pytorch_model.bin": "fast_model_2/pytorch_model.bin",
    "m_models/fast_model_3/model.safetensors": "fast_model_3/model.safetensors",
    "detection/best_model.keras": "detection/best_model.keras",
    "detection/best_plant_detector.keras": "detection/best_plant_detector.keras",
    "detection/final_model.keras": "detection/final_model.keras",
    "detection/health.keras": "detection/health.keras",
    "detection/lefora.keras": "detection/lefora.keras",
    "detection/premium.keras": "detection/premium.keras",
}

def download_model(local_path):
    """Downloads a single model file if it doesn't exist."""
    if local_path not in MODELS_TO_DOWNLOAD:
        print(f"Error: No HF mapping for {local_path}")
        return False

    filename_in_repo = MODELS_TO_DOWNLOAD[local_path]
    
    # Ensure local directory exists
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    if not os.path.exists(local_path):
        print(f"Downloading {filename_in_repo} from {REPO_ID} to {local_path}...")
        try:
            downloaded_path = hf_hub_download(
                repo_id=REPO_ID,
                filename=filename_in_repo,
                local_dir=".",  # Download relative to current directory
                local_dir_use_symlinks=False
            )
            print(f"Successfully downloaded: {local_path}")
            return True
        except Exception as e:
            print(f"Error downloading {filename_in_repo}: {e}")
            return False
    else:
        # print(f"File already exists: {local_path}")
        return True

def download_all():
    """Downloads all defined models."""
    print(f"Starting model downloads from {REPO_ID}...")
    success_count = 0
    for local_path in MODELS_TO_DOWNLOAD.keys():
        if download_model(local_path):
            success_count += 1
    
    print(f"Download complete. {success_count}/{len(MODELS_TO_DOWNLOAD)} models verified.")

if __name__ == "__main__":
    download_all()
