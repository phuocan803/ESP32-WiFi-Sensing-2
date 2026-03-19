"""
estimator.py - Stage 3: BPM Estimation Engine
===============================================
Ước lượng nhịp thở (BPM - Breaths Per Minute) từ tín hiệu đã qua xử lý.

Hai phương pháp được cung cấp:
  1. FFT (Fast Fourier Transform): Đáng tin hơn khi tín hiệu đều đặn và ít nhiễu.
  2. Peak Detection (Miền thời gian): Tốt hơn khi tín hiệu có biên độ rõ ràng.

Note: Sử dụng cả hai và lấy trung bình để tăng độ ổn định.
"""

import numpy as np
from scipy.signal import find_peaks


# ============================================================
# Phương pháp 1: FFT
# ============================================================

def estimate_bpm_fft(signal: np.ndarray, fs: float = 100.0) -> dict:
    """
    Ước lượng BPM bằng cách tìm tần số đỉnh trong miền tần số (FFT).

    Thuật toán:
      1. Tính FFT của tín hiệu.
      2. Chỉ xét dải tần số [0.1, 0.5] Hz (tương ứng [6, 30] BPM).
      3. Tìm đỉnh tần số mạnh nhất trong dải đó.
      4. Chuyển đổi từ Hz sang BPM (nhân 60).

    Parameters:
        signal: Tín hiệu nhịp thở 1D đã qua Band-pass filter.
        fs:     Tần số lấy mẫu (Hz).

    Returns:
        dict với các key:
          - 'bpm': Nhịp thở ước lượng (float).
          - 'dominant_freq_hz': Tần số đỉnh tìm được (Hz).
          - 'fft_magnitude': Biên độ FFT (để visualize).
          - 'fft_freqs': Trục tần số tương ứng (để visualize).
    """
    n = len(signal)
    freqs = np.fft.rfftfreq(n, d=1.0/fs)       # Trục tần số (Hz)
    fft_magnitude = np.abs(np.fft.rfft(signal)) # Biên độ FFT

    # Giới hạn tìm kiếm trong dải nhịp thở
    breathing_mask = (freqs >= 0.1) & (freqs <= 0.5)
    masked_magnitude = fft_magnitude.copy()
    masked_magnitude[~breathing_mask] = 0

    dominant_idx = np.argmax(masked_magnitude)
    dominant_freq = freqs[dominant_idx]
    bpm = dominant_freq * 60.0

    return {
        "bpm": round(bpm, 2),
        "dominant_freq_hz": round(dominant_freq, 4),
        "fft_magnitude": fft_magnitude,
        "fft_freqs": freqs,
    }


# ============================================================
# Phương pháp 2: Peak Detection (miền thời gian)
# ============================================================

def estimate_bpm_peaks(signal: np.ndarray, fs: float = 100.0) -> dict:
    """
    Ước lượng BPM bằng cách đếm số đỉnh (peaks) trong cửa sổ thời gian.

    Thuật toán:
      1. Dùng scipy.signal.find_peaks để tìm các đỉnh cục bộ.
      2. Tính khoảng cách trung bình giữa các đỉnh (giây).
      3. BPM = 60 / (khoảng cách trung bình).

    Parameters:
        signal:     Tín hiệu nhịp thở 1D đã qua Band-pass filter.
        fs:         Tần số lấy mẫu (Hz).

    Returns:
        dict với các key:
          - 'bpm': Nhịp thở ước lượng (float). -1 nếu không tìm được đỉnh.
          - 'peak_count': Số đỉnh tìm được trong cửa sổ.
          - 'peak_indices': Vị trí các đỉnh (để visualize).
    """
    # distance: khoảng cách tối thiểu giữa 2 đỉnh = 1 nhịp thở tối thiểu
    # Nhịp thở tối đa ~40 BPM -> min interval = 60/40 = 1.5 giây = 1.5*fs samples
    min_distance_samples = int(1.5 * fs)
    peaks, _ = find_peaks(signal, distance=min_distance_samples, prominence=0.01)

    n_peaks = len(peaks)
    if n_peaks < 2:
        # Không đủ đỉnh để tính BPM chính xác
        return {"bpm": -1.0, "peak_count": n_peaks, "peak_indices": peaks}

    # Tính khoảng cách trung bình giữa các đỉnh (tính bằng giây)
    intervals_seconds = np.diff(peaks) / fs
    avg_interval = np.mean(intervals_seconds)
    bpm = 60.0 / avg_interval

    return {
        "bpm": round(bpm, 2),
        "peak_count": n_peaks,
        "peak_indices": peaks,
    }


# ============================================================
# Hàm ước lượng tổng hợp (Fusion)
# ============================================================

def estimate_bpm(signal: np.ndarray, fs: float = 100.0) -> dict:
    """
    Kết hợp cả FFT và Peak Detection để cho ra ước lượng BPM ổn định nhất.

    Chiến lược Fusion:
      - Nếu Peaks hoạt động tốt (peak_count >= 2): Lấy trung bình cả hai.
      - Nếu Peaks không đủ đỉnh: Chỉ dùng FFT.

    Parameters:
        signal: Tín hiệu nhịp thở 1D.
        fs:     Tần số lấy mẫu (Hz).

    Returns:
        dict với:
          - 'bpm': BPM cuối cùng (đã fusion).
          - 'bpm_fft': BPM từ FFT.
          - 'bpm_peaks': BPM từ Peak Detection (-1 nếu không đủ đỉnh).
          - 'method': Phương pháp nào được sử dụng.
          - chi tiết FFT và peaks.
    """
    fft_result = estimate_bpm_fft(signal, fs)
    peak_result = estimate_bpm_peaks(signal, fs)

    bpm_fft = fft_result["bpm"]
    bpm_peaks = peak_result["bpm"]

    if bpm_peaks > 0:
        # Fusion: Lấy trung bình có trọng số (FFT:Peaks = 1:1)
        bpm_final = round((bpm_fft + bpm_peaks) / 2.0, 2)
        method = "FFT + Peak Detection (averaged)"
    else:
        bpm_final = bpm_fft
        method = "FFT only (not enough peaks)"

    return {
        "bpm": bpm_final,
        "bpm_fft": bpm_fft,
        "bpm_peaks": bpm_peaks,
        "method": method,
        **fft_result,
        "peak_count": peak_result["peak_count"],
        "peak_indices": peak_result["peak_indices"],
    }
