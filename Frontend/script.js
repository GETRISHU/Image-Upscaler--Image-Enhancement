// 🌐 Change this to your Render backend URL
const BACKEND_URL = "https://image-upscaler-image-enhancement.onrender.com";

class ImageUpscaler {
    constructor() {
        this.selectedFile = null;
        this.initializeElements();
        this.bindEvents();
    }

    initializeElements() {
        this.uploadArea = document.getElementById('uploadArea');
        this.fileInput = document.getElementById('fileInput');
        this.uploadBtn = document.getElementById('uploadBtn');
        this.scaleSelect = document.getElementById('scaleSelect');
        this.uploadSection = document.getElementById('uploadSection');
        this.progressSection = document.getElementById('progressSection');
        this.resultsSection = document.getElementById('resultsSection');
        this.progressFill = document.getElementById('progressFill');
        this.progressText = document.getElementById('progressText');
        this.originalImage = document.getElementById('originalImage');
        this.upscaledImage = document.getElementById('upscaledImage');
        this.originalInfo = document.getElementById('originalInfo');
        this.upscaledInfo = document.getElementById('upscaledInfo');
        this.downloadBtn = document.getElementById('downloadBtn');
        this.newUploadBtn = document.getElementById('newUploadBtn');
        this.errorModal = document.getElementById('errorModal');
        this.closeModal = document.getElementById('closeModal');
        this.errorMessage = document.getElementById('errorMessage');
    }

    bindEvents() {
        this.uploadArea.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));

        this.uploadArea.addEventListener('dragover', (e) => this.handleDragOver(e));
        this.uploadArea.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        this.uploadArea.addEventListener('drop', (e) => this.handleDrop(e));

        this.uploadBtn.addEventListener('click', () => this.uploadImage());
        this.newUploadBtn.addEventListener('click', () => this.resetUploader());
        this.closeModal.addEventListener('click', () => this.hideError());

        this.errorModal.addEventListener('click', (e) => {
            if (e.target === this.errorModal) this.hideError();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.hideError();
        });
    }

    handleDragOver(e) {
        e.preventDefault();
        this.uploadArea.classList.add('dragover');
    }

    handleDragLeave(e) {
        e.preventDefault();
        this.uploadArea.classList.remove('dragover');
    }

    handleDrop(e) {
        e.preventDefault();
        this.uploadArea.classList.remove('dragover');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.handleFileSelect({ target: { files } });
        }
    }

    handleFileSelect(e) {
        const file = e.target.files[0];
        if (!file) return;

        const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
        if (!allowedTypes.includes(file.type)) {
            this.showError('Please select a valid image file (PNG, JPG, JPEG, or WebP).');
            return;
        }

        if (file.size > 16 * 1024 * 1024) {
            this.showError('File size must be less than 16MB.');
            return;
        }

        this.selectedFile = file;
        this.uploadBtn.disabled = false;
        this.updateUploadAreaWithFile(file);
    }

    updateUploadAreaWithFile(file) {
        const uploadContent = this.uploadArea.querySelector('.upload-content');
        uploadContent.innerHTML = `
            <i class="fas fa-check-circle upload-icon" style="color: #10b981;"></i>
            <h3>File Selected</h3>
            <p><strong>${file.name}</strong></p>
            <div class="file-types">
                <span>Size: ${this.formatFileSize(file.size)}</span>
            </div>
        `;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async uploadImage() {
        if (!this.selectedFile) {
            this.showError('Please select an image file first.');
            return;
        }

        this.showProgress();

        const formData = new FormData();
        formData.append('file', this.selectedFile);
        formData.append('scale_factor', this.scaleSelect.value);

        try {
            this.animateProgress();

            const response = await fetch(`${BACKEND_URL}/upload`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                this.showResults(result);
            } else {
                this.showError(result.error || 'An error occurred while processing your image.');
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showError('Network error. Please check your connection and try again.');
        } finally {
            this.hideProgress();
        }
    }

    animateProgress() {
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 15;
            if (progress > 90) progress = 90;

            this.progressFill.style.width = progress + '%';

            if (progress < 30) {
                this.progressText.textContent = 'Uploading image...';
            } else if (progress < 60) {
                this.progressText.textContent = 'Processing image...';
            } else {
                this.progressText.textContent = 'Applying upscaling algorithm...';
            }
        }, 200);

        this.progressInterval = interval;
    }

    showProgress() {
        this.uploadSection.style.display = 'none';
        this.resultsSection.style.display = 'none';
        this.progressSection.style.display = 'block';
        this.progressSection.classList.add('fade-in');
        this.progressFill.style.width = '0%';
    }

    hideProgress() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }
        this.progressFill.style.width = '100%';
        setTimeout(() => {
            this.progressSection.style.display = 'none';
        }, 500);
    }

    showResults(result) {
        this.originalImage.src = `${BACKEND_URL}${result.original_url}`;
        this.upscaledImage.src = `${BACKEND_URL}${result.upscaled_url}`;

        this.originalInfo.innerHTML = `
            <div><strong>Dimensions:</strong> ${result.original_dimensions[0]} × ${result.original_dimensions[1]}</div>
            <div><strong>File Size:</strong> ${this.formatFileSize(result.original_size)}</div>
        `;

        this.upscaledInfo.innerHTML = `
            <div><strong>Dimensions:</strong> ${result.upscaled_dimensions[0]} × ${result.upscaled_dimensions[1]}</div>
            <div><strong>File Size:</strong> ${this.formatFileSize(result.upscaled_size)}</div>
            <div><strong>Scale Factor:</strong> ${result.scale_factor}x</div>
        `;

        this.downloadBtn.onclick = () => {
            window.open(`${BACKEND_URL}${result.download_url}`, '_blank');
        };

        this.resultsSection.style.display = 'block';
        this.resultsSection.classList.add('slide-up');
    }

    resetUploader() {
        this.selectedFile = null;
        this.uploadBtn.disabled = true;

        const uploadContent = this.uploadArea.querySelector('.upload-content');
        uploadContent.innerHTML = `
            <i class="fas fa-cloud-upload-alt upload-icon"></i>
            <h3>Drag & Drop Your Image</h3>
            <p>or <span class="browse-text">browse files</span></p>
            <div class="file-types">
                <span>Supports: PNG, JPG, JPEG, WebP</span>
            </div>
        `;

        this.fileInput.value = '';
        this.uploadSection.style.display = 'block';
        this.resultsSection.style.display = 'none';
        this.progressSection.style.display = 'none';
    }

    showError(message) {
        this.errorMessage.textContent = message;
        this.errorModal.style.display = 'flex';
        this.hideProgress();
    }

    hideError() {
        this.errorModal.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ImageUpscaler();
});

