# HP Cons PDF

Công cụ xử lý PDF nội bộ cho team đấu thầu **HP Cons**. Chạy hoàn toàn offline, không cần internet.

**Tính năng:** chạy một phiên duy nhất — mở/kéo file PDF từ ngoài (double-click Explorer, kéo lên icon taskbar) vào cửa sổ đang chạy thành tab mới (muốn xem 2 màn hình thì kéo tab ra thành cửa sổ riêng) • xem PDF nhiều tab • **in tài liệu Ctrl+P** — MỘT hộp thoại duy nhất gồm: chọn máy in, khổ giấy, hướng (tự động/dọc/ngang), in 2 mặt, màu/đen trắng, số bản, phạm vi trang (tất cả / trang hiện tại / khoảng); nhớ máy in đã chọn; có nút "Thiết lập nâng cao" mở hộp thoại riêng của máy in cho tùy chọn đóng ghim/booklet. In kèm ghi chú/che trắng, hướng "tự động" sẽ xoay trang ngang cho vừa giấy • công cụ **Xem** thông minh: rê vào chữ hiện trỏ chọn — quét chọn & Ctrl+C copy chữ (như Foxit Phantom), kéo chỗ trống để di chuyển trang • ghép file • tách file (theo trang / mỗi trang / dung lượng) • xoay – xóa – chèn – trích xuất – sắp xếp trang (kéo-thả thumbnail, panel kéo rộng ra sẽ hiện nhiều cột) • **kéo-thả file PDF vào thanh thumbnail để gộp** — hiện hộp thoại chọn vị trí ghép (tại vị trí thả / đầu / cuối / trước trang số) • **copy/dán trang** (Ctrl+C / Ctrl+V trên thumbnail, dán được sang tab khác) • **chỉnh sửa nội dung gốc của file: bấm hoặc quét vùng chọn chữ/ảnh/hình có sẵn (tự bỏ qua ảnh nền) để di chuyển, xóa, sửa chữ** • ghi chú mới: thêm chữ, đánh dấu (highlight), vẽ hình • **Xóa vùng**: quét vùng là xóa ngay chữ/hình bên trong (Ctrl+Z hoàn tác) • **Che trắng**: quét vùng để phủ trắng đè lên (hợp file scan) • xoay trang nhanh Ctrl+Shift++ / Ctrl+Shift+- • **Hoàn tác Ctrl+Z** cho mọi thao tác chỉnh sửa; **ESC** quay về công cụ Xem • giao diện 1 hàng công cụ, điều khiển trang/zoom ở thanh dưới cùng • đánh số trang (6 vị trí, đánh số liên tục khi ghép) • watermark chữ & đóng dấu ảnh • OCR tạo PDF tìm kiếm được (Việt/Trung/Anh) • chuyển đổi PDF ↔ ảnh, PDF → text • nén PDF • đặt/gỡ mật khẩu.

Lưu file: **Lưu (Ctrl+S)** — lần đầu hỏi nơi lưu (không bao giờ ghi đè file gốc), các lần sau lưu thẳng vào file đã chọn; **Lưu thành... (Ctrl+Shift+S)** luôn tạo file mới. Ghi chú/hình vẽ và các chỉnh sửa nội dung gốc được ghi vĩnh viễn vào file khi lưu.

Giới hạn của chỉnh sửa nội dung gốc: (1) sửa chữ dùng font nhúng sẵn trong file — nếu font rút gọn thiếu ký tự (hay gặp với dấu tiếng Việt), ứng dụng tự hoàn tác và gợi ý xóa + "Thêm chữ" thay thế; (2) chỉ thao tác được trên trang không xoay; (3) chữ trong PDF thường tách thành từng dòng/cụm nhỏ — mỗi lần chọn là một cụm.

> **An toàn dữ liệu:** ứng dụng **không bao giờ ghi đè file gốc** — mọi thao tác đều xuất file mới (có hậu tố `_merged`, `_ocr`, `_compressed`...). File được ghi qua thư mục tạm rồi mới chuyển về đích để tránh xung đột với OneDrive.

---

## 1. Chạy từ mã nguồn

