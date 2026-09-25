# CLAUDE.md — PathMind (bản tùy biến)

PathMind là bản đổi tên + tùy biến của DeepTutor (HKUDS, Apache-2.0 — xem `LICENSE`,
`THIRD_PARTY_NOTICES.md`). File này tóm tắt **những gì đã làm thêm**, trạng thái từng chức năng
và các quy ước cần nhớ khi sửa code. Kiến trúc lõi (Tools / Capabilities / ChatOrchestrator / StreamBus)
nằm trong `pathmind/`.

> Cập nhật lần cuối: 2026-09-24 — Đổi tên DeepTutor → PathMind, dọn file thừa, Subscription, tín dụng theo giá model, dọn tính năng thừa, hoàn thiện Bạn bè / Chia sẻ Partner / Phòng học, gói cước mở khoá model.

---

## 1. Tổng quan trạng thái

| Mảng chức năng | Trạng thái | Ghi chú ngắn |
| --- | --- | --- |
| Đăng ký / đăng nhập nhiều người dùng | ✅ Xong | `/register` mở cho mọi người, người đầu tiên thành admin |
| Gói cước + hạn mức **tín dụng** theo giá model | ✅ Xong | Trừ theo từng lần gọi LLM (`services/llm/metrics.py`), chặn trước lượt trong `ChatOrchestrator` |
| Bảng giá API model + báo cáo chi phí/lãi gộp | ✅ Xong | `/admin/plans` (bảng giá), `/admin/payments` (chi phí theo model) |
| Thanh toán (checkout → xác nhận → kích hoạt) | ✅ Xong | VietQR chuyển khoản + admin xác nhận / webhook HMAC / demo |
| Vòng đời subscription (hết hạn, gia hạn, huỷ gia hạn) | ✅ Xong | Tự hết hạn khi đọc; gia hạn cộng dồn |
| Trang Bảng giá `/pricing` (user) | ✅ Xong | Xem cả khi chưa đăng nhập |
| Admin: gói cước `/admin/plans` | ✅ Xong | CRUD gói, sửa giá/hạn mức/model/tính năng |
| Admin: người dùng `/admin/users` | ✅ Xong | Xem gói thật, cấp gói có thời hạn, huỷ gói |
| Admin: thanh toán `/admin/payments` | ✅ Xong | Xác nhận / từ chối / hoàn tiền, doanh thu |
| Hồ sơ `/profile` hiển thị gói & usage | ✅ Xong | |
| Hạn mức **dung lượng lưu trữ** | ✅ Xong | Kiểm tra cả lô khi upload KB, trả lại dung lượng khi xoá tệp/KB |
| Giới hạn tệp đính kèm chat theo gói | ✅ Xong | `get_chat_attachment_limits` lấy min(system.json, gói) |
| Cổng Stripe / Crypto thật | ⚠️ Chỉ demo | Chỉ hiện khi `BILLING_DEMO_MODE=true` |
| Bạn bè (friends) | ✅ Xong | Tìm theo tên đăng nhập/email, mời ngược tự chấp nhận, chặn/bỏ chặn, huỷ lời mời |
| Chia sẻ Partner cho bạn bè | ✅ Xong | Chỉ chủ Partner, chỉ cho bạn bè; người nhận được **dùng** (chat), gỡ được |
| Phòng học chung (study rooms) | ✅ Xong (bản đơn giản) | Mã 6 ký tự, vào/rời/đóng/mời ra; thành viên được dùng Partner của phòng. Chưa có hội thoại chung realtime |
| Chống spam đăng ký | ✅ Xong | Tối đa `REGISTER_MAX_PER_IP_PER_HOUR` (mặc định 5) tài khoản/IP/giờ |

Chú thích: ✅ hoàn thiện · 🟡 chạy được nhưng chưa đầy đủ · ⚠️ chưa làm / chỉ demo.

---

