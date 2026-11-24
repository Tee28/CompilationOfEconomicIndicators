# Kế hoạch v2: Economic Outlook Lab — web dự báo kinh tế & thị trường + tổ chức agent Claude Code

> **TRẠNG THÁI 2026-11-24: v2, đã sửa theo kết quả rà soát (xem Phụ lục A). Đang chờ bạn duyệt.** Repo vẫn trống.
> - Bước kế tiếp: bạn duyệt → làm P0 (mục 15). Các bước tác động ra ngoài (tạo repo GitHub, đặt secrets, bật Pages) đều hỏi bạn trước.
> - Cách tiếp tục phiên sau: mở lại hội thoại này, hoặc mở phiên mới và nói "tiếp tục". Memory dự án đã trỏ tới file này.

## Context
Thư mục `CompilationOfEconomicIndicators` đang trống. Mục tiêu:
1. Website tự lấy dữ liệu kinh tế và thị trường, tổng hợp thành chỉ số, đưa ra **dự báo ngắn/trung/dài hạn** cho kinh tế toàn cầu và từng thị trường. Giao diện trực quan, dễ theo dõi.
2. Repo có **agent quản lý giao việc**, **skill của nhà phân tích chuyên nghiệp**, và **bộ nhớ nhiều tầng** để không phải đọc lại repo.
3. Có đề xuất thêm để repo hoàn thiện (mục 14).

**Lựa chọn đã chốt**
- GitHub Pages + GitHub Actions, repo public.
- Thị trường: Kinh tế toàn cầu, Crypto, Vàng, Chứng khoán Mỹ, cộng thêm Việt Nam, Nhật Bản, Dầu & hàng hóa, Ngoại hối & trái phiếu.
- Nhận định trên site **không dùng LLM**, sinh tất định từ rulebook và mẫu câu tiếng Việt.
- Frontend: React + Vite + TS + Apache ECharts.
- Giữ như FilmProductionStudio: file nội bộ viết tiếng Anh, trả lời bạn bằng tiếng Việt, phân tầng model "Balanced", việc máy móc giao cho CLI tất định.

**Môi trường**
- Windows 11, Python 3.13.7, Node 22.19, git, gh (đăng nhập Tee28). Không có Docker.
- Đường dẫn có "その他", nên có rủi ro cp932.
- Máy phát triển có TLS inspection và web filter. Vì vậy **mọi việc lấy dữ liệu chạy trên GitHub Actions**; máy phát triển không dùng làm phương án dự phòng.

**Tái sử dụng** (chi tiết ở Phụ lục B)
- Từ FilmProductionStudio: launcher, hooks, `common`, `cli`, `context`, `audit`, sổ việc, `kb` (FTS5), `http_get`, skill `wrap`/`status`/`audit`/`research`, khung `CLAUDE.md`.
- Từ CoinPortfolioOverview: design token nền tối, status pill, helper định dạng số, bộ chuyển USD/JPY/VND, bảng chuyển thành thẻ trên mobile, `getJson`, FX fallback.

## Thay đổi chính so với v1 (theo rà soát)
1. **Bỏ khóa `"agent"`.** Body của agent sẽ thay toàn bộ system prompt mặc định. Vai trò CIO viết vào `CLAUDE.md` và luồng chính giữ đúng Claude Code. Subagent không có AskUserQuestion, nên **mọi việc xin bạn duyệt đều làm ở luồng chính**.
2. **Bắt đầu với 10 subagent**, gồm 2 manager có quyền giao việc lồng nhau. Lộ trình tách nhỏ dần lên 17 agent đã có sẵn. Quyền sở hữu file được **ép bằng hook theo `agent_type`**, không trông vào prompt.
3. **Lộ trình đảo lại:** sau P0 làm ngay một **lát cắt chạy thật trong khoảng 2 tuần** để forecast ledger bắt đầu tích lũy. Kiểm chứng nguồn dữ liệu trên runner GitHub ngay từ P0.
4. **Bỏ Stooq** (đòi CAPTCHA/key) và **Twelve Data** (gói free cấm hiển thị). Thay đổi nguồn:
   - Vàng: PAXG-USD trên Coinbase làm proxy daily, kèm World Bank Pink Sheet theo tháng.
   - Buffett indicator: tính từ Z.1 (Wilshire đã bị gỡ khỏi FRED).
   - Tín dụng: BAA10Y/AAA10Y + NFCI credit (ICE trên FRED chỉ còn 3 năm và cấm tái bản).
   - Nhật Bản: dùng API chính thức mới của BOJ.
5. **License 3 lớp `open | attributed | internal`.** Nguồn `internal` chỉ dùng để chạy mô hình. Site chỉ hiện tín hiệu, P(tăng) và phân vị % lợi nhuận, **không** hiện mức giá, Δ hay lịch sử. CI quét file JSON xuất ra để bắt rò rỉ.
6. **Kho dữ liệu bền:** repo **private** `econ-data` chỉ ghi thêm (append-only) và lưu vintage mỗi lần fetch. `actions/cache` chỉ dùng để tăng tốc.
7. **Sửa phương pháp thống kê:**
   - Đánh giá trên các điểm gốc không chồng lấp, báo cáo kèm n_eff.
   - Kiểm định DM (HAC + HLN), Clark–West.
   - Brier skill so với climatology.
   - ACI thay cho split-conformal; Platt/beta thay cho isotonic.
   - Ensemble chia trọng số đều cho tới khi đủ 36 điểm ngoài mẫu.
   - Dài hạn chỉ đưa khoảng lợi suất kỳ vọng hoặc dải kịch bản, không đưa p_up.
8. **Rulebook chống data snooping:** khóa holdout 5 năm gần nhất, áp BH-FDR, có trần số rule. Rule trở thành feature của một mô hình có regularization. Động lực trong nhận định lấy từ đóng góp thực của mô hình, nên không thể mâu thuẫn với P(tăng).
9. **Hook sửa lỗi bản Film:**
   - SubagentStop chỉ ghi lại (agent_type, agent_id, đường dẫn transcript); token được đếm sau từ transcript.
   - PreCompact ghi snapshot ra file.
   - Skill dùng `shell: bash` và cờ `--soft` thay cho `|| true`.
