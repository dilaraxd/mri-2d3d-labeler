/**
 * MR Labeler — Ana Web Uygulama Mantığı.
 */

document.addEventListener('DOMContentLoaded', async () => {
    // State
    let configData = null;
    let volumeInfo = null;
    let currentSliceIdx = 0;
    let sliceCache = {}; // { idx: Image }
    let activeTab = 'labeling';
    let isDrawingActive = false;

    // Elements
    const statusText = document.getElementById('status-text');
    const statusDot = document.getElementById('status-dot');
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    const sampleOverlay = document.getElementById('sample-overlay');
    const sampleList = document.getElementById('sample-list');
    const canvasWrapper = document.getElementById('canvas-wrapper');
    const sliceControls = document.getElementById('slice-controls');
    const openBtn = document.getElementById('open-btn');

    const sliceSlider = document.getElementById('slice-slider');
    const sliceLabel = document.getElementById('slice-label');
    const formatLabel = document.getElementById('format-label');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');

    const labelListContainer = document.getElementById('label-list');
    const drawBtn = document.getElementById('draw-btn');
    const undoBtn = document.getElementById('undo-btn');
    const deleteLastBtn = document.getElementById('delete-last-btn');
    const clearBtn = document.getElementById('clear-btn');
    const saveBtn = document.getElementById('save-btn');
    const downloadBtn = document.getElementById('download-btn');

    const progressLabel = document.getElementById('progress-label');
    const progressBar = document.getElementById('progress-bar');
    const statsContent = document.getElementById('stats-content');

    const volOpacitySlider = document.getElementById('vol-opacity');
    const lblOpacitySlider = document.getElementById('lbl-opacity');
    const resetCameraBtn = document.getElementById('reset-camera-btn');
    const refresh3dBtn = document.getElementById('refresh-3d-btn');

    // -------------------------------------------------------------------------
    // Initialize Viewers
    // -------------------------------------------------------------------------
    const sliceViewer = new SliceViewer('slice-canvas', onPolygonCompleted);
    const viewer3D = new Viewer3D('viewer3d-container');

    // -------------------------------------------------------------------------
    // Toast Notification System
    // -------------------------------------------------------------------------
    function showToast(message, type = 'info', duration = 3000) {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    function setStatus(text, state = 'default') {
        statusText.textContent = text;
        statusDot.className = 'status-dot';
        if (state === 'active') statusDot.classList.add('active');
        if (state === 'loading') statusDot.classList.add('loading');
    }

    // -------------------------------------------------------------------------
    // Load Configuration
    // -------------------------------------------------------------------------
    async function loadConfig() {
        try {
            const res = await fetch('/api/config');
            configData = await res.json();
            sliceViewer.setColors(configData.label_colors);
            renderLabelsUI();
        } catch (e) {
            console.error('Config load failed:', e);
            showToast('Yapılandırma yüklenemedi.', 'error');
        }
    }

    function renderLabelsUI() {
        labelListContainer.innerHTML = '';
        configData.labels.forEach((label, idx) => {
            const color = configData.label_colors[label] || { hex: '#4dd8c8' };
            const item = document.createElement('div');
            item.className = `label-item ${idx === 0 ? 'selected' : ''}`;
            item.dataset.label = label;
            item.innerHTML = `
                <div class="label-dot" style="background-color: ${color.hex}; color: ${color.hex};"></div>
                <span class="label-name" style="color: ${color.hex};">${label}</span>
            `;

            item.addEventListener('click', () => {
                document.querySelectorAll('.label-item').forEach(el => el.classList.remove('selected'));
                item.classList.add('selected');
                sliceViewer.setActiveLabel(label);
            });

            labelListContainer.appendChild(item);
        });

        if (configData.labels.length > 0) {
            sliceViewer.setActiveLabel(configData.labels[0]);
        }
    }

    // -------------------------------------------------------------------------
    // Tab Switching
    // -------------------------------------------------------------------------
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            if (tab === activeTab) return;

            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(`tab-${tab}`).classList.add('active');
            activeTab = tab;

            if (tab === 'view3d') {
                viewer3D.resize();
                refresh3D();
            } else {
                sliceViewer.resize();
            }
        });
    });

    // -------------------------------------------------------------------------
    // Sample Browser
    // -------------------------------------------------------------------------
    let currentSampleLabel = '';

    async function setupSamples() {
        openBtn.addEventListener('click', () => sampleOverlay.classList.remove('hidden'));
        try {
            const res = await fetch('/api/samples');
            const data = await res.json();
            sampleList.innerHTML = '';
            (data.samples || []).forEach((s) => {
                const item = document.createElement('button');
                item.className = 'sample-item';
                item.textContent = s.label;
                item.addEventListener('click', () => loadSample(s.id, s.label));
                sampleList.appendChild(item);
            });
            if (!data.samples || !data.samples.length) {
                sampleList.innerHTML = '<div class="sample-empty">Veri seti bulunamadı.</div>';
            }
        } catch (e) {
            console.error('Samples load failed:', e);
        }
    }

    async function loadSample(id, label) {
        setStatus('Yükleniyor...', 'loading');
        try {
            const res = await fetch('/api/load_sample', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Yükleme başarısız');
            currentSampleLabel = label || id;
            showLoaded(data);
            setStatus(currentSampleLabel, 'active');
        } catch (e) {
            console.error(e);
            showToast(`Yükleme hatası: ${e.message}`, 'error');
            setStatus('Hata', 'default');
        }
    }

    function showLoaded(info) {
        sampleOverlay.classList.add('hidden');
        canvasWrapper.classList.remove('hidden');
        sliceControls.classList.remove('hidden');

        sliceCache = {};
        volumeInfo = info;
        currentSliceIdx = 0;

        sliceSlider.min = 0;
        sliceSlider.max = info.num_slices - 1;
        sliceSlider.value = 0;
        formatLabel.textContent = currentSampleLabel;

        showSlice(0);
        updateStats();
    }

    // -------------------------------------------------------------------------
    // Slice Display & Navigation
    // -------------------------------------------------------------------------
    async function showSlice(idx) {
        if (!volumeInfo || idx < 0 || idx >= volumeInfo.num_slices) return;
        currentSliceIdx = idx;

        // Update Slider UI
        sliceSlider.value = idx;
        sliceLabel.textContent = `Slice: ${idx + 1} / ${volumeInfo.num_slices}`;

        // Fetch Slice Image
        let img = sliceCache[idx];
        if (!img) {
            img = new Image();
            img.src = `/api/slice/${idx}?t=${Date.now()}`;
            await new Promise((resolve) => {
                img.onload = resolve;
            });
            sliceCache[idx] = img;
        }

        sliceViewer.setImage(img);

        // Fetch Polygons for this slice
        try {
            const res = await fetch(`/api/polygons/${idx}`);
            const data = await res.json();
            sliceViewer.polygonTool.setPolygons(data.polygons || []);
            sliceViewer.render();
        } catch (e) {
            console.error('Failed to load polygons:', e);
        }
    }

    sliceSlider.addEventListener('input', (e) => {
        showSlice(parseInt(e.target.value, 10));
    });

    prevBtn.addEventListener('click', () => {
        if (currentSliceIdx > 0) showSlice(currentSliceIdx - 1);
    });

    nextBtn.addEventListener('click', () => {
        if (volumeInfo && currentSliceIdx < volumeInfo.num_slices - 1) {
            showSlice(currentSliceIdx + 1);
        }
    });

    // Keyboard Shortcuts for slice navigation
    window.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT') return;
        if (e.key === 'ArrowRight' || e.key === 'd') {
            if (volumeInfo && currentSliceIdx < volumeInfo.num_slices - 1) {
                showSlice(currentSliceIdx + 1);
            }
        } else if (e.key === 'ArrowLeft' || e.key === 'a') {
            if (currentSliceIdx > 0) {
                showSlice(currentSliceIdx - 1);
            }
        }
    });

    // -------------------------------------------------------------------------
    // Polygon Events & Sync
    // -------------------------------------------------------------------------
    async function onPolygonCompleted(poly) {
        // Save current slice polygons to backend
        const polygons = sliceViewer.polygonTool.getPolygons().map(p => p.toDict());

        try {
            await fetch(`/api/polygons/${currentSliceIdx}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ polygons })
            });
            updateStats();
        } catch (e) {
            console.error('Failed to save polygons:', e);
        }
    }

    // Tools
    drawBtn.addEventListener('click', () => {
        isDrawingActive = !isDrawingActive;
        drawBtn.classList.toggle('active', isDrawingActive);
        sliceViewer.setDrawMode(isDrawingActive);
    });

    undoBtn.addEventListener('click', () => {
        sliceViewer.polygonTool.undo();
        sliceViewer.render();
        onPolygonCompleted(null);
    });

    deleteLastBtn.addEventListener('click', () => {
        sliceViewer.polygonTool.deleteLastPolygon();
        sliceViewer.render();
        onPolygonCompleted(null);
    });

    clearBtn.addEventListener('click', async () => {
        if (confirm(`Slice ${currentSliceIdx + 1} üzerindeki tüm etiketler silinecek. Onaylıyor musunuz?`)) {
            sliceViewer.polygonTool.clearAll();
            sliceViewer.render();
            await fetch(`/api/polygons/${currentSliceIdx}`, { method: 'DELETE' });
            updateStats();
            showToast('Slice etiketleri temizlendi.', 'info');
        }
    });

    // Save All
    saveBtn.addEventListener('click', async () => {
        try {
            const res = await fetch('/api/save', { method: 'POST' });
            const data = await res.json();
            if (res.ok) {
                showToast('Tüm etiketler kaydedildi.', 'success');
            } else {
                throw new Error(data.error);
            }
        } catch (e) {
            showToast(`Kaydetme hatası: ${e.message}`, 'error');
        }
    });

    // Download JSON
    downloadBtn.addEventListener('click', () => {
        window.location.href = '/api/download/annotations';
    });

    // -------------------------------------------------------------------------
    // Stats & Progress
    // -------------------------------------------------------------------------
    async function updateStats() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();

            progressLabel.textContent = `Etiketlenen: ${data.labeled_slices} / ${data.total_slices} slice`;
            const pct = data.total_slices > 0 ? (data.labeled_slices / data.total_slices) * 100 : 0;
            progressBar.style.width = `${pct}%`;

            let statsHtml = `
                <span>Toplam poligon: ${data.total_polygons}</span>
                <span>Etiketli slice: ${data.labeled_slices} / ${data.total_slices}</span>
            `;
            if (data.per_label) {
                for (const [name, count] of Object.entries(data.per_label)) {
                    statsHtml += `<span>• ${name}: ${count}</span>`;
                }
            }
            statsContent.innerHTML = statsHtml;
        } catch (e) {
            console.error('Stats error:', e);
        }
    }

    // -------------------------------------------------------------------------
    // 3D Visualizer Sync
    // -------------------------------------------------------------------------
    async function refresh3D() {
        if (!volumeInfo) return;
        setStatus('3D hazırlanıyor...', 'loading');

        try {
            const t = Date.now();
            await viewer3D.load(`/api/nifti/volume?t=${t}`, `/api/nifti/labels?t=${t}`);
            setStatus('3D Hazır', 'active');
        } catch (e) {
            console.error('3D load error:', e);
            setStatus('3D Hatası', 'default');
        }
    }

    refresh3dBtn.addEventListener('click', refresh3D);
    resetCameraBtn.addEventListener('click', () => viewer3D.resetCamera());

    volOpacitySlider.addEventListener('input', (e) => {
        viewer3D.setVolumeOpacity(parseFloat(e.target.value) / 100);
    });

    lblOpacitySlider.addEventListener('input', (e) => {
        viewer3D.setLabelOpacity(parseFloat(e.target.value) / 100);
    });

    // -------------------------------------------------------------------------
    // Start App
    // -------------------------------------------------------------------------
    await loadConfig();
    await setupSamples();

    try {
        const infoRes = await fetch('/api/volume/info');
        const info = await infoRes.json();
        if (info.loaded) {
            currentSampleLabel = '';
            showLoaded(info);
        }
    } catch (e) {
        console.log('No preloaded volume');
    }
});
