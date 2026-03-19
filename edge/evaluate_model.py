"""
evaluate_model.py - Script đánh giá Model sau khi train
========================================================
Tạo ra bộ hình ảnh đánh giá đầy đủ, lưu vào asset/:
  - model_predicted_vs_true.png  : Scatter plot dự đoán vs thực tế
  - model_error_distribution.png : Phân phối sai số theo BPM
  - model_per_scenario.png       : MAE theo từng kịch bản
  - model_confusion_zone.png     : Nhầm lẫn giữa các zone (Normal/Fast/Slow/Apnea)
  - latency_benchmark.png        : Thời gian xử lý mỗi cửa sổ

Cách dùng:
  python edge/evaluate_model.py
"""

import sys
import os
import re
import time
import glob
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

matplotlib.use('Agg')

sys.path.insert(0, os.path.dirname(__file__))
from src.processor import process_window
from src.estimator import estimate_bpm

ASSET_DIR  = os.path.join(os.path.dirname(__file__), '..', 'asset')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
DATASET_DIR = os.path.join(os.path.dirname(__file__), '..', 'datasets')
SAMPLING_RATE = 100.0
WINDOW_SIZE = 3000  # 30s × 100Hz

os.makedirs(ASSET_DIR, exist_ok=True)

# ============================================================
# Helpers
# ============================================================

def classify_zone(bpm: float) -> str:
    if bpm < 5:   return 'Apnea'
    if bpm < 12:  return 'Slow'
    if bpm <= 20: return 'Normal'
    return 'Fast'

ZONE_COLORS = {'Apnea': '#9C27B0', 'Slow': '#2196F3', 'Normal': '#4CAF50', 'Fast': '#F44336'}


def load_and_predict(dataset_dir: str):
    """
    Quét dataset/, tiền xử lý, dự đoán bằng FFT+Peaks (và ONNX nếu có),
    trả về danh sách (true_bpm, pred_bpm, scenario_label).
    """
    from src.model_inferencer import estimate_bpm_model, is_model_available
    use_model = is_model_available()

    csv_files = glob.glob(os.path.join(dataset_dir, '**', '*.csv'), recursive=True)
    results = []

    for fpath in csv_files:
        bname = os.path.basename(fpath)
        m = re.search(r'BPM(\d+)', bname, re.IGNORECASE)
        if not m:
            continue
        true_bpm = float(m.group(1))

        # Nhãn kịch bản từ tên file (nếu có)
        scenario = 'Normal'
        for tag in ['Slow', 'Fast', 'Apnea', 'Noise']:
            if tag.lower() in bname.lower():
                scenario = tag; break

        # Đọc dữ liệu
        try:
            df = pd.read_csv(fpath, header=None, on_bad_lines='skip')
        except Exception:
            continue
        csi_col = df.iloc[:, -1]
        rows = []
        for val in csi_col:
            mm = re.search(r'\[([-\d ]+)\]', str(val))
            if not mm: continue
            try:
                v = list(map(int, mm.group(1).split()))
                if len(v) >= 64: rows.append(np.array(v[:128]))
            except ValueError:
                continue
            if len(rows) >= WINDOW_SIZE: break

        if len(rows) < 500:
            continue

        signal = process_window(np.array(rows[:WINDOW_SIZE]), fs=SAMPLING_RATE)
        trad_result = estimate_bpm(signal, fs=SAMPLING_RATE)
        bpm_trad = trad_result['bpm']

        if use_model:
            try:
                bpm_dl = estimate_bpm_model(signal)
                pred_bpm = round((bpm_dl * 2 + bpm_trad) / 3.0, 2)
            except Exception:
                pred_bpm = bpm_trad
        else:
            pred_bpm = bpm_trad

        results.append({'true': true_bpm, 'pred': pred_bpm, 'scenario': scenario, 'file': bname})

    return results


# ============================================================
# Hình 1: Predicted vs True (Scatter plot)
# ============================================================

