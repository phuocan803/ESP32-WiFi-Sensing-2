# Danh sách Kịch bản Thu thập Dữ liệu

Mỗi kịch bản có file hướng dẫn riêng trong thư mục này.

| File | Kịch bản | BPM mục tiêu | Mẫu tối thiểu |
|:---|:---|:---|:---|
| [01_normal_breathing.md](./01_normal_breathing.md) | Thở bình thường | 12–18 | 5 file |
| [02_slow_breathing.md](./02_slow_breathing.md) | Thở chậm / sâu | < 10 | 2 file |
| [03_fast_breathing.md](./03_fast_breathing.md) | Thở nhanh | > 25 | 2 file |
| [04_apnea.md](./04_apnea.md) | Ngưng thở (Apnea) | ~ 0 | 2 file |
| [05_noisy_environment.md](./05_noisy_environment.md) | Có nhiễu môi trường | bất kỳ | 3 file |

## Thứ tự thu thập khuyến nghị

1. **Bình thường** trước → để làm quen với hệ thống.
2. **Ngưng thở** → dữ liệu tương phản mạnh, dễ kiểm chứng.
3. **Chậm và Nhanh** → mở rộng dải BPM cho model.
4. **Nhiễu** → cuối cùng, sau khi đã có đủ dữ liệu sạch.

## Cách đặt tên file chuẩn

```
[TenNguoi]_BPM[XX]_[YYYYMMDD]_[HHMMSS].csv
```

Ví dụ:
```
An_BPM16_20240320_090000.csv
Huy_BPM8_20240320_091000.csv
An_BPM0_20240320_093000.csv
```

## Tổng số mẫu cần thu tối thiểu: **14 file**
