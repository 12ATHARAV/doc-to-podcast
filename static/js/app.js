document.addEventListener('DOMContentLoaded', () => {
    // --- Elements ---
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    const uploadSection = document.getElementById('upload-section');
    const progressSection = document.getElementById('progress-section');
    const playerSection = document.getElementById('player-section');
    
    const progressBarFill = document.getElementById('progress-bar-fill');
    const progressPctText = document.getElementById('progress-pct');
    const progressStepText = document.getElementById('progress-step-text');
    
    const audioTitle = document.getElementById('audio-title');
    const audioSource = document.getElementById('audio-source');
    const audioPlayer = document.getElementById('audio-player');
    const downloadBtn = document.getElementById('download-btn');
    const generateNewBtn = document.getElementById('generate-new-btn');
    
    const stepItems = {
        'parsing': document.getElementById('step-parsing'),
        'analyzing': document.getElementById('step-analyzing'),
        'outlining': document.getElementById('step-outlining'),
        'writing': document.getElementById('step-writing'),
        'reviewing': document.getElementById('step-reviewing'),
        'synthesizing': document.getElementById('step-synthesizing'),
        'processing_audio': document.getElementById('step-audio'),
    };

    const geminiKeyInput = document.getElementById('gemini-key-input');
    const groqKeyInput = document.getElementById('groq-key-input');
    const settingsToggle = document.getElementById('settings-toggle');
    const settingsContent = document.getElementById('settings-content');
    const settingsToggleIcon = document.getElementById('settings-toggle-icon');

    let socket = null;

    // --- API Settings Accordion & Storage ---
    if (settingsToggle && settingsContent && settingsToggleIcon) {
        // Load stored keys
        if (geminiKeyInput) {
            geminiKeyInput.value = localStorage.getItem('gemini_api_key') || '';
            geminiKeyInput.addEventListener('input', () => {
                localStorage.setItem('gemini_api_key', geminiKeyInput.value.trim());
            });
        }
        if (groqKeyInput) {
            groqKeyInput.value = localStorage.getItem('groq_api_key') || '';
            groqKeyInput.addEventListener('input', () => {
                localStorage.setItem('groq_api_key', groqKeyInput.value.trim());
            });
        }

        // Accordion functionality
        let isCollapsed = localStorage.getItem('settings_collapsed') === 'true';
        
        function updateToggleState() {
            if (isCollapsed) {
                settingsContent.style.maxHeight = '0px';
                settingsContent.style.opacity = '0';
                settingsToggleIcon.style.transform = 'rotate(-90deg)';
            } else {
                settingsContent.style.maxHeight = '500px';
                settingsContent.style.opacity = '1';
                settingsToggleIcon.style.transform = 'rotate(0deg)';
            }
        }
        
        // Initial sync
        updateToggleState();
        
        settingsToggle.addEventListener('click', () => {
            isCollapsed = !isCollapsed;
            localStorage.setItem('settings_collapsed', isCollapsed);
            updateToggleState();
        });
    }

    // --- Drag and Drop Handlers ---
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
        }, false);
    });

    uploadZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    uploadZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFile(fileInput.files[0]);
        }
    });

    // --- File Ingestion & API Call ---
    async function handleFile(file) {
        // Enforce basic extension whitelist
        const allowedExtensions = ['.pdf', '.docx', '.doc', '.pptx', '.txt', '.md', '.rtf', '.csv', '.xlsx', '.json', '.xml', '.html', '.htm'];
        const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        
        if (!allowedExtensions.includes(fileExt)) {
            alert(`Unsupported file format. Supported formats: ${allowedExtensions.join(', ')}`);
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('gemini_api_key', geminiKeyInput ? geminiKeyInput.value.trim() : '');
        formData.append('groq_api_key', groqKeyInput ? groqKeyInput.value.trim() : '');

        try {
            // Show loading view
            uploadSection.style.display = 'none';
            progressSection.style.display = 'block';
            resetSteps();
            updateProgressBar(0, 'Initializing pipeline...');

            // Trigger Upload API
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to upload document.');
            }

            const job = await response.json();
            logger(`Job created successfully: ${job.id}`);
            
            // Connect WebSocket for updates
            connectWebSocket(job.id, file.name);

        } catch (error) {
            logger(`Upload error: ${error.message}`);
            alert(`Error: ${error.message}`);
            // Restore upload zone
            progressSection.style.display = 'none';
            uploadSection.style.display = 'block';
        }
    }

    // --- WebSocket progress listener ---
    function connectWebSocket(jobId, filename) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/progress/${jobId}`;
        
        socket = new WebSocket(wsUrl);

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            logger(`WS Update:`, data);

            const progress = data.progress || 0;
            const step = data.step || 'Processing...';
            const status = data.status;

            updateProgressBar(progress, step);
            updateStepList(status);

            if (status === 'completed' || step.toLowerCase() === 'finished') {
                socket.close();
                showAudioPlayer(jobId, filename, data.output_file);
            } else if (status === 'failed') {
                socket.close();
                alert(`Pipeline failed: ${data.error || 'Unknown error'}`);
                progressSection.style.display = 'none';
                uploadSection.style.display = 'block';
            }
        };

        socket.onclose = () => {
            logger("WebSocket closed");
        };

        socket.onerror = (error) => {
            logger("WebSocket error: ", error);
        };
    }

    // --- DOM Update Handlers ---
    function updateProgressBar(progress, stepName) {
        const pct = Math.round(progress * 100);
        progressBarFill.style.width = `${pct}%`;
        progressPctText.innerText = `${pct}%`;
        progressStepText.innerText = stepName;
    }

    function updateStepList(activeStatus) {
        // Clear all active classes
        Object.keys(stepItems).forEach(key => {
            stepItems[key].classList.remove('active');
        });

        // Set state classifications
        const statusOrder = [
            'parsing',
            'analyzing',
            'outlining',
            'writing',
            'reviewing',
            'synthesizing',
            'processing_audio'
        ];

        const activeIndex = statusOrder.indexOf(activeStatus);
        
        statusOrder.forEach((status, idx) => {
            const el = stepItems[status];
            if (!el) return;

            if (idx < activeIndex) {
                el.classList.add('completed');
                el.classList.remove('active');
            } else if (idx === activeIndex) {
                el.classList.add('active');
                el.classList.remove('completed');
            } else {
                el.classList.remove('completed', 'active');
            }
        });
    }

    function resetSteps() {
        Object.keys(stepItems).forEach(key => {
            stepItems[key].classList.remove('active', 'completed');
        });
        progressBarFill.style.width = '0%';
        progressPctText.innerText = '0%';
        progressStepText.innerText = 'Starting pipeline...';
    }

    function showAudioPlayer(jobId, filename, outputFile) {
        progressSection.style.display = 'none';
        playerSection.style.display = 'block';

        // Clean document extension from title
        const cleanTitle = filename.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ");
        audioTitle.innerText = `Podcast Overview: ${cleanTitle}`;

        const downloadUrl = `/api/download/${jobId}`;
        
        // Load Audio into HTML5 player
        audioSource.src = downloadUrl;
        audioPlayer.load();

        // Connect button link
        downloadBtn.href = downloadUrl;
        downloadBtn.setAttribute('download', outputFile || `podcast_${jobId}.mp3`);
    }

    // --- Reset button ---
    generateNewBtn.addEventListener('click', () => {
        playerSection.style.display = 'none';
        uploadSection.style.display = 'block';
        fileInput.value = '';
    });

    // Helper logging util
    function logger(...args) {
        console.log('[DocToPodcast]', ...args);
    }
});
