# Economic Outlook Lab

Trang web tĩnh tổng hợp chỉ số kinh tế và đưa ra **dự báo xác suất** ngắn, trung và dài hạn cho kinh tế toàn cầu và các thị trường: crypto, vàng, chứng khoán Mỹ/Nhật/Việt Nam, dầu & hàng hóa, ngoại hối & trái phiếu.

- Dữ liệu được lấy tự động bằng GitHub Actions và hiển thị trên GitHub Pages.
- Nhận định trên site sinh tất định từ bộ quy tắc, **không dùng LLM**.
- **Không phải lời khuyên đầu tư.**

> Trạng thái: **P0 (bootstrap & kiểm chứng)**. Kế hoạch đầy đủ ở [docs/PLAN.md](docs/PLAN.md).

## Bắt đầu nhanh (Windows)
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env      # điền API key miễn phí (FRED, EIA, CoinGecko)
python econ.py doctor        # kiểm tra môi trường
python econ.py src check     # kiểm tra từng nguồn dữ liệu
python -m pytest             # chạy test
```

## Lệnh chính (P0)
| Lệnh | Việc |
|---|---|
| `python econ.py doctor` | Sức khỏe môi trường: Python, thư viện, encoding, git, hook, key |
| `python econ.py status` | Brief ≤20 dòng (giống nội dung hook SessionStart in ra) |
| `python econ.py src list` / `src check [--write]` | Danh sách nguồn / kiểm tra truy cập và định dạng |
| `python econ.py probe enable\|report\|disable` | Kiểm chứng tính năng Claude Code. Chạy `/econ-probe` trong một phiên mới |

## Ghi chú
- Máy công ty có TLS inspection và web filter. Việc lấy dữ liệu chính chạy trên GitHub Actions; máy local chỉ để phát triển.
- Secret nằm trong `.env` (không commit) và GitHub Secrets. Không có key nào ở frontend.
- Dữ liệu thô lưu ở repo private `econ-data` (append-only, có vintage). Repo này chỉ chứa code, cấu hình và ledger dự báo.
