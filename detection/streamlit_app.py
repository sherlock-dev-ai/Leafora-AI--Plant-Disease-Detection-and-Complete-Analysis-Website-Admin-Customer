
import streamlit as st
import tensorflow as tf
from PIL import Image, ImageOps
import numpy as np
import cv2

st.set_page_config(page_title="Plant Disease Detection", page_icon="🌿")

def make_gradcam_heatmap(img_array, model, last_conv_layer_name, pred_index=None):
    # First, we create a model that maps the input image to the activations
    # of the last conv layer as well as the output predictions
    grad_model = tf.keras.models.Model(
        model.inputs, [model.get_layer(last_conv_layer_name).output, model.output]
    )

    # Then, we compute the gradient of the top predicted class for our input image
    # with respect to the activations of the last conv layer
    with tf.GradientTape() as tape:
        last_conv_layer_output, preds = grad_model(img_array)
        if pred_index is None:
            pred_index = tf.argmax(preds[0])
        class_channel = preds[:, pred_index]

    # This is the gradient of the output neuron (top predicted or chosen)
    # with regard to the output feature map of the last conv layer
    grads = tape.gradient(class_channel, last_conv_layer_output)

    # This is a vector where each entry is the mean intensity of the gradient
    # over a specific feature map channel
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))

    # We multiply each channel in the feature map array
    # by "how important this channel is" with regard to the top predicted class
    # then sum all the channels to obtain the heatmap class activation
    last_conv_layer_output = last_conv_layer_output[0]
    heatmap = last_conv_layer_output @ pooled_grads[..., tf.newaxis]
    heatmap = tf.squeeze(heatmap)

    # For visualization purpose, we will also normalize the heatmap between 0 & 1
    heatmap = tf.maximum(heatmap, 0) / tf.math.reduce_max(heatmap)
    return heatmap.numpy()

def get_rects_from_heatmap(heatmap, max_rects=5):
    # 1. Sanity check: If the heatmap is too "flat" (no clear peaks), it's likely noise
    # We check if the maximum value is significantly higher than the average
    if np.max(heatmap) < 0.2 or (np.max(heatmap) - np.mean(heatmap)) < 0.15:
        return []

    # 2. Upsample heatmap to full image size (224x224) for high-precision contours
    heatmap_resized = cv2.resize(heatmap, (224, 224), interpolation=cv2.INTER_CUBIC)
    
    # 3. Normalize to 0-255 range
    heatmap_norm = np.uint8(255 * (heatmap_resized / (np.max(heatmap_resized) + 1e-10)))
    
    # 4. Use a very strict threshold (top 65% of intensity) to remove "random" low-confidence highlights
    _, thresh = cv2.threshold(heatmap_norm, int(255 * 0.65), 255, cv2.THRESH_BINARY)
    
    # 5. Find distinct contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    rects = []
    if contours:
        # Sort by area descending
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        
        for cnt in contours[:max_rects]:
            # Filter out tiny noise and also "too big" boxes that likely represent background noise
            area = cv2.contourArea(cnt)
            if 150 < area < (224 * 224 * 0.4): 
                x, y, w, h = cv2.boundingRect(cnt)
                rects.append((x, y, w, h))
                
    return rects

