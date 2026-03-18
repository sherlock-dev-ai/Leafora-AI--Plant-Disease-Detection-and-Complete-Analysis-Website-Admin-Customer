
import os
print("Hello from python")
try:
    import tensorflow as tf
    print("TF imported")
except Exception as e:
    print(f"TF failed: {e}")