### Knowledge Center: phân quyền admin / người dùng (2026-09-25)
- Người dùng thường **vẫn dùng Knowledge Center**: tạo KB, upload (tính vào hạn mức dung lượng của gói), thư mục/xoá file, KB mặc định, reindex, nguồn GitHub/web/EduHub, chọn KB trong chat.
- **Chỉ admin** (`_ADMIN_ONLY = [Depends(require_admin)]` trong `api/routers/knowledge.py`): mọi `PUT /knowledge-bases/rag-pipelines/*/config`, `rag-pipelines/active-model` (trước đây user thường ghi được vào catalog model của admin!), `rag-providers/{p}/mode`; các chức năng đọc thư mục **trên máy chủ** (`connect-folder`, `probe-folder`, `connect-obsidian`, `connect-marginnote4`, `{kb}/link-folder`, `{kb}/sync-folder/*`) và nối máy chủ/tài khoản ngoài (`probe|connect-lightrag-server`, `list|probe|connect-ima`, WeKnora). Muốn giới hạn thư mục admin được nối: biến môi trường `PATHMIND_LINKED_FOLDER_ROOTS`.
- **Nội dung kéo từ GitHub/web tính vào hạn mức dung lượng** của gói: `sync-github` / `sync-web` đo kích thước `raw/` của KB trước–sau mỗi nguồn và ghi chênh lệch bằng `update_user_storage` (trang bị xoá khi đồng bộ ⇒ trả lại dung lượng). Hết dung lượng ⇒ từ chối đồng bộ (403, `billing.storage_full`). Kích thước một lần crawl không biết trước nên lần đồng bộ cuối có thể vượt nhẹ hạn mức; khi đó các lần upload/đồng bộ sau bị chặn đến khi xoá bớt. Xoá KB/tệp trả lại dung lượng như upload. Đồng bộ nền định kỳ của GitHub chỉ chạy cho kho của admin (không giới hạn).
- Nguồn web: chặn địa chỉ nội bộ ngay khi thêm (crawler vốn đã chặn từng lần chuyển hướng); user thường bị giới hạn `KB_WEB_SOURCE_MAX_PAGES` (mặc định 50) và `KB_WEB_SOURCE_MAX_DEPTH` (3). Nguồn GitHub phải đúng dạng `owner/repo`.
- Giao diện (`KnowledgePage` → `useKnowledgeAdminAccess`): user thường không thấy tab "Knowledge engines", modal tạo KB không có "Link existing" và không có engine LightRAG Server / WeKnora / IMA. Test: `tests/services/test_knowledge_admin_only.py`.

### Đổi thư mục C:\DeepTutor → C:\PathMind + ẩn Personalization (2026-09-25)
- Kho workspace (`data/**/.runtime/workspaces.sqlite3`, metadata `root`, binding cũ trong settings) lưu **đường dẫn tuyệt đối**. Sau khi đổi tên/chuyển thư mục cài đặt, chat báo "The selected workspace folder does not exist". `services/workspace/relocate.py` (`relocate_stale_path`) tự neo lại đường dẫn cũ vào `data/` hiện tại khi đường dẫn cũ không còn và vị trí tương ứng có thật; `catalog._catalog()` ghi lại hàng đã sửa. Áp dụng cả khi chuyển `data/` sang server khác.
- Learning Space: nhóm **Personalization** (Personas, Skills, MCP, CLI Apps, Memory) chỉ hiện cho **admin** khi bật đăng nhập (`components/common/AdminOnlyGuard.tsx`: `usePersonalizationAccess`, guard trong `SpaceMain` cho `/space/personas|skills|mcp|cli-apps` và `app/(utility)/memory/layout.tsx`). User thường vào URL trực tiếp ⇒ về `/space`. Chỉ ẩn giao diện; API backend không đổi, trí nhớ (memory) vẫn chạy ngầm.

### Model mặc định theo gói (2026-09-25)
- Cột mới `subscription_plans.default_model` (sửa ở `/admin/plans` → "Default model", phải nằm trong `allowed_models`). Người dùng **chưa tự chọn model** sẽ dùng model này; trống ⇒ model mặc định của deployment (Cài đặt → Models). Admin không bị ảnh hưởng.
- Gói **Free mặc định `deepseek-v4-flash`** (×1.9 tín dụng, catalog đang đặt tên `deepseek-flash` — khớp qua alias bảng giá) thay vì `gemini-3.6-flash` (×5.4): cùng hạn mức dùng được ~3 lần nhiều hơn (tạo đề Quiz ~38k tín dụng thay vì ~108k). Seed chỉ điền khi cột còn NULL; admin xoá trống thì lưu "" và không bị ghi đè.
- Áp dụng ở: `model_access.allowed_llm_options` (đánh dấu `active` cho ô chọn model), `request_preparer` (lượt không có `llm_selection`), và `orchestrator` giờ quy `llm_selection {profile_id, model_id}` ra tên model thật để kiểm tra gói/ước tính tín dụng đúng model đang dùng (trước đây luôn tính theo model mặc định của deployment).

### Tự xoá tài khoản (GDPR) + admin chỉ khoá/mở khoá (2026-09-25)
- **Chỉ chủ tài khoản được xoá**: Cài đặt → Profile → Delete account (nhập mật khẩu + gõ `DELETE`) ⇒ `POST /api/auth/account/delete` (sai mật khẩu tính vào khoá đăng nhập). Admin cuối cùng không tự xoá được (409). Xoá xong ⇒ về `/login?deleted=1`.
- **Admin không xoá được tài khoản** (đã bỏ `DELETE /api/auth/users/{username}`). Admin chỉ **khoá / mở khoá**: `PUT /api/auth/users/{username}/status {disabled}` (nút ổ khoá ở `/admin/users`, nhãn "Locked"). Khoá ⇒ giữ nguyên dữ liệu, đăng xuất mọi phiên ngay, thu hồi thiết bị, không đăng nhập được (403 `account_disabled` — chỉ báo khi mật khẩu đúng). Không tự khoá mình, không khoá admin đang hoạt động cuối cùng.
- Xoá thực hiện ở `services/account_deletion.py`: **xoá hẳn** bản ghi đăng nhập (tên, email, mật khẩu, avatar), toàn bộ `data/users/<id>/` (chat, ghi chú, sách, KB, partner, memory, file, key cá nhân), grant/thiết bị/secret MCP–CLI, bạn bè, chia sẻ partner, thành viên phòng (phòng do user làm chủ bị đóng), mã xác thực email. **Giữ lại** thanh toán + usage/chi phí (nghĩa vụ kế toán) nhưng dòng `users` bị ẩn danh (`deleted~<id8>~<ts>`, không email/tên, inactive). Gói trả phí đang chạy kết thúc ngay, không tự hoàn tiền.
- **Phiên cũ hết hiệu lực ngay**: `decode_token` kiểm tra tài khoản còn tồn tại, đúng id và không bị khoá (đọc lại `users.json` chỉ khi file đổi).

