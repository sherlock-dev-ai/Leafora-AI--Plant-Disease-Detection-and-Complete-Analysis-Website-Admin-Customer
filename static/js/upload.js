document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('file');
    const uploadArea = document.getElementById('uploadArea');
    const previewContainer = document.getElementById('previewContainer');
    const imagePreview = document.getElementById('imagePreview');
    const removeBtn = document.getElementById('removeImage');
    const submitBtn = document.getElementById('submitBtn');
    const uploadForm = document.getElementById('uploadForm');
    const scanningOverlay = document.getElementById('scanningOverlay');

    // Drag and Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        if (uploadArea) uploadArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        if (uploadArea) uploadArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        if (uploadArea) uploadArea.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        uploadArea.classList.add('border-primary');
    }

    function unhighlight(e) {
        uploadArea.classList.remove('border-primary');
    }

    if (uploadArea) {
        uploadArea.addEventListener('drop', handleDrop, false);
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    if (fileInput) {
        fileInput.addEventListener('change', function() {
            handleFiles(this.files);
        });
    }

    function handleFiles(files) {
        if (files.length > 0) {
            const file = files[0];
            previewFile(file);
        }
    }

    function previewFile(file) {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onloadend = function() {
            if (imagePreview) imagePreview.src = reader.result;
            if (uploadArea) uploadArea.style.display = 'none';
            if (previewContainer) previewContainer.style.display = 'block';
            if (submitBtn) submitBtn.style.display = 'inline-block';
        }
    }

    if (removeBtn) {
        removeBtn.addEventListener('click', function() {
            if (fileInput) fileInput.value = '';
            if (imagePreview) imagePreview.src = '';
            if (uploadArea) uploadArea.style.display = 'block';
            if (previewContainer) previewContainer.style.display = 'none';
            if (submitBtn) submitBtn.style.display = 'none';
        });
    }

    if (uploadForm) {
        uploadForm.addEventListener('submit', function() {
            if (scanningOverlay) scanningOverlay.style.display = 'flex';
            const stepLabel = document.getElementById('scanStepText');
            if (stepLabel) {
                const steps = [
                    'Checking if this is a leaf image...',
                    'Detecting plant type...',
                    'Analyzing leaf patterns...',
                    'Preparing diagnostic report...'
                ];
                let index = 0;
                stepLabel.textContent = steps[index];
                const intervalId = setInterval(function() {
                    index += 1;
                    if (index >= steps.length) {
                        clearInterval(intervalId);
                        return;
                    }
                    stepLabel.textContent = steps[index];
                }, 1200);
            }
        });
    }
});
