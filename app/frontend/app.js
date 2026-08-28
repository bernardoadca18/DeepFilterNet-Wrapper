const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8994' : '/api';

let currentJobId = null;
let pollInterval = null;

const uploadSection = document.getElementById('upload-section');
const processingSection = document.getElementById('processing-section');
const resultSection = document.getElementById('result-section');
const errorSection = document.getElementById('error-section');
const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const progressPercentage = document.getElementById('progress-percentage');
const originalAudio = document.getElementById('original-audio');
const enhancedAudio = document.getElementById('enhanced-audio');
const downloadBtn = document.getElementById('download-btn');
const newFileBtn = document.getElementById('new-file-btn');
const retryBtn = document.getElementById('retry-btn');
const errorText = document.getElementById('error-text');

uploadArea.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFile(e.target.files[0]);
    }
});

downloadBtn.addEventListener('click', () => {
    if (currentJobId) {
        window.location.href = `${API_BASE}/download/${currentJobId}`;
    }
});

newFileBtn.addEventListener('click', resetToUpload);
retryBtn.addEventListener('click', resetToUpload);

function handleFile(file) {
    if (!file.name.toLowerCase().endsWith('.wav')) {
        showError('Only WAV files are supported');
        return;
    }

    if (file.size > 100 * 1024 * 1024) {
        showError('File size exceeds 100MB limit');
        return;
    }

    uploadFile(file);
}

async function uploadFile(file) {
    showSection('processing');
    updateProgress(0, 'Uploading file...');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/enhance`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }

        const data = await response.json();
        currentJobId = data.job_id;
        
        pollJobStatus(file);
    } catch (error) {
        showError(error.message);
    }
}

async function pollJobStatus(originalFile) {
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/status/${currentJobId}`);
            
            if (!response.ok) {
                throw new Error('Failed to get job status');
            }

            const job = await response.json();
            
            updateProgress(job.progress, job.message);

            if (job.status === 'completed') {
                clearInterval(pollInterval);
                showResult(originalFile);
            } else if (job.status === 'failed') {
                clearInterval(pollInterval);
                showError(job.error || 'Processing failed');
            }
        } catch (error) {
            clearInterval(pollInterval);
            showError(error.message);
        }
    }, 1000);
}

function updateProgress(percentage, message) {
    progressFill.style.width = `${percentage}%`;
    progressPercentage.textContent = `${percentage}%`;
    progressText.textContent = message;
}

async function showResult(originalFile) {
    showSection('result');

    const originalUrl = URL.createObjectURL(originalFile);
    originalAudio.src = originalUrl;

    const enhancedUrl = `${API_BASE}/download/${currentJobId}`;
    enhancedAudio.src = enhancedUrl;
}

function showError(message) {
    if (pollInterval) {
        clearInterval(pollInterval);
    }
    errorText.textContent = message;
    showSection('error');
}

function resetToUpload() {
    if (pollInterval) {
        clearInterval(pollInterval);
    }
    currentJobId = null;
    fileInput.value = '';
    progressFill.style.width = '0%';
    showSection('upload');
}

function showSection(section) {
    uploadSection.style.display = section === 'upload' ? 'block' : 'none';
    processingSection.style.display = section === 'processing' ? 'block' : 'none';
    resultSection.style.display = section === 'result' ? 'block' : 'none';
    errorSection.style.display = section === 'error' ? 'block' : 'none';
}

async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const health = await response.json();
        console.log('API Health:', health);
    } catch (error) {
        console.error('API not reachable:', error);
    }
}

checkHealth();