10. **Bổ sung:** script probe ở P0, ngân sách lượt gọi theo từng nguồn, SLA độ tươi có tính lịch nghỉ lễ US/JP/VN, kiểm tra toàn vẹn ledger, ẩn API key trong log/fixture, dòng ghi công FRED bắt buộc.

## 1. Kiến trúc
```
GitHub Actions — update-data.yml (cron 2 lần/ngày + chạy tay)
  checkout repo public + repo private econ-data (PAT chỉ có quyền trên repo đó)
  econ update: fetch (ngân sách lượt gọi) → store (append-only + vintage) → compute → forecast → ledger → publish (license gate)
     ├─► push econ-data: raw/<source>/<series>.parquet (lưu cả các bản số liệu đã điều chỉnh)
     ├─► commit ledger/ vào repo public (dự báo của chính mình, không chứa mức giá internal)
     └─► build web + data/*.<hash>.json + manifest.json ─► GitHub Pages (HashRouter)
                                       └─► artifact site-data (giữ 30 ngày) cho `econ pull-site`
Trình duyệt: tải manifest (no-store) → JSON đã hash. Giá crypto live và quy đổi USD/JPY/VND gọi API công khai từ client.
Máy bạn: Claude Code + agents/skills ─► `python econ.py …` (CLI tất định) ─► code, registry, rulebook, KB
```
- Dev local không gọi API: `econ pull-site` dùng `gh run download` (đi qua được proxy), hoặc fixture ghi sẵn.
- Vintage tự lưu cho phép backtest "real-time" cho những chuỗi ALFRED không có, ví dụ OECD CLI.

## 2. Nguồn dữ liệu & license (`config/sources.yaml`)
Mỗi nguồn có các trường:
- `license_class`: `open` | `attributed` | `internal`.
- `attribution`, `budget` (ví dụ 10k/tháng, 60/giờ), `freshness_sla`, `holiday_calendar`, `verified: YYYY-MM-DD`.

HTTP client tự ép ngân sách lượt gọi và tự xóa `api_key` khỏi URL trong log, cache và fixture.

| Nhóm | Nguồn | Lớp license / ghi chú |
|---|---|---|
| Vĩ mô Mỹ, lãi suất, USD, GDPNow, NFCI, Z.1 | FRED API (key free), ALFRED | Chuỗi của chính phủ: `attributed` (bắt buộc ghi "This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis."). SP500, NIKKEI225, VIX, ICE, Moody's: `internal` (xác minh từng chuỗi ở P0) |
| Vĩ mô toàn cầu, dự phóng 5 năm | IMF DataMapper (WEO), IMF portal mới (SDMX, có PCPS), World Bank, OECD (CLI/BCI/CCI; ≤60 lượt/giờ → gom batch), ECB, BIS | `attributed` |
| Crypto | CoinGecko Demo key (≤10k lượt/tháng), Coinbase candles (backfill phân trang), alternative.me F&G, DefiLlama stablecoins, mempool.space | CoinGecko và F&G: `attributed`. OHLC sàn: `internal`. CoinMetrics MVRV **tùy chọn**, dùng khi xác nhận còn free (CC BY-NC; site không có quảng cáo) |
| Vàng | Coinbase PAXG-USD (proxy daily, ghi rõ là proxy), World Bank Pink Sheet (tháng, CC BY 4.0) | Pink Sheet: `attributed`. PAXG: `internal` |
| Dầu, khí, đồng | FRED/EIA (WTI, Brent, Henry Hub, tồn kho, SPR), IMF PCPS (đồng) | `open` / `attributed` |
| Chứng khoán Mỹ | FRED SP500 (10 năm, sau đó tự tích lũy), dữ liệu Shiller (CAPE), Z.1 cho Buffett indicator | SP500: `internal`. CAPE: `internal` (xác minh) |
| Nhật Bản | BOJ Time-Series API (mới, từ 2026-02), MOF `jgbcme_all.csv`, e-Stat (appId free), FRED DEXJPUS | `attributed`. NIKKEI225: `internal` |
| Việt Nam | vnstock (VN-Index), SJC, Vietcombank XML, NHNN; IMF/World Bank | Tất cả nguồn VN có license không rõ: `internal`. Nếu runner bị chặn thì hạ xuống IMF/WB/NHNN theo tháng + nhập tay |
| Lịch kinh tế | FRED release dates, `config/calendar.yaml` (FOMC/ECB/BOJ/NHNN, lịch nghỉ lễ), ước tính halving | — |

- Secrets: `FRED_API_KEY`, `EIA_API_KEY`, `COINGECKO_API_KEY`, `DATA_REPO_TOKEN`. Tùy chọn: `ESTAT_APP_ID`.
- **Không dùng** yfinance, Stooq, Twelve Data. Binance chỉ gọi từ trình duyệt.
- Registry khác: `indicators.yaml`, `markets.yaml`, `composites.yaml`, `models.yaml`, `calendar.yaml`, `manual/` (số liệu nhập tay theo quý).
- Thống kê chuẩn cho mỗi chỉ số: mới nhất, Δ (1 tuần, 1 tháng, 3 tháng, 1 năm), z-score 10 năm, percentile, xu hướng, tín hiệu, độ tươi.
  - Mức giá và Δ chỉ đăng khi chỉ số có lớp `open` hoặc `attributed`.

