# Kịch bản 3: Thở Nhanh (Fast Breathing / Tachypnea)

## Mục tiêu
Thu tín hiệu khi nhịp thở cao, kiểm tra giới hạn trên của thuật toán
(Band-pass filter tối đa 0.5 Hz = 30 BPM).

## Cấu hình `collect_data.py`
```python
SUBJECT_NAME     = "TenNguoi"
BPM_GROUND_TRUTH = "26"   # Điều chỉnh sau khi đếm thực tế
```

## Hướng dẫn thực hiện

### Cách A: Vận động nhẹ (Tự nhiên hơn)
1. Người đo đứng dậy và **đi bộ nhanh tại chỗ 2 phút**.
2. Ngay khi vừa ngồi xuống, **bắt đầu chạy script ngay lập tức**.
3. Thu liên tục **90 giây** (nhịp thở sẽ giảm dần về cuối – đây là dữ liệu thú vị).

### Cách B: Chủ động thở nhanh (Kiểm soát được hơn)
1. Người đo thở theo nhịp đếm: **hít 1 giây, thở ra 1 giây**.
2. Duy trì nhịp 25-30 BPM trong **60 giây đầu** sau khi chạy script.

> **Cảnh báo**: Đừng ép người đo thở quá nhanh liên tục, có thể gây chóng mặt.
> Nên dừng nếu cảm thấy khó chịu.

## Tên file output mẫu
```
An_BPM26_20240320_092000.csv
```

## Số mẫu tối thiểu
- **2 file**.
