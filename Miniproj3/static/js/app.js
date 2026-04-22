/* app.js - Main Application Logic & State */

// Global state to share across different modules
window.appState = {
    summary: null,
    data: [],
    originalData: [],
    isModelTrained: false
};

document.addEventListener('DOMContentLoaded', () => {
    initAuth();
    initTheme();
    initNavigation();
    initUploadForm();
});

function initAuth() {
    const loginForm = document.getElementById('login-form');
    const overlay = document.getElementById('login-overlay');
    const mainApp = document.getElementById('main-app');
    const logoutBtn = document.getElementById('logout-btn');
    const roleSpan = document.getElementById('current-user-role');
    
    loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const role = email.toLowerCase().includes('admin') ? 'Admin' : 'User';
        
        roleSpan.textContent = role;
        
        overlay.classList.remove('active');
        setTimeout(() => { overlay.style.display = 'none'; }, 400);
        mainApp.classList.remove('hidden');
    });

    logoutBtn.addEventListener('click', () => {
        // Reset app state on logout
        window.appState.isModelTrained = false;
        window.appState.data = [];
        
        overlay.style.display = 'flex';
        setTimeout(() => { overlay.classList.add('active'); }, 50);
        mainApp.classList.add('hidden');
        
        document.querySelectorAll('.page-section').forEach(sec => sec.classList.add('hidden'));
        document.getElementById('upload-page').classList.remove('hidden');
        document.getElementById('top-header').classList.add('hidden');
        document.getElementById('sidebar').classList.add('hidden');
    });
}

function initTheme() {
    const themeBtn = document.getElementById('theme-toggle');
    themeBtn.addEventListener('click', () => {
        document.body.classList.toggle('light-theme');
        const isLight = document.body.classList.contains('light-theme');
        themeBtn.innerHTML = isLight ? '<i class="fa-solid fa-moon"></i>' : '<i class="fa-solid fa-sun"></i>';
        
        // Let charts know about theme change if they exist
        if (window.appState.isModelTrained && window.dashboardChart) {
            window.dashboardChart.updateTheme(isLight);
        }
    });
}

function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.page-section');
    const pageTitle = document.getElementById('page-title');
    const pageSubtitle = document.getElementById('page-subtitle');
    
    const titles = {
        'dashboard-page': { title: 'Dashboard Overview', sub: 'Key metrics and center predictions' },
        'heatmap-page': { title: 'Geographic Heatmap', sub: 'Interactive map of demand zones' },
        'reports-page': { title: 'Detailed Reports', sub: 'Tabular data and exports' },
        'upload-page': { title: 'New Upload', sub: 'Process a new dataset' }
    };

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Prevent navigating if model isn't trained and they try to go somewhere else
            const targetId = item.getAttribute('data-target');
            if (targetId !== 'upload-page' && !window.appState.isModelTrained) {
                Swal.fire({
                    icon: 'warning',
                    title: 'No Data',
                    text: 'Please upload and analyze a dataset first.',
                    background: document.body.classList.contains('light-theme') ? '#fff' : '#1e293b',
                    color: document.body.classList.contains('light-theme') ? '#000' : '#fff'
                });
                return;
            }

            // Update active nav
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            // Update active section
            sections.forEach(sec => sec.classList.add('hidden'));
            document.getElementById(targetId).classList.remove('hidden');
            
            // Update Headers
            if (titles[targetId]) {
                pageTitle.textContent = titles[targetId].title;
                pageSubtitle.textContent = titles[targetId].sub;
            }
            
            // Trigger specific page renders
            if (targetId === 'dashboard-page') {
                // Charts auto-resize mostly, but scatter might need trigger
            } else if (targetId === 'heatmap-page') {
                // Leaflet needs to know its container size changed
                setTimeout(() => {
                    if (window.heatmapMap) window.heatmapMap.resize();
                }, 100);
            }
        });
    });
}

