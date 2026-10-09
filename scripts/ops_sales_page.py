"""Render a read-only, source-qualified sales ledger page for ONNELLAB Ops."""
from __future__ import annotations
import html
import json
from collections.abc import Mapping

def safe_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("&", "\\u0026")

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
               "proceeds", "proceeds_currency", "sources"}
    data = [{k: v for k, v in row.items() if k in allowed} for row in rows if isinstance(row, dict)]
    checked = html.escape(str(ledger.get("checked_at", "수집 전"))[:16].replace("T", " "))
    state = []
    labels = {
        "ok":"연결됨", "partial":"일부 자료만 수집됨",
        "not_collected":"수집 전", "not_configured":"연결 정보 없음",
        "vendor_number_required":"Apple Vendor Number 등록 필요",
        "credentials_unavailable":"API 키 점검 필요",
        "no_reports":"판매 보고서 미수신 · 판매 0건 확정 아님",
    }
    for platform,name in (("google","Google Play"),("apple","App Store")):
        source = statuses.get(platform,{})
        code = str(source.get("status","not_collected")) if isinstance(source,dict) else "not_collected"
        state.append('<div class="sales-state-item"><b>'+name+'</b> <span>'+html.escape(labels.get(code,code))+'</span></div>')
    return HTML.replace("__LEDGER__",safe_json(data)).replace("__STATUSES__",safe_json(statuses)).replace(
        "__STATE__", "".join(state)).replace("__CHECKED__", checked)

