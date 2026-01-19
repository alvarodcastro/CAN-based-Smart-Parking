# Adversarial ANPR (Automatic Number Plate Recognition)

Research-oriented notebook exploring three adversarial attacks against a modern ANPR pipeline that combines object detection (YOLO) for license plate localization and OCR (PaddleOCR) for text extraction.

This README summarizes the experimental setup, methods, evaluation procedure, and how to reproduce the results presented in the notebook.

## Overview
- Goal: Evaluate robustness of ANPR to image-space adversarial perturbations that (a) break plate detection or (b) alter OCR output, while keeping perturbations localized and visually subtle when possible.
- Pipeline:
  1. YOLO detector for plate localization (bounding boxes + confidence).
  2. PaddleOCR for text recognition within detected plate regions.
  3. Three attacks tested for DoS on detection, region-targeted transfer, and imperceptible OCR changes.
- Notebook: adversarial_ANPR.ipynb (run cells top-to-bottom).

## Environment & Setup
- Python: 3.9–3.11 recommended (tested with common ML stacks).
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```
- GPU (optional but recommended): Install a CUDA-enabled PyTorch build per your CUDA version for faster YOLO inference.
- Kaggle access: The notebook uses `kagglehub` to download the dataset.
  - Ensure you have a Kaggle account and have accepted the dataset terms.
  - Configure Kaggle API credentials (KAGGLE_USERNAME / KAGGLE_KEY) or sign in as required by kagglehub.

## Data
- Dataset: Spain License Plate Dataset from Kaggle
  - Source: `unidpro/spain-license-plate-dataset` (downloaded via `kagglehub.dataset_download(...)`).
  - The notebook automatically downloads and lists a subset of `.jpg`/`.png` files for experiments.

## Models
- Detector: YOLO (Ultralytics) loaded from a local checkpoint.
  - Code expects a weight at `../models/best.pt` relative to the notebook. Adjust the path if needed.
- OCR: PaddleOCR initialized with `use_angle_cls=True, lang="en"`.

## Baseline Evaluation
- The notebook loads N sample images and computes:
  - Detection presence and confidence for the first predicted plate per image.
  - A quick OCR probe on a detected plate using helper `extract_license_plate()` which selects the highest-confidence text and cleans non-alphanumerics.
- Baseline outputs printed in the notebook include a detection success rate and sample image shapes.

## Attacks

### 1) Detection DoS (FGSM-inspired noise on pixels)
- Function: `fgsm_attack_simple(model, image, epsilon, targeted_region=None)`
- Idea: Add bounded, pixel-space perturbations (uniform random in this implementation) with magnitude `epsilon` (0–255 scale). Optionally restrict to the detected plate region (bbox) to localize changes.
- Procedure:
  - For each successfully detected image, sweep `epsilon ∈ {5,10,15,20,25,30,40,50}`.
  - Re-run YOLO on the perturbed image and record new confidence.
  - Success criterion: detector misses the plate OR confidence drops below 0.5.
- Outputs:
  - Console summary (per-image results, drops, success rate).
  - Visualizations saved: `original_image_{i}.png`, `adversarial_image_{i}.png`, `perturbation_{i}.png`.

### 2) Targeted Region Transfer (strong localized blend)
- Idea: Transfer the visual appearance of a target plate’s ROI into the source image’s detected plate ROI, enforcing a bounded delta and smoothing edges to remain plausible.
- Steps:
  - Detect plate on source image (bbox S) and target image (bbox T).
  - Resize target ROI to source ROI size; apply scale/offset; clamp per-pixel delta by `epsilon=80`.
  - Apply mild Gaussian smoothing to mask seams.
  - Evaluate YOLO on the adversarial image and compute IoU between the new detection and T to check whether the detector “migrates” toward the target-like region.
- Outputs:
  - Console logs with bbox, confidence, IoU to target.
  - Visualization saved: `adv_region_transfer_strong.png` plus side-by-side plots in the notebook.

### 3) Imperceptible OCR Attack (edge-weighted, gradient-free search)
- Goal: Change OCR text with visually subtle, localized perturbations restricted to high-frequency regions of the plate.
- Method:
  - Build an edge-weighted perturbation mask via Canny+dilation+blur to focus on strokes and boundaries.
  - Perform a finite-difference directional search in the masked ROI:
    - Sample a smoothed random direction `z`.
    - Evaluate OCR confidence for `ROI ± σ·z` and choose the direction that reduces the current OCR confidence/text stability.
    - Update with a sign step bounded by `ε`, apply bilateral filtering for visual smoothness.
  - Early stop when OCR text changes from the baseline.
- Hyperparameters (example sweeps in notebook):
  - `epsilon_list = [4, 6, 8, 10, 12]`, `steps_list = [6, 8, 10, 12]`, `sigma = 1.5`.
- Outputs:
  - Console prints showing OCR text and confidence per step.
  - Saved images: `tgt_image.png`, `adv_fgsm_sweep.png` (with side-by-side and amplified |Δ|).

## Metrics & Reporting
- Detection DoS:
  - Per-ε success rate = (# successes / # attempts) × 100.
  - Confidence drop statistics (avg per ε).
- Targeted Transfer:
  - Post-attack detection confidence and IoU between final bbox and target bbox.
- Imperceptible OCR:
  - Whether text changed; final confidence of new text; visual inspection of perturbation magnitude.
- The notebook prints tabular summaries and produces figures for quick interpretation.

## Reproducibility Notes
- Randomness: Attacks 1 and 3 depend on random noise directions; set Python/NumPy seeds early in the notebook for more determinism if desired.
- Hardware: GPU inference can change timing; core results should remain qualitatively similar.
- Weights: Ensure `../models/best.pt` exists and corresponds to your intended detector; results depend on detector quality.
- Data: Make sure the Kaggle dataset download completes successfully and that sample images are available.

## How to Run
1. Install requirements: `pip install -r requirements.txt`.
2. Ensure YOLO weights are accessible at the path used in the notebook (or edit the path).
3. Open and run `adversarial_ANPR.ipynb` in order:
   - Import + dataset download
   - Model initialization
   - Baseline detection + OCR probe
   - Attack 1 (Detection DoS) + visualization + analysis
   - Attack 2 (Targeted Region Transfer) + OCR probe
   - Attack 3 (Imperceptible OCR Attack)
4. Inspect generated images and console summaries for quantitative and qualitative results.

## Ethical Use
This work is for academic research on robustness, safety, and defenses of computer vision systems. Do not deploy or apply these techniques for unlawful or unethical purposes. Always follow local laws and institutional review policies when working with license plate imagery.

## CPS Integration: Man-in-the-Middle Threat Model
- Goal: Study a cyber-physical system (CPS) setting where an attacker intercepts the video link between a camera and the ANPR system to craft adversarial frames on-the-fly before they reach inference.
- Topology (example): IP Camera (RTSP/HTTP/ONVIF) → Edge/Gateway (optional) → ANPR Service.
- Adversary position: Transparent network proxy between camera and ANPR that decodes frames, perturbs them, re-encodes, and forwards with minimal delay.

### Assumptions and Constraints
- Stream protocols: RTSP/RTP (H.264/H.265), HTTP-MJPEG, or proprietary vendor streams.
- Capability: Attacker can read/modify frames in transit but cannot break end-to-end TLS/SRTP if enabled and correctly configured.
- Real-time budget: Maintain 25–30 FPS and keep added latency below 30–60 ms per frame for operational viability.
- Compute: Lightweight GPU (preferred) or CPU for decode/encode and perturbation; batching is limited in streaming scenarios.

### Prototype MITM Pipeline (Research Environment)
Two practical paths to emulate a MITM without touching production systems:

1) RTSP restream + adversarial transform
- Use an RTSP server (e.g., MediaMTX) to host two paths: `raw` (ingest) and `adv` (egress).
- Ingest the camera stream into `raw` and publish adversarially-perturbed frames to `adv`.

Example steps (conceptual):
1. Ingest camera → `raw` using ffmpeg:
```bash
ffmpeg -rtsp_transport tcp -i rtsp://CAMERA_HOST/stream -c copy -f rtsp rtsp://localhost:8554/raw
```
2. Subscribe to `raw`, perturb frames with Python (OpenCV), and push to `adv` via ffmpeg stdin:
```python
import cv2, subprocess, numpy as np
from pathlib import Path

