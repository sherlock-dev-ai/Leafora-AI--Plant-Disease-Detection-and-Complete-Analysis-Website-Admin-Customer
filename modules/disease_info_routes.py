"""
Disease Information & Treatment Management Module
Handles routes for viewing supported plants and disease information
"""
from flask import Blueprint, render_template
import logging

from modules import disease_info

logger = logging.getLogger(__name__)

def init_disease_info_routes():
    """Initialize disease info routes"""
    disease_info_bp = Blueprint('disease_info', __name__)
    
    @disease_info_bp.route('/supported-plants')
    def supported_plants():
        """Show supported plant types, treating rose and cassava as beta"""
        try:
            import json, os
            artifacts_path = os.path.join(os.getcwd(), 'artifacts', 'discovered_plants.json')
            ready_plants = []
            beta_plants = []
            manual_beta = {'orange', 'rose', 'strawberry', 'sugercane'}
            
            if os.path.exists(artifacts_path):
                with open(artifacts_path, 'r', encoding='utf-8') as f:
                    dj = json.load(f)
                    for p, info in (dj.get('by_plant') or {}).items():
                        status = (info or {}).get('status')
                        name_key = str(p).lower()
                        name_cap = str(p).capitalize()
                        if name_key in manual_beta or status == 'beta':
                            beta_plants.append(name_cap)
                        elif status == 'ready':
                            ready_plants.append(name_cap)
            else:
                # Fallback: build plant list from disease_info definitions
                try:
                    all_diseases = disease_info.get_all_diseases()
                    for d in all_diseases:
                        if ' - ' not in d:
                            continue
                        plant = d.split('-', 1)[0].strip()
                        if not plant or 'background' in plant.lower():
                            continue
                        ready_plants.append(plant.capitalize())
                except Exception:
                    pass
            
            ready_plants = sorted(set(ready_plants))
            beta_plants = sorted(set(beta_plants))
            
            # Keep Rice and Cassava (any variant containing 'rice' or 'cassava') in Basic/Pro;
            # move everything else to Beta
            pro_ready = [p for p in ready_plants if any(k in p.lower() for k in ('rice', 'cassava'))]
            extra_beta = [p for p in ready_plants if p not in pro_ready]
            basic_plants = pro_ready
            pro_plants = pro_ready
            manual_beta_plants = ["Orange", "Rose", "Strawberry", "Sugercane"]
            beta_plants = sorted(set(beta_plants + extra_beta + manual_beta_plants))
            
            return render_template('supported_plants.html',
                                 basic_plants=basic_plants,
                                 pro_plants=pro_plants,
                                 beta_plants=beta_plants,
                                 num_basic=len(basic_plants),
                                 num_pro=len(pro_plants))
        except Exception as e:
            logger.error(f"Error loading supported plants: {e}")
            return render_template('supported_plants.html',
                                 basic_plants=[],
                                 pro_plants=[],
                                 beta_plants=[],
                                 num_basic=0,
                                 num_pro=0)
    
    
    @disease_info_bp.route('/disease-info/<disease_name>')
    def disease_info_page(disease_name):
        """Get disease information page"""
        info = disease_info.get_disease_info(disease_name)
        return render_template('disease_info.html', 
                             disease_name=disease_name,
                             treatment_info=info)
    
    return disease_info_bp
