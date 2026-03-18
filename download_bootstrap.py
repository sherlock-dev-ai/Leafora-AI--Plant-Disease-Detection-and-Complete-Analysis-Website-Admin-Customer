"""
Script to download Bootstrap files for offline use
Run this script to automatically download Bootstrap CSS and JS files
"""
import os
import urllib.request

def download_bootstrap():
    """Download Bootstrap 5.3.2 files for offline use"""
    
    # URLs
    bootstrap_css_url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css"
    bootstrap_js_url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"
    
    # Local paths
    css_dir = "static/bootstrap/css"
    js_dir = "static/bootstrap/js"
    css_file = os.path.join(css_dir, "bootstrap.min.css")
    js_file = os.path.join(js_dir, "bootstrap.bundle.min.js")
    
    # Create directories
    os.makedirs(css_dir, exist_ok=True)
    os.makedirs(js_dir, exist_ok=True)
    
    print("Downloading Bootstrap files...")
    
    try:
        # Download CSS
        print(f"Downloading CSS from {bootstrap_css_url}...")
        urllib.request.urlretrieve(bootstrap_css_url, css_file)
        print(f"✓ CSS saved to {css_file}")
        
        # Download JS
        print(f"Downloading JS from {bootstrap_js_url}...")
        urllib.request.urlretrieve(bootstrap_js_url, js_file)
        print(f"✓ JS saved to {js_file}")
        
        print("\n✅ Bootstrap files downloaded successfully!")
        print("The application is now ready to run offline.")
        
    except Exception as e:
        print(f"\n❌ Error downloading files: {str(e)}")
        print("\nPlease download manually:")
        print("1. Visit: https://getbootstrap.com/docs/5.3/getting-started/download/")
        print("2. Download 'Compiled CSS and JS'")
        print("3. Extract and copy files to:")
        print(f"   - {css_file}")
        print(f"   - {js_file}")

if __name__ == "__main__":
    download_bootstrap()

