"""
model_inferencer.py - Stage 3 (Option B): Deep Learning BPM Estimator
======================================================================
Thay thế hoặc kết hợp song song với estimator.py (FFT + Peaks).

Luồng hoạt động:
  1. Nhận tín hiệu nhịp thở đã qua processor.py (shape: WINDOW_SIZE,).
  2. Chạy ONNX model (được export từ train_model.ipynb).
  3. Denormalize output về BPM thực tế.
  4. Trả về BPM cho main.py.

Yêu cầu:
  - File `models/respiration_model.onnx` đã được train và export.
  - File `models/model_metadata.json` chứa thông số denormalize.

Cài đặt trên Jetson Nano:
  pip install onnxruntime
"""

import json
import os
import numpy as np

# Đường dẫn đến thư mục models (tính từ thư mục edge/)
_MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')
_ONNX_PATH  = os.path.join(_MODELS_DIR, 'respiration_model.onnx')
_META_PATH  = os.path.join(_MODELS_DIR, 'model_metadata.json')

# Lazy loading: chỉ load model khi cần, tránh chiếm RAM ngay từ đầu
_session  = None
_metadata = None


def _load_model():
    """Load ONNX session và metadata nếu chưa load (Singleton pattern)."""
    global _session, _metadata

    if _session is not None:
        return _session, _metadata

    if not os.path.exists(_ONNX_PATH):
        raise FileNotFoundError(
            f'Không tìm thấy ONNX model tại: {_ONNX_PATH}\n'
            'Hãy chạy notebook notebooks/train_model.ipynb để train và export model.'
        )

    import onnxruntime as ort

    print(f'[ModelInferencer] Đang load ONNX model từ: {_ONNX_PATH}')
    _session = ort.InferenceSession(_ONNX_PATH, providers=['CPUExecutionProvider'])

    with open(_META_PATH, 'r') as f:
        _metadata = json.load(f)

    print(f"[ModelInferencer] Model loaded. MAE={_metadata.get('model_mae_bpm')} BPM")
    return _session, _metadata


def estimate_bpm_model(breathing_signal: np.ndarray) -> float:
    """
    Ước lượng BPM từ tín hiệu nhịp thở bằng ONNX model.

    Parameters:
        breathing_signal: Tín hiệu nhịp thở 1D (output của processor.process_window).
                          Shape phải khớp với WINDOW_SIZE khi train.

    Returns:
        bpm: Nhịp thở ước lượng (float).
    """
    session, meta = _load_model()

    bpm_min = meta['bpm_min']
    bpm_max = meta['bpm_max']

    # Chuẩn bị input: (WINDOW_SIZE,) → (1, WINDOW_SIZE, 1) [batch, time, channel]
    x = breathing_signal.astype(np.float32)
    x = x[np.newaxis, :, np.newaxis]  # (1, n, 1)

    # Chạy inference
    input_name  = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    y_norm = session.run([output_name], {input_name: x})[0][0][0]

    # Denormalize về BPM
    bpm = float(y_norm) * (bpm_max - bpm_min) + bpm_min
    bpm = max(bpm_min, min(bpm_max, bpm))  # Clamp trong [bpm_min, bpm_max]

    return round(bpm, 2)


def is_model_available() -> bool:
    """Kiểm tra xem ONNX model đã được train và tồn tại hay chưa."""
    return os.path.exists(_ONNX_PATH) and os.path.exists(_META_PATH)
