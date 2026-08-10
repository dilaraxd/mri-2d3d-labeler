/**
 * 3D Viewer — Three.js tabanlı 3D hacim ve etiket yüzeyi görselleştirici.
 */

class Viewer3D {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.placeholder = document.getElementById('viewer3d-placeholder');

        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;

        this.labelMeshes = {}; // { labelName: THREE.Mesh }
        this.volumeGroup = null;
        this.boxHelper = null;

        this.volumeOpacity = 0.3;
        this.labelOpacity = 0.7;
        this.initialized = false;

        this._initThree();
    }

    _initThree() {
        if (!window.THREE) {
            console.error("Three.js not loaded.");
            return;
        }

        const width = this.container.clientWidth || 800;
        const height = this.container.clientHeight || 600;

        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x060a0e);

        // Camera
        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 2000);
        this.camera.position.set(200, 200, 300);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.shadowMap.enabled = true;
        this.container.appendChild(this.renderer.domElement);

        // Controls
        if (THREE.OrbitControls) {
            this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
            this.controls.enableDamping = true;
            this.controls.dampingFactor = 0.05;
        }

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
        this.scene.add(ambientLight);

        const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight1.position.set(1, 1, 1).normalize();
        this.scene.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0x4dd8c8, 0.4);
        dirLight2.position.set(-1, -1, -1).normalize();
        this.scene.add(dirLight2);

        // Groups
        this.volumeGroup = new THREE.Group();
        this.scene.add(this.volumeGroup);

        this.initialized = true;

        // Resize handler
        window.addEventListener('resize', () => this.resize());

        // Animation Loop
        const animate = () => {
            requestAnimationFrame(animate);
            if (this.controls) this.controls.update();
            this.renderer.render(this.scene, this.camera);
        };
        animate();
    }

    resize() {
        if (!this.container || !this.renderer || !this.camera) return;
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        if (width === 0 || height === 0) return;

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    setVolumeBounds(shape, spacing = [1, 1, 1]) {
        // Clear previous volume bounds
        while (this.volumeGroup.children.length > 0) {
            this.volumeGroup.remove(this.volumeGroup.children[0]);
        }

        const [nz, ny, nx] = shape;
        const sx = nx * spacing[2];
        const sy = ny * spacing[1];
        const sz = nz * spacing[0];

        const geometry = new THREE.BoxGeometry(sx, sy, sz);
        const edges = new THREE.EdgesGeometry(geometry);
        const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: 0x1e3a45, transparent: true, opacity: 0.6 }));
        this.volumeGroup.add(line);

        // Center scene around volume
        this.volumeGroup.position.set(0, 0, 0);

        if (this.placeholder) {
            this.placeholder.style.display = 'none';
        }
    }

    updateLabels(meshesData) {
        // Remove old label meshes
        for (const [name, mesh] of Object.entries(this.labelMeshes)) {
            this.scene.remove(mesh);
            if (mesh.geometry) mesh.geometry.dispose();
            if (mesh.material) mesh.material.dispose();
        }
        this.labelMeshes = {};

        if (!meshesData || Object.keys(meshesData).length === 0) {
            return;
        }

        for (const [labelName, data] of Object.entries(meshesData)) {
            const { vertices, faces, normals, color } = data;
            if (!vertices || vertices.length === 0) continue;

            const geometry = new THREE.BufferGeometry();

            // Vertices
            const posArray = new Float32Array(faces.length * 3 * 3);
            const normArray = new Float32Array(faces.length * 3 * 3);

            let idx = 0;
            for (let i = 0; i < faces.length; i++) {
                const [i0, i1, i2] = faces[i];

                for (const vIdx of [i0, i1, i2]) {
                    const v = vertices[vIdx];
                    // Center offset adjustment: (z, y, x) mapping to Three.js coordinates
                    posArray[idx] = v[2]; // X
                    posArray[idx + 1] = v[1]; // Y
                    posArray[idx + 2] = v[0]; // Z

                    if (normals && normals[vIdx]) {
                        normArray[idx] = normals[vIdx][2];
                        normArray[idx + 1] = normals[vIdx][1];
                        normArray[idx + 2] = normals[vIdx][0];
                    }
                    idx += 3;
                }
            }

            geometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
            if (normals && normals.length > 0) {
                geometry.setAttribute('normal', new THREE.BufferAttribute(normArray, 3));
            } else {
                geometry.computeVertexNormals();
            }

            geometry.center();

            const threeColor = new THREE.Color(color.r, color.g, color.b);
            const material = new THREE.MeshStandardMaterial({
                color: threeColor,
                roughness: 0.4,
                metalness: 0.2,
                transparent: true,
                opacity: this.labelOpacity,
                side: THREE.DoubleSide
            });

            const mesh = new THREE.Mesh(geometry, material);
            this.scene.add(mesh);
            this.labelMeshes[labelName] = mesh;
        }

        if (this.placeholder) {
            this.placeholder.style.display = 'none';
        }
    }

    setLabelVisibility(labelName, visible) {
        if (this.labelMeshes[labelName]) {
            this.labelMeshes[labelName].visible = visible;
        }
    }

    setLabelOpacity(opacity) {
        this.labelOpacity = opacity;
        for (const mesh of Object.values(this.labelMeshes)) {
            if (mesh.material) {
                mesh.material.opacity = opacity;
            }
        }
    }

    setVolumeOpacity(opacity) {
        this.volumeOpacity = opacity;
        // Adjust volume wireframe/slice opacity if present
        for (const child of this.volumeGroup.children) {
            if (child.material) {
                child.material.opacity = opacity;
            }
        }
    }

    resetCamera() {
        if (!this.camera || !this.controls) return;
        this.camera.position.set(150, 150, 250);
        this.controls.target.set(0, 0, 0);
        this.camera.lookAt(0, 0, 0);
        this.controls.update();
    }
}
