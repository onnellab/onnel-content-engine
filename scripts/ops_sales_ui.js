(() => {
  "use strict";
  const byId = id => document.getElementById(id);
  const rows = JSON.parse(byId("sales-ledger").textContent || "[]");
  const settlements = JSON.parse(byId("sales-settlements").textContent || "[]");
  const confirmedFees = JSON.parse(byId("sales-verified-fees").textContent || "[]");
  const fxState = JSON.parse(byId("sales-fx-data").textContent || "{}");
  const mode = byId("sales-period-mode");
  const month = byId("sales-month");
  const year = byId("sales-year");
  const startInput = byId("sales-start");
  const endInput = byId("sales-end");
  const platform = byId("sales-platform");
  const app = byId("sales-app");
  const country = byId("sales-country");
  const body = byId("sales-body");
  const caption = byId("sales-caption");
  const exportButton = byId("sales-export");

  const parts = new Intl.DateTimeFormat("en", {
    timeZone:"Asia/Seoul", year:"numeric", month:"2-digit", day:"2-digit"
  }).formatToParts(new Date());
  const part = kind => parts.find(x => x.type === kind)?.value || "";
  const today = part("year") + "-" + part("month") + "-" + part("day");
  const currentMonth = today.slice(0,7);
  const earliest = "2026-01-01";
  const months = new Set(rows.map(r=>String(r.date||"").slice(0,7))
                          .filter(x=>/^\d{4}-\d{2}$/.test(x)));
  for(let y=2026; y<=Number(part("year")); y++) {
    for(let m=1; m<=12; m++) {
      const value = y+"-"+String(m).padStart(2,"0");
      if(value<=currentMonth) months.add(value);
    }
  }
  months.add(currentMonth);
  for(const value of [...months].sort().reverse()) {
    const option=document.createElement("option");
    option.value=value; option.textContent=value;
    month.append(option);
  }
  month.value=currentMonth;
  for(let y=Number(part("year")); y>=2026; y--) {
    const option=document.createElement("option");
    option.value=String(y); option.textContent=y+"년";
    year.append(option);
  }
  startInput.value=currentMonth+"-01";
  endInput.value=today;
  startInput.max=today;
  endInput.max=today;
  for(const [key,element] of [["app_slug",app],["country",country]]) {
    for(const value of [...new Set(rows.map(r=>String(r[key]||"")).filter(Boolean))].sort()) {
      const option=document.createElement("option");
      option.value=value; option.textContent=value;
      element.append(option);
    }
  }
  const money = value => {
    const amount=Number(value);
    return Number.isFinite(amount)
      ? amount.toLocaleString("ko-KR",{maximumFractionDigits:2})
      : "—";
  };
  const krw = value => Number.isFinite(Number(value))
    ? Number(value).toLocaleString("ko-KR",{maximumFractionDigits:0})+"원"
    : "—";
  const number = value => {
    const result=Number(value);
    return Number.isFinite(result) ? result : 0;
  };
  const hasAmount = (row,key) => row[key]!==null && row[key]!==undefined &&
    Number.isFinite(Number(row[key]));
  const td = (tr,value,cls="") => {
    const cell=document.createElement("td");
    cell.textContent=String(value??"—");
    if(cls) cell.className=cls;
    tr.append(cell);
  };
  const csvCell = (raw,isNumeric=false) => {
    let value=String(raw??"");
    if(!(isNumeric && /^-?\d+(?:\.\d+)?$/.test(value)) && /^\s*[=+\-@]/.test(value)){
      value="'"+value;
    }
    return '"'+value.replaceAll('"','""')+'"';
  };
  const downloadCsv = (header, records, filename, numericColumns=new Set()) => {
    const csv=[header,...records].map((record,index)=>
      record.map((value,i)=>csvCell(value,index>0 && numericColumns.has(i))).join(",")
    ).join("\r\n");
    const url=URL.createObjectURL(new Blob(["\ufeff",csv],{type:"text/csv;charset=utf-8"}));
    const link=document.createElement("a");
    link.href=url;
    link.download=filename;
    link.click();
    setTimeout(()=>URL.revokeObjectURL(url),2000);
  };

  function selectedRange() {
    let start, end, label;
    if(mode.value==="month"){
      start=month.value+"-01";
      const partsOfMonth=month.value.split("-").map(Number);
      const lastDay=new Date(Date.UTC(partsOfMonth[0],partsOfMonth[1],0)).getUTCDate();
      end=month.value+"-"+String(lastDay).padStart(2,"0");
      label=month.value;
    }else if(mode.value==="year"){
      start=year.value+"-01-01";
      end=year.value+"-12-31";
      label=year.value+"년";
    }else if(mode.value==="custom"){
      start=startInput.value;
      end=endInput.value;
      label=start+" ~ "+end;
      if(!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end))
        return {valid:false,error:"시작일과 종료일을 모두 선택해 주세요."};
      if(start>end)
        return {valid:false,error:"시작일은 종료일보다 늦을 수 없어요."};
      if(start>today || end>today)
        return {valid:false,error:"오늘 이후 날짜는 조회할 수 없어요."};
    }else{
      start=earliest;
      end=today;
      label="전체 누적 ("+earliest+" ~ "+today+")";
    }
    end=end>today ? today : end;
    return {valid:true,start,end,label};
  }
  const selectedRows = (records,dateKey,range,os) => records.filter(r=>{
    const day=String(r[dateKey]||"");
    return range.valid && day>=range.start && day<=range.end &&
      (!os || !platform.value || platform.value===os) &&
      (!app.value || r.app_slug===app.value) &&
      (!country.value || r.country===country.value);
  });
  const filteredSales = range => selectedRows(rows,"date",range);
  const filteredFees = range => selectedRows(confirmedFees,"date",range,"android");
  const filteredSettlements = range => {
    // Custom dates are calendar days; Apple's fiscal month can start/end
    // mid-calendar-month. Displaying an entire fiscal month would mislead.
    if(!range.valid || mode.value==="custom") return [];
    // Finance reports are Apple fiscal-month aggregates. The displayed fiscal
    // months can overlap calendar months and are NEVER added to daily totals.
    const first=range.start.slice(0,7);
    const last=range.end.slice(0,7);
    return settlements.filter(r=>
      range.valid && r.fiscal_month>=first && r.fiscal_month<=last &&
      (!platform.value || platform.value==="ios") &&
      (!app.value || r.app_slug===app.value) &&
      (!country.value || r.country===country.value));
  };

  function renderSummary(visible,range) {
    const grouped=new Map();
    let gross=0, refunds=0, net=0, fees=0, appleProceeds=0;
    let converted=0, feeRows=0, unavailable=0, missingFee=0;
    let appleProceedsRows=0, missingAppleProceeds=0;
    for(const r of visible){
      const currency=String(r.currency||"미상");
      if(!grouped.has(currency))
        grouped.set(currency,{gross:0,refunds:0,net:0,fee:0,feesSeen:0,units:0});
      const group=grouped.get(currency);
      group.gross+=number(r.gross);
      group.refunds+=number(r.refund);
      group.net+=number(r.net_sales);
      group.units+=number(r.units);
      if(r.platform==="ios") {
        if(hasAmount(r,"proceeds_krw")) {
          appleProceeds+=number(r.proceeds_krw);
          appleProceedsRows++;
        } else if(number(r.proceeds)!==0) missingAppleProceeds++;
      }
      if(r.fee_confirmed){
        group.fee+=number(r.fee);
        group.feesSeen++;
        if(hasAmount(r,"fee_krw")) {fees+=number(r.fee_krw);feeRows++;}
        else missingFee++;
      }
      if(hasAmount(r,"net_sales_krw")){
        gross+=number(r.gross_krw);
        refunds+=number(r.refund_krw);
        net+=number(r.net_sales_krw);
        converted++;
      }else if(number(r.net_sales)!==0 || number(r.gross)!==0 || number(r.refund)!==0) {
        unavailable++;
      }
    }
    const summary=(id,value,empty=false)=> {
      byId(id).textContent=empty?"—":krw(value);
    };
    summary("sales-total-net",net, !visible.length || converted===0);
    summary("sales-total-gross",gross, !visible.length || converted===0);
    summary("sales-total-refunds",refunds,!visible.length || converted===0);
    summary("sales-total-fee",fees,!feeRows);
    summary("sales-total-ios-proceeds",appleProceeds,!appleProceedsRows);
    byId("sales-total-units").textContent=visible.length?
      money(visible.reduce((sum,r)=>sum+number(r.units),0))+"건":"—";
    const originalBody=byId("sales-currency-body");
    originalBody.replaceChildren();
    for(const [currency,item] of [...grouped].sort((a,b)=>a[0].localeCompare(b[0]))){
      const tr=document.createElement("tr");
      for(const value of [currency,money(item.gross),money(item.refunds),
                          money(item.net),item.feesSeen?money(item.fee):"미확정",
                          money(item.units)]){
        td(tr,value);
      }
      originalBody.append(tr);
    }
    if(!grouped.size){
      const tr=document.createElement("tr"),cell=document.createElement("td");
      cell.colSpan=6;cell.className="sales-empty";
      cell.textContent="선택한 기간의 확인된 판매 기록이 없어요.";
      tr.append(cell);originalBody.append(tr);
    }
    const notes=[];
    if(unavailable) notes.push("외화 환율을 확인할 수 없는 매출 "+unavailable+"개 행은 원화 합계에서 제외했어요.");
    if(missingFee) notes.push("확정 수수료 "+missingFee+"개 행은 환율 미확인으로 제외했어요.");
    if(missingAppleProceeds) notes.push("Apple 예상 개발자 수익금 "+missingAppleProceeds+"개 행은 환율 미확인으로 제외했어요.");
    if(fxState.status==="unavailable") notes.push("ECB 연결이 불안정해 보관된 과거 환율만 사용했어요.");
    notes.push("ECB 기준환율을 우선 적용하고 미제공 통화는 NBU·NBP 공식 기준환율로 보완했어요. 금액은 원화 추정액이며 실제 입금액과 달라요.");
    notes.push("Apple 회계월 확정 정산액은 위의 판매액에 중복 합산하지 않아요.");
    byId("sales-fx-status").textContent=notes.join(" ");
  }

  function renderDaily(visible) {
    body.replaceChildren();
    for(const row of visible){
      const tr=document.createElement("tr");
      for(const text of [row.date,row.app_name||row.app_slug,
        row.platform==="ios"?"App Store":"Google Play",row.country,
        row.units,money(row.gross),money(row.refund),
        row.fee_confirmed?money(row.fee):"미확정",row.currency,
        hasAmount(row,"net_sales_krw")?krw(row.net_sales_krw):"미환산",
        row.platform==="ios" ? (hasAmount(row,"proceeds_krw")?krw(row.proceeds_krw):"미환산") : "해당 없음",
        row.currency==="KRW"?"원화 원본":(row.fx_sales_date ? row.fx_sales_date+" ("+(row.fx_sales_source||"ECB")+")" : "—")]){
        td(tr,text);
      }
      body.append(tr);
    }
    if(!visible.length){
      const tr=document.createElement("tr"),cell=document.createElement("td");
      cell.colSpan=12;cell.className="sales-empty";
      cell.textContent="이 조건에서 확인된 판매 자료가 없어요. 보고서 미제공은 판매 0건을 뜻하지 않아요.";
      tr.append(cell);body.append(tr);
    }
    exportButton.disabled=!visible.length;
  }

  function renderExtras(range) {
    const settlementBody=byId("settlement-body");
    settlementBody.replaceChildren();
    const financeRows=filteredSettlements(range);
    let settledKrw=0, settledConverted=0, settledMissing=0;
    for(const item of financeRows){
      const tr=document.createElement("tr");
      if(hasAmount(item,"proceeds_krw")) {
        settledKrw+=number(item.proceeds_krw);settledConverted++;
      } else settledMissing++;
      for(const field of [
        item.fiscal_month,item.app_name||item.app_slug,item.country,item.units,
        (item.gross||"0")+" "+(item.customer_currency||""),
        (item.proceeds||"0")+" "+(item.proceeds_currency||""),
        hasAmount(item,"proceeds_krw")?krw(item.proceeds_krw):"미환산",
        "수수료 별도 증빙 필요"
      ]) td(tr,field);
      settlementBody.append(tr);
    }
    if(!financeRows.length){
      const tr=document.createElement("tr"),cell=document.createElement("td");
      cell.colSpan=8;cell.className="sales-empty";
      cell.textContent=mode.value==="custom"
        ? "일자 직접 지정 시 Apple 회계월 정산액은 표시하지 않아요. 월별·연도별 조회에서 확인해 주세요."
        : "선택한 기간에 해당하는 Apple 회계월 정산자료가 없어요.";
      tr.append(cell);settlementBody.append(tr);
    }
    byId("sales-settlement-sum").textContent=!financeRows.length || !settledConverted?"—":
      krw(settledKrw)+(settledMissing?" (미환산 "+settledMissing+"행 제외)":"");
    const grantBody=byId("grant-fees-body");
    grantBody.replaceChildren();
    const fees=filteredFees(range);
    for(const item of fees){
      const tr=document.createElement("tr");
      const kind=item.kind==="refund_adjustment"?"환불 수수료 조정":"해외 판매 플랫폼 정산 수수료";
      const details="Google Play · "+item.app_name+" · "+item.country+" · "+kind;
      for(const text of [item.date,details,item.fee,item.currency,
        hasAmount(item,"fee_krw")?krw(item.fee_krw):"미환산",item.source]) td(tr,text);
      grantBody.append(tr);
    }
    if(!fees.length){
      const tr=document.createElement("tr"),cell=document.createElement("td");
      cell.colSpan=6;cell.className="sales-empty";
      cell.textContent="이 기간의 확인된 해외 Google 수수료 내역이 없어요.";
      tr.append(cell);grantBody.append(tr);
    }
    byId("grant-fee-count").textContent=range.label+" · 확인된 "+fees.length+"개 수수료 내역";
    byId("grant-fees-export").disabled=!fees.length;
  }

  function updateModeVisibility(){
    byId("sales-month-field").hidden=mode.value!=="month";
    byId("sales-year-field").hidden=mode.value!=="year";
    byId("sales-start-field").hidden=mode.value!=="custom";
    byId("sales-end-field").hidden=mode.value!=="custom";
  }
  function draw(){
    updateModeVisibility();
    const range=selectedRange();
    byId("sales-period-error").textContent=range.valid?"":range.error;
    const visible=filteredSales(range);
    renderSummary(visible,range);
    renderDaily(visible);
    renderExtras(range);
    caption.textContent=range.valid
      ? range.label+" · "+visible.length+"개 집계 내역 · "+range.start+" ~ "+range.end
      : range.error;
  }
  [mode,month,year,startInput,endInput,platform,app,country]
    .forEach(node=>node.addEventListener("change",draw));
  [startInput,endInput].forEach(node=>node.addEventListener("input",draw));

  exportButton.addEventListener("click",()=>{
    const range=selectedRange();
    if(!range.valid)return;
    const fields=["date","app_name","platform","country","units","gross",
                  "refund","net_sales","fee","fee_confirmed","currency",
                  "gross_krw","refund_krw","net_sales_krw","fee_krw",
                  "fx_sales_rate","fx_sales_date","fx_sales_source",
                  "proceeds","proceeds_currency","proceeds_krw"];
    const header=["판매일","앱","스토어","국가","건수","판매액","환불",
                  "환불 반영 판매액","확정 수수료","수수료 확정","원통화",
                  "판매액 원화 추정","환불 원화 추정","순판매 원화 추정",
                  "확정 수수료 원화 추정","1통화당 원화 기준환율","환율 기준일","환율 출처",
                  "Apple 개발자 수익금 원통화","Apple 수익금 통화","Apple 수익금 원화 추정"];
    const records=filteredSales(range).map(r=>fields.map(key=>
      key==="fee"&&!r.fee_confirmed ? "" :
      key==="fee_krw"&&!r.fee_confirmed ? "" : r[key]??""
    ));
    downloadCsv(header,records,"ONNELLAB-sales-"+range.start+"-"+range.end+".csv",
                new Set([4,5,6,7,8,11,12,13,14,15]));
  });
  byId("grant-fees-export").addEventListener("click",()=>{
    const range=selectedRange();
    if(!range.valid)return;
    const header=["발생일자","세부내용","금액","통화","원화 금액","환율 기준일","환율 출처","근거자료"];
    const records=filteredFees(range).map(r=>[
      r.date,"Google Play / "+r.app_name+" / "+r.country+" / "+
        (r.kind==="refund_adjustment"?"환불 수수료 조정":"플랫폼 정산 수수료"),
      r.fee,r.currency,r.fee_krw??"",r.fx_sales_date??"",r.fx_sales_source??"",r.source
    ]);
    downloadCsv(header,records,"ONNELLAB-overseas-fees-"+range.start+"-"+range.end+".csv",
                new Set([2,4]));
  });
  draw();
})();
