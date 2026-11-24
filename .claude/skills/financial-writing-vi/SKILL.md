---
name: financial-writing-vi
description: Vietnamese financial writing - BLUF structure, fixed probability wording scale, VI-EN glossary conventions, number formatting, slot templates for deterministic narratives, and no-advice compliance wording.
user-invocable: false
---
# Financial writing (Vietnamese)

## Structure
- **BLUF**: câu đầu nói nhận định + mức tin cậy + tầm thời gian. Chi tiết, động lực, rủi ro sau.
- Câu ngắn (<= 25 từ), chủ động, một ý một câu. Không rào đón dài, không cường điệu.
- Luôn có ngày dữ liệu ("tính đến 24/11/2026").

## Probability wording scale (fixed - templates choose by number, never by feel)
| P | Cụm từ | Hướng (khi nói về tăng) |
|---|---|---|
| >= 85% | rất có khả năng | rất có khả năng tăng |
| 70-85% | khả năng cao | khả năng cao tăng |
| 55-70% | nghiêng về | nghiêng về tăng |
| 45-55% | trung lập / ngang nhau | không nghiêng về bên nào |
| 30-45% | nghiêng về giảm | nghiêng về giảm |
| 15-30% | khả năng thấp | khả năng thấp tăng |
| < 15% | rất khó | rất khó tăng |
- Always print the number too: "nghiêng về tăng (62%)". Compare with base rate: "cao hơn mức bình thường 60%".
- Confidence labels: Cao / Trung bình / Thấp - separate from the probability ("62%, độ tin cậy Thấp").

## Banned / required
- Banned: "nên mua", "nên bán", "chắc chắn", "đảm bảo", "khuyến nghị", "cơ hội vàng", "bắt đáy", "x2 tài khoản".
- Required on every page: "Không phải lời khuyên đầu tư. Dự báo mang tính xác suất và có thể sai."
- Conditional voice for scenarios: "nếu ... thì ...", never predictions of certainty.

## Glossary conventions (content/glossary.vi.yaml)
- Vietnamese term first, English in parentheses on first use per page: "lạm phát lõi (core inflation)".
- Keep tickers/IDs as-is (CPI, PCE, ISM, VN-Index, MVRV). Prefer established Vietnamese finance terms:
  lợi suất (yield), đường cong lợi suất (yield curve), chênh lệch tín dụng (credit spread), suy thoái
  (recession), thanh khoản (liquidity), định giá (valuation), lợi suất thực (real yield), tỷ giá (exchange rate),
  ngân hàng trung ương (central bank), lãi suất điều hành (policy rate), khẩu vị rủi ro (risk appetite).

## Number formatting
- en-US separators in the UI (1,234.5) per Owner preference; percent 1 decimal; bp for spreads ("45 bp");
  currencies "$", "¥", "₫" with switcher; units always stated.
- Changes: "tăng 0.3 điểm %" for rates (not "tăng 0.3%"), "%" for relative changes.

## Slot templates (rulebook/phrases.vi.yaml)
```yaml
curve_inversion:
  risk_up: "Đường cong lợi suất 10 năm - 3 tháng đã đảo ngược {months} tháng liên tiếp, một tín hiệu thường đi trước suy thoái 6-18 tháng."
  neutral: "Đường cong lợi suất không còn đảo ngược; tín hiệu suy thoái từ chỉ báo này yếu đi."
headline:
  p_up: "{market}: {prob_phrase} ({p_up}) trong {horizon}, độ tin cậy {confidence}."
```
- Slots only; no hard-coded numbers; every template grammatical for all slot values (golden tests).
- Internal-license inputs: no `{value}` slot - describe the state only.
- Driver sentences come from model contributions, so their direction always matches the headline.

## Explainers (content/indicators.vi.yaml), <= 120 words each
Đo gì · Vì sao quan trọng · Chúng tôi dùng thế nào · Lưu ý (độ trễ công bố, điều chỉnh số liệu, giới hạn).
