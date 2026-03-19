"""
visualize.py - Công cụ trực quan hóa dữ liệu CSI và nhịp thở
==============================================================
Script độc lập, chạy SAU khi thu thập dữ liệu hoặc sau khi train model.

Tạo ra các hình ảnh tự động lưu vào thư mục asset/:
  - breathing_pipeline.png  : Tín hiệu qua từng bước xử lý (giống amp-graph.png của V1)
  - fft_spectrum.png         : Phân tích tần số FFT
  - bpm_distribution.png    : Phân phối BPM trong dataset
  - training_history.png    : Đường cong loss khi train model (nếu có)

Cách dùng:
  # Xem tín hiệu từ 1 file CSV
  python edge/visualize.py datasets/An_BPM16_20240320.csv

  # Xem phân phối toàn bộ dataset
  python edge/visualize.py --dataset-stats
"""

import sys
import os
import re
import glob
import argparse
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import pandas as pd

matplotlib.use('Agg')  # Không cần hiển thị cửa sổ GUI, chỉ lưu file

# Thêm thư mục edge/ vào sys.path để import src/
sys.path.insert(0, os.path.dirname(__file__))
from src.processor import extract_amplitude, hampel_filter, apply_pca, bandpass_filter, process_window

ASSET_DIR = os.path.join(os.path.dirname(__file__), '..', 'asset')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
SAMPLING_RATE = 100.0

os.makedirs(ASSET_DIR, exist_ok=True)


# ============================================================
# Đọc file CSV lấy CSI thô
# ============================================================

def load_csi_from_csv(filepath: str, max_packets: int = 3000) -> np.ndarray:
    """Đọc file CSV và trả về ma trận CSI thô (n_packets, 128)."""
    df = pd.read_csv(filepath, header=None, on_bad_lines='skip')
    csi_col = df.iloc[:, -1]

    rows = []
    for val in csi_col:
        match = re.search(r'\[([-\d ]+)\]', str(val))
        if not match:
            continue
        try:
            values = list(map(int, match.group(1).split()))
            if len(values) >= 64:
                rows.append(np.array(values[:128]))  # Cắt đúng 128 nếu dài hơn
        except ValueError:
            continue
        if len(rows) >= max_packets:
            break

    return np.array(rows)


# ============================================================
# Hình 1: Breathing Pipeline (giống amp-graph.png của V1)
# ============================================================

