"""
pretrain_physionet.py - Script chạy pre-training với PhysioNet BIDMC
Tương đương với notebook pretrain_physionet.ipynb nhưng chạy được từ terminal.
"""

import os, sys, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import resample, butter, filtfilt, find_peaks
from sklearn.model_selection import train_test_split

MODELS_DIR    = os.path.join(os.path.dirname(__file__), '..', 'models')
ASSET_DIR     = os.path.join(os.path.dirname(__file__), '..', 'asset')
SAMPLING_RATE = 100.0
WINDOW_SEC    = 30
WINDOW_SIZE   = int(SAMPLING_RATE * WINDOW_SEC)
STEP_SEC      = 5
STEP_SIZE     = int(SAMPLING_RATE * STEP_SEC)
BPM_MIN, BPM_MAX = 4.0, 40.0
BIDMC_RECORDS = [f'bidmc{i:02d}' for i in range(1, 54)]
DB_NAME = 'bidmc'

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(ASSET_DIR, exist_ok=True)

# ── Helpers ──────────────────────────────────────────────────

def bpm_from_peaks(signal, fs):
    duration_sec = len(signal) / fs
    min_distance = int(fs * 1.5)
    peaks, _ = find_peaks(signal, distance=min_distance, height=np.std(signal) * 0.3)
    n_peaks = len(peaks)
    if n_peaks < 2:
        return 0.0
    return round((n_peaks / duration_sec) * 60.0, 2)

def bandpass_resp(signal, fs, low=0.1, high=0.8):
    nyq = fs / 2.0
    b, a = butter(4, [low / nyq, high / nyq], btype='band')
    return filtfilt(b, a, signal)

def load_bidmc_record(record_name):
    try:
        import wfdb
        record = wfdb.rdrecord(record_name, pn_dir=DB_NAME)
    except Exception as e:
        print(f'  [SKIP] {record_name}: {e}')
        return None

    fs_orig = record.fs
    sig_names = [s.lower() for s in record.sig_name]
    resp_idx = None
    for i, name in enumerate(sig_names):
        if any(candidate in name for candidate in ['resp', 'respiration', 'br']):
            resp_idx = i
            break

    if resp_idx is None:
        print(f'  [SKIP] {record_name}: Không có kênh RESP. Có: {record.sig_name}')
        return None

    resp = record.p_signal[:, resp_idx]
    resp = resp[~np.isnan(resp)]

    target_len = int(len(resp) * SAMPLING_RATE / fs_orig)
    return resample(resp, target_len)

# ── Step 1: Load Dataset ───────────────────────────────────

print('='*60)
print('  PhysioNet BIDMC Pre-training')
print('='*60)
print(f'\n[1] Đang tải {len(BIDMC_RECORDS)} bản ghi từ PhysioNet...')

X_list, y_list = [], []
skipped = 0
for i, rec in enumerate(BIDMC_RECORDS):
    print(f'    [{i+1:02d}/{len(BIDMC_RECORDS)}] {rec}...', end=' ', flush=True)
    resp = load_bidmc_record(rec)
    if resp is None:
        skipped += 1; continue

    resp_f = bandpass_resp(resp, SAMPLING_RATE)
    if len(resp_f) < WINDOW_SIZE:
        print(f'ngắn ({len(resp_f)/SAMPLING_RATE:.0f}s) — SKIP')
        skipped += 1; continue

    n_windows = 0
    for start in range(0, len(resp_f) - WINDOW_SIZE + 1, STEP_SIZE):
        window = resp_f[start: start + WINDOW_SIZE]
        bpm = bpm_from_peaks(window, SAMPLING_RATE)
        if bpm < BPM_MIN or bpm > BPM_MAX:
            continue
        win_norm = (window - window.mean()) / (window.std() + 1e-8)
        X_list.append(win_norm)
        y_list.append(bpm)
        n_windows += 1

    print(f'{n_windows} windows')

X = np.array(X_list)
y = np.array(y_list)
print(f'\n  Tổng: {len(X)} windows | Bỏ qua: {skipped} records')
print(f'  BPM: min={y.min():.1f}, max={y.max():.1f}, mean={y.mean():.2f}')