## 3. Chỉ số tổng hợp (`config/composites.yaml`)
| ID | Ý nghĩa | Thành phần |
|---|---|---|
| `GLB_GROWTH` | Động lượng tăng trưởng toàn cầu | OECD CLI (G7/TQ/EU), BCI/CCI, sản lượng công nghiệp, tỷ lệ đồng/vàng |
| `US_RECESSION_12M` | Xác suất suy thoái Mỹ 12 tháng | Probit 10Y–3M (kiểu NY Fed), Sahm real-time, xu hướng claims, CFNAI |
| `INFLATION_PRESSURE` | Áp lực lạm phát | CPI/PCE lõi 3 tháng năm hóa so với mục tiêu, 5y5y, tiền lương, dầu, PPI |
| `GLB_LIQUIDITY` | Thanh khoản toàn cầu | Fed net liquidity (WALCL−TGA−RRP), M2 toàn cầu quy USD, DXY nghịch |
| `RISK_APPETITE` | Khẩu vị rủi ro | NFCI (kể cả phần credit), STLFSI, BAA10Y, percentile VIX (nội bộ), F&G |
| `MACRO_REGIME` | Ma trận Tăng trưởng × Lạm phát (Goldilocks/Reflation/Stagflation/Deflation) | `GLB_GROWTH` + `INFLATION_PRESSURE` |
| `GOLD_DRIVERS` | Động lực vàng | Lợi suất thực 10Y, DXY, breakeven, GPR, NHTW mua ròng (nhập tay), tỷ lệ vàng/bạc |
| `CRYPTO_CYCLE` | Chu kỳ crypto | Pha halving, stablecoin 90 ngày, dominance, F&G, MVRV (nếu có) |
| `EQUITY_VALUATION` | Định giá cổ phiếu | CAPE percentile, ERP, Buffett indicator (Z.1/GDP) |
| `VN_MACRO_PRESSURE` | Áp lực vĩ mô VN | USD/VND so với trần biên độ, chênh lệch SJC, lãi suất liên ngân hàng, CPI |
| `JP_POLICY` | Chính sách Nhật | JGB 10Y, lãi suất BOJ, USD/JPY so với vùng từng can thiệp, CPI lõi |

## 4. Động cơ dự báo
| Tầm | Thị trường | Kinh tế | Dạng đầu ra |
|---|---|---|---|
| Ngắn hạn | 1 tuần, 1 tháng | Nowcast quý (GDPNow, WEI, CLI) | P(tăng) + phân vị |
| Trung hạn | 3, 6, 12 tháng | Suy thoái 12 tháng, lạm phát 12 tháng, pha chu kỳ | P(tăng) + phân vị |
| Dài hạn | 3–5 năm | IMF WEO + tăng trưởng tiềm năng | **Khoảng lợi suất kỳ vọng năm hóa.** Crypto, dầu, vàng: **dải kịch bản có nhãn**, không có p_up |

**Đầu ra:**
- Tín hiệu 5 mức, độ tin cậy, top động lực (đóng góp thực của mô hình), kịch bản Tăng/Cơ sở/Giảm.
- `model_version`, `data_asof`, `input_hash`.

**Mô hình** (tất định, có seed):
1. **Baseline:** random walk + drift; biến động EWMA/GARCH(1,1). Mọi mô hình khác phải thắng baseline.
2. **Ngắn/trung hạn:** một mô hình logistic/ridge có regularization, nhận feature từ rulebook (xu hướng, động lượng, định giá, regime, thanh khoản, tâm lý, carry); huấn luyện walk-forward.
   - Phân phối có điều kiện theo regime: tối đa 2 điều kiện, có co rút.
   - Probit suy thoái.
3. **Dài hạn:**
   - Cổ phiếu: CAPE/ERP. Trái phiếu: YTM.
   - Vàng: kịch bản theo lợi suất thực. Lưu ý quan hệ này đã gãy từ 2022, nên luôn có nhãn cảnh báo.
   - Dầu: hồi quy về giá thực.
   - Crypto: dải theo chu kỳ halving. Chỉ có khoảng 3 chu kỳ để học, nên độ tin cậy luôn ở mức "Thấp".
4. **Hiệu chuẩn và ensemble:**
   - Khoảng dự báo: ACI (adaptive conformal), hoặc conformal trên phần dư đã chuẩn hóa GARCH theo cửa sổ trượt.
   - P(tăng): Platt/beta, hoặc co về base rate.
   - Trọng số ensemble chia đều cho tới khi đủ 36 điểm ngoài mẫu.

**Đánh giá và quản trị**
- Điểm gốc dự báo **không chồng lấp**, báo cáo kèm n_eff.
- Thước đo:
  - DM với HAC(h−1) + hiệu chỉnh HLN; Clark–West so với baseline lồng.
  - Brier skill so với climatology; pinball/CRPS.
- Coverage chỉ kiểm khi **n_eff ≥ 30**, kèm khoảng tin cậy nhị thức. Chưa đủ thì gắn nhãn **"chưa hiệu chuẩn"**.
- **Forecast ledger:**
  - Lưu ở `ledger/forecasts/YYYY-MM.jsonl`, mỗi dòng có `schema_version, input_hash, data_asof, model_version`.
  - CI kiểm tra các dòng cũ không bị sửa.
  - `econ ledger score` → trang Độ chính xác.
- **Champion/challenger:** mô hình mới chỉ được promote khi thắng ngoài mẫu, risk-manager duyệt và bạn duyệt. Có model card cho từng mô hình.
- **Test chống nhìn trước:** dự báo tại ngày t với dữ liệu đầy đủ phải bằng dự báo khi dữ liệu bị cắt tại t. Có tôn trọng độ trễ công bố.

## 5. Nhận định không dùng LLM: rulebook + mẫu câu
- `rulebook/<market>.yaml`: mỗi rule có `id, market, horizon, when` (điều kiện có cấu trúc, không eval), `score`, `evidence`, `text_vi`, `text_en`. Rule là **feature** của mô hình ở mục 4.2; trọng số do mô hình học.
```yaml
- id: us_curve_inverted_long
  market: macro_us
  horizon: MT
  when: {all: [{ind: US_T10Y3M, op: lt, value: 0}, {ind: US_T10Y3M, op: run_days_lt, value: 0, days: 90}]}
  score: -2
  evidence: knowledge/methods/yield-curve.md
  text_vi: "Đường cong 10 năm–3 tháng đảo ngược {run_days} ngày; lịch sử cho thấy suy thoái thường đến sau 6–18 tháng."
```
- **Chống data snooping:**
  - Khóa **holdout 5 năm gần nhất**; thiết kế rule không được nhìn vào khoảng này.
  - BH-FDR (hoặc Hansen SPA) trên tổ hợp rule × thị trường × tầm.
  - Trần số rule cho mỗi thị trường.
- **Narrative engine:**
  - Ghép câu kết luận (theo thang từ ngữ xác suất) → 3 động lực có đóng góp lớn nhất → rủi ro (đóng góp ngược chiều) → điều cần theo dõi (lịch).
  - Có test nhất quán dấu: nhận định không được mâu thuẫn với P(tăng).
  - Phrase bank `phrases.vi.yaml` có nhiều biến thể, chọn tất định. Có golden test tiếng Việt.
