## Plant Disease Detection Integration Guide

This file explains how to reuse the plant disease detection feature from this project inside another website.

The core detection logic in this folder consists of:
- Trained model files like `best_plant_detector.keras`, `best_model.keras`, `final_model.keras`
- Python scripts such as `infer_classes.py`, `inspect_detector.py`, `simple_test.py`
- A Streamlit UI in `streamlit_app.py` (optional for integration)

You will usually integrate only the **model loading and prediction code** into your other project, not the entire UI and debug tooling.

---

## Option 1 (Recommended): Run detection as a separate backend service

The cleanest way to reuse this detection feature in another website is:

1. Keep this detection project as a **separate backend service** (for example, a small API built with FastAPI, Flask, Django, or even Streamlit with an HTTP endpoint).
2. Your new website calls this service with an image (file upload or URL).
3. The service runs the model using the logic from `infer_classes.py` and returns predictions (e.g., disease name, confidence).

High‑level steps:
- Expose an HTTP endpoint like `POST /detect` that accepts an image.
- Inside the endpoint:
  - Load the Keras model (using the same code you use in this project).
  - Preprocess the image exactly the same way as here.
  - Run `model.predict(...)` and convert the output to a JSON‑friendly structure.
- From your other website:
  - On file upload / user action, send the image to the `/detect` endpoint.
  - Display the returned prediction on the page.

This way, you do **not** need to copy this entire folder into your other website’s codebase. You only call the detection service over HTTP.

---

## Option 2: Copy the detection module into another Python web project

If your other website is also a Python project (e.g., Django/Flask/FastAPI):

1. Create a folder in that project, for example `detection/`.
2. Copy the **minimum required files** from this folder into `detection/`, typically:
   - The model file(s): `best_plant_detector.keras` (and any others you actually use).
   - The Python script that performs inference (e.g., `infer_classes.py`), or a simplified version of it.
3. Turn the inference code into a function you can import, for example:
   - `from detection.infer_classes import run_detection_on_image`
4. In your web views / API endpoints:
   - Call that function when an image is uploaded.
   - Return the results to the frontend.

Avoid copying:
- Debug logs and temporary text files.
- Old or unused model variants, unless you know you need them.

Also make sure:
- The Python environment for the new website has the same ML dependencies installed (TensorFlow / Keras, Pillow, etc.).
- File paths inside the detection code are updated so they point to the correct locations in the new project structure.

---

## Prompt you can give to an AI when integrating this detection feature

You can paste the following prompt into an AI assistant in your **other website’s** project. Before you do, make sure you have copied the detection folder (or equivalent code) into that project, or have the detection service code available.

### Prompt template

> You are helping me integrate an existing plant disease detection module into this web project.  
> I have a separate folder (or service) that contains a trained Keras model and inference code originally from another project. The important files are:
> - One or more model files, for example: `best_plant_detector.keras` / `best_model.keras`
> - Python inference code, for example: `infer_classes.py`, which loads the model and runs predictions on an input image
> - Optional UI code (such as a Streamlit app) that I **do not** want to reuse directly here, only the detection logic.
>
> Goals:
> 1. Add a file upload feature in this web project so users can upload a plant image.
> 2. On upload, call the detection logic from the existing module (or via an HTTP API if we keep it as a separate service).
> 3. Return and display the predicted disease and any confidence score or additional details.
>
> Assumptions you can make:
> - The model is a Keras/TensorFlow model trained to classify plant diseases from images.
> - The preprocessing steps (resize, normalization, etc.) should match the original project’s `infer_classes.py`.
> - If needed, you can help me refactor the detection code into a reusable function like `run_detection_on_image(image_bytes_or_path)`, which loads the model once and reuses it.
>
> What I want from you:
> - Inspect this project’s structure and show me exactly where to place the detection code.
> - Write or adapt the backend code to:
>   - Load the existing model.
>   - Accept an uploaded image.
>   - Run inference and return the result.
> - Write any necessary frontend code (routes, forms, JavaScript) to:
>   - Let a user upload an image.
>   - Display the prediction result.
> - Explain any configuration or dependency changes I must make (e.g., installing TensorFlow/Keras, Pillow, or setting environment variables).
>
> Here is the detection code folder I copied from the original project (describe or paste file list here), and here is the current structure of this web project (describe or paste file list here). Please propose a clear integration plan and then implement the necessary changes step by step.

You can adjust filenames in the prompt (like `best_plant_detector.keras` or `infer_classes.py`) to match whatever you actually copy into the new project.

---

## Should you copy all files, or only some?

If you are unsure, a safe approach is:

1. Copy only:
   - The main model file you use.
   - The main inference script you use to get predictions.
2. If something is missing (for example, a helper function or label mapping), copy the additional Python file that defines it.

If you prefer simplicity and don’t mind some extra unused files, you can:
- Create a folder called `detection/` in your other project.
- Copy this entire folder’s relevant `.py` and `.keras` files into it.
- Then, in that project, ask an AI assistant (using the prompt above) to help you:
  - Remove unused files.
  - Wire up the actual upload → predict → display flow.

---

## How to use this file

- Keep this file together with your detection code when you copy it to the other project.
- Open it in the AI assistant for that project.
- Paste the **Prompt template** section into the assistant.
- Optionally, add:
  - A list of the files you actually copied.
  - The tech stack used by the new website (e.g., React + Node, Django, Flask, etc.).

The assistant will then have enough context to understand what this detection feature does and how to integrate it into your other website.