### Bảo mật API key & đăng nhập (2026-09-25)
- **Mã hoá API key khi lưu** (`services/secret_box.py`): mọi trường bí mật (`api_key`, `*token*`, `*secret*`, `extra_headers`…) trong `model_catalog.json` (cả catalog cá nhân) và `settings_draft.json` được lưu dạng `enc:v1:<Fernet>`. `ModelCatalogService` tự giải mã khi đọc/mã hoá khi ghi; file cũ dạng chữ thường được tự chuyển khi đọc lần đầu. Khoá: biến môi trường `PATHMIND_SECRETS_KEY` (khuyên dùng khi deploy), không có thì tự tạo `data/system/secrets.key`. **Mất/đổi khoá ⇒ không đọc được key** (vẫn giữ nguyên bản mã hoá trên đĩa, trả khoá cũ là dùng lại được) — nhớ sao lưu khoá riêng.
- **Đổi endpoint phải nhập lại key**: khi lưu cấu hình mà `base_url` đổi **host** (hoặc đổi `proxy`) và ô key vẫn là `***`, key cũ **không** được mang sang (bị xoá, ghi log cảnh báo) — tránh admin/kẻ chiếm admin trỏ connection sang server lạ để hứng key thật. Đổi path trên cùng host thì vẫn giữ key.
- **Khoá đăng nhập khi sai nhiều**: `POST /api/auth/login` — sai `LOGIN_MAX_FAILURES` (mặc định 5) lần trong `LOGIN_LOCK_MINUTES` (15) phút cho cùng IP+tài khoản ⇒ 429 `detail.code = "login_locked"`; một tài khoản bị sai 4× số đó từ nhiều IP cũng bị khoá. Chỉ tin `X-Forwarded-For` khi `PATHMIND_TRUST_PROXY=1`.

### Theme theo tài khoản (2026-09-25)
- Theme được lưu **theo từng tài khoản** (file `settings/interface.json` của chính user, đổi ở Cài đặt → Appearance → Apply, lưu qua `PUT /api/settings/ui`). localStorage `pathmind-theme` chỉ là **bản đệm** để `ThemeScript` tô đúng màu trước khi React tải.
- `GET /api/settings/ui` (public) giờ dùng `optional_auth` (`api/routers/auth.py`): có cookie đăng nhập ⇒ trả theme/ngôn ngữ **của user đó**; chưa đăng nhập ⇒ như cũ. Trước đây endpoint này luôn đọc cấu hình mặc định nên theme hiển thị lệch với tài khoản.
- **Theme mặc định** khi chưa đăng nhập và cho tài khoản mới chưa chọn theme: biến môi trường `PATHMIND_DEFAULT_THEME` (snow = "Default" | light | dark | glass; mặc định snow). Khách chưa đăng nhập luôn nhận theme này (không bao giờ thấy theme cá nhân của admin). Đăng xuất ⇒ xoá theme đệm trong trình duyệt và về theme mặc định. Không còn tự theo chế độ sáng/tối của hệ điều hành.
- `components/common/AccountThemeSync.tsx` (gắn trong `app/layout.tsx`): mỗi lần mở app, nếu đã đăng nhập thì lấy theme của tài khoản và áp dụng nếu khác bản đệm (đổi tài khoản trên cùng máy, hoặc đổi theme ở máy khác). `SettingsStore` khi tải cũng áp dụng theme của tài khoản để ô chọn theme luôn khớp với giao diện.

