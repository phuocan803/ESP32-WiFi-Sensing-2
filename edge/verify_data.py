import pandas as pd
import numpy as np
import os
import sys

def verify_csv(filepath):
    if not os.path.exists(filepath):
        print(f"[ERROR] Không tìm thấy file: {filepath}")
        return

    print(f"[*] Đang phân tích file: {filepath}")
    
    try:
        # Đọc file không header (theo chuẩn V1)
        # Trong V1, cột timestamp thường ở vị trí 24 (index 23 nếu bắt đầu từ 0)
        # Nhưng tùy firmware, hãy kiểm tra lại. Ở đây chúng ta tìm cột có giá trị lớn tăng dần.
        df = pd.read_csv(filepath, header=None, on_bad_lines='skip')
        
        num_rows = len(df)
        print(f"[+] Tổng số gói tin (packets): {num_rows}")
        
        if num_rows < 100:
            print("[!] CẢNH BÁO: Dữ liệu quá ít. Hãy thu thập ít nhất 2 phút.")
        
        # Kiểm tra cột CSI (thường là cột cuối cùng và có dấu ngoặc [])
        csi_col = df.iloc[:, -1]
        valid_csi = csi_col.str.contains(r'\[.*\]', na=False).sum()
        print(f"[+] Số dòng chứa dữ liệu CSI hợp lệ: {valid_csi} ({valid_csi/num_rows*100:.2f}%)")
        
        # Thử tính toán Packet Rate (nếu có cột timestamp ở index 23 hoặc 20)
        # Trong example_csi.csv của bạn, timestamp ở index 23 (cột thứ 24)
        if df.shape[1] >= 24:
            timestamps = pd.to_numeric(df.iloc[:, 18], errors='coerce') # Thường là cột 19 hoặc 24
            timestamps = timestamps.dropna()
            if len(timestamps) > 1:
                duration_ms = (timestamps.iloc[-1] - timestamps.iloc[0])
                if duration_ms > 0:
                    rate = len(timestamps) / (duration_ms / 1000000.0) # Nếu là micro giây
                    if rate > 1000: # Nếu là nano giây
                         rate = len(timestamps) / (duration_ms / 1000000000.0)
                    
                    print(f"[+] Tốc độ gói tin ước tính: {rate:.2f} Hz")
                    if rate < 20:
                        print("[!] CẢNH BÁO: Tần số quá thấp (< 20Hz). Cần kiểm tra lại cấu hình TX.")
        
    except Exception as e:
        print(f"[ERROR] Lỗi khi phân tích: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Sử dụng: python verify_data.py <đường_dẫn_file_csv>")
    else:
        verify_csv(sys.argv[1])