HTML = r"""
<header class="ops-head">
 <p class="eyebrow" data-ko="판매·정산" data-en="Sales & settlement">판매·정산</p>
 <h1 data-ko="월별 앱 매출" data-en="Monthly app sales">월별 앱 매출</h1>
 <p data-ko="매월 1일부터 조회일까지, 앱·국가·판매일별 판매금액을 확인해요."
 data-en="Review daily app sales by country, from the first of each month.">매월 1일부터 조회일까지, 앱·국가·판매일별 판매금액을 확인해요.</p>
</header>
<style>
.sales-controls{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;padding:17px;border:1px solid var(--line);background:white;border-radius:12px}
.sales-controls label{display:grid;gap:5px;color:#625c55;font-size:12px;font-weight:730}
.sales-controls select{width:100%;border:1px solid #ddd4c8;padding:10px;min-height:43px;border-radius:8px;color:#292825;background:white;font:inherit;font-size:14px}
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
@media(max-width:800px){.sales-controls{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:480px){.sales-controls{gap:9px;padding:12px}.sales-table th,.sales-table td{padding:10px 9px}}
</style>
<section class="sales-states" aria-label="연동 상태">__STATE__</section>
<section class="sales-controls" aria-label="매출 상세 조건">
 <label><span data-ko="월" data-en="Month">월</span><select id="sales-month"></select></label>
 <label><span data-ko="스토어" data-en="Store">스토어</span>
   <select id="sales-platform"><option value="">전체 스토어</option><option value="android">Google Play</option><option value="ios">App Store</option></select></label>
 <label><span data-ko="앱" data-en="App">앱</span><select id="sales-app"><option value="">모든 앱</option></select></label>
 <label><span data-ko="국가" data-en="Country">국가</span><select id="sales-country"><option value="">모든 국가</option></select></label>
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
<th data-ko="통화" data-en="Currency">통화</th></tr></thead>
<tbody id="sales-body"></tbody>
</table>
</div>
<p class="sales-note">
 • Google Play 판매금액은 현지 통화의 예상 판매 보고서, 수수료는 확정 수익 보고서의 Google fee 거래예요.<br>
 • Apple 판매액에는 세금이 포함될 수 있으므로 소비자 가격과 개발자 수익의 차이를 수수료로 표시하지 않아요.<br>
 • 국가·통화별 금액을 서로 환산하거나 임의로 더하지 않아요. 집계일 이후 거래와 보고서 미수집은 0원으로 취급하지 않아요.<br>
 마지막 갱신: __CHECKED__ (UTC)
</p>
<script id="sales-ledger" type="application/json">__LEDGER__</script>
<script id="sales-source-status" type="application/json">__STATUSES__</script>
<script>
(() => {
 const rows = JSON.parse(document.getElementById('sales-ledger').textContent || '[]');
 const month = document.getElementById('sales-month');
 const platform = document.getElementById('sales-platform');
 const app = document.getElementById('sales-app');
 const country = document.getElementById('sales-country');
 const body = document.getElementById('sales-body');
 const caption = document.getElementById('sales-caption');
 const exportButton = document.getElementById('sales-export');
 const nowParts = new Intl.DateTimeFormat('en', {timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'})
   .formatToParts(new Date());
 const part = kind => nowParts.find(x => x.type === kind)?.value || '';
 const today = part('year') + '-' + part('month') + '-' + part('day');
 const currentMonth = today.slice(0,7);
 const months = new Set(rows.map(r=>String(r.date||'').slice(0,7)).filter(x=>/^\d{4}-\d{2}$/.test(x)));
 for(let year=2026;year<=Number(part('year'));year++){
   for(let m=1;m<=12;m++){
     const value=year+'-'+String(m).padStart(2,'0');
     if(value<=currentMonth)months.add(value);
   }
 }
 months.add(currentMonth);
 for(const value of [...months].sort().reverse()){
   const opt=document.createElement('option');opt.value=value;opt.textContent=value;month.append(opt);
 }
 month.value=currentMonth;
 for(const [key,element] of [['app_slug',app],['country',country]]){
   for(const value of [...new Set(rows.map(r=>String(r[key]||'')).filter(Boolean))].sort()){
     const opt=document.createElement('option');opt.value=value;opt.textContent=value;element.append(opt);
   }
 }
 const money = v => {const n=Number(v);return Number.isFinite(n)?n.toLocaleString('ko-KR',{maximumFractionDigits:2}):'—';};
 const cell = (tr,value,cls='') => {const td=document.createElement('td');td.textContent=String(value??'—');if(cls)td.className=cls;tr.append(td);};
 const filtered = () => rows.filter(r=>r.date && r.date.startsWith(month.value) && r.date<=today &&
   (!platform.value||r.platform===platform.value)&&(!app.value||r.app_slug===app.value)&&
   (!country.value||r.country===country.value));
 const draw = () => {
   const visible=filtered();body.replaceChildren();
   for(const row of visible){
     const tr=document.createElement('tr');
     cell(tr,row.date);cell(tr,row.app_name||row.app_slug);
     cell(tr,row.platform==='ios'?'App Store':'Google Play');cell(tr,row.country);
     cell(tr,row.units,'num');cell(tr,money(row.gross),'num sales-amount');
     cell(tr,money(row.refund),'num');cell(tr,row.fee_confirmed?money(row.fee):'미확정','num');
     cell(tr,row.currency);body.append(tr);
   }
   if(!visible.length){
     const tr=document.createElement('tr');const td=document.createElement('td');
     td.colSpan=9;td.className='sales-empty';td.textContent='이 조건에 해당하는 확인된 판매 자료가 없어요. 아직 수집 중일 수도 있어요.';
     tr.append(td);body.append(tr);
   }
   caption.textContent=month.value+' · '+visible.length+'개 내역 (1일~'+(month.value===currentMonth?today:'말일')+')';
   exportButton.disabled=!visible.length;
 };
 [month,platform,app,country].forEach(node=>node.addEventListener('change',draw));
 exportButton.addEventListener('click',()=>{
   const fields=['date','app_name','platform','country','units','gross','refund','fee','fee_confirmed','currency'];
   const escapeCsv=v=>'"'+String(v??'').replaceAll('"','""')+'"';
   const csv=[fields.join(','),...filtered().map(r=>fields.map(k=>escapeCsv(k==='fee'&&!r.fee_confirmed?'':r[k])).join(','))].join('\r\n');
   const url=URL.createObjectURL(new Blob(['\ufeff',csv],{type:'text/csv;charset=utf-8'}));
   const anchor=document.createElement('a');anchor.href=url;anchor.download='ONNELLAB-sales-'+month.value+'.csv';anchor.click();
   setTimeout(()=>URL.revokeObjectURL(url),2000);
 });
 draw();
})();
</script>
"""