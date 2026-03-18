"""
Plant Type Detection Module
Detects the plant/crop type from disease predictions to filter results
"""
import re
from typing import List, Dict, Optional

# Plant keywords mapping
PLANT_KEYWORDS = {
    'rice': ['rice', 'tungro', 'blast', 'brownspot', 'bacterial blight'],
    'wheat': ['wheat', 'rust', 'smut', 'scab', 'mildew', 'blight', 'aphid', 'mite', 'stem fly'],
    'cotton': ['cotton', 'bollworm', 'boll rot', 'aphid', 'mealy bug', 'whitefly', 'thrips', 'wilt', 'leaf curl', 'bacterial blight'],
    'maize': ['maize', 'corn', 'ear rot', 'armyworm', 'stem borer'],
    'sugarcane': ['sugarcane', 'mosaic', 'redrot', 'redrust', 'yellow rust'],
    # Dataset 16/17 additions
    'apple': ['apple', 'scab', 'cedar apple rust', 'powdery mildew', 'healthy'],
    'tomato': ['tomato', 'bacterial spot', 'early blight', 'late blight', 'leaf mold', 'septoria', 'spider mites', 'target spot', 'mosaic virus', 'yellow leaf curl', 'healthy'],
    'potato': ['potato', 'early blight', 'late blight', 'healthy'],
    'pepper': ['pepper', 'bell', 'bacterial spot', 'healthy'],
    'blueberry': ['blueberry', 'healthy'],
    'cherry': ['cherry', 'powdery mildew', 'healthy'],
    'grape': ['grape', 'black rot', 'esca', 'leaf blight', 'healthy'],
    'peach': ['peach', 'bacterial spot', 'healthy'],
    'raspberry': ['raspberry', 'healthy'],
    'rose': ['rose', 'healthy'],
    'soybean': ['soybean', 'healthy'],
    'squash': ['squash', 'powdery mildew'],
    'strawberry': ['strawberry', 'leaf scorch', 'healthy'],
    'watermelon': ['watermelon', 'healthy']
}

# Plant name variations
PLANT_NAMES = {
    'rice': ['rice', 'paddy'],
    'wheat': ['wheat'],
    'cotton': ['cotton'],
    'maize': ['maize', 'corn'],
    'sugarcane': ['sugarcane', 'sugar cane'],
    'apple': ['apple'],
    'tomato': ['tomato'],
    'potato': ['potato'],
    'pepper': ['pepper', 'bell pepper'],
    'blueberry': ['blueberry'],
    'cherry': ['cherry'],
    'grape': ['grape'],
    'peach': ['peach'],
    'raspberry': ['raspberry'],
    'rose': ['rose'],
    'soybean': ['soybean'],
    'squash': ['squash'],
    'strawberry': ['strawberry'],
    'watermelon': ['watermelon']
}


def detect_plant_type(predictions: List[Dict]) -> Optional[str]:
    """
    Detect plant type from prediction results
    
    Args:
        predictions: List of prediction dicts with 'label' field
    
    Returns:
        Detected plant type ('rice', 'wheat', 'cotton', 'maize', 'sugarcane', etc.) or None
    """
    if not predictions:
        return None
    
    # Count plant mentions in predictions
    plant_scores = {plant: 0 for plant in PLANT_KEYWORDS.keys()}
    
    # Check each prediction
    for pred in predictions[:5]:  # Check top 5 predictions
        label = pred.get('label', '').lower()
        confidence = pred.get('confidence', 0) or pred.get('prob', 0) * 100
        
        # Weight by confidence (higher confidence = more weight)
        weight = confidence / 100.0 if confidence > 0 else 0.5
        
        # Check for plant keywords
        for plant, keywords in PLANT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in label:
                    # Boost score if keyword IS the plant name
                    score_boost = 1.0
                    if keyword == plant or keyword in PLANT_NAMES.get(plant, []):
                        score_boost = 5.0  # Strong bias towards explicit plant name match
                    
                    plant_scores[plant] += weight * score_boost
                    # Don't break here, as a label might match multiple keywords/plants
                    # But we should probably count it only once per plant
                    break
    
    # Find plant with highest score
    if plant_scores:
        max_plant = max(plant_scores.items(), key=lambda x: x[1])
        if max_plant[1] > 0:  # Only return if we found something
            return max_plant[0]
    
    return None


def filter_predictions_by_plant(predictions: List[Dict], detected_plant: str) -> List[Dict]:
    """
    Filter predictions to only include those matching the detected plant type
    
    Args:
        predictions: List of prediction dicts
        detected_plant: Detected plant type ('rice', 'wheat', etc.)
    
    Returns:
        Filtered list of predictions
    """
    if not detected_plant or not predictions:
        return predictions
    
    keywords = PLANT_KEYWORDS.get(detected_plant, [])
    if not keywords:
        return predictions
    
    # Filter predictions that match the plant type
    filtered = []
    for pred in predictions:
        label = pred.get('label', '').lower()
        
        # Special case: 'healthy' matches the specific plant if it contains the plant name
        # e.g. 'Tomato - Healthy' matches 'tomato'
        # But we also added 'healthy' to the keywords for each plant where applicable
        
        # Check if label contains any keyword for this plant
        if any(keyword in label for keyword in keywords):
            filtered.append(pred)
    
    # If we filtered out everything, return original (better than nothing)
    if not filtered:
        return predictions
    
    return filtered


def get_plant_from_label(label: str) -> Optional[str]:
    """
    Extract plant type from a single label
    
    Args:
        label: Disease label string
    
    Returns:
        Plant type or None
    """
    label_lower = label.lower()
    
    for plant, keywords in PLANT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in label_lower:
                return plant
    
    return None