if len(X) < 50:
    print('[ERROR] Không đủ dữ liệu. Kiểm tra kết nối mạng.')
    sys.exit(1)

# ── Step 2: Dataset visualization ─────────────────────────

print('\n[2] Vẽ overview dataset...')
fig, axes = plt.subplots(1, 3, figsize=(18, 4))
fig.suptitle('PhysioNet BIDMC Dataset Overview', fontsize=13, fontweight='bold')
axes[0].hist(y, bins=20, color='#2196F3', edgecolor='white', alpha=0.85)
axes[0].axvline(12, color='green', linestyle='--', alpha=0.7)
axes[0].axvline(20, color='orange', linestyle='--', alpha=0.7)
axes[0].set_title('BPM Distribution'); axes[0].set_xlabel('BPM')
t = np.arange(WINDOW_SIZE) / SAMPLING_RATE
axes[1].plot(t, X[0], '#F44336', linewidth=0.8)
axes[1].set_title(f'Example Signal (BPM={y[0]:.1f})')
axes[1].set_xlabel('Time (s)')
axes[2].plot(t, X[len(X)//2], '#4CAF50', linewidth=0.8)
axes[2].set_title(f'Example (BPM={y[len(y)//2]:.1f})')
axes[2].set_xlabel('Time (s)')
plt.tight_layout()
plt.savefig(os.path.join(MODELS_DIR, 'physionet_data_overview.png'), dpi=150)
plt.close()
print('  OK → physionet_data_overview.png')

# ── Step 3: Train/Test Split ───────────────────────────────

print('\n[3] Train/Test split...')
X_cnn = X[..., np.newaxis]
y_norm = (y - BPM_MIN) / (BPM_MAX - BPM_MIN)
X_train, X_test, y_train, y_test = train_test_split(
    X_cnn, y_norm, test_size=0.15, random_state=42, shuffle=True
)
print(f'  Train: {X_train.shape[0]} | Test: {X_test.shape[0]}')

# ── Step 4: Build & Train Model ───────────────────────────

print('\n[4] Xây dựng và train model...')
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
tf.random.set_seed(42)

def build_model(input_length):
    inp = keras.Input(shape=(input_length, 1), name='breathing_signal')
    x = layers.Conv1D(32, 50, strides=5, activation='relu', padding='same')(inp)
    x = layers.BatchNormalization()(x)
    x = layers.MaxPooling1D(2)(x)
    x = layers.Conv1D(64, 25, strides=2, activation='relu', padding='same')(x)
    x = layers.BatchNormalization()(x)
    x = layers.MaxPooling1D(2)(x)
    x = layers.Dropout(0.3)(x)
    x = layers.LSTM(64, return_sequences=False)(x)
    x = layers.Dropout(0.3)(x)
    out = layers.Dense(1, activation='sigmoid', name='bpm')(x)
    return keras.Model(inp, out, name='respiration_cnn_lstm')

model = build_model(WINDOW_SIZE)
model.compile(optimizer=keras.optimizers.Adam(1e-3), loss='mse', metrics=['mae'])
model.summary()

pretrain_h5 = os.path.join(MODELS_DIR, 'pretrained_physionet.h5')
callbacks = [
    keras.callbacks.EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True, verbose=1),
    keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-5, verbose=1),
    keras.callbacks.ModelCheckpoint(pretrain_h5, save_best_only=True, verbose=1)
]

history = model.fit(
    X_train, y_train,
    epochs=80, batch_size=32, validation_split=0.15,
    callbacks=callbacks, verbose=1
)

np.savez(os.path.join(MODELS_DIR, 'physionet_training_history.npz'),
    loss=history.history['loss'], val_loss=history.history['val_loss'],
    mae=history.history['mae'], val_mae=history.history['val_mae']
)
print('[OK] Đã lưu model và history.')

# ── Step 5: Evaluate & Plot Report ────────────────────────

