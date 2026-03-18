
print("Testing imports...")
try:
    import numpy as np
    print("NumPy imported")
except Exception as e:
    print(f"NumPy failed: {e}")

try:
    import tensorflow as tf
    print("TensorFlow imported")
except Exception as e:
    print(f"TensorFlow failed: {e}")