### Đăng ký chi tiết + xác thực email + sửa DB (2026-09-25)
- **Đăng ký** (`POST /api/auth/register`, model `SignupRequest`): họ tên (2–120), email (duy nhất, không phân biệt hoa thường), username tuỳ chọn (trống ⇒ dùng email), mật khẩu ≥ 8 ký tự có cả chữ và số (không trùng username/email), nhập lại mật khẩu, bắt buộc tick **Điều khoản** (`/terms`). Lỗi trả `detail = {code, field, message}` để form tô đỏ đúng ô. Đăng nhập được bằng username **hoặc** email.
- Thông tin hồ sơ (`full_name`, `email`, `email_verified`, `email_verified_at`) nằm trong kho định danh (`identity._profile_fields`, `update_profile`, `find_user_by_email`) và được sao sang bảng `users` (cột mới `full_name`, `email_verified`, `email_verified_at`).
- **Xác thực email** (`services/email_verification.py`, bảng `email_verifications`): mã 6 số, chỉ lưu HMAC, hết hạn 30 phút, tối đa 5 lần nhập sai, gửi lại cách nhau 60 giây. Endpoint công khai `POST /api/auth/email/verify {email, code}` và `POST /api/auth/email/resend {email}` (luôn trả ok, không lộ email có tồn tại hay không). Admin: `POST /api/auth/users/{username}/verify-email`; email do admin nhập khi tạo user được coi là đã xác thực.
  - **Chưa cấu hình SMTP** (`SMTP_HOST` trống): mã chỉ ghi vào log backend, tài khoản **không bị chặn** (chỉ ghi "chưa xác thực").
  - **Có SMTP**: user thường có email chưa xác thực bị chặn đăng nhập (403, `detail.code = "email_not_verified"`) → giao diện chuyển sang bước nhập mã. `EMAIL_VERIFICATION_REQUIRED=false` để không bao giờ chặn. Tài khoản cũ không có email không bị ảnh hưởng.
- Profile (Cài đặt → Profile) có thẻ **Thông tin tài khoản**: sửa họ tên (`PUT /api/auth/profile/details`), xem email + trạng thái, gửi/nhập mã xác thực. Trang admin Users hiện họ tên/email/trạng thái và nút "Mark verified"; ô tìm kiếm tìm cả họ tên/email.
- **Sửa DB khi khởi động** (`database/maintenance.py`, gọi từ `init_database()`): gộp dòng trùng rồi tạo unique index `uq_friendship_pair`, `uq_room_member`, `uq_partner_share_target`, `uq_usage_log_day` (usage trùng ngày được **cộng dồn**); đồng bộ bảng `users` với kho định danh (đúng id + username thật, email, họ tên, trạng thái khoá). Dòng "mồ côi" (không có tài khoản) **không bị xoá**: đổi tên thành `…~orphan~<id8>` và `is_active=False`. Chạy lại nhiều lần vẫn an toàn.
- **Hộp xác nhận**: không dùng `window.confirm()` (trình duyệt nhúng trả `false` ngay ⇒ nút "Delete chat" không làm gì). Dùng `await confirmAction(t("…?"))` từ `web/lib/confirm.ts`; `ConfirmHost` (gắn trong `app/layout.tsx`) hiển thị `ConfirmDialog`. `window.alert` ⇒ `notify` (toast).

### Tài khoản trong Cài đặt + đa ngôn ngữ cho gói cước (2026-09-24)
- Sidebar: chân sidebar chỉ còn **thẻ người dùng** (`components/auth/UserMenu.tsx`), bấm vào mở thẳng **Cài đặt → Profile**. **Đăng xuất** và **Admin** (chỉ admin) nằm ở cuối thanh điều hướng Cài đặt (`components/settings/SettingsNav.tsx`) và nút Sign out trên trang Profile.
- Sidebar không còn nhóm **More**: mọi tính năng (kể cả Co-Writer) luôn hiện; vẫn kéo-thả đổi thứ tự được. Đã bỏ chấm trạng thái phiên bản (`VersionBadge`).
- Đã bỏ trang **Cài đặt → About** (`/settings/about` chuyển về General). Ghi nguồn DeepTutor/Apache-2.0 nằm ở `README.md`, `LICENSE`, `THIRD_PARTY_NOTICES.md`.
- Hồ sơ chuyển vào **Cài đặt → Profile** (`/settings/profile`, `ProfileSettingsSection`); `/profile` tự chuyển hướng.
- **Cài đặt → Plans & billing** (`/settings/billing`, `BillingSettingsSection`): gói hiện tại, hạn mức, huỷ/bật lại gia hạn,
  lịch sử thanh toán; nút sang `/pricing` để mua/nâng cấp. Dùng chung `components/billing/SubscriptionOverview` + `PaymentHistory`.
  Hai trang này chỉ hiện khi bật đăng nhập (`authOnly` trong `settings-pages.ts`).
- Trang giá, thanh toán, hồ sơ và các trang admin gói/giao dịch/bảng giá dùng i18n (`t("English key")`, bản dịch trong
  `web/locales/{en,zh}/app.json`) — theo ngôn ngữ ở Cài đặt → General. Khoá "Plan" của gói cước dùng context: `t("Plan", { context: "billing" })`.
- Thông báo backend về gói/hạn mức/thanh toán dùng `pathmind.services.i18n.t("billing.*" | "admin.*")` theo ngôn ngữ giao diện của từng người dùng.
  Ghi chú lưu trong DB (`payments.note`) viết bằng tiếng Anh.

### Đổi tên sang PathMind (2026-09-24)
- Package Python `deeptutor` → `pathmind`; biến môi trường `DEEPTUTOR_*` → `PATHMIND_*`;
  mọi chữ "DeepTutor" trên giao diện/email/i18n → "PathMind"; logo/favicon/banner mới trong `web/public`.
