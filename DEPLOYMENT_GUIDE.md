# DEPLOYMENT GUIDE: ESP32-WiFi-Sensing-2

Hướng dẫn triển khai hệ thống nhận diện nhịp thở từ đầu đến cuối.

---

## Yêu cầu

| Thành phần | Chi tiết |
|:---|:---|
| Phần cứng | 2x ESP32 (bất kỳ loại nào), USB cable |
| PC / Edge Device | Windows/Linux/macOS, hoặc Jetson Nano |
| Firmware IDE | ESP-IDF **v4.3** |
| Python | **3.9+** |
| Mã nguồn Firmware | `ESP32-WiFi-Sensing-1/esp32-csi-tool/` |

---

## Giai đoạn 1: Cài đặt Firmware

### Bước 1.1 – Cài ESP-IDF v4.3

Làm theo hướng dẫn chính thức của Espressif:
https://docs.espressif.com/projects/esp-idf/en/release-v4.3/esp32/get-started/index.html

> **Quan trọng:** Phải dùng đúng phiên bản v4.3. Các phiên bản khác không tương thích.

### Bước 1.2 – Nạp firmware cho ESP32-TX (active_sta)

```bash
cd ESP32-WiFi-Sensing-1/esp32-csi-tool/active_sta
idf.py menuconfig
```

Trong menuconfig, chỉnh các giá trị sau:

| Menu Path | Giá trị |
|:---|:---|
| `Serial flasher config > Custom baud rate value` | `921600` |
| `Component config > Common ESP32-related > Channel for console output` | `Custom UART` |
| `Component config > Common ESP32-related > UART console baud rate` | `921600` |
| `Component config > Wi-Fi > WiFi CSI` | `Enable` (nhấn Space) |
| `Component config > FreeRTOS > Tick rate (Hz)` | `1000` |
| `ESP32 CSI Tool Config > WiFi Channel` | `6` |
| `ESP32 CSI Tool Config > WiFi SSID` | `myssid` |
| `ESP32 CSI Tool Config > WiFi Password` | `mypassword` |
| `ESP32 CSI Tool Config > Packet TX Rate` | `100` |
| `ESP32 CSI Tool Config > Should this ESP32 collect CSI?` | `N` (TX không cần thu) |

```bash
idf.py flash monitor
```

### Bước 1.3 – Nạp firmware cho ESP32-RX (active_ap)

```bash
cd ESP32-WiFi-Sensing-1/esp32-csi-tool/active_ap
idf.py menuconfig
```

| Menu Path | Giá trị |
|:---|:---|
| `Serial flasher config > Custom baud rate value` | `921600` |
| `Component config > Common ESP32-related > UART console baud rate` | `921600` |
| `Component config > Wi-Fi > WiFi CSI` | `Enable` |
| `Component config > FreeRTOS > Tick rate (Hz)` | `1000` |
| `ESP32 CSI Tool Config > WiFi Channel` | `6` (phải trùng TX) |
| `ESP32 CSI Tool Config > WiFi SSID` | `myssid` (phải trùng TX) |
| `ESP32 CSI Tool Config > WiFi Password` | `mypassword` (phải trùng TX) |
| `ESP32 CSI Tool Config > Should this ESP32 collect CSI?` | `Y` |
| `ESP32 CSI Tool Config > Send CSI data to Serial` | `Y` |

```bash
idf.py flash monitor
```

> Sau bước này, bạn sẽ thấy dữ liệu dạng `CSI_DATA,...,[101 -48 5 ...]` chạy trên màn hình. Đó là tín hiệu đang hoạt động.

---

## Giai đoạn 2: Cài đặt Python

```bash
pip install -r requirements.txt
```

Nếu dùng Jetson Nano (ARM), cài thêm:
```bash
pip install onnxruntime  # hoặc onnxruntime-gpu nếu muốn GPU
```

---

## Giai đoạn 3: Thu thập Dữ liệu

### Bước 3.1 – Thiết lập vật lý
- Đặt **ESP32-TX** và **ESP32-RX** cách nhau **1.5 – 2 mét**.
- Người đo ngồi **giữa đường thẳng nối TX và RX** (Line-of-Sight).
- Cắm **ESP32-RX** vào PC/Jetson Nano qua USB.

### Bước 3.2 – Cấu hình `edge/collect_data.py`

Mở file và chỉnh 2-3 biến trước mỗi lần đo:

```python
SERIAL_PORT      = "COM3"     # Windows, hoặc "/dev/ttyUSB0" Linux
SUBJECT_NAME     = "An"       # Tên người được đo
BPM_GROUND_TRUTH = "16"       # Nhịp thở thực tế (đếm tay hoặc đặt placeholder)
```

### Bước 3.3 – Chạy thu thập

```bash
python edge/collect_data.py
```

- Mỗi session thu thập khoảng **2 phút** (120 giây).
- Nhấn **Ctrl+C** để dừng và lưu file.
- File được lưu vào: `datasets/An_BPM16_YYYYMMDD_HHMMSS.csv`.

