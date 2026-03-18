
import sys
import time

with open("test_predict_import_result.txt", "w") as f:
    sys.stdout = f
    sys.stderr = f
    
    print("Start import predict...")
    start_time = time.time()
    import predict
    end_time = time.time()
    print(f"Import predict took {end_time - start_time:.4f} seconds")

    if predict.tf is None:
        print("SUCCESS: tensorflow is NOT loaded initially.")
    else:
        print("FAILURE: tensorflow IS loaded initially.")

    print("Attempting to load premium model (should trigger TF load)...")
    start_time = time.time()
    try:
        model = predict._load_premium_model()
        end_time = time.time()
        print(f"Load premium model took {end_time - start_time:.4f} seconds")

        if predict.tf is not None:
            print("SUCCESS: tensorflow is loaded after model load.")
        else:
            print("FAILURE: tensorflow is NOT loaded after model load.")
    except Exception as e:
        print(f"FAILURE: Load premium model crashed: {e}")