// ------------------------------
// Extra bottom listener (cleaned)
// ------------------------------
document.getElementById('uploadBtn').addEventListener('click', async () => {
    const fileInput = document.getElementById('fileInput');
    const scaleSelect = document.getElementById('scaleSelect');
    const file = fileInput.files[0];
    const scale = scaleSelect.value;

    if (!file) return alert("Please select a file");

    const formData = new FormData();
    formData.append('file', file);
    formData.append('scale_factor', scale);

    document.getElementById('progressSection').style.display = 'block';

    try {
        const res = await fetch(`${BACKEND_URL}/upload`, {
            method: 'POST',
            body: formData
        });

        const data = await res.json();

        if (data.error) {
            document.getElementById('errorMessage').textContent = data.error;
            document.getElementById('errorModal').style.display = 'block';
            document.getElementById('progressSection').style.display = 'none';
            return;
        }

        document.getElementById('progressSection').style.display = 'none';
        document.getElementById('resultsSection').style.display = 'block';

        document.getElementById('originalImage').src = `${BACKEND_URL}${data.original_url}`;
        document.getElementById('upscaledImage').src = `${BACKEND_URL}${data.upscaled_url}`;
        document.getElementById('downloadBtn').onclick = () => {
            window.location.href = `${BACKEND_URL}${data.download_url}`;
        };

        document.getElementById('originalInfo').textContent =
            `Size: ${(data.original_size / 1024).toFixed(2)} KB, Dimensions: ${data.original_dimensions}`;
        document.getElementById('upscaledInfo').textContent =
            `Size: ${(data.upscaled_size / 1024).toFixed(2)} KB, Dimensions: ${data.upscaled_dimensions}`;

    } catch (err) {
        document.getElementById('errorMessage').textContent = 'Something went wrong';
        document.getElementById('errorModal').style.display = 'block';
    }
});
