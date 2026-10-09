"""Render a read-only, source-qualified sales ledger page for ONNELLAB Ops."""
from __future__ import annotations
import html
import json
from pathlib import Path
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

SALES_LOGIC = Path(__file__).with_name('ops_sales_ui.js').read_text(encoding='utf-8')

def safe_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("&", "\\u0026")

def confirmed_foreign_fees(rows: list[dict]) -> list[dict]:
    """Only official Google fee entries with a known foreign buyer country."""
    verified = []
    for row in rows:
        country = str(row.get("country") or "").upper()
        if (row.get("platform") != "android"
            or row.get("fee_confirmed") is not True
            or "google_earnings_actual" not in row.get("sources", [])
            or len(country) != 2 or not country.isalpha() or country in {"KR","ZZ"}):
            continue
        try:
            fee = Decimal(str(row.get("fee") or "0"))
        except InvalidOperation:
            continue
        if not fee.is_finite() or fee == 0:
            continue
        verified.append({
            "date":str(row.get("date") or ""),
            "app_name":str(row.get("app_name") or ""),
            "app_slug":str(row.get("app_slug") or ""),
            "country":country,
            "fee":str(fee),
            "currency":str(row.get("currency") or "").upper(),
            "source":"Google Play Earnings (Google fee)",
            "kind":"refund_adjustment" if fee < 0 else "platform_commission",
            "fee_krw":row.get("fee_krw"),
            "fx_sales_date":row.get("fx_sales_date"),
            "fx_sales_source":row.get("fx_sales_source"),
        })
    return verified


def sales_page_body(ledger: Mapping | None) -> str:
    ledger = ledger or {}
    rows = ledger.get("rows", [])
    if not isinstance(rows, list):
        rows = []
    statuses = ledger.get("source_status", {})
    if not isinstance(statuses, dict):
        statuses = {}
    allowed = {"date", "platform", "app_slug", "app_name", "country", "currency",
               "units", "gross", "refund", "net_sales", "fee", "fee_confirmed",
               "proceeds", "proceeds_currency", "sources",
               "gross_krw", "refund_krw", "net_sales_krw", "fee_krw",
               "fx_sales_rate", "fx_sales_date", "fx_sales_source"}
    data = [{k: v for k, v in row.items() if k in allowed} for row in rows if isinstance(row, dict)]
    monthly = ledger.get("settlements", [])
    monthly = monthly if isinstance(monthly, list) else []
    verified = confirmed_foreign_fees(data)
    checked = html.escape(str(ledger.get("checked_at", "수집 전"))[:16].replace("T", " "))
    state = []
    labels = {
        "ok":"연결됨", "partial":"일부 자료만 수집됨",
        "not_collected":"수집 전", "not_configured":"연결 정보 없음",
        "vendor_number_required":"Apple Vendor Number 등록 필요",
        "credentials_unavailable":"API 키 점검 필요",
        "no_reports":"판매 보고서 미수신 · 판매 0건 확정 아님",
    }
    for platform,name in (("google","Google Play"),("apple","App Store"),("apple_finance","Apple 월별 정산")):
        source = statuses.get(platform,{})
        code = str(source.get("status","not_collected")) if isinstance(source,dict) else "not_collected"
        state.append('<div class="sales-state-item"><b>'+name+'</b> <span>'+html.escape(labels.get(code,code))+'</span></div>')
    google_status = statuses.get("google", {})
    if isinstance(google_status,dict) and google_status.get("missing_earnings_months"):
        missing = ", ".join(google_status["missing_earnings_months"])
        state.append('<div class="sales-state-item"><b>Google 확정 수수료</b><span>미수신 월: '+
                     html.escape(missing)+'</span></div>')
    # Fill trusted HTML/script placeholders BEFORE user-derived JSON, so an
    # app/report value that happens to contain a placeholder stays inert data.
    base = (HTML.replace("__SALES_JS__", SALES_LOGIC)
            .replace("__STATE__", "".join(state))
            .replace("__CHECKED__", checked))
    return (base.replace("__LEDGER__",safe_json(data))
        .replace("__SETTLEMENTS__",safe_json(monthly))
        .replace("__GRANT__",safe_json(verified))
        .replace("__FX_STATUS__",safe_json(ledger.get("fx_status", {})))
        .replace("__STATUSES__",safe_json(statuses)))

