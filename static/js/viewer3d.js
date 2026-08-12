import { Niivue } from "./niivue.js";

class Viewer3D {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.placeholder = document.getElementById("viewer3d-placeholder");

    this.canvas = document.createElement("canvas");
    this.canvas.className = "nv3d-canvas";
    this.container.appendChild(this.canvas);

    this.volOpacity = 0.18;
    this.lblOpacity = 0.9;
    this.loaded = false;

    this.nv = new Niivue({
      backColor: [0.05, 0.07, 0.09, 1],
      show3Dcrosshair: false,
      loadingText: "",
      textHeight: 0.0,
      isColorbar: false,
    });
    this.ready = this.nv.attachToCanvas(this.canvas).then(() => {
      this.nv.addColormap("label_petrol", { R: [0, 0], G: [0, 176], B: [0, 168], A: [0, 255], I: [0, 255] });
    });
  }

  async load(volUrl, lblUrl) {
    await this.ready;
    const vols = [{ url: volUrl, name: "volume.nii.gz", colormap: "gray", opacity: this.volOpacity }];
    if (lblUrl) vols.push({ url: lblUrl, name: "labels.nii.gz", colormap: "label_petrol", opacity: this.lblOpacity });
    await this.nv.loadVolumes(vols);
    this.nv.setSliceType(this.nv.sliceTypeRender);
    this.loaded = true;
    if (this.placeholder) this.placeholder.style.display = "none";
  }

  setVolumeOpacity(o) {
    this.volOpacity = o;
    if (this.loaded && this.nv.volumes[0]) this.nv.setOpacity(0, o);
  }

  setLabelOpacity(o) {
    this.lblOpacity = o;
    if (this.loaded && this.nv.volumes[1]) this.nv.setOpacity(1, o);
  }

  resetCamera() {
    if (this.nv.setRenderAzimuthElevation) this.nv.setRenderAzimuthElevation(120, 15);
  }

  resize() { if (this.nv.resizeListener) this.nv.resizeListener(); }

  setVolumeBounds() {}
  updateLabels() {}
  setLabelVisibility() {}
}

window.Viewer3D = Viewer3D;