- **Vòng đời rule:** strategist soạn → quant kiểm trên khoảng train → risk-manager phản biện → bạn duyệt ở luồng chính.

## 6. Giao diện (`web/`)
- **Các trang:**
  1. Tổng quan: bản đồ thời tiết thị trường × tầm, ma trận regime, đồng hồ suy thoái/thanh khoản/rủi ro, "Điều gì thay đổi", status pill độ tươi.
  2. Kinh tế toàn cầu: heatmap z-score, IMF 5 năm.
  3. Một trang cho mỗi thị trường: Crypto, Vàng & kim loại, Dầu & hàng hóa, Chứng khoán, Ngoại hối & trái phiếu, Việt Nam, Nhật Bản.
  4. Chi tiết chỉ số: lịch sử, ngưỡng, giải thích 3 phần (Là gì / Vì sao quan trọng / Cách đọc), nguồn.
  5. Lịch kinh tế, Độ chính xác, Phương pháp (mỗi thị trường ghi rõ cửa sổ backtest, n_eff, lưu ý về điều chỉnh số liệu, so sánh với baseline), Nguồn & ghi công, Thuật ngữ, Miễn trừ.
- **Theo lớp license:**
  - `open`/`attributed`: biểu đồ mức giá đầy đủ, dòng ghi công đặt ngay cạnh dữ liệu.
  - `internal`: chỉ tín hiệu, P(tăng), fan chart **% lợi nhuận**, động lực. Có thể kèm link biểu đồ bên ngoài (tùy chọn).
- **UX:**
  - Tiếng Việt, có khung i18n.
  - Nền tối mặc định theo phong cách CoinPortfolioOverview, có chế độ sáng.
  - Xanh tăng / đỏ giảm, kèm ▲▼. Số monospace tabular.
  - Chuyển USD/JPY/VND, mobile-first.
  - Luôn hiện độ bất định và nhãn tin cậy.
- **Kỹ thuật:**
  - ECharts import theo module, lazy-load từng trang, mỗi JSON ≤ 200KB, tên file có hash.
  - Type TS sinh tự động từ JSON Schema.
  - Dùng skill `dataviz` khi làm biểu đồ.

## 7. Tổ chức agent
**Luồng chính = CIO.** Vai trò CIO viết trong `CLAUDE.md` (≤30 dòng): nói chuyện với bạn bằng tiếng Việt, định tuyến, chạy gate, mọi câu hỏi duyệt đều qua AskUserQuestion, ghi decision. Luồng chính dùng model bạn đang chọn; có thể đặt `model` trong settings nếu muốn tiết kiệm.

**10 subagent (`.claude/agents/*.md`, viết tiếng Anh)**
| Agent | Vai trò | Model / effort | Skill preload |
|---|---|---|---|
| **engineering-manager** | Biến tính năng thành DAG việc, giao ≤4 việc lồng song song, kiểm DoD, gom 1 báo cáo | sonnet / medium | project-management, engineering-standards |
| **research-lead** | Điều phối strategist, review chéo rulebook, thủ thư KB, vòng đời rule | sonnet / medium | project-management, signal-rulebook |
| data-engineer | Connector, registry nguồn, kho dữ liệu, chất lượng, license | sonnet / medium | data-engineering |
| quant-researcher | Mô hình, backtest, hiệu chuẩn, model card | **opus** / high | forecasting-methods, signal-rulebook |
| frontend-engineer | React/ECharts, i18n, a11y, hiệu năng | sonnet / medium | dashboard-ux, engineering-standards |
| platform-engineer | Kiến trúc/review, QA/test, CI/CD, Pages, secrets | sonnet / medium | engineering-standards, data-engineering |
| macro-strategist | Vĩ mô toàn cầu, lãi suất/FX, Việt Nam, Nhật Bản | sonnet / medium | macro-cycle-analysis, rates-fx-analysis, asia-markets, signal-rulebook |
| markets-strategist | Chứng khoán, vàng/dầu/kim loại, crypto | sonnet / medium | equity-strategy, commodities-analysis, crypto-analysis, signal-rulebook |
| risk-manager | Red team, kịch bản, rủi ro đuôi, hiệu chuẩn, tuân thủ | **opus** / medium | risk-scenario-analysis, forecasting-methods |
| content-editor | Phrase bank, giải thích chỉ số, thuật ngữ, trang phương pháp (tiếng Việt) | sonnet / low | financial-writing-vi, dashboard-ux |

- **Lộ trình tách nhỏ** (skill đã tách sẵn, nên tách agent chỉ là thêm 1 file). Tách khi memory của agent vượt 80 dòng hoặc việc bị dồn:
  - macro-strategist → macro-economist + rates-fx-strategist + asia-strategist.
  - markets-strategist → equity-strategist + commodities-analyst + crypto-analyst.
  - platform-engineer → tech-lead + qa-engineer + devops-engineer.
- **Giao việc:**
  - Brief: `TASK | TARGET | INPUTS | OUTPUT | CONSTRAINTS | DONE-WHEN`.
  - Báo cáo ≤8 dòng: `STATUS | WROTE | NOTES ≤3 | NEXT | ASK`. Manager gom lại thành 1 báo cáo ≤10 dòng.
  - Luồng chính → manager (chạy nền, có thông báo khi xong) → chuyên viên (manager chờ kết quả của việc lồng bên dưới).
  - `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=2`. Bật hay tắt `CLAUDE_CODE_FORK_SUBAGENT` quyết định theo kết quả probe ở P0.
- **Ép quyền bằng hook:** PreToolUse(Write|Edit|Agent) đọc `agent_type`, đối chiếu với bảng `owners` trong `config/econ.yaml`, rồi chặn ghi ngoài phần mình sở hữu hoặc chặn spawn sai đối tượng. Luồng chính không bị giới hạn.
- **Bảng sở hữu:**
  - Nguồn, connector, quality, kho dữ liệu → data-engineer.
  - `composites`, `models`, `backtest`, `docs/models` → quant-researcher.
  - `rulebook/<market>` → strategist phụ trách.
  - `phrases.*`, `content/**` → content-editor.
  - `web/**` → frontend-engineer.
  - Data contract, `publish/`, `tests/`, `.github/`, ARCHITECTURE/ADR → platform-engineer.
  - `knowledge/**` → research-lead.
  - `work/tasks.yaml` → các manager.
  - `decisions`, `handoff` → luồng chính.
  - `ledger/**` → chỉ CI.
