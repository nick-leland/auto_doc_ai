# Synthetic Stroke-Based Signature Generator

A lightweight Python utility for generating **synthetic handwritten signatures** using a **stroke-based trajectory model**.
The generator creates realistic-looking signatures by simulating pen strokes with **Bezier curves, pressure variation, jitter, and pen lifts**, producing transparent PNG images suitable for synthetic document datasets.

This tool is particularly useful for:

* Document AI / OCR training datasets
* Synthetic form generation
* Signature detection models
* Layout parsing pipelines
* Rapid prototyping for document-processing ML systems

---

# Overview

Unlike font-based approaches, this generator produces signatures by modeling **pen trajectories**. Each signature is constructed from multiple strokes composed of chained **Bezier curves**. The system simulates common handwriting dynamics such as:

* pen pressure variation
* stroke width changes
* natural jitter
* baseline drift
* forward slant
* occasional pen lifts
* ink fading and scan artifacts

The result is a synthetic signature that more closely resembles **natural handwriting movement** rather than static typography.

---

# Features

* Stroke-based signature generation
* Deterministic signatures based on input name
* Transparent PNG output
* Configurable stroke physics
* Ink fading simulation
* Scan / photocopy noise simulation
* Slight ink bleed blur
* Pen lift gaps for realism

---

# Installation

Requirements:

* Python 3.9+
* numpy
* pillow

Install dependencies:

```bash
pip install numpy pillow
```

Clone repository:

```bash
git clone https://github.com/yourname/synthetic-signatures
cd synthetic-signatures
```

---

# Usage

Generate a signature:

```python
from signature_generator import generate_signature

img = generate_signature("John A. Smith")
img.save("signature.png")
```

Running the script directly:

```bash
python signature_generator.py
```

Output:

```
signature.png
```

---

# Example Output

Each generated signature is unique but deterministic based on the name input.

Example names:

```
John Smith
J. Smith
Jane Doe
Michael Anderson
```

The system produces a distinct signature style for each name.

---

# Configuration

Signature generation behavior can be customized via the `SigConfig` class.

Example:

```python
from signature_generator import generate_signature, SigConfig

cfg = SigConfig(
    strokes=6,
    slant_deg=-15,
    min_width=1.2,
    max_width=4.8
)

img = generate_signature("Jane Doe", cfg)
```

Key parameters:

| Parameter           | Description                        |
| ------------------- | ---------------------------------- |
| strokes             | Number of pen strokes in signature |
| slant_deg           | Signature slant angle              |
| jitter              | Small positional noise             |
| wobble              | Slow sinusoidal drift              |
| min_width           | Minimum pen thickness              |
| max_width           | Maximum pen thickness              |
| blur                | Simulated ink bleed                |
| scan_noise_strength | Simulated scanning artifacts       |

---

# How It Works

The generator constructs signatures in several steps:

1. **Baseline construction**

A writing baseline is created across the canvas.

2. **Bezier stroke generation**

Each stroke is defined using chained cubic Bezier curves.

3. **Trajectory sampling**

Points are sampled along the curves to simulate pen movement.

4. **Pressure simulation**

A sinusoidal pressure curve determines stroke thickness.

5. **Noise & jitter**

Random variation simulates natural handwriting imperfections.

6. **Rendering**

Line segments are drawn with varying width and opacity.

7. **Post-processing**

Blur and scan noise simulate scanned documents.

---

# Example Integration (Synthetic Document Pipeline)

Typical usage in a synthetic dataset generator:

```python
signature = generate_signature(name)

form.paste(
    signature,
    (signature_x, signature_y),
    signature
)
```

Output dataset:

```
dataset/
    images/
        form_001.png
    annotations/
        form_001.json
```

Example annotation:

```json
{
  "signature_bbox": [520, 720, 840, 780],
  "name": "John Smith"
}
```

This can be used to train:

* YOLO
* LayoutLM
* Donut
* Document transformers

---

# Limitations

This generator produces **visually plausible signatures**, but it does not attempt to model true human motor control or biometric handwriting dynamics.

For biometric-grade signature synthesis, consider trajectory models such as:

* Sigma-lognormal handwriting models
* RNN handwriting synthesis (Graves 2013)

---

# License

Apache License

---

# Future Improvements

Possible enhancements:

* SVG trajectory export
* multi-style signatures per name
* pen pressure shading
* stylus tilt simulation
* dataset batch generation
* stroke-level annotation export

---

# Contributing

Contributions welcome. Potential areas:

* improved handwriting physics
* generative handwriting models
* document dataset pipelines
* form template generators