print('\n[5] Đánh giá model...')
best = keras.models.load_model(pretrain_h5)
y_pred_norm = best.predict(X_test, verbose=0).flatten()
y_pred_bpm  = y_pred_norm * (BPM_MAX - BPM_MIN) + BPM_MIN
y_true_bpm  = y_test * (BPM_MAX - BPM_MIN) + BPM_MIN
errors      = y_pred_bpm - y_true_bpm
mae_final   = float(np.mean(np.abs(errors)))
rmse_final  = float(np.sqrt(np.mean(errors**2)))
within_2    = float(np.mean(np.abs(errors) <= 2.0) * 100)

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Pre-training Report — PhysioNet BIDMC', fontsize=14, fontweight='bold')
axes[0,0].plot(history.history['loss'], '#2196F3', label='Train Loss')
axes[0,0].plot(history.history['val_loss'], '#F44336', label='Val Loss')
best_ep = int(np.argmin(history.history['val_loss']))
axes[0,0].axvline(best_ep, color='green', linestyle=':', label=f'Best={best_ep}')
axes[0,0].set_title('(A) Loss'); axes[0,0].legend(); axes[0,0].grid(True, linestyle='--', alpha=0.4)
axes[0,1].plot(np.array(history.history['mae'])*(BPM_MAX-BPM_MIN), '#4CAF50', label='Train MAE')
axes[0,1].plot(np.array(history.history['val_mae'])*(BPM_MAX-BPM_MIN), '#FF9800', label='Val MAE')
axes[0,1].axhline(2.0, color='red', linestyle='--', label='Target 2 BPM')
axes[0,1].set_title('(B) MAE (BPM)'); axes[0,1].legend(); axes[0,1].grid(True, linestyle='--', alpha=0.4)
axes[1,0].scatter(y_true_bpm, y_pred_bpm, alpha=0.3, color='#2196F3', s=10)
lim = [0, max(float(y_true_bpm.max()), float(y_pred_bpm.max())) + 3]
axes[1,0].plot(lim, lim, 'k--', alpha=0.5)
axes[1,0].fill_between(lim, [l-2 for l in lim], [l+2 for l in lim], alpha=0.08, color='green')
axes[1,0].set_title(f'(C) Predicted vs True\nMAE={mae_final:.2f} | RMSE={rmse_final:.2f}')
axes[1,0].set_xlabel('True BPM'); axes[1,0].set_ylabel('Pred BPM'); axes[1,0].grid(True, linestyle='--', alpha=0.3)
axes[1,1].hist(errors, bins=30, color='#9C27B0', edgecolor='white', alpha=0.8)
axes[1,1].axvline(0, color='black', linestyle='--')
axes[1,1].axvline(-2, color='green', linestyle=':'); axes[1,1].axvline(+2, color='green', linestyle=':')
axes[1,1].set_title(f'(D) Error Distribution\n{within_2:.1f}% within ±2 BPM')
axes[1,1].set_xlabel('Error (BPM)'); axes[1,1].grid(True, linestyle='--', alpha=0.4)
plt.tight_layout()
report_path = os.path.join(MODELS_DIR, 'pretrain_report.png')
asset_path  = os.path.join(ASSET_DIR, 'pretrain_report.png')
plt.savefig(report_path, dpi=150, bbox_inches='tight')
plt.savefig(asset_path, dpi=150, bbox_inches='tight')
plt.close()
print(f'  OK → pretrain_report.png')

meta = {
    'dataset': 'PhysioNet BIDMC PPG and Respiration',
    'n_windows': int(len(X)),
    'window_sec': WINDOW_SEC,
    'sampling_rate': SAMPLING_RATE,
    'bpm_min': BPM_MIN, 'bpm_max': BPM_MAX,
    'pretrain_mae_bpm': round(mae_final, 2),
    'pretrain_rmse_bpm': round(rmse_final, 2),
    'within_2bpm_pct': round(within_2, 1)
}
with open(os.path.join(MODELS_DIR, 'pretrain_metadata.json'), 'w') as f:
    json.dump(meta, f, indent=2)

print('\n' + '='*60)
print(f'  MAE  : {mae_final:.2f} BPM')
print(f'  RMSE : {rmse_final:.2f} BPM')
print(f'  ±2 BPM: {within_2:.1f}%')
print(f'  Model: {pretrain_h5}')
print('='*60)