- **Gate** (`econ gate check` kiểm tất định trước → bạn duyệt → ghi decision):
  - G0 Phạm vi & kiểm chứng (P0).
  - G1 Lát cắt chạy thật (P2).
  - G2 Dữ liệu & chỉ số đầy đủ.
  - G3 Mô hình: có báo cáo theo n_eff; mô hình không thắng baseline phải mang nhãn Thấp; đã qua red team.
  - G4 Giao diện đầy đủ: a11y, hiệu năng, quét license sạch.
  - Gate định kỳ: promote mô hình (hằng tháng), thay đổi rule.

## 8. Skills (`.claude/skills/`)
**Chuyên môn (14 skill, `user-invocable: false`, ≤150 dòng + `references/`).** Các skill chạy được bằng tool `Skill` sẽ luôn chiếm chỗ trong danh sách mỗi lượt, nên description phải ngắn.
| Skill | Nội dung chính |
|---|---|
| macro-cycle-analysis | 4 pha chu kỳ + ma trận GIP; chỉ báo dẫn dắt/trùng/trễ; probit suy thoái, Sahm, claims; nowcast; Taylor/r*; thanh khoản; độ trễ công bố và điều chỉnh số liệu; base rate |
| rates-fx-analysis | Đường cong lợi suất, term premium, lợi suất thực, breakeven, tín dụng (BAA10Y, NFCI), chênh lệch lãi suất, carry; JPY/BOJ/MOF; VND biên độ ±5% |
| equity-strategy | CAPE, ERP, Buffett (Z.1), chu kỳ lợi nhuận, độ rộng, luân chuyển ngành, Grinold–Kroner. refs: VN (T+2, room ngoại, margin, nâng hạng), JP (cải cách TSE, độ nhạy với yen) |
| commodities-analysis | Vàng (lợi suất thực, USD, NHTW mua ròng, quan hệ gãy từ 2022, proxy PAXG), bạc, dầu (OPEC+, EIA, SPR), khí, đồng; cơ chế SJC |
| crypto-analysis | Halving, on-chain, stablecoin, phái sinh, ETF, tâm lý, tương quan Nasdaq; giới hạn của mô hình chu kỳ |
| asia-markets | VN: NHNN, tín dụng, tỷ giá trung tâm, GSO. JP: BOJ, Shunto, Tankan, JGB, carry trade |
| forecasting-methods | Walk-forward, look-ahead/vintage, điểm gốc không chồng lấp/n_eff, DM-HLN/Clark–West, Brier skill, ACI, Platt/beta, co rút, ensemble đều, model card, gate promote |
| signal-rulebook | Schema rule, bằng chứng, khóa holdout, BH-FDR/SPA, trần số rule, vòng đời rule, viết template |
| risk-scenario-analysis | Kịch bản kèm điều kiện kích hoạt, pre-mortem, checklist red team, rủi ro đuôi, tuân thủ |
| data-engineering | Registry, mẫu connector, ngân sách lượt gọi, retry/cache/TLS, vintage, license 3 lớp, ẩn key, SLA độ tươi, chế độ suy giảm |
| dashboard-ux | Thứ bậc thông tin, màu ngữ nghĩa, trực quan hóa độ bất định, hiển thị theo license, mobile/a11y |
| financial-writing-vi | BLUF, glossary VI–EN, thang từ ngữ xác suất, không khuyến nghị mua/bán, định dạng số |
| engineering-standards | Data contract, tháp test, CI gate, ADR, Definition of Done |
| project-management | DAG `econ task`, brief/báo cáo, giao việc lồng, gate, decision, handoff |

**Workflow (14 skill, `disable-model-invocation: true`, `shell: bash`, ≤60 dòng).** Dùng `` !`python econ.py <cmd> --soft` `` (luôn exit 0, nên lỗi không làm hỏng skill).
- `/econ-status`, `/update-data`, `/gate G#`, `/wrap`, `/token-audit`.
- `/feature "<mô tả>"`, `/add-indicator <ID>`, `/add-source <tên>`, `/add-rule <market>`.
- `/backtest`, `/model-review`.
- `/outlook <market> [tầm]`: trả lời trong phiên dựa trên `digest`, không đăng lên site.
- `/research <chủ đề>`: `context: fork`, `agent: research-lead`, chạy nền.
- `/deploy-site`.

**Rule theo đường dẫn (7, ≤40 dòng):** `python-core`, `connectors`, `models`, `registries`, `frontend`, `knowledge`, `ci-workflows`. Lưu ý: rule chỉ nạp khi Read/Write/Edit file khớp, không nạp khi dữ liệu đi qua CLI.

## 9. Bộ nhớ nhiều tầng và tiết kiệm token
| Tầng | Vị trí | Khi nào nạp | Giới hạn |
|---|---|---|---|
| L0 Hiến chương + vai trò CIO | `CLAUDE.md` | Mỗi phiên và mỗi subagent | ≤120 dòng |
| L1 Brief | SessionStart → `econ status`: độ tươi và nguồn lỗi (`ledger/health.json`), mô hình, gate, top việc, handoff, 2 decision gần nhất | startup/resume/clear/compact | ≤20 dòng |
| L2 Rule theo đường dẫn | `.claude/rules/` | Khi chạm file khớp | ≤40 dòng |
| L3 Memory agent | `.claude/agent-memory/<agent>/MEMORY.md` | Khi agent chạy | ≤120 dòng |
| L4 Bản đồ code | `docs/ARCHITECTURE.md` + `docs/CODEMAP.md` (`econ codemap` sinh tự động) | Khi sửa code, thay cho quét repo | ≤150 dòng |
| L5 Registry & digest | `ind get`, `rule list`, `digest <market>` | Khi cần | ≤60 dòng |
| L6 KB | `knowledge/**` + FTS5 | `kb search` | Card ≤80 dòng |
| L7 Sổ sách | `work/` (tasks, notes, decisions, handoff) | Qua brief | handoff ≤30 dòng |
| Auto memory | `~/.claude/projects/.../memory/` | Mỗi phiên | Sở thích và trạng thái dự án của bạn |