# Disease Information Dictionary
DISEASE_INFO = {
    "Bacterial Spot": {
        "description": "Small, water-soaked spots on leaves that eventually turn brown or black. It spreads rapidly in warm, wet conditions.",
        "treatment": "Use copper-based fungicides. Remove infected plant debris and avoid overhead watering."
    },
    "Early Blight": {
        "description": "Characterized by dark spots with concentric rings (target-like) on older leaves. Can lead to significant leaf loss.",
        "treatment": "Apply fungicides containing chlorothalonil or mancozeb. Improve air circulation and prune lower leaves."
    },
    "Late Blight": {
        "description": "A serious disease causing large, irregular greenish-black patches on leaves that quickly turn papery and kill the plant.",
        "treatment": "Immediate application of protective fungicides. Remove and destroy infected plants immediately to prevent spreading."
    },
    "Leaf Mold": {
        "description": "Yellow spots on the upper leaf surface with olive-green mold on the underside. Common in high humidity.",
        "treatment": "Increase ventilation and reduce humidity. Use resistant varieties and apply fungicides if necessary."
    },
    "Septoria Leaf Spot": {
        "description": "Small, circular spots with dark borders and gray centers. Usually starts on lower leaves.",
        "treatment": "Remove infected leaves. Apply fungicides and avoid working with wet plants."
    },
    "Spider Mites": {
        "description": "Tiny pests that cause yellow stippling on leaves. Fine webbing may be visible on the undersides.",
        "treatment": "Increase humidity or spray plants with a strong stream of water. Use insecticidal soap or neem oil."
    },
    "Target Spot": {
        "description": "Small, brown spots that expand into circular lesions with light brown centers and dark borders.",
        "treatment": "Ensure proper spacing for airflow. Apply fungicides and remove infected leaves."
    },
    "Yellow Leaf Curl Virus": {
        "description": "Viral disease transmitted by whiteflies. Leaves curl upward and turn yellow; plant growth is severely stunted.",
        "treatment": "Control whitefly populations using yellow sticky traps or insecticides. Remove infected plants immediately."
    },
    "Mosaic Virus": {
        "description": "Causes mottled green and yellow patterns on leaves, which may also be distorted or stunted.",
        "treatment": "No cure for viral infections. Remove and destroy infected plants. Wash hands and tools frequently."
    },
    "Alternaria Leaf Spot": {
        "description": "Circular, brown to black spots with concentric rings. Often affects stressed plants.",
        "treatment": "Apply fungicides and improve plant vigor through proper fertilization and watering."
    },
    "Black Rot": {
        "description": "A fungal disease causing dark, sunken lesions on fruit and V-shaped yellow lesions on leaf margins.",
        "treatment": "Prune out infected areas. Apply fungicides and maintain good orchard hygiene."
    },
    "Brown Spot": {
        "description": "Small, circular brown spots on leaves that can coalesce into larger dead areas.",
        "treatment": "Apply fungicides and avoid overhead irrigation. Remove fallen leaves."
    },
    "Rust": {
        "description": "Orange or reddish-brown powdery pustules on the undersides of leaves.",
        "treatment": "Apply sulfur or copper-based fungicides. Remove infected leaves and improve air circulation."
    },
    "Scab": {
        "description": "Olive-green to black velvety spots on leaves and fruit. Can cause premature leaf drop.",
        "treatment": "Apply fungicides during the growing season. Rake and destroy fallen leaves in autumn."
    },
    "Powdery Mildew": {
        "description": "White, flour-like fungal growth on leaf surfaces, stems, and flowers.",
        "treatment": "Use neem oil or potassium bicarbonate sprays. Increase spacing for better airflow."
    },
    "Bacterial Wilt": {
        "description": "Sudden wilting of the plant despite adequate moisture. Caused by bacteria blocking water transport.",
        "treatment": "No effective chemical control. Remove infected plants and control soil-borne pests."
    },
    "Leafroll Virus": {
        "description": "Leaves curl upward and become stiff and leathery. Transmitted by aphids.",
        "treatment": "Control aphid populations and use certified disease-free seeds/tubers."
    },
    "Citrus Greening": {
        "description": "Also known as HLB. Causes mottled yellow leaves and bitter, misshapen fruit. Fatal to citrus trees.",
        "treatment": "Control the Asian citrus psyllid (insect vector). Remove infected trees to protect healthy ones."
    },
    "Anthracnose": {
        "description": "Causes dark, sunken lesions on leaves, stems, and fruit. Thrives in wet weather.",
        "treatment": "Apply fungicides. Avoid overhead watering and remove infected plant parts."
    },
    "Downy Mildew": {
        "description": "Yellowish patches on upper leaf surfaces with gray, fuzzy growth underneath.",
        "treatment": "Apply fungicides. Improve air circulation and reduce leaf wetness."
    },
    "Gray Spot": {
        "description": "Small, grayish spots on leaves that can lead to leaf death in severe cases.",
        "treatment": "Use resistant varieties and apply fungicides if necessary."
    },
    "Common Rust": {
        "description": "Small, cinnamon-brown pustules on both leaf surfaces.",
        "treatment": "Use resistant hybrids and apply fungicides if infection is early and severe."
    },
    "Northern Leaf Blight": {
        "description": "Large, cigar-shaped grayish-green lesions on leaves.",
        "treatment": "Use resistant varieties and practice crop rotation."
    },
    "Black Measles": {
        "description": "Causes 'tiger-stripe' patterns on leaves and small dark spots on berries.",
        "treatment": "Prune infected wood during dormancy. Use fungicides to protect pruning wounds."
    },
    "Citrus Greening": {
        "description": "Mottled yellow leaves and misshapen, bitter fruit. Transmitted by psyllids.",
        "treatment": "Control insect vectors and remove infected trees immediately."
    }
}

