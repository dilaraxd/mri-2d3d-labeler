/**
 * Slice Viewer — HTML5 Canvas tabanlı 2D MR Slice görüntüleyici.
 * Zoom, Pan ve PolygonTool entegrasyonu içerir.
 */

class SliceViewer {
    constructor(canvasId, onPolygonEvent = null) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.wrapper = this.canvas.parentElement;
        this.onPolygonEvent = onPolygonEvent;

        // Image state
        this.currentImage = null;
        this.imgWidth = 0;
        this.imgHeight = 0;

        // Transform state (Pan & Zoom)
        this.scale = 1.0;
        this.offsetX = 0;
        this.offsetY = 0;
        this.isPanning = false;
        this.panStartX = 0;
        this.panStartY = 0;
        this.isSpacePressed = false;

        // Polygon Tool
        this.polygonTool = new PolygonTool(this.canvas, (poly) => {
            this.render();
            if (this.onPolygonEvent) {
                this.onPolygonEvent(poly);
            }
        });

        this.drawMode = false;

        this._setupEvents();
        this.resize();
        window.addEventListener('resize', () => this.resize());
    }

    setDrawMode(enabled) {
        this.drawMode = enabled;
        this.polygonTool.enabled = enabled;
        if (enabled) {
            this.wrapper.classList.add('draw-mode');
        } else {
            this.wrapper.classList.remove('draw-mode');
            this.polygonTool.cancelDrawing();
        }
        this.render();
    }

    setColors(colors) {
        this.polygonTool.setColors(colors);
    }

    setActiveLabel(label) {
        this.polygonTool.setActiveLabel(label);
    }

    resize() {
        if (!this.wrapper) return;
        const rect = this.wrapper.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        this.render();
    }

    setImage(imageElement) {
        this.currentImage = imageElement;
        this.imgWidth = imageElement.naturalWidth || imageElement.width;
        this.imgHeight = imageElement.naturalHeight || imageElement.height;
        this.fitToScreen();
    }

    fitToScreen() {
        if (!this.imgWidth || !this.imgHeight || !this.canvas.width || !this.canvas.height) return;

        const pad = 20;
        const scaleX = (this.canvas.width - pad * 2) / this.imgWidth;
        const scaleY = (this.canvas.height - pad * 2) / this.imgHeight;
        this.scale = Math.min(scaleX, scaleY, 3.0);

        this.offsetX = (this.canvas.width - this.imgWidth * this.scale) / 2;
        this.offsetY = (this.canvas.height - this.imgHeight * this.scale) / 2;

        this.render();
    }

    imageToScreen(x, y) {
        return {
            x: x * this.scale + this.offsetX,
            y: y * this.scale + this.offsetY
        };
    }

    screenToImage(screenX, screenY) {
        return {
            x: (screenX - this.offsetX) / this.scale,
            y: (screenY - this.offsetY) / this.scale
        };
    }

    render() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Fill background
        ctx.fillStyle = '#060a0e';
        ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        if (!this.currentImage) return;

        // Draw image with smooth scaling
        ctx.save();
        ctx.imageSmoothingEnabled = false; // Nearest neighbor for pixel crispness
        ctx.drawImage(
            this.currentImage,
            this.offsetX,
            this.offsetY,
            this.imgWidth * this.scale,
            this.imgHeight * this.scale
        );
        ctx.restore();

        // Draw polygons
        this.polygonTool.draw(ctx, {
            imageToScreen: (x, y) => this.imageToScreen(x, y)
        });
    }

    _setupEvents() {
        // Prevent context menu on canvas (used for closing polygon)
        this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());

        // Mouse Down
        this.canvas.addEventListener('mousedown', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.x;
            const mouseY = e.clientY - rect.y;

            // Middle click or Space+Left click -> Pan
            if (e.button === 1 || (e.button === 0 && this.isSpacePressed)) {
                this.isPanning = true;
                this.panStartX = mouseX - this.offsetX;
                this.panStartY = mouseY - this.offsetY;
                return;
            }

            // Left Click in Draw Mode
            if (e.button === 0 && this.drawMode) {
                const pts = this.polygonTool.currentPoints;
                if (this.polygonTool.isDrawing && pts.length >= 3) {
                    const first = this.imageToScreen(pts[0][0], pts[0][1]);
                    if (Math.hypot(first.x - mouseX, first.y - mouseY) < 12) {
                        this.polygonTool.closePolygon();
                        this.render();
                        return;
                    }
                }
                const imgPt = this.screenToImage(mouseX, mouseY);
                // Clamp within image bounds
                const clampedX = Math.max(0, Math.min(this.imgWidth, imgPt.x));
                const clampedY = Math.max(0, Math.min(this.imgHeight, imgPt.y));
                this.polygonTool.addVertex(clampedX, clampedY);
                this.render();
                return;
            }

            // Right Click in Draw Mode -> Close Polygon
            if (e.button === 2 && this.drawMode) {
                this.polygonTool.closePolygon();
                this.render();
            }
        });

        // Mouse Move
        this.canvas.addEventListener('mousemove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.x;
            const mouseY = e.clientY - rect.y;

            if (this.isPanning) {
                this.offsetX = mouseX - this.panStartX;
                this.offsetY = mouseY - this.panStartY;
                this.render();
            }
        });

        // Mouse Up
        window.addEventListener('mouseup', () => {
            this.isPanning = false;
        });

        // Double Click -> Close polygon
        this.canvas.addEventListener('dblclick', (e) => {
            if (this.drawMode) {
                this.polygonTool.closePolygon();
                this.render();
            }
        });

        // Wheel -> Zoom
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.x;
            const mouseY = e.clientY - rect.y;

            const zoomFactor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
            const newScale = Math.max(0.1, Math.min(this.scale * zoomFactor, 30.0));

            // Zoom centered around mouse pointer
            this.offsetX = mouseX - (mouseX - this.offsetX) * (newScale / this.scale);
            this.offsetY = mouseY - (mouseY - this.offsetY) * (newScale / this.scale);
            this.scale = newScale;

            this.render();
        }, { passive: false });

        // Key listeners for space pan & shortcuts
        window.addEventListener('keydown', (e) => {
            if (e.code === 'Space' && !this.isSpacePressed) {
                this.isSpacePressed = true;
                this.wrapper.style.cursor = 'grab';
            }
            if (e.key === 'Escape') {
                this.polygonTool.cancelDrawing();
                this.render();
            }
            if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
                this.polygonTool.undo();
                this.render();
            }
            if (e.key === 'Delete') {
                this.polygonTool.deleteLastPolygon();
                this.render();
            }
        });

        window.addEventListener('keyup', (e) => {
            if (e.code === 'Space') {
                this.isSpacePressed = false;
                this.wrapper.style.cursor = this.drawMode ? 'crosshair' : 'default';
            }
        });
    }
}