**Hook** (chỉ dùng stdlib, 1 process, fail-open, im lặng khi không có lỗi):
- SessionStart: in brief.
- PreToolUse(Read): chặn đọc `data/`, `*.parquet`, JSON lớn, `node_modules`, `dist` → gợi ý lệnh CLI.
- PreToolUse(Write|Edit|Agent): ép quyền sở hữu (mục 7).
- PostToolUse(Write|Edit): kiểm schema YAML/rulebook.
- SubagentStop: chỉ ghi `(ts, agent_type, agent_id, transcript_path)`, bỏ qua `agent_type` rỗng hoặc trùng tên luồng chính.
- PreCompact: ghi `work/compact-snapshot.md`, in ≤5 dòng.

**Cơ chế khác**
- `econ log tokens` đọc transcript sau: expanduser, gộp theo message id.
- Đọc `context` / `digest` thay vì mở file.
- Việc tất định giao cho CLI.
- Phân tầng model, `maxTurns`, ít tool.
- Workflow skill không tốn token lúc khởi động.
- `/wrap` → `/clear`.
- `econ audit` kiểm ngân sách kích thước.
- `permissions.allow`: `Bash(python econ.py *)`, `Bash(python -m pytest *)`, `Bash(npm --prefix web run *)`.

## 10. CLI `econ` (`econ.py` là launcher, code nằm trong `src/econ/`)
- **Hệ thống:** `doctor`, `probe` (P0), `status [--full]`, `audit`, `codemap`, `context <role> <target>`, `serve`, `pull-site`.
- **Sổ việc:** `task …`, `notes …`, `handoff …`, `log decision|tail|tokens`, `gate check|approve`.
- **Registry:** `src list|get|check`, `ind …`, `rule list|get|test|backtest`, `market …`.
- **Dữ liệu & mô hình:** `fetch`, `quality`, `compute`, `forecast`, `backtest`, `model card|promote`, `ledger score|report|verify`.
- **Xuất bản:** `publish` (license gate), `license-scan`, `digest <market>`, `update` (chạy cả chuỗi; khi chạy local thì không ghi ledger).
- **KB:** `kb search|add|index`.
- **Hợp đồng output:** mặc định ≤40 dòng, có `--json`, mã thoát 0/1/2, cờ `--soft` cho skill.
- **Dependency:**
  - Python: pandas, numpy, pyarrow, pyyaml, pydantic, requests, statsmodels, scipy, arch, scikit-learn, truststore; dev: pytest, ruff.
  - Web: react, react-router, echarts, vite, typescript, vitest, @testing-library/react, json-schema-to-typescript.

## 11. Cấu trúc thư mục
```
CLAUDE.md  README.md(VI)  econ.py  pyproject.toml  requirements*.txt  .env.example  .gitignore  LICENSE
config/    econ.yaml(lịch, ngân sách, owners) sources.yaml indicators.yaml composites.yaml markets.yaml models.yaml calendar.yaml manual/
rulebook/  <market>.yaml  phrases.vi.yaml  phrases.en.yaml
content/   indicators.vi.yaml glossary.vi.yaml methodology.vi.md
src/econ/  cli common http store registry schemas connectors/ transforms/ composites/ models/ rules/ backtest/ ledger/ publish/ quality/
           work context codemap audit kb doctor probe hooks
tests/     unit/ golden/ contract/ hooks/ fixtures/ (đã ẩn key)
web/       src/{pages,components,charts,lib,i18n,types(sinh),styles}  public/data/ (sinh, gitignore)
ledger/    forecasts/YYYY-MM.jsonl  scores/  health.json      (chỉ CI ghi)
knowledge/ docs/(ARCHITECTURE, CODEMAP, methodology, data-sources, source-verification, runbook, token-playbook, models/, adr/)
work/      tasks.yaml notes.csv decisions.md handoff.md
.claude/   settings.json agents/(10) skills/(14+14) rules/(7) agent-memory/
.github/   workflows/{ci, src-check, update-data, model-weekly}.yml  dependabot.yml
.econ/ data/  (gitignore)          + repo private Tee28/econ-data: raw/<source>/<series>.parquet (append-only, vintage)
```

## 12. CI/CD và vận hành
- **`ci.yml`** (push/PR):
  - ruff, pytest offline, `npm ci`/typecheck/vitest/build.
  - Kiểm schema, `econ audit`.
  - `ledger verify` (không sửa dòng cũ), `license-scan` (JSON xuất ra không chứa ID hoặc dấu vân tay giá trị của chuỗi `internal`), test ẩn key.
- **`src-check.yml`** (chạy tay): thử từng nguồn từ runner, ghi kết quả vào `docs/source-verification.md`.
- **`update-data.yml`:**
  - Lịch: cron `17 23 * * *` và `17 9 * * 1-5`, kèm `workflow_dispatch`.
  - Các bước: restore cache → `econ update` → push `econ-data` → commit `ledger/` → build → deploy Pages → upload artifact `site-data` (giữ 30 ngày).
  - Nguồn lỗi vượt SLA (đã tính lịch nghỉ lễ) thì tự mở/cập nhật issue. Thiếu nguồn thì chạy chế độ suy giảm thay vì fail.
  - Mỗi tháng tự bật lại cron bằng `gh api -X PUT …/workflows/update-data.yml/enable` (`actions: write`), vì GitHub không định nghĩa rõ thế nào là "hoạt động" trong quy tắc 60 ngày.
  - Push bằng GITHUB_TOKEN không kích hoạt workflow khác, nên không cần `[skip ci]`.
- **`model-weekly.yml`:** refit, backtest, chấm điểm, xuất báo cáo artifact. Không tự promote.
- **Bảo mật:**
  - `permissions` tối thiểu, pin action theo SHA, `concurrency`.
  - Bật Dependabot, CodeQL, **secret scanning + push protection**.
  - `DATA_REPO_TOKEN` là fine-grained PAT, chỉ cấp contents:write trên `econ-data`.