# Simplified hooks from the notebook
def fgsm_attack_simple(model, image, epsilon, targeted_region=None):
  adv = image.astype(np.float32)
  noise = np.random.uniform(-epsilon, epsilon, image.shape).astype(np.float32)
  if targeted_region is not None:
    x1,y1,x2,y2 = targeted_region
    mask = np.zeros_like(adv); mask[y1:y2, x1:x2] = 1
    noise *= mask
  adv = np.clip(adv + noise, 0, 255).astype(np.uint8)
  return adv

cap = cv2.VideoCapture("rtsp://localhost:8554/raw", cv2.CAP_FFMPEG)
ok, frame = cap.read(); assert ok
H, W = frame.shape[:2]

# ffmpeg process to publish to adv path (bgr24 rawvideo → H.264 → RTSP)
cmd = [
  "ffmpeg","-y","-f","rawvideo","-pix_fmt","bgr24","-s",f"{W}x{H}","-r","25","-i","-",
  "-an","-c:v","libx264","-preset","veryfast","-tune","zerolatency","-f","rtsp","rtsp://localhost:8554/adv"
]
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

# Optional: load YOLO model here if bbox targeting is desired
model = None  # placeholder; reuse your notebook model if running in the same env
bbox = None   # supply bbox per-frame from a lightweight detector, or default to full-frame

