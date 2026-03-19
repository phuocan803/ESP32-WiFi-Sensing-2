"""
main.py - Entry Point: Real-time Respiration Rate Detection
===========================================================
Luồng xử lý chính (Pipeline):
  1. Đọc liên tục từ Serial (ESP32-RX).
  2. Buffer dữ liệu theo cửa sổ trượt (Sliding Window = 30 giây = 3000 packets @ 100Hz).
  3. Khi đủ cửa sổ → gọi processor.process_window() → estimator.estimate_bpm().
  4. Nếu có ONNX model (đã train): kết hợp Fusion với Deep Learning BPM.
  5. In kết quả và gửi qua MQTT.

Cách chạy:
  python main.py

Để thay đổi cổng Serial hoặc kích thước cửa sổ:
  Chỉnh CONFIG bên dưới.
"""

import serial
import re
import time
import numpy as np
from collections import deque

from src.processor import process_window
from src.estimator import estimate_bpm
from src.mqtt_client import publish_result
from src.model_inferencer import estimate_bpm_model, is_model_available


# ============================================================
# CONFIG
# ============================================================
SERIAL_PORT      = "COM3"       # Cổng ESP32-RX (COM3 Windows / /dev/ttyUSB0 Linux)
BAUD_RATE        = 921600
SAMPLING_RATE    = 100.0        # Hz (phải khớp với PACKET_RATE trên firmware)
WINDOW_SECONDS   = 30           # Cửa sổ phân tích: 30 giây
STEP_SECONDS     = 5            # Tính lại BPM mỗi 5 giây (Sliding Window)
WINDOW_SIZE      = int(SAMPLING_RATE * WINDOW_SECONDS)  # = 3000 packets
STEP_SIZE        = int(SAMPLING_RATE * STEP_SECONDS)    # = 500 packets


def parse_csi_from_line(line: str) -> np.ndarray | None:
    """
    Trích xuất mảng số nguyên CSI từ một dòng dữ liệu Serial.

    Kế thừa logic từ ESP32-WiFi-Sensing-1/python_utils/parse_csi.py.
    Tìm chuỗi nằm trong dấu ngoặc vuông [...] và chuyển thành mảng int.

    Parameters:
        line: Chuỗi ký tự dòng dữ liệu từ Serial.

    Returns:
        np.ndarray kiểu int, hoặc None nếu không tìm thấy CSI.
    """
    match = re.search(r'\[([-\d ]+)\]', line)
    if not match:
        return None
    try:
        csi_values = list(map(int, match.group(1).split()))
        if len(csi_values) < 64:
            # Loại bỏ các gói tin không đủ dữ liệu
            return None
        return np.array(csi_values)
    except ValueError:
        return None


def main():
    """
    Vòng lặp chính thu thập dữ liệu và tính toán BPM theo thời gian thực.
    
    Sử dụng deque (hàng đợi hai đầu) làm buffer vòng tròn cho hiệu quả tốt nhất.
    Khi buffer đầy (đủ 1 cửa sổ), tiến hành tính BPM và trượt cửa sổ đi STEP_SIZE.
    """
    print(f"[Main] Đang mở cổng {SERIAL_PORT} @ {BAUD_RATE} baud...")
    print(f"[Main] Cửa sổ phân tích: {WINDOW_SECONDS}s | Bước trượt: {STEP_SECONDS}s")

    try:
        ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=1)
    except serial.SerialException as e:
        print(f"[ERROR] Không mở được cổng Serial: {e}")
        return

    # Deque tự động xóa phần tử cũ khi đầy (sliding window)
    buffer = deque(maxlen=WINDOW_SIZE)
    step_counter = 0

    print("[Main] Bắt đầu thu thập... (Ctrl+C để dừng)\n")

    try:
        while True:
            if ser.in_waiting:
                try:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                except Exception:
                    continue

                if "CSI_DATA" not in line:
                    continue

                csi_array = parse_csi_from_line(line)
                if csi_array is None:
                    continue

                buffer.append(csi_array)
                step_counter += 1

                # Chỉ xử lý khi đủ 1 cửa sổ dữ liệu
                if len(buffer) < WINDOW_SIZE:
                    print(f"\r[Buffer] {len(buffer)}/{WINDOW_SIZE} packets...", end="")
                    continue

                # Trượt cửa sổ: Chỉ tính lại mỗi STEP_SIZE packet mới
                if step_counter < STEP_SIZE:
                    continue
                step_counter = 0

                print("\n[Main] Đang xử lý cửa sổ dữ liệu...")

                # Stage 2: Xử lý tín hiệu
                csi_window = np.array(list(buffer))
                breathing_signal = process_window(csi_window, fs=SAMPLING_RATE)

                # Stage 3: Ước lượng BPM
                # Phương pháp A: FFT + Peak Detection (luôn chạy)
                result = estimate_bpm(breathing_signal, fs=SAMPLING_RATE)
                bpm_traditional = result["bpm"]

                # Phương pháp B: Deep Learning Model (chạy nếu đã train)
                if is_model_available():
                    try:
                        bpm_dl = estimate_bpm_model(breathing_signal)
                        # Fusion: Trung bình có trọng số (DL:Traditional = 2:1)
                        # DL được ưu tiên hơn vì đã học từ dữ liệu thực tế
                        bpm = round((bpm_dl * 2 + bpm_traditional * 1) / 3.0, 2)
                        method = f"Fusion (DL={bpm_dl:.1f}, Signal={bpm_traditional:.1f})"
                    except Exception as e:
                        bpm = bpm_traditional
                        method = f"{result['method']} [DL fallback: {e}]"
                else:
                    bpm = bpm_traditional
                    method = result["method"]

                # Hiển thị kết quả
                timestamp = time.strftime("%H:%M:%S")
                print(f"[{timestamp}] BPM = {bpm:.1f} | Peaks = {result['peak_count']} | Method: {method}")

                # Stage 4: Gửi lên MQTT
                try:
                    publish_result(bpm)
                except Exception as e:
                    print(f"[MQTT Warning] Không gửi được: {e}")

    except KeyboardInterrupt:
        print("\n[Main] Dừng lại theo yêu cầu.")
    finally:
        ser.close()
        print("[Main] Đã đóng cổng Serial.")


if __name__ == "__main__":
    main()