HTML = r"""
<header class="ops-head">
 <p class="eyebrow" data-ko="판매·정산" data-en="Sales & settlement">판매·정산</p>
 <h1 data-ko="앱 매출 분석" data-en="App sales analytics">앱 매출 분석</h1>
 <p data-ko="월별·연도별·직접 기간 지정·전체 누적 매출을 비교하고 원화 환산 추정액을 확인해요."
 data-en="Explore monthly, yearly, custom, and lifetime sales with estimated KRW conversions.">월별·연도별·직접 기간 지정·전체 누적 매출을 비교하고 원화 환산 추정액을 확인해요.</p>
</header>
<style>
.sales-controls,.sales-period-controls{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;padding:17px;border:1px solid var(--line);background:white;border-radius:12px}
.sales-period-controls{grid-template-columns:repeat(3,minmax(0,1fr));margin:14px 0 10px}
.sales-controls [hidden],.sales-period-controls [hidden]{display:none!important}
.sales-period-error{color:#a13c51;font-size:13px;margin:6px 0 10px}
.sales-controls label,.sales-period-controls label{display:grid;gap:5px;color:#625c55;font-size:12px;font-weight:730}
.sales-controls select,.sales-period-controls select,.sales-period-controls input{width:100%;box-sizing:border-box;border:1px solid #ddd4c8;padding:10px;min-height:43px;border-radius:8px;color:#292825;background:white;font:inherit;font-size:14px}
.sales-actions{display:flex;justify-content:space-between;flex-wrap:wrap;align-items:center;gap:12px;margin:15px 0}
.sales-actions button{padding:10px 15px;background:#f7f3ff;color:#514275;border:1px solid #d9c8f0;border-radius:8px;font-weight:750;cursor:pointer;min-height:42px}
.sales-actions button:disabled{cursor:not-allowed;opacity:.55}
.sales-states{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}
.sales-state-item{display:flex;gap:8px;align-items:center;min-height:40px;padding:10px 13px;border:1px solid var(--line);border-radius:8px;background:#fff;font-size:13px}
.sales-state-item span{color:#66615b}
.sales-table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:#fff}
.sales-table{width:100%;border-collapse:collapse;text-align:left;font-size:13px;white-space:nowrap}
.sales-table thead{background:#f8f7fb;color:#665c6f}
.sales-table th,.sales-table td{padding:12px 13px;border-bottom:1px solid #f0ede9;vertical-align:middle}
.sales-table th{font-size:12px;font-weight:800}
.sales-table td.num{font-variant-numeric:tabular-nums;text-align:right}
.sales-table tbody tr:last-child td{border-bottom:0}
.sales-note{font-size:12px;line-height:1.7;color:#777067;max-width:880px;margin-top:13px}
.sales-empty{padding:30px 16px;text-align:center;color:#746d66;background:#fff}
.sales-caption{font-size:13px;color:#686159}
.sales-amount{font-weight:740;color:#333039}
.sales-secondary{margin-top:28px}.sales-secondary h2{font-size:19px;color:#36323b;margin:0 0 9px}
.sales-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:10px;margin:16px 0 8px}
.sales-summary-item{border:1px solid var(--line);border-radius:10px;padding:14px;background:white;display:grid;gap:9px;min-width:0}
.sales-summary-item small{font-size:12px;color:#736a7b;font-weight:730}
.sales-summary-item strong{font-size:21px;color:#34313b;font-weight:800;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.sales-original{margin:12px 0 0}
.sales-original h2{font-size:16px;margin:16px 0 9px;color:#45404a}
.sales-period-note{font-size:12px;line-height:1.6;color:#777067;margin:8px 0 13px}
@media(max-width:800px){.sales-controls,.sales-period-controls{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:480px){.sales-controls,.sales-period-controls{gap:9px;padding:12px}.sales-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.sales-summary-item{padding:12px}.sales-summary-item strong{font-size:18px}.sales-table th,.sales-table td{padding:10px 9px}}
</style>
<section class="sales-states" aria-label="연동 상태">__STATE__</section>
<section class="sales-period-controls" aria-label="매출 조회 기간">
 <label><span data-ko="조회 기준" data-en="Period">조회 기준</span>
 <select id="sales-period-mode" aria-label="기간 선택">
 <option value="month">월별</option><option value="year">연도별</option>
 <option value="custom">기간 직접 지정</option><option value="all">전체 누적</option>
 </select></label>
 <label id="sales-month-field"><span data-ko="월" data-en="Month">월</span><select id="sales-month"></select></label>
 <label id="sales-year-field" hidden><span data-ko="연도" data-en="Year">연도</span><select id="sales-year"></select></label>
 <label id="sales-start-field" hidden><span data-ko="시작일" data-en="Start date">시작일</span><input type="date" id="sales-start"/></label>
 <label id="sales-end-field" hidden><span data-ko="종료일" data-en="End date">종료일</span><input type="date" id="sales-end"/></label>
</section>
<div id="sales-period-error" class="sales-period-error" role="status" aria-live="polite"></div>
<section class="sales-controls" aria-label="매출 상세 조건">
 <label><span data-ko="스토어" data-en="Store">스토어</span>
   <select id="sales-platform"><option value="">전체 스토어</option><option value="android">Google Play</option><option value="ios">App Store</option></select></label>
 <label><span data-ko="앱" data-en="App">앱</span><select id="sales-app"><option value="">모든 앱</option></select></label>
 <label><span data-ko="국가" data-en="Country">국가</span><select id="sales-country"><option value="">모든 국가</option></select></label>
</section>
<section class="sales-summary" aria-label="선택한 기간의 원화 매출 요약">
 <div class="sales-summary-item"><small>환불 반영 매출 · 원화 추정</small><strong id="sales-total-net">—</strong></div>
 <div class="sales-summary-item"><small>고객 결제액 · 원화 추정</small><strong id="sales-total-gross">—</strong></div>
 <div class="sales-summary-item"><small>환불 · 원화 추정</small><strong id="sales-total-refunds">—</strong></div>
 <div class="sales-summary-item"><small>확정 수수료 · 원화 환산</small><strong id="sales-total-fee">—</strong></div>
 <div class="sales-summary-item"><small>환불 반영 판매 건수</small><strong id="sales-total-units">—</strong></div>
</section>
<p id="sales-fx-status" class="sales-period-note" role="status" aria-live="polite">과거 기준환율을 확인하고 있어요.</p>
<section class="sales-original">
 <h2>통화별 원금액</h2>
 <div class="sales-table-wrap"><table class="sales-table" aria-label="통화별 매출">
 <thead><tr><th>통화</th><th>판매액</th><th>환불</th><th>환불 반영 매출</th><th>확정 수수료</th><th>건수</th></tr></thead>
 <tbody id="sales-currency-body"></tbody></table></div>
</section>
<div class="sales-actions">
 <div class="sales-caption" id="sales-caption" aria-live="polite">데이터를 조회하고 있어요.</div>
 <button type="button" id="sales-export" data-ko="조회 내역 CSV 저장" data-en="Export filtered CSV">조회 내역 CSV 저장</button>
</div>
<div class="sales-table-wrap">
<table class="sales-table" aria-label="일별 앱 국가별 판매 내역">
<thead><tr>
<th data-ko="판매일" data-en="Date">판매일</th><th data-ko="앱" data-en="App">앱</th>
<th data-ko="스토어" data-en="Store">스토어</th><th data-ko="국가" data-en="Country">국가</th>
<th data-ko="건수" data-en="Units">건수</th><th data-ko="판매금액" data-en="Gross sales">판매금액</th>
<th data-ko="환불" data-en="Refunds">환불</th><th data-ko="수수료" data-en="Fee">수수료</th>
<th data-ko="통화" data-en="Currency">통화</th><th>환불 반영 매출(원화 추정)</th><th>환율 기준일</th></tr></thead>
<tbody id="sales-body"></tbody>
</table>
</div>
<section class="sales-secondary">
 <h2 data-ko="월별 확정 정산" data-en="Monthly finalized settlements">월별 확정 정산</h2>
 <p class="sales-note">Apple 회계월 기준 확정 재무 보고서예요. 회계월은 달력 날짜와 다를 수 있어요. 원화 환산액은 회계월 말일 기준환율의 추정액이며 실제 입금액과 다를 수 있어요. 위의 판매액 총계에 더하지 않아요.</p>
 <p class="sales-caption">선택된 Apple 회계월 정산금 · 원화 환산 추정: <strong id="sales-settlement-sum">—</strong></p>
 <div class="sales-table-wrap"><table class="sales-table" aria-label="확정 재무 보고서">
 <thead><tr><th>회계월</th><th>앱</th><th>국가</th><th>판매량</th><th>고객 결제액</th><th>확정 수익금</th><th>정산금 원화 추정</th><th>수수료 증빙</th></tr></thead>
 <tbody id="settlement-body"></tbody></table></div>
</section>
<section class="sales-secondary">
 <h2 data-ko="지원금 신청용 해외 플랫폼 수수료" data-en="Documented foreign platform fees">지원금 신청용 해외 플랫폼 수수료</h2>
 <p class="sales-note">국가가 확인된 해외 Google Play 판매의 확정 수수료만 표시해요. 환불 수수료 조정은 음수로 표시해요. Apple은 별도 수수료 세금계산서 등 공식 증빙을 확보하기 전까지 제외해요.</p>
 <div class="sales-actions"><span id="grant-fee-count" class="sales-caption"></span>
 <button type="button" id="grant-fees-export">증빙 내역 CSV 저장</button></div>
 <div class="sales-table-wrap"><table class="sales-table" aria-label="해외 수수료 명세">
 <thead><tr><th>발생일자</th><th>세부내용</th><th>금액</th><th>통화</th><th>원화 환산</th><th>근거 자료</th></tr></thead>
 <tbody id="grant-fees-body"></tbody></table></div>
</section>
<p class="sales-note">
 • Google Play 판매금액은 현지 통화의 예상 판매 보고서, 수수료는 확정 수익 보고서의 Google fee 거래예요.<br>
 • Apple 판매액에는 세금이 포함될 수 있으므로 소비자 가격과 개발자 수익의 차이를 수수료로 표시하지 않아요.<br>
 • 외화는 ECB 과거 기준환율을 우선 적용하고, 미제공 통화는 NBU·NBP 공식 과거 기준환율로 보완해 원화 추정 합계를 보여줘요. 환율이 없으면 미환산으로 구분해요.<br>
 • 집계일 이후 거래와 보고서 미수집은 0원으로 취급하지 않아요.<br>
 마지막 갱신: __CHECKED__ (UTC)
</p>
<script id="sales-ledger" type="application/json">__LEDGER__</script>
<script id="sales-settlements" type="application/json">__SETTLEMENTS__</script>
<script id="sales-verified-fees" type="application/json">__GRANT__</script>
<script id="sales-source-status" type="application/json">__STATUSES__</script>
<script id="sales-fx-data" type="application/json">__FX_STATUS__</script>
<script>__SALES_JS__</script>
"""