- DB đổi tên `data/user/deeptutor.db` → `pathmind.db`. Cookie/localStorage đổi tiền tố ⇒ người dùng đăng nhập lại một lần.
- Giữ nguyên link tới dịch vụ/dự án gốc: EduHub (`eduhub.deeptutor.info`), trang About ghi nguồn DeepTutor.
- Kiểm tra cập nhật phiên bản (release của DeepTutor) **tắt mặc định** (`version_check_enabled=false`).
- Tiện ích đọc (read aloud, quiz, …) có danh sách built-in dự phòng khi chạy từ source không cài package.

### Dọn file không cần để chạy (2026-09-24)
Đã chuyển sang `C:\PathMind_removed\` (kèm `DeepTutor_source_backup.zip` là bản sao mã nguồn trước khi đổi):
tài liệu & README dịch, `assets/`, `docs-for-user/`, CONTRIBUTING/CODE_OF_CONDUCT/CITATION/AGENTS/SKILL;
Docker/compose, `.github/`, `packaging/`, `deeptutor_web/`; CLI `deeptutor_cli/`, pre-commit, import-linter,
script dev (`scripts/check_*`, `update.py`, …); toàn bộ test (`tests/`, `web/tests`, cấu hình Playwright/Vitest).

### Đã loại bỏ (2026-09-24)
- Trang Cài đặt **Attachments** (+ `PUT /api/settings/chat-attachments`): giới hạn tệp đính kèm giờ theo gói cước.
- Trang Cài đặt **Plans & Billing**: trùng `/pricing` và thẻ gói ở `/profile`.
- Trang Cài đặt **Usage statistics** (+ `GET /api/settings/usage`): thay bằng tín dụng/chi phí ở `/pricing` và `/admin/payments`.
- **Guardian & Learner profile**: trang Cài đặt, editor trong `/admin/users`, API `/api/multi-user/guardians…`,
  `/api/multi-user/learners/…`, `/api/auth/…/learner-profile`, `lib/guardian-api.ts`.
  Module `multi_user/guardians.py`, `learner_profile.py` và preset tài khoản `learner` (giới hạn tính năng học)
  vẫn giữ vì phần lõi còn dùng. `learner_profile` của **Mastery path** (hồ sơ học theo chủ đề) là tính năng khác, vẫn giữ.
- `web/contracts/generated/api.ts` + `openapi.json` còn mô tả các endpoint cũ → chạy `npm run contracts:generate` khi tiện.

## 2. Kiến trúc phần Subscription

### Hai kho dữ liệu người dùng (quan trọng!)
- **Kho định danh (nguồn sự thật):** `data/user/auth_users.json` qua
  `pathmind/services/auth.py` / `multi_user/identity.py`. Đăng nhập, mật khẩu,
  role (nằm trong JWT) đều ở đây. API: `/api/auth/users…`.
- **Database quan hệ (SQLAlchemy, mặc định SQLite `data/user/pathmind.db`,
  hoặc `DATABASE_URL`):** chỉ là *bản sao* để làm khoá ngoại cho subscription,
  payment, usage, friends… Dòng `users` được tạo **lười** bởi
  `quota_service.ensure_db_user()`.
- Quyết định phân quyền luôn dùng **role trong JWT** (truyền `role=` vào các hàm
  quota), không dùng `users.role` trong DB.
- User không có dòng trong DB ⇒ được tính là **gói Free** (không bao giờ được
  "không giới hạn").

### Tín dụng (credits) — cách tính hạn mức
- `services/model_pricing.py`: bảng giá `model_prices` (USD/1M token: vào, cache, ra) →
  chi phí thật của mỗi lần gọi → **tín dụng = chi phí / (BILLING_CREDIT_USD_PER_MTOK, mặc định $0.25) × 1M**.
  1 tín dụng ≈ 1 token của model rẻ nhất; Sonnet 4.6 ≈ ×22, Gemini 3.6 Flash ≈ ×5.4.
- Tra giá: bỏ tiền tố `models/…`, khớp id/alias, rồi id dài nhất là tiền tố (`…-preview`),
  không có thì dùng dòng `*` (giá an toàn, đắt). Provider `openai_codex` (tài khoản riêng của user) = 0.
- Trừ tín dụng: hook `_charge_current_user` trong `CallMeasurement.finish` → `quota_service.record_llm_call`
  (ghi `usage_logs.credits_used/cost_usd` và `usage_model_logs` theo model). Mọi đường gọi LLM có user context đều bị tính.
- Chặn trước lượt: `check_turn_allowed` = model có trong gói + còn đủ tín dụng cho **ước tính theo capability**
  (`CAPABILITY_TOKEN_ESTIMATE` × hệ số model), tránh một lượt deep_research vượt hạn mức lớn.
- Cột `max_tokens_per_day/month` của plan giờ mang nghĩa **tín dụng** (giữ tên cột để khỏi migrate).
- Hạn mức mặc định giữ chi phí API tối đa ≈ 55% giá bán: Free 1,5M/tháng (≈$0.38), Pro 22M (≈$5.50),
  Enterprise 66M (≈$16.50). Trang admin hiện badge "Chi phí API tối đa … % giá bán" cho từng gói.
- `init_db.seed_initial_data` tự chuyển các gói còn giữ nguyên số liệu bản đầu sang hạn mức/model mới
  (không đụng gói admin đã sửa) và thêm giá model còn thiếu.

### Bảng (xem `pathmind/database/models.py`)
- `subscription_plans` — giá tháng/năm, token/ngày, token/tháng, dung lượng,
  kích thước tệp, `allowed_models` (rỗng = không giới hạn), `features`,
  `description`, `sort_order`, `is_active`.
- `subscriptions` — `status`: `active | canceled | expired | replaced`;
  `current_period_end = NULL` nghĩa là không hết hạn (gói free / admin cấp vĩnh viễn);
  `cancel_at_period_end`, `billing_interval`, `source` (`register|payment|admin|user|system`).
- `payments` — luôn lưu `amount` theo **USD**, kèm `amount_vnd`;
  `status`: `pending | completed | failed | canceled | expired | refunded`;
  `transaction_id` = mã `DTXXXXXXXXXX` = **nội dung chuyển khoản**.
- `usage_logs` — theo ngày (UTC): token, `credits_used`, `cost_usd`, dung lượng hiện tại.
- `usage_model_logs` — chi tiết theo user/ngày/model (lượt gọi, token, cache, tín dụng, chi phí).
- `model_prices` — bảng giá API (admin sửa được).

### Luồng thanh toán
1. User `POST /api/billing/checkout` → tạo payment **pending** (không kích hoạt gì).
2. User chuyển khoản VietQR với nội dung = mã giao dịch (pending hết hạn sau 24h).
3. Payment chuyển `completed` bằng **một** trong ba cách:
   - `POST /api/billing/webhook` có header `X-Billing-Signature` = HMAC-SHA256(secret, raw body);
   - admin bấm xác nhận ở `/admin/payments`;
   - `POST /api/billing/payments/{tx}/simulate` (chỉ khi demo mode).
4. `quota_service.complete_payment()` → `activate_subscription()`:
   cùng gói còn hạn ⇒ cộng thêm 30/365 ngày; khác gói ⇒ gói cũ `replaced`, gói mới bắt đầu.

### Enforcement
- `runtime/orchestrator.py`: trước mỗi turn gọi `check_turn_allowed()` (model user chọn,
  hoặc model mặc định của deployment qua `default_llm_model_name()`). Lỗi DB ⇒ fail-open + `logger.warning`.
- So khớp model: khớp chính xác, bỏ tiền tố (`models/…`), chấp nhận hậu tố phiên bản
  (`-20241022`, `-preview`, `-latest`) hoặc alias trong bảng giá (`deepseek-chat` → `deepseek-v4-flash`);
  `gpt-4o` **không** mở `gpt-4o-mini`.
- **Gói = quyền dùng model.** `multi_user/model_access.redacted_model_access` gộp 3 nguồn:
  `plan` (model trong catalog admin khớp `allowed_models` của gói, qua `quota_service.plan_allows_model`),
  `admin` (grant gán tay) và `personal` (đăng nhập riêng). Vì thế gán/mua gói là mở khoá ngay
  danh sách model, cổng capability (hết "Feature locked") và kiểm tra `llm_selection` của Partner.
  Model chỉ hiện nếu **có trong catalog** (Settings → Models) — gói liệt kê model chưa cấu hình thì không có tác dụng.
  Profile owner-bound (Codex/CodeBuddy) không bao giờ mở qua gói.

---

## 3. API đã có

**User — `/api/billing`** (`api/routers/billing.py`)
| Method | Path | Mô tả |
| --- | --- | --- |
| GET | `/config` | Cổng thanh toán nào đang bật, demo mode, tỉ giá (public) |
| GET | `/plans` | Danh sách gói đang bán (public) |
| GET | `/model-rates` | Hệ số tín dụng từng model (public) |
| GET | `/summary` | Gói, subscription, usage của user |
| POST | `/checkout` | Tạo giao dịch pending `{plan_id, interval, gateway}` |
| GET | `/payments`, `/payments/{tx}` | Lịch sử / trạng thái giao dịch |
| POST | `/payments/{tx}/cancel` | Huỷ giao dịch pending |
| POST | `/payments/{tx}/simulate` | Demo: giả lập đã thanh toán |
| POST | `/cancel`, `/resume` | Tắt / bật lại gia hạn |
| POST | `/upgrade` | **Chỉ** chuyển về gói miễn phí (gói trả phí ⇒ 402) |
| POST | `/webhook` | Callback cổng thanh toán, bắt buộc chữ ký HMAC |

**Admin — `/api/admin`** (`api/routers/admin_dashboard.py`, cả router yêu cầu admin)
| Method | Path | Mô tả |
| --- | --- | --- |
| GET | `/stats` | Tổng user, user trả phí, phân bổ gói, token, doanh thu, pending |
| GET | `/users` | User (từ kho định danh) + gói + usage |
| PUT | `/users/{id}/plan` | Cấp gói `{plan_id, duration_days (0 = vĩnh viễn), interval}` |
| PUT | `/users/{id}/role` | Đổi role (ghi vào kho định danh) |
| POST | `/users/{id}/subscription/cancel` | Huỷ gói trả phí ngay |
| GET | `/users/{id}/subscriptions` | Lịch sử subscription |
| GET/POST | `/plans` | Liệt kê / tạo gói |
| PUT/DELETE | `/plans/{id}` | Sửa / xoá gói (gói đã dùng ⇒ 409, hãy "Ngừng bán") |
| PUT | `/plans/{id}/models` | Sửa danh sách model |
| GET | `/payments?status=` | Danh sách giao dịch |
| POST | `/payments/{tx}/confirm` · `/reject` · `/refund` | Xử lý giao dịch |
| GET | `/available-models` | Gợi ý model (từ bảng giá) |
| GET/POST | `/model-prices` | Bảng giá API model |
| PUT/DELETE | `/model-prices/{id}` | Sửa / xoá giá model (`*` không xoá được) |

**Bạn bè — `/api/friends`** (`api/routers/friends.py`): `GET /list`, `GET /pending` (nhận / đã gửi / đã chặn),
`POST /request {target}`, `POST /respond {request_id, action: accept|reject|block}`,
`DELETE /requests/{id}` (huỷ lời mời đã gửi hoặc bỏ chặn), `DELETE /{friend_user_id}` (huỷ kết bạn + gỡ chia sẻ giữa hai người).

**Xã hội — `/api/social`** (`api/routers/partner_shares.py`, trước đây nằm chung `/api/partners` và dễ trùng route):
`POST /partners/{id}/share`, `GET /partners/shared-with-me`, `GET /partners/{id}/shares`, `DELETE /shares/{id}`,
`POST /rooms`, `GET /rooms`, `GET /rooms/{code}`, `POST /rooms/{code}/join|leave`, `DELETE /rooms/{code}`,
`DELETE /rooms/{code}/members/{user_id}`.
Quyền dùng Partner: `multi_user/partner_access.assigned_partner_ids` = grant của admin ∪ `social_partner_ids`
(được chia sẻ + Partner của phòng đang tham gia). Chỉ cấp quyền **dùng**, không bao giờ cấp quyền quản lý.

---

## 4. Frontend (Next.js, thư mục `web/`)

| Route / file | Vai trò |
| --- | --- |
| `app/(settings)/pricing/page.tsx` | Bảng giá, usage, checkout VietQR, huỷ/bật gia hạn, lịch sử thanh toán |
| `app/(admin)/admin/plans/page.tsx` | Quản lý gói cước |
| `app/(admin)/admin/users/page.tsx` | Quản lý user + cấp gói |
| `app/(admin)/admin/payments/page.tsx` | Duyệt thanh toán |
| `components/admin/AdminTabs.tsx` | Thanh tab dùng chung cho các trang admin |
| `components/admin/ModelPriceTable.tsx` | Bảng giá API model (trong `/admin/plans`) |
| `components/partners/FriendsTab.tsx` | Tab Bạn bè: kết bạn, lời mời, chặn, Partner được chia sẻ, phòng học |
| `components/partners/SharePartnerModal.tsx` | Chia sẻ Partner cho bạn bè / mở phòng học (từ trang cấu hình Partner) |
| `lib/friends-api.ts` | Client `/api/friends` + `/api/social` |
| `app/(utility)/profile/page.tsx` | Thẻ "Gói cước & Hạn mức" |
| `lib/billing-api.ts` | Client API user + helper format (USD/VND/ngày) |
| `lib/admin-api.ts` | Client API admin |
| `lib/proxy-policy.ts` | `/pricing` được miễn đăng nhập |

---

## 5. Cấu hình

PathMind **bỏ qua file `.env` ở gốc dự án**. Các biến dưới đây
phải là **biến môi trường của tiến trình backend** (VD Windows:
`set BILLING_DEMO_MODE=true` trước khi chạy, hoặc thêm vào `start.bat`). Mẫu và giải thích có trong `.env.example`.

| Biến | Ý nghĩa |
| --- | --- |
| `BILLING_DEMO_MODE` | `true` = hiện cổng demo + nút "Mô phỏng thanh toán" (chỉ dùng khi demo) |
| `BILLING_WEBHOOK_SECRET` | Secret HMAC cho webhook; để trống = tắt webhook |
| `BILLING_USD_VND_RATE` | Tỉ giá hiển thị/QR (mặc định 25400) |
| `BILLING_CREDIT_USD_PER_MTOK` | Giá gốc của 1 tín dụng, USD/1M token (mặc định 0.25) |
| `BILLING_BANK_BIN`, `BILLING_BANK_NAME`, `BILLING_BANK_ACCOUNT_NO`, `BILLING_BANK_ACCOUNT_NAME` | Tài khoản nhận tiền để sinh mã VietQR |
| `DATABASE_URL` | Tuỳ chọn; mặc định SQLite trong `data/user/` |
| `REGISTER_MAX_PER_IP_PER_HOUR` | Số tài khoản tự đăng ký tối đa mỗi IP mỗi giờ (mặc định 5, 0 = tắt) |

Không có cổng nào được cấu hình ⇒ modal thanh toán báo "chưa cấu hình".

---

## 6. Việc còn tồn đọng (ưu tiên từ cao xuống)

1. **Cập nhật bảng giá model định kỳ** (`/admin/plans` → Bảng giá API). Gemini 3.6–3.8 Flash
   tăng giá gấp đôi từ 01/01/2027; model mặc định hiện là `gemini-3.6-flash` (×5.4) — cân nhắc
   đổi sang `gemini-3.1-flash-lite` (×2) hoặc `deepseek-v4-flash` (×1.9) để rẻ hơn.
2. **Phòng học realtime**: hiện mỗi thành viên chat riêng với Partner của phòng; muốn hội thoại chung
   cần nối phòng với `partner_groups`/WebSocket.
3. **Chống spam mạnh hơn**: throttle đăng ký lưu trong bộ nhớ (1 process); nên thêm captcha / xác thực email.
4. **Múi giờ**: hạn mức ngày reset theo 00:00 UTC (7h sáng giờ VN).
   Doanh thu tháng ghi nhận theo ngày thanh toán (gói năm chưa phân bổ 12 tháng).
5. **i18n**: chuỗi tiếng Việt đang hard-code trong các trang mới — `npm run i18n:check` có thể báo lỗi.
6. **Contracts**: chạy `npm run contracts:generate` để cập nhật `web/contracts` sau khi bỏ endpoint cũ.
7. Tích hợp cổng thật (PayOS/Casso/SePay → gọi `/api/billing/webhook` có ký HMAC; Stripe).

Chạy dev: `start.bat` / `stop.bat` ở thư mục gốc (log ở `logs\backend.log`, `logs\frontend.log`).

---

## 7. Quy ước khi sửa code

- Datetime trong DB là **UTC naive** — dùng `quota_service._utcnow()`.
- Thêm cột mới: khai báo `nullable=True` trong `models.py`; `init_database()` tự
  `ALTER TABLE ADD COLUMN` cho cột thiếu. Thay đổi phức tạp hơn ⇒ dùng Alembic.
- Mọi logic gói/usage đặt ở `services/quota_service.py`; router chỉ gọi lại.
- Không bao giờ kích hoạt gói trả phí ngoài `complete_payment()` hoặc admin cấp.
- Không tin `user_id`/`plan_id` từ client hay webhook — lấy từ payment trong DB.
- Frontend: dùng biến theme `var(--background)`, `var(--card)`, `var(--border)`…
  (không hard-code màu tối); **không dùng `window.confirm/alert/prompt`** — dùng
  `confirmAction()` (`lib/confirm.ts`) hoặc `ConfirmDialog`, và toast `notify`.
- Một số file frontend dùng **CRLF** (`admin/users/page.tsx`, `profile/page.tsx`,
  `lib/admin-api.ts`); giữ nguyên kiểu xuống dòng để diff sạch. File `.py` luôn LF.
- `lib/` không được import từ `app/`, `components/` (luật dependency-cruiser).

## 8. Kiểm thử

Bộ test không nằm trong repo: ở `C:\PathMind_removed\tests\tests` (đã đổi tên sang `pathmind`; có thêm
`multi_user/test_signup_flow.py`, `multi_user/test_account_deletion.py`, `services/test_security_hardening.py`,
`services/test_plan_default_model.py`). Script chạy toàn bộ `fulltest.bat` đã chuyển sang
`C:\PathMind_removed\cleanup_20260925\` — nó chép test vào `tests/`, đặt `DATABASE_URL` sang SQLite tạm
(để **không ghi vào DB thật**), chạy pytest (log `logs/pytest_full2.log`) rồi chuyển test về chỗ cũ.

Kết quả lần chạy 2026-09-25: **6004 pass / 113 fail / 66 skip**. Các lỗi còn lại đều do môi
trường, không phải do code: sandbox/bwrap/symlink/quyền "owner-only" chỉ chạy trên Linux/macOS;
test của phần đã gỡ (CLI `pathmind_cli`, Docker, `services/subagent`, kênh Telegram/Slack/Weixin
chưa cài thư viện); và test API trả 401 vì chạy trong thư mục dự án đang bật đăng nhập
(`data/user/settings/auth.json`).

```bash
# Frontend
cd web
npm run typecheck
npm run lint
npm run i18n:check
```

Kiểm tra tay nhanh: bật `BILLING_DEMO_MODE=true` → đăng ký user mới → `/pricing`
→ nâng cấp Pro → "Mô phỏng thanh toán" → xem gói ở `/profile` và
`/admin/users`, giao dịch ở `/admin/payments`.
