# Kịch bản 1: Thở Bình Thường (Normal Breathing)

## Mục tiêu
Thu thập tín hiệu CSI khi người đo ngồi yên, thở đều ở nhịp sinh lý bình thường.
Đây là kịch bản **quan trọng nhất** và phải thu nhiều nhất.

## Cấu hình `collect_data.py`
```python
SUBJECT_NAME     = "TenNguoi"
BPM_GROUND_TRUTH = "16"   # Đếm tay 1 phút trước khi chạy rồi điền vào
```

## Hướng dẫn thực hiện
1. Người đo ngồi **thẳng lưng**, tay đặt lên đùi, mắt nhắm hoặc nhìn thẳng.
2. Thở **tự nhiên, không cố ý điều chỉnh** nhịp.
3. Người đo thứ hai dùng đồng hồ đếm số lần ngực phồng lên trong **60 giây**.
4. Điền số đó vào `BPM_GROUND_TRUTH`, sau đó chạy script.
5. Thu liên tục **120 giây**.

## Yêu cầu môi trường
- Phòng yên tĩnh, không có người đi lại.
- Không có quạt/máy lạnh thổi thẳng vào đường truyền TX–RX.
- Người đo **không nói chuyện hay cử động tay** trong lúc đo.

## Tên file output mẫu
```
An_BPM15_20240320_090000.csv
```

## Số mẫu tối thiểu
- **5 file** × người khác nhau (hoặc session khác nhau).