function initUploadForm() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('dataset');
    const selectedFile = document.getElementById('selected-file-info');
    const uploadBtn = document.getElementById('upload-btn');
    const form = document.getElementById('upload-form');

    // Click to open file dialog
    uploadArea.addEventListener('click', () => fileInput.click());

    // Drag events
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
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            handleFileSelect();
        }
    });

    // File input change
    fileInput.addEventListener('change', handleFileSelect);

    function handleFileSelect() {
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            const extension = file.name.split('.').pop().toLowerCase();
            
            if (extension === 'csv' || extension === 'xlsx') {
                selectedFile.innerHTML = `<i class="fa-solid fa-file-${extension === 'csv' ? 'csv' : 'excel'}"></i> <strong>${file.name}</strong> (${(file.size / 1024).toFixed(1)} KB)`;
                selectedFile.classList.remove('hidden');
                uploadBtn.disabled = false;
            } else {
                Swal.fire('Invalid File', 'Please upload a .csv or .xlsx file.', 'error');
                resetUpload();
            }
        }
    }

    function resetUpload() {
        fileInput.value = '';
        selectedFile.classList.add('hidden');
        uploadBtn.disabled = true;
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!fileInput.files.length) return;

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        // Transition to Processing Route
        transitionToProcessing();

        try {
            // It will be sent to the relative /upload endpoint
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok) {
                // Success! Save data and init modules
                window.appState.summary = result.summary;
                window.appState.data = result.data;
                window.appState.originalData = result.data;
                window.appState.isModelTrained = true;

                // Simulate progress bar completing
                document.getElementById('progress-bar').style.width = '100%';
                
                setTimeout(() => {
                    populateKPIs(result.summary);
                    
                    // Initialize Dashboard Charts
                    if (window.dashboardChart) {
                        window.dashboardChart.init(result.data);
                    }
                    
                    // Initialize Map
                    if (window.heatmapMap) {
                        window.heatmapMap.init(result.data);
                    }
                    
                    // Initialize Reports
                    if (window.reportsTable) {
                        window.reportsTable.init(result.data, result.summary);
                    }

                    // Show sidebar & header, go to dashboard
                    document.getElementById('sidebar').classList.remove('hidden');
                    document.getElementById('top-header').classList.remove('hidden');
                    document.querySelector('[data-target="dashboard-page"]').click();
                    
                    // Toast success
                    Swal.fire({
                        icon: 'success',
                        title: 'Model Trained Successfully!',
                        text: `Processed ${result.summary.total_rows} records.`,
                        timer: 2000,
                        showConfirmButton: false,
                        background: document.body.classList.contains('light-theme') ? '#fff' : '#1e293b',
                        color: document.body.classList.contains('light-theme') ? '#000' : '#fff'
                    });
                }, 800);

            } else {
                throw new Error(result.error || 'Server error occurred');
            }
        } catch (error) {
            Swal.fire({
                icon: 'error',
                title: 'Processing Failed',
                text: error.message,
                background: document.body.classList.contains('light-theme') ? '#fff' : '#1e293b',
                color: document.body.classList.contains('light-theme') ? '#000' : '#fff'
            });
            // Revert back
            document.getElementById('processing-page').classList.add('hidden');
            document.getElementById('upload-page').classList.remove('hidden');
        }
    });

    function transitionToProcessing() {
        // Hide upload, header, sidebar based on state
        document.getElementById('upload-page').classList.add('hidden');
        document.getElementById('processing-page').classList.remove('hidden');
        
        // Animate progress bar
        const pb = document.getElementById('progress-bar');
        pb.style.width = '0%';
        setTimeout(() => { pb.style.width = '40%'; }, 500);
        setTimeout(() => { pb.style.width = '75%'; }, 1500);
    }
}

function populateKPIs(summary) {
    // animate numbers
    animateValue("kpi-total-areas", 0, summary.total_rows, 1000);
    animateValue("kpi-high-demand", 0, summary.high_demand_areas, 1000);
    animateValue("kpi-medium-demand", 0, summary.medium_demand_areas, 1000);
    animateValue("kpi-total-needed", 0, summary.total_new_centers_needed, 1000);
}

function animateValue(id, start, end, duration) {
    if (start === end) {
        document.getElementById(id).textContent = end;
        return;
    }
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        let current = Math.floor(progress * (end - start) + start);
        document.getElementById(id).textContent = current.toLocaleString();
        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            document.getElementById(id).textContent = end.toLocaleString();
        }
    };
    window.requestAnimationFrame(step);
}
