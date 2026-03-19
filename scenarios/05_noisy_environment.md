# Kịch bản 5: Có Nhiễu Môi Trường (Noisy Environment)

## Mục tiêu
Thu tín hiệu khi có các nguồn nhiễu ngoài môi trường.
Kiểm tra khả năng của Hampel Filter và PCA trong việc loại bỏ nhiễu.

## Cấu hình `collect_data.py`
```python
SUBJECT_NAME     = "TenNguoi"
BPM_GROUND_TRUTH = "16"   # Nhịp thở bình thường của người đo
```

## Các loại nhiễu cần thử

### Nhiễu A: Người đi lại (Moving Person)
- Trong khi người đo ngồi yên thở, một người khác đi **vòng quanh phòng** liên tục.
- Khoảng cách người đi lại với đường TX-RX: **1-3 mét**.
- Ghi chú tên file: `An_BPM16_Noise_Moving_*.csv`.

### Nhiễu B: Quạt / Gió (Fan Interference)
- Bật quạt để tạo dao động không khí trong phòng.
- Quạt không thổi thẳng vào người đo, nhưng thổi qua **gần đường TX–RX**.
- Ghi chú tên file: `An_BPM16_Noise_Fan_*.csv`.

### Nhiễu C: Thiết bị WiFi khác (RF Interference)
- Bật hotspot điện thoại trên **cùng channel 6**.
- Ghi chú tên file: `An_BPM16_Noise_RF_*.csv`.

## Cách ghi bổ sung tên file
Vì file sẽ tự đặt tên theo `SUBJECT_NAME` và BPM, bạn hãy **đổi tên file thủ công**
sau khi thu xong để ghi rõ loại nhiễu:

```
An_BPM16_20240320_094000.csv  →  An_BPM16_Noise_Moving_20240320.csv
```

## Số mẫu tối thiểu
- **1 file** cho mỗi loại nhiễu.

## Kỳ vọng
- Thuật toán vẫn ước lượng đúng BPM trong điều kiện nhiễu nhẹ (sai số < ±3 BPM).
- Nếu sai số lớn hơn, cần điều chỉnh tham số `window_size` của Hampel Filter.