Yêu cầu: **Python 3.11 trở lên** (tải tại https://www.python.org/downloads/ — khi cài nhớ tick **"Add python.exe to PATH"**).

Mở PowerShell tại thư mục dự án và chạy:

```powershell
python -m pip install -r requirements.txt
python main.py
```

## 2. Cài Tesseract OCR (bắt buộc nếu dùng chức năng OCR)

Chức năng OCR cần phần mềm **Tesseract OCR** cài riêng trên máy (miễn phí, mã nguồn mở):

1. Tải bộ cài Tesseract cho Windows (bản của UB Mannheim, được cộng đồng khuyên dùng):
   https://github.com/UB-Mannheim/tesseract/wiki
   → tải file `tesseract-ocr-w64-setup-xxx.exe` mới nhất.
2. Chạy bộ cài. Ở bước **"Choose components"**, mở mục **"Additional language data (download)"** và tick chọn:
   - **Vietnamese** (`vie`)
   - **Chinese (Simplified)** (`chi_sim`)
   - **Chinese (Traditional)** (`chi_tra`)
   - English (`eng`) đã có sẵn.
3. Cài vào vị trí mặc định `C:\Program Files\Tesseract-OCR\` — ứng dụng sẽ tự tìm thấy.

### Cài thêm gói ngôn ngữ sau khi đã cài Tesseract

Nếu lúc cài quên chọn ngôn ngữ, tải file `.traineddata` rồi chép vào thư mục `tessdata`:

1. Tải tại https://github.com/tesseract-ocr/tessdata (bấm vào file → nút **Download raw file**):
   `vie.traineddata`, `chi_sim.traineddata`, `chi_tra.traineddata`
2. Chép các file này vào: `C:\Program Files\Tesseract-OCR\tessdata\`

### Nếu ứng dụng không tìm thấy Tesseract

Mở hộp thoại **OCR** trong ứng dụng → bấm **"Chọn tesseract.exe..."** → trỏ tới file `tesseract.exe` (thường ở `C:\Program Files\Tesseract-OCR\tesseract.exe`). Đường dẫn được ghi nhớ cho các lần sau.

## 3. Đóng gói

### 3a. File cài đặt để gửi cho team (khuyên dùng)

Chạy file **`build_installer.bat`** (cần cài sẵn [Inno Setup](https://jrsoftware.org/isdl.php)).
Kết quả: **`Output\HPConsPDF_Setup_1.0.0.exe`** — gửi file này cho các máy trong team.

Người nhận chỉ cần chạy, bấm Next → Install là xong:
- Cài **theo từng người dùng** (`%LocalAppData%\Programs\HP Cons PDF`) — **không cần quyền Administrator**, hợp với máy công ty bị hạn chế quyền.
- Tự tạo shortcut ngoài **Desktop** và trong **Start Menu**, gỡ được qua Control Panel (Apps).
- **Không cần cài Python**.
- **Liên kết file PDF** (mục chọn khi cài):
  - *"Cho phép mở file PDF bằng HP Cons PDF"* (tick sẵn) — thêm HP Cons PDF vào menu chuột phải **Open with**, và đăng ký vào Windows Settings → Default apps (không đụng tới trình đọc PDF hiện tại của máy).
  - *"Đặt HP Cons PDF làm ứng dụng mở PDF mặc định"* (không tick sẵn) — cố đặt mặc định. Lưu ý: Windows 10/11 bảo vệ lựa chọn mặc định để chống phần mềm tự chiếm quyền, nên nếu máy đã đặt Edge/CocCoc... thì Windows có thể vẫn hỏi xác nhận. **Cách chắc chắn nhất:** chuột phải một file PDF → *Open with* → *Choose another app* → chọn **HP Cons PDF** → tick *Always use this app*.

> Muốn đổi số phiên bản: sửa `#define AppVersion` trong `installer.iss` (và `APP_VERSION` trong `hpcons_pdf/__init__.py`).

### 3b. File .exe chạy trực tiếp (không cần cài)

Chạy file `build.bat` để tạo `dist\HPConsPDF.exe` (bản onefile, chép đâu chạy đó).

> Lưu ý chung: chức năng OCR vẫn cần cài Tesseract riêng (xem mục 2) trên máy dùng.

> Icon ứng dụng: `logo.png` (nền trong suốt) và `logo.ico` được tạo từ logo "HP PDF". Nếu đổi logo mới (ví dụ `new logo.jpg`), tạo lại bằng:
> ```powershell
> python -c "from PIL import Image; im=Image.open('new logo.jpg').convert('RGBA'); px=im.load(); w,h=im.size; [px.__setitem__((x,y),(px[x,y][0],px[x,y][1],px[x,y][2],0)) for y in range(h) for x in range(w) if max(px[x,y][:3])<60]; im=im.crop(im.getbbox()); im.save('logo.png'); im.save('logo.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
> ```
> (lệnh trên bỏ nền tối ở 4 góc thành trong suốt rồi xuất `logo.png` + `logo.ico`)

## 3c. Tự động cập nhật (auto-update)

App tự kiểm tra phiên bản mới trên **GitHub Releases** khi khởi động (chạy ngầm, offline thì bỏ qua). Có bản mới → hiện thông báo cho tải & cài (app tự đóng, cập nhật, mở lại). Có thể tắt tự kiểm tra trong menu **Trợ giúp → Tự động kiểm tra cập nhật**, hoặc kiểm thủ công qua **Trợ giúp → Kiểm tra cập nhật...**

**Thiết lập lần đầu (một lần):**
1. Sửa 2 dòng trong [hpcons_pdf/core/updater.py](hpcons_pdf/core/updater.py): `GITHUB_OWNER` và `GITHUB_REPO` cho khớp repo GitHub **public** của công ty.
2. Đưa mã nguồn lên GitHub (xem mục 3d).

**Phát hành phiên bản mới:**
```powershell
release.bat 1.0.2
```
Lệnh này đặt version = 1.0.2 (đồng bộ `__init__.py` + `installer.iss`), commit, tạo tag `v1.0.2`, push lên GitHub. **GitHub Actions** ([.github/workflows/release.yml](.github/workflows/release.yml)) tự build installer trên máy ảo Windows và đăng vào **Releases**. Các máy đang chạy app cũ sẽ nhận được thông báo cập nhật.

## 3d. Đưa mã nguồn lên GitHub (một lần)

```powershell
git init
git add .
git commit -m "HP Cons PDF - ban dau"
git branch -M main
git remote add origin https://github.com/<GITHUB_OWNER>/<GITHUB_REPO>.git
git push -u origin main
```
> Tạo repo trống (public) trên GitHub trước, đặt tên khớp với `GITHUB_OWNER`/`GITHUB_REPO` đã điền ở updater.py. Repo để **public** thì app tải bản cập nhật không cần token.

## 4. Chạy test hồi quy

```powershell
python tests/test_core_regression.py   # lỗi dải đen ICC, trang xoay, ưu tiên chọn chữ
python tests/test_gui_tools.py         # Ctrl+click chọn dồn, quét chữ gạch chân, chọn nhiều trang
python tests/test_updater.py           # so sánh version, đọc Release API, tải file
python tests/test_update_gui.py        # luồng auto-update trong app (skip/offer)
python tests/test_drop_merge.py        # thả file gộp vào thanh trang / mở tab
python tests/test_single_instance.py   # một phiên duy nhất, mở file vào cửa sổ đang chạy
```
(còn `test_windows.py`, `test_print.py`, `test_drag_reorder.py`, `test_multiselect.py`, `test_batch4/6/8.py`, `test_toggle_arrow.py`, `test_view_nav.py`.)

## 5. Cấu trúc mã nguồn

```
main.py                  # điểm khởi chạy
logo.jpg / logo.ico      # logo công ty (icon app + toolbar)
hpcons_pdf/
├── config.py            # cấu hình người dùng → %APPDATA%\HPConsPDF\config.json
├── resources.py         # đường dẫn tài nguyên (tương thích PyInstaller)
├── core/                # lõi xử lý PDF (không phụ thuộc giao diện)
│   ├── document.py      # model tài liệu: render (pypdfium2), xoay/xóa/chèn/sắp xếp, lưu (pikepdf)
│   ├── operations.py    # ghép, tách (khoảng trang / mỗi trang / dung lượng)
│   ├── overlay.py       # đánh số trang, watermark chữ, đóng dấu ảnh (reportlab + pypdf)
│   ├── annotations.py   # ghi chú/chỉnh sửa: chữ, highlight, hình vẽ + nướng vào PDF
│   ├── ocr.py           # OCR → PDF searchable (pytesseract)
│   ├── convert.py       # PDF ↔ ảnh, PDF → text
│   ├── compress.py      # nén (downsample ảnh trong PDF)
│   ├── security.py      # đặt/gỡ mật khẩu, quyền (AES-256)
│   └── worker.py        # QThread cho thao tác nặng (có nút Hủy)
├── ui/                  # giao diện PyQt6
│   ├── main_window.py   # cửa sổ chính, toolbar, menu, tab
│   ├── pdf_view.py      # khung xem: cuộn liên tục, zoom, fit, highlight tìm kiếm
│   ├── thumbnail_panel.py  # thumbnail kéo-thả sắp xếp trang
│   ├── document_tab.py  # ghép thumbnail + khung xem + tìm kiếm
│   ├── render_thread.py # luồng render nền
│   ├── theme.py         # bảng màu thương hiệu (#4A4F54, #5FBF2D, #1B75BB)
│   ├── icons.py         # bộ icon phẳng vẽ bằng font hệ thống
│   └── dialogs/         # các hộp thoại chức năng
└── utils/
    ├── fileutils.py     # lưu qua thư mục tạm, chống ghi đè, phân tích khoảng trang
    └── errors.py        # chuyển lỗi kỹ thuật → thông báo tiếng Việt
```

## 6. Thư viện sử dụng & giấy phép

| Thư viện | Vai trò | Giấy phép |
|---|---|---|
| PyQt6 | Giao diện | GPL/Thương mại — dùng nội bộ, không phân phối ra ngoài |
| pypdfium2 | Render trang PDF | Apache-2.0 / BSD-3-Clause |
| pikepdf | Ghép/tách/nén/mã hóa | MPL-2.0 |
| pypdf | Trộn lớp phủ (overlay) | BSD |
| reportlab | Vẽ số trang/watermark (vector) | BSD |
| pytesseract | Gọi Tesseract OCR | Apache-2.0 |
| Pillow | Xử lý ảnh | MIT-CMU |

Không dùng PyMuPDF/Ghostscript (AGPL/GPL) theo yêu cầu.