def plot_breathing_pipeline(csv_filepath: str):
    """
    Tạo hình 4 panel hiển thị tín hiệu qua từng bước xử lý:
    (a) Amplitude thô của một subcarrier
    (b) Sau Hampel Filter
    (c) Sau PCA
    (d) Sau Band-pass Filter (tín hiệu nhịp thở cuối cùng)
    """
    print(f'[*] Đang phân tích: {os.path.basename(csv_filepath)}')
    csi_raw = load_csi_from_csv(csv_filepath)
    if len(csi_raw) < 200:
        print('[!] Không đủ dữ liệu để vẽ.')
        return

    n = min(len(csi_raw), 3000)
    csi_raw = csi_raw[:n]
    t = np.arange(n) / SAMPLING_RATE  # Trục thời gian (giây)

    # Bước 1: Amplitude toàn bộ
    amp_matrix = np.array([extract_amplitude(row) for row in csi_raw])  # (n, 64)

    # Lấy subcarrier số 30 để hiển thị đại diện (không phải subcarrier cuối thường bị nhiễu)
    amp_one = amp_matrix[:, 30]

    # Bước 2: Hampel Filter cho subcarrier đó
    amp_hampel = hampel_filter(amp_one)

    # Bước 3: PCA toàn bộ matrix
    pc1 = apply_pca(amp_matrix)

    # Bước 4: Band-pass
    breathing = bandpass_filter(pc1, fs=SAMPLING_RATE)

    # Vẽ 4 panel
    fig, axes = plt.subplots(4, 1, figsize=(14, 12))
    fig.suptitle(f'Breathing Signal Pipeline\n{os.path.basename(csv_filepath)}',
                 fontsize=14, fontweight='bold')

    axes[0].plot(t, amp_one, color='#2196F3', linewidth=0.7)
    axes[0].set_title('(a) Raw Amplitude — Subcarrier #30')
    axes[0].set_ylabel('Amplitude')

    axes[1].plot(t, amp_hampel, color='#FF9800', linewidth=0.7)
    axes[1].set_title('(b) After Hampel Filter (Outlier Removal)')
    axes[1].set_ylabel('Amplitude')

    axes[2].plot(t, pc1, color='#9C27B0', linewidth=0.7)
    axes[2].set_title('(c) After PCA (Principal Component 1 — 64 channels → 1)')
    axes[2].set_ylabel('Amplitude')

    axes[3].plot(t, breathing, color='#4CAF50', linewidth=1.0)
    axes[3].set_title('(d) After Band-pass Filter 0.1–0.5 Hz (Final Breathing Signal)')
    axes[3].set_ylabel('Amplitude')
    axes[3].set_xlabel('Time (seconds)')

    for ax in axes:
        ax.grid(True, linestyle='--', alpha=0.4)

    plt.tight_layout()
    out_path = os.path.join(ASSET_DIR, 'breathing_pipeline.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'[+] Đã lưu: {out_path}')


# ============================================================
# Hình 2: FFT Spectrum
# ============================================================

def plot_fft_spectrum(csv_filepath: str):
    """Vẽ phổ tần số FFT của tín hiệu nhịp thở để kiểm tra đỉnh BPM."""
    csi_raw = load_csi_from_csv(csv_filepath)
    if len(csi_raw) < 200:
        return

    n = min(len(csi_raw), 3000)
    breathing = process_window(csi_raw[:n], fs=SAMPLING_RATE)

    freqs = np.fft.rfftfreq(len(breathing), d=1.0 / SAMPLING_RATE)
    magnitude = np.abs(np.fft.rfft(breathing))

    # Chỉ hiển thị dải 0–1 Hz
    mask = freqs <= 1.0

    # Tìm đỉnh trong dải nhịp thở
    breathing_mask = (freqs >= 0.1) & (freqs <= 0.5)
    peak_idx = np.argmax(magnitude * breathing_mask)
    peak_freq = freqs[peak_idx]
    peak_bpm = peak_freq * 60

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(freqs[mask] * 60, magnitude[mask], color='#2196F3', linewidth=1.2)
    ax.axvspan(6, 30, alpha=0.1, color='green', label='Breathing zone (6–30 BPM)')
    ax.axvline(x=peak_bpm, color='red', linestyle='--',
               label=f'Dominant peak: {peak_bpm:.1f} BPM')
    ax.set_title(f'FFT Spectrum — {os.path.basename(csv_filepath)}', fontweight='bold')
    ax.set_xlabel('Frequency (BPM)')
    ax.set_ylabel('Magnitude')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.4)

    out_path = os.path.join(ASSET_DIR, 'fft_spectrum.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'[+] Đã lưu: {out_path}')


# ============================================================
# Hình 3: BPM Distribution của toàn bộ dataset
# ============================================================

def plot_dataset_stats():
    """Quét thư mục datasets/ và vẽ phân phối BPM Ground Truth."""
    dataset_dir = os.path.join(os.path.dirname(__file__), '..', 'datasets')
    csv_files = glob.glob(os.path.join(dataset_dir, '**', '*.csv'), recursive=True)

    if not csv_files:
        print('[!] Không tìm thấy file CSV trong thư mục datasets/')
        return

    bpms = []
    names = []
    for f in csv_files:
        match = re.search(r'BPM(\d+)', os.path.basename(f), re.IGNORECASE)
        if match:
            bpms.append(int(match.group(1)))
            names.append(os.path.basename(f))

    if not bpms:
        print('[!] Không tìm thấy thông tin BPM trong tên file.')
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Dataset Statistics', fontsize=14, fontweight='bold')

    # Histogram
    axes[0].hist(bpms, bins=range(0, max(bpms) + 5, 2), edgecolor='white',
                 color='#2196F3', alpha=0.85)
    axes[0].set_title('Ground Truth BPM Distribution')
    axes[0].set_xlabel('BPM'); axes[0].set_ylabel('Number of files')
    axes[0].grid(True, linestyle='--', alpha=0.4)

    # Bar chart theo từng file
    colors = ['#4CAF50' if b <= 20 else ('#FF9800' if b <= 25 else '#F44336') for b in bpms]
    short_names = [os.path.basename(n)[:20] for n in names]
    axes[1].barh(range(len(bpms)), bpms, color=colors)
    axes[1].set_yticks(range(len(bpms)))
    axes[1].set_yticklabels(short_names, fontsize=8)
    axes[1].set_title('BPM per File')
    axes[1].set_xlabel('BPM')
    axes[1].axvline(x=12, color='green', linestyle='--', alpha=0.5, label='Normal min')
    axes[1].axvline(x=20, color='orange', linestyle='--', alpha=0.5, label='Normal max')
    axes[1].legend(fontsize=8)

    plt.tight_layout()
    out_path = os.path.join(ASSET_DIR, 'bpm_distribution.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'[+] Đã lưu: {out_path}')
    print(f'    Tổng: {len(bpms)} file | BPM min={min(bpms)}, max={max(bpms)}, mean={np.mean(bpms):.1f}')


# ============================================================
# Hình 4: Training History (đọc từ file log nếu có)
# ============================================================

def plot_training_history():
    """Đọc history từ models/ và vẽ đường cong Loss/MAE."""
    history_path = os.path.join(MODELS_DIR, 'training_history.npz')
    if not os.path.exists(history_path):
        print(f'[!] Chưa có file training_history.npz. Hãy train model trước.')
        return

    data = np.load(history_path)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('Model Training History', fontsize=14, fontweight='bold')

    axes[0].plot(data['loss'], color='#2196F3', label='Train Loss')
    axes[0].plot(data['val_loss'], color='#F44336', label='Val Loss')
    axes[0].set_title('Loss (MSE)'); axes[0].set_xlabel('Epoch')
    axes[0].legend(); axes[0].grid(True, linestyle='--', alpha=0.4)

    axes[1].plot(data['mae'], color='#4CAF50', label='Train MAE')
    axes[1].plot(data['val_mae'], color='#FF9800', label='Val MAE')
    axes[1].set_title('MAE (BPM)'); axes[1].set_xlabel('Epoch')
    axes[1].legend(); axes[1].grid(True, linestyle='--', alpha=0.4)

    plt.tight_layout()
    out_path = os.path.join(ASSET_DIR, 'training_history.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'[+] Đã lưu: {out_path}')


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Công cụ trực quan hóa dữ liệu CSI nhịp thở')
    parser.add_argument('csv_file', nargs='?', help='Đường dẫn file CSV cần phân tích')
    parser.add_argument('--dataset-stats', action='store_true',
                        help='Vẽ thống kê toàn bộ dataset (BPM distribution)')
    parser.add_argument('--training-history', action='store_true',
                        help='Vẽ đường cong training loss/MAE')
    args = parser.parse_args()

    if args.dataset_stats:
        plot_dataset_stats()
    elif args.training_history:
        plot_training_history()
    elif args.csv_file:
        plot_breathing_pipeline(args.csv_file)
        plot_fft_spectrum(args.csv_file)
        print('\n[Done] Các hình đã lưu vào thư mục asset/')
    else:
        parser.print_help()
