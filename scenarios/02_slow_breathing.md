# Kịch bản 2: Thở Chậm / Sâu (Deep Breathing)

## Mục tiêu
Thu tín hiệu khi người đo thở theo nhịp chậm, biên độ lớn (kiểu thiền định).
Kịch bản này kiểm tra khả năng nhận diện tần số thấp của thuật toán FFT.

## Cấu hình `collect_data.py`
```python
SUBJECT_NAME     = "TenNguoi"
BPM_GROUND_TRUTH = "8"   # Ước tính 8 nhịp/phút
```

## Hướng dẫn thực hiện
1. Người đo ngồi tư thế thoải mái.
2. Hít vào **4 giây** → nín **1 giây** → thở ra **4 giây**. Lặp lại.
   - Chu kỳ = 4+1+4 = ~9 giây → ~6-7 BPM.
3. Luyện tập nhịp này **30 giây** trước khi bắt đầu ghi dữ liệu.
4. Chạy script và duy trì nhịp thở đều trong **120 giây**.

## Cách tính BPM Ground Truth
> Đếm số lần thở hoàn chỉnh (hít + thở ra) trong 60 giây.
> Ví dụ: 7 lần → `BPM_GROUND_TRUTH = "7"`

## Tên file output mẫu
```
An_BPM7_20240320_091000.csv
```

## Số mẫu tối thiểu
- **2 file** (có thể cùng người, khác session).
