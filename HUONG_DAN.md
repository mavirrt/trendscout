# TrendScout Mỹ — hướng dẫn nhanh

## Chạy
Nhấp đúp `run.bat`: tool thu thập dữ liệu (khoảng 3–4 phút) rồi tự mở `dashboard.html`.
Nên chạy mỗi ngày một lần để có cột so sánh (▲, MỚI).

## Dashboard
- **Tổng quan**: mỗi lĩnh vực một thẻ, mỗi thẻ có top 5 trend. Bấm vào thẻ để xem chi tiết.
- **Theo lĩnh vực**: Game · Thể thao · Ca sĩ & âm nhạc · Idol & người nổi tiếng · Phim · TV/series/anime · Công nghệ & app · Sách & podcast · Thời sự.
  Mỗi trend có **điểm 0–100**, gộp từ 3 tín hiệu:
  - 📖 Wikipedia: lượt xem bài viết hôm qua, so với 7 ngày trước (MỚI = tuần trước chưa vào top)
  - 📊 Bảng xếp hạng: thứ hạng trên các bảng xếp hạng chính thức
  - 📰 Tin: số bài báo trong 3 ngày qua nhắc tới
- **Sản phẩm & ngách**, **Chủ đề người tiêu dùng**, **Mạng xã hội**, **Tất cả tín hiệu**: giữ như bản trước.

## Nguồn theo lĩnh vực (đều miễn phí, không cần key)
| Lĩnh vực | Nguồn |
|---|---|
| Game | SteamCharts (số người chơi cùng lúc), SteamSpy (hot 2 tuần), IGN, Google News |
| Thể thao | Wikipedia (cầu thủ, đội bóng, giải đấu), Google News (NFL, NBA, MLB, NHL, UFC, F1...) |
| Âm nhạc | Billboard Hot 100, Apple Music top bài hát Mỹ, tin Billboard, Google News |
| Idol & người nổi tiếng | Wikipedia (diễn viên, influencer...), Soompi (K-pop), Google News |
| Phim | Box Office Mojo (phòng vé Mỹ cuối tuần), iTunes top phim, Variety, Google News |
| TV / series / anime | iTunes top mùa phim, Wikipedia, Google News (Netflix, HBO, anime...) |
| Công nghệ & app | App Store top app miễn phí, Wikipedia, Google News |
| Sách & podcast | Apple Books, Apple Podcasts |
| Thời sự | Wikipedia, Google News |

Lưu ý: Wikipedia ở đây là bản tiếng Anh, người đọc phần lớn ở Mỹ nhưng không phải chỉ người Mỹ. Steam là số liệu toàn cầu.
Trang Steam chính thức bị chặn tại Việt Nam, nên tool lấy số liệu qua SteamCharts/SteamSpy.

## Mùa lễ & sự kiện
Tool tự tính lịch lễ hội Mỹ (Halloween, Day of the Dead, Thanksgiving, Black Friday, Cyber Monday, Christmas, Valentine, Super Bowl, Mother's Day...). Các dịp trong vòng 70 ngày tới được quét tin tức và mạng xã hội riêng.

## Mạng xã hội
- **Bluesky** (giống X/Twitter, phần lớn người dùng ở Mỹ): chủ đề trending và bài viết có nhiều tương tác theo từng lĩnh vực. Miễn phí, tự động.
- **YouTube**: video đăng trong tuần khớp từ khoá từng lĩnh vực, kèm lượt xem. Miễn phí, tự động.
- **TikTok / Facebook**: Claude quét bằng trình duyệt (TikTok Creative Center, Meta Ad Library). TikTok One đã đăng nhập trong trình duyệt tích hợp của app Claude, nên quét được top 100 hashtag và top theo ngành. Muốn cập nhật thì nhắn Claude "quét lại TikTok/FB".

## Gợi ý sản phẩm
Tab "💡 Gợi ý sản phẩm" gồm 2 phần:
- Ý tưởng đã research kèm link sản phẩm thật, đọc từ `data/research/*.json` (file mới nhất).
- Gợi ý tự động từ trend mỗi ngày, kèm link tìm kiếm Amazon, Etsy, Walmart, AliExpress.

Lưu ý IP: không in tên, hình nhân vật hay logo khi chưa có license.

## Gửi dashboard cho người khác
File `dashboard.html` đã chặn bôi đen, chuột phải, Ctrl+C / Ctrl+S / Ctrl+U / Ctrl+P và in. Dữ liệu trong file được mã hoá nên mở mã nguồn cũng không đọc thẳng được.
Đây chỉ là lớp chống copy thông thường: người rành kỹ thuật vẫn có thể chụp màn hình hoặc giải mã. Thông tin thật sự nhạy cảm thì đừng gửi file.

## Tuỳ chỉnh
- `config.json`: ngách sản phẩm (`niches`), truy vấn người tiêu dùng (`buzz_queries`).
- `domains.py`: muốn thêm/bớt lĩnh vực hoặc từ khoá tin tức thì sửa mục `DOMAINS`.
