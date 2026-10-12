#!/bin/bash
# Probe WSL for rknn-toolkit2 (x86 simulator) capabilities.
echo "=== python3 ==="
which python3 || true
python3 --version 2>&1
echo "=== rknn-toolkit2 ==="
python3 -c 'from rknn.api import RKNN; print("rknn-toolkit2 import OK")' 2>&1 | tail -5
echo "=== numpy/cv2/onnxruntime ==="
python3 -c 'import numpy; print("numpy", numpy.__version__)' 2>&1 | tail -2
python3 -c 'import cv2; print("cv2", cv2.__version__)' 2>&1 | tail -2
python3 -c 'import onnxruntime; print("ort", onnxruntime.__version__)' 2>&1 | tail -2
echo "=== home ==="
ls "$HOME" 2>/dev/null | head -20