### Bước 3.4 – Kiểm tra chất lượng

```bash
python edge/verify_data.py datasets/An_BPM16_*.csv
```

Đạt yêu cầu: tần số > 20Hz, CSI hợp lệ > 90%.

### Các kịch bản cần thu thập

| Kịch bản | BPM mục tiêu | Ghi chú |
|:---|:---|:---|
| Normal (Bình thường) | 12–18 | Ngồi yên, thở đều |
| Slow (Thở chậm/sâu) | < 10 | Hít thở thiền định |
| Fast (Thở nhanh) | > 25 | Sau vận động nhẹ |
| Apnea (Nín thở) | ~ 0 | Giữ hơi 20–30 giây |
| Noise (Có nhiễu) | bất kỳ | Có người đi lại trong phòng |

> Thu thập **ít nhất 5 file CSV** (mỗi kịch bản 1 file, mỗi file 120s) trước khi train model.

---

## Giai đoạn 4: Train Model (Tùy chọn)

Nếu muốn dùng Deep Learning để tăng độ chính xác:

```bash
jupyter notebook notebooks/train_model.ipynb
```

Chạy tất cả các cell theo thứ tự. Sau khi train xong, notebook sẽ tự export:
- `models/respiration_model.onnx`
- `models/model_metadata.json`

> **Không có model**: Hệ thống vẫn hoạt động bình thường bằng FFT + Peak Detection.

---

## Giai đoạn 5: Chạy Hệ thống Real-time

### Bước 5.1 – Cấu hình `edge/main.py`

```python
SERIAL_PORT   = "COM3"     # Cổng của ESP32-RX
SAMPLING_RATE = 100.0      # Phải khớp với Packet TX Rate trong firmware
WINDOW_SECONDS = 30        # Cửa sổ phân tích (giây)
STEP_SECONDS   = 5         # Cập nhật BPM mỗi N giây
```

### Bước 5.2 – Chạy

```bash
python edge/main.py
```

**Output mẫu trên terminal:**
```
[Main] Đang mở cổng COM3 @ 921600 baud...
[Buffer] 1250/3000 packets...
[Main] Đang xử lý cửa sổ dữ liệu...
[01:15:30] BPM = 15.2 | Peaks = 8 | Method: Fusion (DL=15.0, Signal=15.5)
[MQTT] Gửi BPM=15.2, Status=Normal
```

---

## Giai đoạn 6: Triển khai trên Jetson Nano

### Bước 6.1 – Copy project lên Jetson Nano

```bash
scp -r ESP32-WiFi-Sensing-2/ user@jetson-nano-ip:/home/user/
```

### Bước 6.2 – Cài đặt trên Jetson Nano

```bash
pip install -r requirements.txt
pip install onnxruntime
```

### Bước 6.3 – Cắm ESP32-RX vào USB port của Jetson Nano

Kiểm tra cổng:
```bash
ls /dev/ttyUSB*   # Thường là /dev/ttyUSB0
```

Chỉnh `SERIAL_PORT = "/dev/ttyUSB0"` trong `edge/main.py`.

### Bước 6.4 – Chạy

```bash
python edge/main.py
```

### (Tùy chọn) Chạy như background service với systemd

```bash
# Tạo file service
sudo nano /etc/systemd/system/respiration.service
```

```ini
[Unit]
Description=Respiration Rate Detection
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/user/ESP32-WiFi-Sensing-2/edge/main.py
WorkingDirectory=/home/user/ESP32-WiFi-Sensing-2/edge
Restart=always
User=user

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable respiration
sudo systemctl start respiration
```

---

## Cấu hình MQTT

Chỉnh trong `edge/src/mqtt_client.py`:

```python
MQTT_BROKER   = "your-broker.hivemq.cloud"
MQTT_PORT     = 8883
MQTT_USERNAME = "your_username"
MQTT_PASSWORD = "your_password"
TOPIC_BPM     = "respiration/bpm"
TOPIC_STATUS  = "respiration/status"
```

**Payload JSON được gửi đi:**
```json
{
  "bpm": 15.2,
  "status": "Normal"
}
```

| Status | BPM |
|:---|:---|
| `Apnea` | < 5 |
| `Slow` | 5 – 12 |
| `Normal` | 12 – 20 |
| `Fast` | > 20 |

---

## Troubleshooting

| Vấn đề | Nguyên nhân | Giải pháp |
|:---|:---|:---|
| Không thấy dữ liệu CSI | TX và RX chưa kết nối WiFi | Kiểm tra SSID/Password trong menuconfig |
| Tần số < 20Hz | Baud rate thấp hoặc Serial bị nghẽn | Tăng baud rate lên 1000000 |
| BPM sai lệch lớn | Người đo không ở giữa TX-RX | Điều chỉnh vị trí vật lý |
| Import error khi chạy `main.py` | Thiếu thư viện | Chạy `pip install -r requirements.txt` |
| ONNX model không load | File `.onnx` chưa được tạo | Chạy `train_model.ipynb` trước |
