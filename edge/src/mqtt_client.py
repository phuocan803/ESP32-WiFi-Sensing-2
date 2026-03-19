"""
mqtt_client.py - Stage 4: MQTT Integration
===========================================
Kế thừa cấu hình từ ESP32-WiFi-Sensing-1 (HiveMQ Cloud, TLS, MQTTv5).
Được refactor thành lớp để quản lý kết nối hiệu quả hơn.

Topic mặc định:
  - "respiration/bpm"   : Gửi giá trị BPM ước lượng.
  - "respiration/status": Gửi trạng thái (Normal/Fast/Slow/Apnea).

Để thay đổi thông tin kết nối, chỉnh các hằng số ở phần CONFIG bên dưới.
"""

import json
import paho.mqtt.client as paho
from paho import mqtt

# ============================================================
# CONFIG - Thay đổi nếu bạn dùng broker khác
# ============================================================
MQTT_BROKER   = "1904448cf01a4564947dae8e889f5fee.s2.eu.hivemq.cloud"
MQTT_PORT     = 8883
MQTT_USERNAME = "JetsonNano"
MQTT_PASSWORD = "JetsonNano123"
TOPIC_BPM     = "respiration/bpm"
TOPIC_STATUS  = "respiration/status"


# ============================================================
# Hàm phân loại trạng thái nhịp thở
# ============================================================

def classify_breathing(bpm: float) -> str:
    """
    Phân loại trạng thái nhịp thở dựa trên ngưỡng lâm sàng.

    Ngưỡng tham khảo (người trưởng thành khi nghỉ ngơi):
      - Apnea (Ngưng thở): < 5 BPM (hoặc không phát hiện được)
      - Bradypnea (Thở chậm): 5 – 12 BPM
      - Normal (Bình thường): 12 – 20 BPM
      - Tachypnea (Thở nhanh): > 20 BPM

    Parameters:
        bpm: Nhịp thở ước lượng.

    Returns:
        Chuỗi trạng thái: "Apnea", "Slow", "Normal", hoặc "Fast".
    """
    if bpm < 5:
        return "Apnea"
    elif bpm < 12:
        return "Slow"
    elif bpm <= 20:
        return "Normal"
    else:
        return "Fast"


# ============================================================
# MQTT Publisher
# ============================================================

def _on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[MQTT] Kết nối thành công tới broker.")
    else:
        print(f"[MQTT] Kết nối thất bại với mã lỗi: {rc}")


def _on_publish(client, userdata, mid, properties=None):
    print(f"[MQTT] Đã gửi gói tin với mid={mid}")


def publish_result(bpm: float):
    """
    Gửi kết quả BPM và trạng thái nhịp thở lên MQTT broker.

    Payload JSON được gửi đi:
      {
        "bpm": <float>,
        "status": "Normal" | "Fast" | "Slow" | "Apnea"
      }

    Parameters:
        bpm: Giá trị BPM ước lượng từ estimator.py.
    """
    status = classify_breathing(bpm)
    payload = json.dumps({"bpm": bpm, "status": status})

    client = paho.Client(client_id="", userdata=None, protocol=paho.MQTTv5)
    client.on_connect = _on_connect
    client.on_publish = _on_publish

    # Kết nối bảo mật TLS (kế thừa từ V1)
    client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_start()

    client.publish(TOPIC_BPM, payload=payload, qos=1)
    print(f"[MQTT] Gửi BPM={bpm}, Status={status}")

    client.loop_stop()
    client.disconnect()