while True:
  ok, frame = cap.read()
  if not ok: break
  # Apply localized or full-frame perturbation
  adv = fgsm_attack_simple(model, frame[..., ::-1], epsilon=10, targeted_region=bbox)  # expects RGB if reusing notebook code
  adv_bgr = adv[..., ::-1]
  proc.stdin.write(adv_bgr.tobytes())

cap.release(); proc.stdin.close(); proc.wait()
```
3. Point the ANPR system to `rtsp://localhost:8554/adv` instead of the original camera URL.

2) HTTP/MJPEG proxy (simpler demo)
- Wrap `cv2.VideoCapture` on the camera stream and serve a multipart MJPEG endpoint with perturbed frames (Flask/FastAPI). Many ANPR stacks accept HTTP streams for testing.

Minimal sketch:
```python
from flask import Flask, Response
import cv2, numpy as np

app = Flask(__name__)
cap = cv2.VideoCapture("rtsp://CAMERA/stream", cv2.CAP_FFMPEG)

def gen():
  while True:
    ok, bgr = cap.read()
    if not ok: break
    # apply perturbation (full-frame or ROI)
    pert = (bgr.astype(np.float32) + np.random.uniform(-10,10,bgr.shape)).clip(0,255).astype(np.uint8)
    ok, jpg = cv2.imencode('.jpg', pert, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok: continue
    yield (b"--frame\r\n"
         b"Content-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n")

@app.route('/video')
def video():
  return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

app.run(host='0.0.0.0', port=5000)
```

### Evaluation in Streaming Context
- Measure per-frame latency and throughput (FPS) before/after MITM.
- Track attack success rate over time windows (e.g., % frames with missed detection, OCR changes/min).
- Quantify visual deviation with PSNR/SSIM to gauge perceptibility.
- Log re-encoding artifacts and bitrate drift (may affect OCR and detectability).

### Defenses to Consider
- Transport: SRTP/TLS with mutual auth; disable insecure fallbacks; signed frames or watermarking at the camera.
- Content checks: Temporal consistency of detections/OCR, sudden confidence drops, perturbation fingerprinting on plate ROI.
- Model-side: Adversarial training, test-time augmentations, randomized crops/denoise on ROI, ensemble checks.
- Operational: Monitor latency/bitrate anomalies; restrict who can act as RTSP/HTTP sources; network segmentation.

Note: All MITM experiments should be run in a controlled, ethical testbed with owned/consented devices and no impact on real traffic.

### MQTT Transport Variant
- Pipeline: Camera/Edge publishes encoded frames to an MQTT broker (e.g., `cameras/cam01/frame`), ANPR subscribes and decodes.
- Payloads: Commonly JPEG bytes (raw) or Base64-encoded JPEG inside a JSON envelope (optionally with timestamps/seq).
- QoS: Use QoS 0 or 1 for low-latency streaming; QoS 2 typically adds too much overhead. Disable `retain` for live streams.

MITM options over MQTT:
- Broker bridge: A downstream broker bridges topics from an upstream broker, transforming payloads in between.
- Client-side proxy: A subscriber to source topics that republishes perturbed frames to mirror topics (e.g., `.../frame_adv`). ANPR is pointed at the adv topic.

Security & performance notes:
- Enable TLS (`mqtts`) and client auth to prevent easy interception; enforce authorization per topic.
- Expect broker message size limits; use JPEG quality control to keep payloads <~512KB/frame.
- Measure end-to-end delay using embedded timestamps (`ts`) and compute perturbation success/failure over moving windows.

## References
- Ultralytics YOLO: https://docs.ultralytics.com/
- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR
- Kaggle Dataset (Spain License Plate): https://www.kaggle.com/datasets/unidpro/spain-license-plate-dataset

## Acknowledgments
- Open-source contributors of Ultralytics, PaddleOCR, and the dataset authors.
- The VS Code environment and tooling used to run and document experiments.
