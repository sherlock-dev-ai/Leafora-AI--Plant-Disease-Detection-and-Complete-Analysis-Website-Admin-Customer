
import sys
import time

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
model = predict._load_premium_model()
end_time = time.time()
print(f"Load premium model took {end_time - start_time:.4f} seconds")

if predict.tf is not None:
    print("SUCCESS: tensorflow is loaded after model load.")
else:
    print("FAILURE: tensorflow is NOT loaded after model load.")