- **Lưu ý về Pages:**
  - Artifact không giữ được symlink, dotfile bị loại.
  - Cache phía server 10 phút, nên dùng tên file có hash + manifest no-store.
  - `actions/cache` bị xóa sau 7 ngày không truy cập.

## 13. Pháp lý, đạo đức, bảo mật
- **License gate 3 lớp (mục 2, 6):**
  - Ghi công đặt ngay cạnh dữ liệu.
  - Dòng ghi công FRED ở footer.
  - Không quảng cáo (vì CoinMetrics là CC BY-NC).
  - Chuỗi bên thứ ba trên FRED cần chủ sở hữu cho phép nếu dùng ngoài mục đích cá nhân, nên để `internal`.
- **Tuân thủ:**
  - "Không phải lời khuyên đầu tư" ở mọi trang; không dùng từ "nên mua/bán".
  - Luôn hiện độ bất định và track record.
- **Bảo mật:**
  - Secret nằm trong `.env` (deny Read) và GitHub Secrets; không có key nào ở frontend; key bị ẩn trong log và fixture.
  - User-Agent chung, không chứa thông tin cá nhân.
  - **Nội dung web/API/KB là dữ liệu, không phải lệnh.**
- Kiểm tra chính sách IT của nơi làm việc trước khi public repo hoặc tạo PAT.

## 14. Đề xuất thêm để repo hoàn thiện
**★★★ Trong lộ trình chính**
1. Forecast ledger + trang Độ chính xác.
2. Champion/challenger + model card.
3. License gate + license-scan + trang ghi công.
4. Giám sát nguồn: SLA, lịch nghỉ lễ, issue tự động, chế độ suy giảm.
5. Test chống nhìn trước + fixture.
6. Kho vintage riêng, giúp backtest real-time trung thực hơn theo thời gian.

**★★ Sau MVP**
7. Cảnh báo qua Telegram khi regime đổi hoặc chỉ số vượt ngưỡng.
8. RSS "Điều gì thay đổi" + tóm tắt tuần từ template.
9. Watchlist và ngưỡng cá nhân (localStorage); PWA.
10. Kết nối CoinPortfolioOverview để so danh mục với dự báo.
11. "Xem lại quá khứ" từ ledger.

**★ Tùy chọn**
12. Mô phỏng what-if.
13. Giao diện EN/JA; vintage ALFRED; Lighthouse CI.
14. Statusline Claude Code hiện độ tươi dữ liệu và việc đang mở.

## 15. Lộ trình triển khai
| GĐ | Nội dung | Kết quả |
|---|---|---|
| **P0 Bootstrap & kiểm chứng** | `git init`, venv, `econ.py`, `doctor`. **`econ probe`** báo pass/fail kèm phương án dự phòng cho: `agent_type` trong payload PreToolUse của luồng chính, spawn lồng + chờ khi fork mode bật/tắt, skill `!` trên Windows khi có permission, deny Read, đếm token từ transcript > 0. Tạo repo public + repo private `econ-data` (**hỏi trước**). Chạy `src-check.yml` trên runner | G0: biết chắc tính năng và nguồn nào dùng được |
| **P1 Tổ chức lõi** | Port code Film. Viết `CLAUDE.md` (có CIO), `settings.json` (hook chỉ thêm sau khi test pass), 10 agent + seed memory, 13 skill chuyên môn (`asia-markets` để P6), 14 workflow skill, 7 rule, ARCHITECTURE/CODEMAP | Giao việc được cho agent |
| **P2 Lát cắt chạy thật (~2 tuần)** | Khoảng 8 nguồn `open/attributed` (FRED, IMF DataMapper, World Bank, OECD, CoinGecko, Coinbase, alternative.me, DefiLlama/mempool), khoảng 20 chỉ số, 3 composite (`US_RECESSION_12M`, `GLB_LIQUIDITY`, `RISK_APPETITE`). Forecast baseline cho vĩ mô Mỹ, chứng khoán Mỹ, vàng, BTC ở tầm 1 tháng / 12 tháng / 5 năm. Có ledger, `econ-data`, cron + Pages. UI tối thiểu: Tổng quan, 4 trang thị trường, Phương pháp, Ghi công | G1: **site chạy, ledger bắt đầu tích lũy** |
| **P3 Dữ liệu & chỉ số đầy đủ** | ECB, BIS, EIA, ACM, Z.1, Shiller, CoinMetrics (tùy chọn). Khoảng 100 chỉ số, 11 composite. SLA, lịch nghỉ lễ, chế độ suy giảm | G2 |
| **P4 Mô hình đầy đủ** | Mô hình feature từ rulebook (holdout, FDR), ngắn/trung/dài hạn, ACI/Platt, bộ đánh giá đầy đủ, champion/challenger | G3 |
| **P5 Website đầy đủ** | Đủ các trang, heatmap, fan chart, lịch, Độ chính xác, i18n, USD/JPY/VND, a11y/hiệu năng | G4 |
| **P6 Mở rộng** | Nhật Bản (BOJ API, MOF, e-Stat), Việt Nam (theo kết quả src-check; nếu bị chặn thì suy giảm), bạc/đồng/khí, skill `asia-markets`, tách agent khi cần | Đủ 8 nhóm thị trường |
| ★ P7 | Các đề xuất ★★ và ★ | |

Phiên đầu tiên sau khi bạn duyệt sẽ làm **P0 → P1**.

## 16. Rủi ro
- **API free thay đổi hoặc bị chặn:** đã có probe/src-check, fallback, issue tự động, chế độ suy giảm. Nguồn VN có thể chặn IP Mỹ, khi đó hạ xuống dữ liệu theo tháng + nhập tay (không dùng máy phát triển).
- **Bản quyền khi public:** license 3 lớp, license-scan trong CI, dòng ghi công FRED.
- **Dự báo vốn bất định:** n_eff, nhãn "chưa hiệu chuẩn", so với baseline, miễn trừ trách nhiệm.
- **Overfit / data snooping:** holdout, FDR, trần số rule, walk-forward, test cắt dữ liệu.
- **Lịch sử không tải lại được** (ICE 3 năm, SP500 10 năm, Kraken 720 điểm): kho `econ-data` append-only bắt đầu ghi từ P2.
- **Tính năng Claude Code** (fork mode, spawn lồng, `agent_type`): kiểm bằng `econ probe` ở P0, mỗi mục đều có phương án dự phòng.
- **GitHub Actions:** cron trễ hoặc bị tắt → phút lẻ, tự bật lại hằng tháng, `workflow_dispatch`.
- **Mạng có TLS inspection:** truststore, `PYTHONUTF8`, `pull-site` qua `gh`.
- **Phạm vi lớn:** làm lát cắt mỏng trước, mở rộng dần.

