/**
 * Polygon Tool — HTML5 Canvas üzerinde poligon çizimi ve yönetimi.
 */

class PolygonData {
    constructor(labelName, points = []) {
        this.label = labelName;
        this.points = points; // Array of [x, y]
    }

    toDict() {
        return {
            label: this.label,
            points: this.points
        };
    }

    static fromDict(d) {
        return new PolygonData(d.label, d.points || []);
    }
}

class PolygonTool {
    constructor(canvas, onPolygonCompleted = null) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.onPolygonCompleted = onPolygonCompleted;

        this.activeLabel = '';
        this.labelColors = {}; // { labelName: { r, g, b, a, hex } }
        this.enabled = false;
        this.isDrawing = false;

        this.currentPoints = []; // [[x,y], ...]
        this.polygons = [];      // Array of PolygonData
        this.undoStack = [];     // Array of actions

        this.vertexRadius = 4;
        this.hoverVertex = null;
    }

    setColors(colors) {
        this.labelColors = colors;
    }

    setActiveLabel(label) {
        this.activeLabel = label;
    }

    getColor(labelName) {
        return this.labelColors[labelName] || { r: 255, g: 255, b: 0, a: 128, hex: '#ffff00' };
    }

    startDrawing() {
        if (!this.enabled) return;
        this.cancelDrawing();
        this.isDrawing = true;
        this.currentPoints = [];
    }

    addVertex(x, y) {
        if (!this.enabled) return;
        if (!this.isDrawing) {
            this.startDrawing();
        }
        this.currentPoints.push([x, y]);
        this.undoStack.push({ type: 'vertex', index: this.currentPoints.length - 1 });
    }

    closePolygon() {
        if (!this.isDrawing || this.currentPoints.length < 3) {
            this.cancelDrawing();
            return;
        }

        const poly = new PolygonData(this.activeLabel, [...this.currentPoints]);
        this.polygons.push(poly);
        this.undoStack.push({ type: 'polygon', index: this.polygons.length - 1 });

        this.isDrawing = false;
        this.currentPoints = [];

        if (this.onPolygonCompleted) {
            this.onPolygonCompleted(poly);
        }
    }

    cancelDrawing() {
        this.isDrawing = false;
        this.currentPoints = [];
    }

    undo() {
        if (this.undoStack.length === 0) return;
        const lastAction = this.undoStack.pop();

        if (lastAction.type === 'vertex' && this.isDrawing) {
            this.currentPoints.pop();
            if (this.currentPoints.length === 0) {
                this.isDrawing = false;
            }
        } else if (lastAction.type === 'polygon') {
            if (this.polygons.length > 0) {
                this.polygons.splice(lastAction.index, 1);
                if (this.onPolygonCompleted) {
                    this.onPolygonCompleted(null);
                }
            }
        }
    }

    deleteLastPolygon() {
        if (this.polygons.length === 0) return;
        this.polygons.pop();
        if (this.onPolygonCompleted) {
            this.onPolygonCompleted(null);
        }
    }

    clearAll() {
        this.cancelDrawing();
        this.polygons = [];
        this.undoStack = [];
    }

    setPolygons(polygons) {
        this.clearAll();
        this.polygons = polygons.map(p => p instanceof PolygonData ? p : PolygonData.fromDict(p));
    }

    getPolygons() {
        return this.polygons;
    }

    draw(ctx, transform) {
        // Render existing completed polygons
        for (const poly of this.polygons) {
            if (!poly.points || poly.points.length < 3) continue;
            const color = this.getColor(poly.label);

            ctx.beginPath();
            const p0 = transform.imageToScreen(poly.points[0][0], poly.points[0][1]);
            ctx.moveTo(p0.x, p0.y);

            for (let i = 1; i < poly.points.length; i++) {
                const pt = transform.imageToScreen(poly.points[i][0], poly.points[i][1]);
                ctx.lineTo(pt.x, pt.y);
            }
            ctx.closePath();

            // Fill
            ctx.fillStyle = `rgba(${color.r}, ${color.g}, ${color.b}, 0.3)`;
            ctx.fill();

            // Stroke
            ctx.strokeStyle = `rgba(${color.r}, ${color.g}, ${color.b}, 0.9)`;
            ctx.lineWidth = 2;
            ctx.setLineDash([]);
            ctx.stroke();

            // Draw vertices
            ctx.fillStyle = `rgb(${color.r}, ${color.g}, ${color.b})`;
            for (const pt of poly.points) {
                const screenPt = transform.imageToScreen(pt[0], pt[1]);
                ctx.beginPath();
                ctx.arc(screenPt.x, screenPt.y, this.vertexRadius, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // Render current active drawing polygon
        if (this.isDrawing && this.currentPoints.length > 0) {
            const color = this.getColor(this.activeLabel);

            if (this.currentPoints.length >= 2) {
                ctx.beginPath();
                const p0 = transform.imageToScreen(this.currentPoints[0][0], this.currentPoints[0][1]);
                ctx.moveTo(p0.x, p0.y);

                for (let i = 1; i < this.currentPoints.length; i++) {
                    const pt = transform.imageToScreen(this.currentPoints[i][0], this.currentPoints[i][1]);
                    ctx.lineTo(pt.x, pt.y);
                }

                ctx.strokeStyle = `rgba(${color.r}, ${color.g}, ${color.b}, 0.9)`;
                ctx.lineWidth = 2;
                ctx.setLineDash([4, 4]);
                ctx.stroke();
                ctx.setLineDash([]);
            }

            // Draw vertices for current drawing
            ctx.fillStyle = `rgb(${color.r}, ${color.g}, ${color.b})`;
            for (const pt of this.currentPoints) {
                const screenPt = transform.imageToScreen(pt[0], pt[1]);
                ctx.beginPath();
                ctx.arc(screenPt.x, screenPt.y, this.vertexRadius + 1, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }
}