def plot_predicted_vs_true(results):
    true_bpms = np.array([r['true'] for r in results])
    pred_bpms = np.array([r['pred'] for r in results])
    zones = [r['scenario'] for r in results]

    mae  = np.mean(np.abs(pred_bpms - true_bpms))
    rmse = np.sqrt(np.mean((pred_bpms - true_bpms)**2))

    fig, ax = plt.subplots(figsize=(8, 8))
    for z in set(zones):
        idx = [i for i, s in enumerate(zones) if s == z]
        ax.scatter(true_bpms[idx], pred_bpms[idx], label=z,
                   color=ZONE_COLORS.get(z, 'gray'), s=80, alpha=0.85, edgecolors='white', linewidth=0.5)

    # Đường lý tưởng y=x
    lim = [0, max(true_bpms.max(), pred_bpms.max()) + 5]
    ax.plot(lim, lim, 'k--', linewidth=1.2, alpha=0.5, label='Perfect prediction')

    # ±2 BPM bands (mục tiêu của dự án)
    ax.fill_between(lim, [l - 2 for l in lim], [l + 2 for l in lim],
                    alpha=0.08, color='green', label='±2 BPM target zone')

    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel('Ground Truth BPM', fontsize=12)
    ax.set_ylabel('Predicted BPM', fontsize=12)
    ax.set_title(f'Predicted vs Ground Truth\nMAE = {mae:.2f} BPM | RMSE = {rmse:.2f} BPM',
                 fontsize=13, fontweight='bold')
    ax.legend(fontsize=9); ax.grid(True, linestyle='--', alpha=0.3)

    out = os.path.join(ASSET_DIR, 'model_predicted_vs_true.png')
    plt.savefig(out, dpi=150, bbox_inches='tight'); plt.close()
    print(f'[+] {out}')
    print(f'    MAE={mae:.2f} BPM | RMSE={rmse:.2f} BPM')
    return mae, rmse


# ============================================================
# Hình 2: Error Distribution (Histogram + Boxplot)
# ============================================================

def plot_error_distribution(results):
    errors = np.array([r['pred'] - r['true'] for r in results])
    within_2 = np.mean(np.abs(errors) <= 2.0) * 100

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('Prediction Error Distribution', fontsize=13, fontweight='bold')

    # Histogram
    axes[0].hist(errors, bins=20, color='#2196F3', edgecolor='white', alpha=0.85)
    axes[0].axvline(0, color='black', linestyle='--', linewidth=1.2)
    axes[0].axvline(-2, color='green', linestyle=':', linewidth=1, label='±2 BPM target')
    axes[0].axvline(+2, color='green', linestyle=':', linewidth=1)
    axes[0].set_title(f'Error Distribution\n{within_2:.1f}% predictions within ±2 BPM')
    axes[0].set_xlabel('Error (Predicted − True) BPM')
    axes[0].set_ylabel('Count')
    axes[0].legend()

    # Boxplot theo kịch bản
    scenarios = sorted(set(r['scenario'] for r in results))
    data_by_scenario = [[r['pred'] - r['true'] for r in results if r['scenario'] == s]
                        for s in scenarios]
    bp = axes[1].boxplot(data_by_scenario, labels=scenarios, patch_artist=True, notch=False)
    for patch, s in zip(bp['boxes'], scenarios):
        patch.set_facecolor(ZONE_COLORS.get(s, '#9E9E9E'))
        patch.set_alpha(0.7)
    axes[1].axhline(0, color='black', linestyle='--', linewidth=1)
    axes[1].axhline(-2, color='green', linestyle=':', linewidth=1)
    axes[1].axhline(+2, color='green', linestyle=':', linewidth=1)
    axes[1].set_title('Error by Scenario')
    axes[1].set_ylabel('Error (BPM)')
    axes[1].grid(True, linestyle='--', alpha=0.3)

    out = os.path.join(ASSET_DIR, 'model_error_distribution.png')
    plt.savefig(out, dpi=150, bbox_inches='tight'); plt.close()
    print(f'[+] {out}')
    print(f'    {within_2:.1f}% samples trong ±2 BPM')


# ============================================================
# Hình 3: MAE per Scenario
# ============================================================

def plot_per_scenario(results):
    scenarios = sorted(set(r['scenario'] for r in results))
    maes  = [np.mean(np.abs([r['pred'] - r['true'] for r in results if r['scenario'] == s])) for s in scenarios]
    rmses = [np.sqrt(np.mean([(r['pred'] - r['true'])**2 for r in results if r['scenario'] == s])) for s in scenarios]
    counts = [sum(1 for r in results if r['scenario'] == s) for s in scenarios]

    x = np.arange(len(scenarios))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width/2, maes, width, label='MAE (BPM)',
                   color=[ZONE_COLORS.get(s, '#9E9E9E') for s in scenarios], alpha=0.85)
    bars2 = ax.bar(x + width/2, rmses, width, label='RMSE (BPM)',
                   color=[ZONE_COLORS.get(s, '#9E9E9E') for s in scenarios], alpha=0.5)

    ax.axhline(y=2.0, color='red', linestyle='--', linewidth=1.2, label='Target: ≤ 2.0 BPM')
    ax.set_xticks(x)
    ax.set_xticklabels([f'{s}\n(n={c})' for s, c in zip(scenarios, counts)])
    ax.set_ylabel('Error (BPM)')
    ax.set_title('MAE & RMSE per Scenario', fontsize=13, fontweight='bold')
    ax.legend(); ax.grid(True, linestyle='--', alpha=0.3, axis='y')

    # Ghi giá trị lên bar
    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                f'{bar.get_height():.2f}', ha='center', va='bottom', fontsize=9)

    out = os.path.join(ASSET_DIR, 'model_per_scenario.png')
    plt.savefig(out, dpi=150, bbox_inches='tight'); plt.close()
    print(f'[+] {out}')

    print('\n  Kết quả theo kịch bản:')
    for s, m, r in zip(scenarios, maes, rmses):
        status = '✓' if m <= 2.0 else '✗'
        print(f'    {status} {s}: MAE={m:.2f}, RMSE={r:.2f}')