## 17. Kiểm tra (verification)
1. **`econ doctor` + `econ probe`:** mọi mục pass, hoặc đã chọn phương án dự phòng và ghi vào ARCHITECTURE. `src-check.yml` xanh với các nguồn của lát cắt.
2. **`python -m pytest -q`:**
   - Transform, composite.
   - Rule engine, narrative (golden + nhất quán dấu).
   - Mô hình tất định; không nhìn trước.
   - Ledger score/verify, license gate/scan, ẩn key, contract schema.
   - Connector với fixture.
   - Hook qua subprocess: fail-open, chặn Read, ép quyền theo `agent_type`, brief ≤20 dòng, SubagentStop bỏ qua `agent_type` rỗng.
3. **Web:** typecheck, vitest (render từng trang với fixture), build, kích thước bundle và JSON.
4. **E2E local:** `econ update --offline` → `publish` → `serve` http://127.0.0.1:8765.
5. **E2E CI:**
   - Push → `ci.yml` xanh.
   - `gh workflow run update-data.yml` → Pages cập nhật, `manifest.data_asof` mới, có commit ledger, `econ-data` có snapshot mới.
   - Giả lập nguồn lỗi → issue được mở và site chạy chế độ suy giảm.
6. **Backtest:** báo cáo theo n_eff. Coverage chỉ kết luận khi n_eff ≥ 30; mô hình không thắng baseline mang nhãn Thấp.
7. **Claude Code, phiên mới:**
   - Brief xuất hiện; `/econ-status` chạy được.
   - `/feature` cho 1 việc nhỏ → engineering-manager giao 2 việc lồng, mỗi báo cáo ≤8 dòng.
   - Hook chặn ghi sai chủ sở hữu.
   - `econ log tokens` > 0 cho từng agent.
   - `/wrap` → `/clear` → brief hiện handoff; `econ audit` trong ngân sách.

## Phụ lục A: Kết quả rà soát 2026-11-24 (tóm tắt, có nguồn)
- **Claude Code (code.claude.com/docs):**
  - Frontmatter `model/effort/tools/skills/memory/maxTurns/color` hợp lệ. `memory` tự thêm Read/Write/Edit.
  - Subagent spawn lồng được; `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` có thật; danh sách `Agent(type)` bị bỏ qua bên trong subagent.
  - Từ v2.1.302 fork mode bật mặc định: luồng chính không chờ subagent (chạy nền), subagent spawn thì có chờ việc lồng; tắt bằng `CLAUDE_CODE_FORK_SUBAGENT=0`.
  - Subagent không có AskUserQuestion.
  - Khóa `agent` thay toàn bộ system prompt mặc định; VS Code không ghi trong tài liệu.
  - SubagentStop có `agent_id, agent_type, agent_transcript_path, last_assistant_message`, không có token. Agent nội bộ (prompt suggestion) cũng kích hoạt SubagentStop, với `agent_type` rỗng hoặc trùng tên agent chính.
  - PreToolUse deny dùng `hookSpecificOutput.permissionDecision`; hook cũng chạy cho tool gọi trong subagent (có `agent_type`).
  - Matcher SessionStart gồm `startup|resume|clear|compact|fork`; PreCompact gồm `manual|auto`. Exec form `command+args` hợp lệ.
  - Field skill hợp lệ. Skill có `disable-model-invocation` không preload được. Forked skill chạy nền.
  - `!` chạy bằng Git Bash nếu có; lệnh không được allow làm hỏng skill, exit ≥2 cũng vậy.
  - Rule `paths:` chỉ nạp khi Read/Write/Edit file khớp.
- **Dữ liệu:**
  - CoinGecko: keyless khoảng 5 lượt/phút (không dùng cho polling); Demo 100 lượt/phút, 10k lượt/tháng, phải ghi nguồn.
  - Stooq: đòi apikey qua CAPTCHA. Twelve Data free: chỉ "internal non-display". yfinance: bị chặn trên IP cloud.
  - FRED:
    - ICE chỉ còn 3 năm (từ 04/2026), cấm tái bản.
    - Không có vàng LBMA (từ 2022). SP500 chỉ 10 năm. NIKKEI225 cần Nikkei cho phép.
    - Wilshire đã bị gỡ (06/2024). Bắt buộc ghi công FRED.
  - IMF DataMapper còn chạy (đã thấy WEO 04/2026); portal mới dùng SDMX; IFS đã ngừng.
  - OECD giới hạn khoảng 60 lượt/giờ, chặn VPN.
  - CoinMetrics community: 10 lượt/6 giây, CC BY-NC; MVRV chưa xác nhận còn free.
  - alternative.me cho dùng thương mại kèm ghi công. DefiLlama và mempool không cần key.
  - Kraken OHLC chỉ 720 điểm; Coinbase tối đa 300 điểm mỗi request.
  - MOF có `jgbcme_all.csv`. **BOJ ra API chính thức ngày 2026-02-18.**
  - vnstock: license phi thương mại (chưa chắc chắn); SJC/VCB không có tài liệu API.
  - Không có nguồn vàng daily miễn phí nào sạch về license.
- **GitHub:**
  - Không có định nghĩa rõ thế nào là "hoạt động" trong quy tắc 60 ngày.
  - Pages artifact giữ mặc định 1 ngày; cache phía server 600 giây; `actions/cache` bị xóa sau 7 ngày không dùng.

## Phụ lục B: Ghi chú khảo sát
Ghi chú khảo sát nội bộ (đường dẫn máy, repo khác) không được đưa lên repo public; bản đầy đủ nằm trong plan file và memory local.
