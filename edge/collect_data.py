import serial
import csv
import time
import os
import signal
import sys

# --- Cấu hình ---
SERIAL_PORT = "COM3"  # Thay đổi tùy theo hệ điều hành (ví dụ: /dev/ttyUSB0 trên Linux)
BAUD_RATE = 921600
OUTPUT_DIR = "datasets"
SUBJECT_NAME = "An"
BPM_GROUND_TRUTH = "16" # Số nhịp thở thực tế đếm được (Ground Truth) // placeholder

# --- Khởi tạo file lưu trữ ---
timestamp_str = time.strftime("%Y%m%d_%H%M%S")
filename = f"{SUBJECT_NAME}_BPM{BPM_GROUND_TRUTH}_{timestamp_str}.csv"
filepath = os.path.join(OUTPUT_DIR, filename)

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def signal_handler(sig, frame):
    print("\n[!] Đang dừng thu thập và đóng cổng Serial...")
    if 'ser' in globals() and ser.is_open:
        ser.close()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def main():
    print(f"[*] Đang mở cổng {SERIAL_PORT} với baudrate {BAUD_RATE}...")
    try:
        global ser
        ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=1)
        
        with open(filepath, mode='w', newline='') as f:
            csv_writer = csv.writer(f)
            # Không viết header theo chuẩn V1 để tương thích hoàn toàn với script cũ
            
            print(f"[*] Đang thu thập dữ liệu vào: {filepath}")
            print("[*] Nhấn Ctrl+C để dừng lại.")
            
            while True:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if "CSI_DATA" in line:
                        # Dữ liệu từ serial thường có dạng: CSI_DATA,AP,MAC,RSSI, ...
                        # Chúng ta lưu nguyên xi dòng này vào CSV để parse sau
                        csv_writer.writerow(line.split(","))
                        
    except serial.SerialException as e:
        print(f"[ERROR] Không thể mở cổng Serial: {e}")
    except Exception as e:
        print(f"[ERROR] Đã xảy ra lỗi: {e}")

if __name__ == "__main__":
    main()