# ============================================================
# Hình 4: Latency Benchmark
# ============================================================

def plot_latency_benchmark(n_runs: int = 20):
    """Đo thời gian xử lý của từng bước pipeline và vẽ biểu đồ."""
    print(f'[*] Đo latency với {n_runs} lần chạy...')
    dummy_csi = np.random.randn(WINDOW_SIZE, 128).astype(np.float32)

    steps = {
        'process_window\n(Hampel+PCA+BPF)': lambda: process_window(dummy_csi, fs=SAMPLING_RATE),
        'estimate_bpm\n(FFT+Peaks)': lambda: None,  # sẽ đo thực
    }

    from src.processor import process_window as pw
    from src.estimator import estimate_bpm as eb

    latencies = {}

    # process_window
    times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        sig = pw(dummy_csi, fs=SAMPLING_RATE)
        times.append((time.perf_counter() - t0) * 1000)
    latencies['process_window\n(Hampel+PCA+BPF)'] = times

    # estimate_bpm
    times2 = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        eb(sig, fs=SAMPLING_RATE)
        times2.append((time.perf_counter() - t0) * 1000)
    latencies['estimate_bpm\n(FFT+Peaks)'] = times2

    # ONNX model (nếu có)
    try:
        from src.model_inferencer import estimate_bpm_model, is_model_available
        if is_model_available():
            times3 = []
            for _ in range(n_runs):
                t0 = time.perf_counter()
                estimate_bpm_model(sig)
                times3.append((time.perf_counter() - t0) * 1000)
            latencies['ONNX Model\nInference'] = times3
    except Exception:
        pass

    fig, ax = plt.subplots(figsize=(10, 6))
    positions = range(len(latencies))
    labels = list(latencies.keys())
    data = list(latencies.values())

    bp = ax.boxplot(data, positions=positions, patch_artist=True, notch=False)
    colors = ['#2196F3', '#4CAF50', '#FF9800']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color); patch.set_alpha(0.75)

    ax.set_xticks(positions); ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel('Latency (ms)')
    ax.set_title(f'Pipeline Step Latency Benchmark\n(WINDOW={WINDOW_SIZE} samples = 30s @ 100Hz)',
                 fontsize=12, fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.3, axis='y')
    ax.axhline(y=1000, color='red', linestyle='--', label='1s threshold', linewidth=1)
    ax.legend()

    means = [np.mean(d) for d in data]
    for i, (pos, m) in enumerate(zip(positions, means)):
        ax.text(pos, m + 5, f'{m:.1f}ms', ha='center', fontsize=10, color='black')

    out = os.path.join(ASSET_DIR, 'latency_benchmark.png')
    plt.savefig(out, dpi=150, bbox_inches='tight'); plt.close()
    print(f'[+] {out}')
    for label, d in zip(labels, data):
        print(f'    {label.replace(chr(10), " ")}: mean={np.mean(d):.1f}ms, max={max(d):.1f}ms')


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    print('='*60)
    print('  Model Evaluation — ESP32-WiFi-Sensing-2')
    print('='*60)

    # 1. Load results từ dataset
    print('\n[1] Đang load và đánh giá dataset...')
    results = load_and_predict(DATASET_DIR)

    if not results:
        print('[!] Không tìm thấy dữ liệu. Hãy thu thập dữ liệu trước (Stage 1).')
        print('    Chạy latency benchmark...\n')
        plot_latency_benchmark()
    else:
        print(f'    Tổng: {len(results)} mẫu\n')

        print('[2] Vẽ Predicted vs True...')
        mae, rmse = plot_predicted_vs_true(results)

        print('[3] Vẽ Error Distribution...')
        plot_error_distribution(results)

        print('[4] Vẽ MAE per Scenario...')
        plot_per_scenario(results)

        print('[5] Đo Latency...')
        plot_latency_benchmark()

        print('\n' + '='*60)
        print(f'  Tổng kết: MAE={mae:.2f} BPM | RMSE={rmse:.2f} BPM')
        target = '✓ ĐẠT' if mae <= 2.0 else '✗ CHƯA ĐẠT'
        print(f'  Mục tiêu sai số ≤ 2 BPM: {target}')
        print('='*60)
        print(f'\n[Done] Tất cả hình đã lưu vào: {ASSET_DIR}')
