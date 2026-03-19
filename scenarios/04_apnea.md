# Kịch bản 4: Ngưng Thở (Apnea / Breath Hold)

## Mục tiêu
Thu tín hiệu khi ngưng thở trong thời gian ngắn.
Đây là kịch bản **quan trọng nhất cho tính năng cảnh báo** (alert khi ngưng thở).

## Cấu hình `collect_data.py`
```python
SUBJECT_NAME     = "TenNguoi"
BPM_GROUND_TRUTH = "0"   # Apnea = 0 BPM
```

## Hướng dẫn thực hiện
Mỗi session có cấu trúc xen kẽ:

```
[0–20s]   Thở đều bình thường     → baseline
[20–40s]  Nín thở                 → apnea event
[40–60s]  Thở đều bình thường     → recovery
[60–80s]  Nín thở                 → apnea event
[80–120s] Thở đều bình thường     → recovery
```

### Các bước thực hiện
1. Chạy script `collect_data.py`.
2. Nói với người đo: **"Thở đều đi"** (0-20 giây đầu).
3. Ra hiệu: **"Nín thở đi"** vào giây thứ 20.
4. Ra hiệu: **"Thở bình thường lại"** vào giây thứ 40.
5. Lặp lại từ bước 3 theo timeline ở trên.

> **Lưu ý**: Không ép nín thở quá 30 giây. Nếu người đo không thoải mái, dừng ngay.

## Tên file output mẫu
```
An_BPM0_20240320_093000.csv
```

## Giá trị khi phân tích
File này sẽ có **2 vùng BPM gần 0** và **2 vùng BPM bình thường** xen kẽ nhau.
Dùng để test tính năng phát hiện Apnea trong thời gian thực.

## Số mẫu tối thiểu
- **2 file**.