def get_disease_info(prediction_name):
    # Try to find a match in our dictionary
    for key in DISEASE_INFO.keys():
        if key.lower() in prediction_name.lower():
            return DISEASE_INFO[key]
    return None

st.title("🌿 Plant Disease Detection")
st.write("Upload an image of a plant leaf to detect diseases.")

# Load the models
@st.cache_resource
def load_models():
    disease_model = tf.keras.models.load_model('best_model.keras')
    detector_model = tf.keras.models.load_model('best_plant_detector.keras')
    lefora_model = tf.keras.models.load_model('lefora.keras')
    return disease_model, detector_model, lefora_model

try:
    disease_model, detector_model, lefora_model = load_models()
except Exception as e:
    st.error(f"Error loading models: {e}")
    st.stop()

# File uploader
uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption='Uploaded Image', use_container_width=True)
    
    st.write("Checking if image contains a plant leaf...")
    
    # Preprocess for detector
    size = (224, 224)
    image_resized = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
    img_array = np.asarray(image_resized)
    
    # Check if image has 3 channels (RGB)
    if img_array.ndim == 2:  # Grayscale
        img_array = np.stack((img_array,)*3, axis=-1)
    elif img_array.shape[2] == 4:  # RGBA
        img_array = img_array[:, :, :3]
        
    normalized_image_array = (img_array.astype(np.float32) / 255.0)
    data = np.expand_dims(normalized_image_array, axis=0)
    
    # Step 1: Detect if it's a plant
    detection_score = detector_model.predict(data)[0][0]
    is_plant = detection_score > 0.5 
    
    if not is_plant:
        st.error(f"No plant detected! (Confidence: {(1-detection_score)*100:.2f}%)")
        st.warning("Please upload a clear image of a plant leaf.")
    else:
        st.success(f"Plant detected! (Confidence: {detection_score*100:.2f}%)")
        
        # Define class mappings for all models
        best_model_classes = [
            "Pepper Bell - Bacterial Spot", "Pepper Bell - Healthy",
            "Potato - Early Blight", "Potato - Late Blight", "Potato - Healthy",
            "Tomato - Bacterial Spot", "Tomato - Early Blight", "Tomato - Late Blight",
            "Tomato - Leaf Mold", "Tomato - Septoria Leaf Spot",
            "Tomato - Spider Mites (Two-spotted spider mite)", "Tomato - Target Spot",
            "Tomato - Yellow Leaf Curl Virus", "Tomato - Mosaic Virus", "Tomato - Healthy"
        ]
        
        lefora_classes = [
            'Apple___alternaria_leaf_spot', 'Apple___black_rot', 'Apple___brown_spot', 'Apple___gray_spot', 'Apple___healthy', 'Apple___rust', 'Apple___scab', 
            'Bell_pepper___bacterial_spot', 'Bell_pepper___healthy', 'Blueberry___healthy', 'Cassava___bacterial_blight', 'Cassava___brown_streak_disease', 
            'Cassava___green_mottle', 'Cassava___healthy', 'Cassava___mosaic_disease', 'Cherry___healthy', 'Cherry___powdery_mildew', 'Coffee___healthy', 
            'Coffee___red_spider_mite', 'Coffee___rust', 'Corn___common_rust', 'Corn___gray_leaf_spot', 'Corn___healthy', 'Corn___northern_leaf_blight', 
            'Grape___black_measles', 'Grape___black_rot', 'Grape___healthy', 'Grape___Leaf_blight', 'Orange___citrus_greening', 'Peach___bacterial_spot', 
            'Peach___healthy', 'Pepper__bell___Bacterial_spot', 'Pepper__bell___healthy', 'Potato___bacterial_wilt', 'Potato___Early_blight', 'Potato___healthy', 
            'Potato___Late_blight', 'Potato___leafroll_virus', 'Potato___mosaic_virus', 'Potato___nematode', 'Potato___pests', 'Potato___phytophthora', 
            'Raspberry___healthy', 'Rice___bacterial_blight', 'Rice___blast', 'Rice___brown_spot', 'Rice___tungro', 'Rose___healthy', 'Rose___rust', 
            'Rose___slug_sawfly', 'Soybean___healthy', 'Squash___powdery_mildew', 'Strawberry___healthy', 'Strawberry___leaf_scorch', 'Sugercane___healthy', 
            'Sugercane___mosaic', 'Sugercane___red_rot', 'Sugercane___rust', 'Sugercane___yellow_leaf', 'Tomato_Bacterial_spot', 'Tomato_Early_blight', 
            'Tomato_healthy', 'Tomato_Late_blight', 'Tomato_Leaf_Mold', 'Tomato_Septoria_leaf_spot', 'Tomato_Spider_mites_Two_spotted_spider_mite', 
            'Tomato__Target_Spot', 'Tomato__Tomato_mosaic_virus', 'Tomato__Tomato_YellowLeaf__Curl_Virus', 'Tomato___bacterial_spot', 'Tomato___early_blight', 
            'Tomato___healthy', 'Tomato___late_blight', 'Tomato___leaf_curl', 'Tomato___leaf_mold', 'Tomato___mosaic_virus', 'Tomato___septoria_leaf_spot', 
            'Tomato___spider_mites', 'Tomato___target_spot', 'Watermelon___anthracnose', 'Watermelon___downy_mildew', 'Watermelon___healthy', 'Watermelon___mosaic_virus'
        ]

        # Exclude these specific plants for Model 2 as requested previously
        excluded_plants = ['Cherry', 'Soybean', 'Blueberry', 'Squash', 'Peach', 'Grape', 'Coffee', 'Sugarcane', 'Watermelon', 'Raspberry', 'Potato']
        
        def get_prediction(model, data, classes, exclude_plants=None):
            pred = model.predict(data)
            probs = pred[0].copy()
            
            if exclude_plants:
                for i, class_name in enumerate(classes):
                    if any(plant.lower() in class_name.lower() for plant in exclude_plants):
                        probs[i] = 0
            
            idx = np.argmax(probs)
            conf = probs[idx]
            return classes[idx], conf, probs

        # Container for results
        st.write("## 🔍 Analysis Results")
        
        # Function to show prediction with localization
        def show_prediction_with_loc(model, data, classes, model_label, last_conv_layer, exclude_plants=None):
            st.write(f"### {model_label}")
            name, conf, probs = get_prediction(model, data, classes, exclude_plants=exclude_plants)
            st.success(f"Prediction: **{name}**")
            st.metric(label="Confidence", value=f"{conf*100:.2f}%")
            
            # Show Disease Info
            info = get_disease_info(name)
            if info:
                with st.expander(f"📖 About {name}"):
                    st.write(f"**Description:** {info['description']}")
                    st.write(f"**Treatment Suggestion:** {info['treatment']}")
            
            # Highlight detected areas
            try:
                # Generate heatmap
                heatmap = make_gradcam_heatmap(data, model, last_conv_layer)
                rects = get_rects_from_heatmap(heatmap)
                
                if rects:
                    # Draw on the 224x224 image
                    img_to_draw = (normalized_image_array * 255).astype(np.uint8).copy()
                    
                    for (x, y, w, h) in rects:
                        cv2.rectangle(img_to_draw, (x, y), (x+w, y+h), (255, 0, 0), 2)
                    
                    # Show the highlighted image
                    caption = f"Detected disease area(s) for {name}"
                    if len(rects) > 1:
                        caption += f" ({len(rects)} regions highlighted)"
                    st.image(img_to_draw, caption=caption, use_container_width=True)
                else:
                    st.info("Could not pinpoint a specific disease area.")
            except Exception as e:
                st.warning(f"Could not generate visualization: {e}")

        # 1. Best Model (224x224)
        show_prediction_with_loc(disease_model, data, best_model_classes, "Model 1: Best Plant Model", "Conv_1")
        
        # 2. Lefora Model (224x224)
        show_prediction_with_loc(lefora_model, data, lefora_classes, "Model 2: Lefora Advanced Model", "Conv_1", exclude_plants=excluded_plants)

        # Supported Plants Info
        with st.expander("📚 View Supported Plants"):
            col1, col2 = st.columns(2)
            
            def format_plant_list(classes, separator="___", exclude=None):
                plants = set()
                for c in classes:
                    # Handle different naming conventions in the models
                    if " - " in c:
                        plant = c.split(" - ")[0]
                    elif separator in c:
                        plant = c.split(separator)[0]
                    else:
                        plant = c.split("_")[0] # fallback
                    
                    if exclude and any(e.lower() in plant.lower() for e in exclude):
                        continue
                    plants.add(plant)
                return ", ".join(sorted(plants))

            with col1:
                st.write("**Model 1 Support:**")
                st.write(format_plant_list(best_model_classes))
            with col2:
                st.write("**Model 2 Support:**")
                st.write(format_plant_list(lefora_classes, exclude=excluded_plants))
