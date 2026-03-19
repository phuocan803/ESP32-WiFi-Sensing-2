"""
processor.py - Stage 2: Signal Processing Pipeline
====================================================
Pipeline xử lý tín hiệu CSI để cô lập sóng nhịp thở.
Thứ tự xử lý: Amplitude → Hampel → PCA → Band-pass

Lý do thứ tự này:
  1. Trích xuất Amplitude vì nhịp thở ảnh hưởng đến biên độ sóng WiFi.
  2. Hampel Filter trước Band-pass để các giá trị nhiễu xung (spike) không
     gây hiện tượng "ringing" trong bộ lọc Butterworth.
  3. PCA gom tín hiệu nhịp thở từ 64 kênh xuống 1 kênh mạnh nhất.
  4. Band-pass (0.1–0.5 Hz) giữ lại đúng dải tần số nhịp thở.
"""

import numpy as np
from scipy.signal import butter, filtfilt
from sklearn.decomposition import PCA


# ============================================================
# Bước 1: Trích xuất Biên độ (Amplitude)
# ============================================================

def extract_amplitude(csi_raw: np.ndarray) -> np.ndarray:
    """
    Tính biên độ (magnitude) từ mảng CSI thô.

    CSI từ ESP32 là cặp giá trị xen kẽ: [imaginary, real, imaginary, real, ...]
    Biên độ = sqrt(imaginary^2 + real^2)

    Parameters:
        csi_raw: mảng 1D các giá trị CSI thô, shape (128,) với 64 kênh.

    Returns:
        amplitudes: mảng 1D biên độ, shape (64,).
    """
    imaginary = csi_raw[0::2]  # Chỉ số chẵn
    real = csi_raw[1::2]       # Chỉ số lẻ
    amplitudes = np.sqrt(imaginary**2 + real**2)
    return amplitudes


# ============================================================
# Bước 2: Hampel Filter - Khử nhiễu xung
# ============================================================

def hampel_filter(signal: np.ndarray, window_size: int = 5, n_sigma: float = 3.0) -> np.ndarray:
    """
    Phát hiện và thay thế các outlier trong chuỗi thời gian bằng Median.

    Thuật toán quét qua cửa sổ trượt (sliding window). Nếu một điểm lệch khỏi
    Median của cửa sổ hơn (n_sigma * k * MAD) thì bị coi là nhiễu xung và
    được thay thế bằng Median.

    Parameters:
        signal:      Chuỗi thời gian 1D cần lọc.
        window_size: Độ bán rộng (half-window) của cửa sổ. Tổng cửa sổ = 2*window_size+1.
        n_sigma:     Ngưỡng bội số (thường dùng 3 theo quy tắc 3-sigma).

    Returns:
        filtered: Chuỗi sau khi loại bỏ outlier.
    """
    k = 1.4826  # Hệ số scale để MAD tương đương Std (phân phối chuẩn)
    filtered = signal.copy()
    n = len(signal)

    for i in range(window_size, n - window_size):
        window = signal[i - window_size: i + window_size + 1]
        median = np.median(window)
        mad = np.median(np.abs(window - median))
        threshold = n_sigma * k * mad

        if np.abs(signal[i] - median) > threshold:
            filtered[i] = median

    return filtered


# ============================================================
# Bước 3: PCA - Chọn kênh nhạy nhất với nhịp thở
# ============================================================

def apply_pca(amplitude_matrix: np.ndarray, n_components: int = 1) -> np.ndarray:
    """
    Nén ma trận biên độ (n_samples x 64_kênh) xuống thành phần chính.

    Thành phần chính thứ nhất (PC1) thường chứa sóng nhịp thở rõ nhất
    vì nhịp thở làm toàn bộ kênh biến đổi đồng pha, PCA sẽ gom lại.

    Parameters:
        amplitude_matrix: ma trận 2D shape (n_samples, n_subcarriers).
        n_components:     Số thành phần PCA cần giữ lại (mặc định 1).

    Returns:
        pc1: chuỗi thời gian 1D shape (n_samples,).
    """
    pca = PCA(n_components=n_components)
    transformed = pca.fit_transform(amplitude_matrix)
    return transformed[:, 0]


# ============================================================
# Bước 4: Band-pass Filter (Butterworth)
# ============================================================

def bandpass_filter(signal: np.ndarray, fs: float, lowcut: float = 0.1, highcut: float = 0.5, order: int = 4) -> np.ndarray:
    """
    Lọc Band-pass Butterworth để giữ lại dải tần số nhịp thở.

    Nhịp thở người bình thường: 12–20 lần/phút = 0.2–0.33 Hz.
    Dải 0.1–0.5 Hz bao phủ cả nhịp thở chậm (6/phút) và nhanh (30/phút).

    Parameters:
        signal:  Chuỗi tín hiệu 1D.
        fs:      Tần số lấy mẫu (Hz), thường là 100 Hz (cấu hình PACKET_RATE).
        lowcut:  Tần số cắt dưới (Hz).
        highcut: Tần số cắt trên (Hz).
        order:   Bậc bộ lọc (bậc cao hơn = sharp hơn nhưng dễ ringing hơn).

    Returns:
        filtered: Tín hiệu sau khi lọc.
    """
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    # filtfilt: lọc hai chiều để không bị lệch pha
    filtered = filtfilt(b, a, signal)
    return filtered


# ============================================================
# Pipeline hoàn chỉnh
# ============================================================

def process_window(csi_window: np.ndarray, fs: float = 100.0) -> np.ndarray:
    """
    Chạy toàn bộ pipeline xử lý tín hiệu trên một cửa sổ dữ liệu CSI.

    Parameters:
        csi_window: Ma trận CSI thô shape (n_samples, 128).
                    Mỗi hàng là 128 giá trị thực/ảo từ 64 subcarriers.
        fs:         Tần số lấy mẫu (Hz).

    Returns:
        breathing_signal: Tín hiệu nhịp thở 1D đã được làm sạch.
    """
    # Bước 1: Trích xuất biên độ từng packet -> (n_samples, 64)
    amplitude_matrix = np.array([extract_amplitude(row) for row in csi_window])

    # Bước 2: Hampel filter trên từng kênh để khử nhiễu xung
    for i in range(amplitude_matrix.shape[1]):
        amplitude_matrix[:, i] = hampel_filter(amplitude_matrix[:, i])

    # Bước 3: PCA để lấy thành phần chính (n_samples,)
    pc1 = apply_pca(amplitude_matrix)

    # Bước 4: Band-pass để cô lập tần số nhịp thở
    breathing_signal = bandpass_filter(pc1, fs=fs)

    return breathing_signal
