try:
    from PIL import Image
    print("PIL imported")
    from tensorflow.keras.preprocessing import image
    print("Keras preprocessing imported")
except Exception as e:
    print(f"Error: {e}")
