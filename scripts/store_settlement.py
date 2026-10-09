"""Apple settled fiscal-month proceeds. Commission is NOT recoverable from net/gross."""
from __future__ import annotations
import csv, gzip, io, re, urllib.parse, urllib.request, urllib.error
from collections import defaultdict
from datetime import date
from decimal import Decimal

def value(row, name):
    names = {re.sub(r"[^a-z0-9]", "", str(k).casefold()): str(v or "").strip()
             for k,v in row.items() if k is not None}
    return names.get(re.sub(r"[^a-z0-9]", "", name.casefold()), "")

def parse_finance(raw, month, apps, stats=None):
    if raw.startswith(b"\x1f\x8b"):
        raw = gzip.decompress(raw)
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), delimiter="\t")
    headers = {re.sub(r"[^a-z0-9]", "", h.casefold()) for h in (reader.fieldnames or [])}
    needed = ["Apple Identifier", "Country of Sale", "Quantity", "Extended Partner Share",
              "Partner Share Currency"]
    if any(re.sub(r"[^a-z0-9]", "", h.casefold()) not in headers for h in needed):
        raise ValueError("Unsupported Apple Finance report field structure")
    grouped = {}
    for source in reader:
        quantity = value(source,"Quantity")
        if not quantity:
            continue
        identifier = value(source,"Apple Identifier")
        vendor_sku = value(source,"Vendor Identifier")
        app = apps.get(identifier) or apps.get(vendor_sku)
        if stats is not None:
            stats["rows_with_quantity"] = stats.get("rows_with_quantity",0) + 1
            if not app:
                stats["unmatched_app_rows"] = stats.get("unmatched_app_rows",0) + 1
            else:
                stats["matched_app_rows"] = stats.get("matched_app_rows",0) + 1
        if not app:
            continue
        count = Decimal(value(source,"Quantity"))
        if count != count.to_integral_value():
            raise ValueError("Invalid Apple financial unit count")
        units = int(count)
        if value(source, "Sale or Return").upper() == "R":
            units = -abs(units)
        country = value(source,"Country of Sale").upper() or "ZZ"
        customer_currency = value(source,"Customer Currency").upper()
        proceeds_currency = value(source,"Partner Share Currency").upper()
        if not proceeds_currency:
            raise ValueError("Apple Finance row missing proceeds currency")
        proceeds = Decimal(value(source, "Extended Partner Share"))
        proceeds = -abs(proceeds) if units < 0 else proceeds
        customer_price = value(source,"Customer Price")
        customer_amount = (abs(Decimal(customer_price) * units)
                           if customer_currency and customer_price else Decimal(0))
        key = month, app["app_slug"], country, customer_currency, proceeds_currency
        item = grouped.setdefault(key, {
            "fiscal_month":month, "app_slug":app["app_slug"],"app_name":app["app_name"],
            "country":country,"customer_currency":customer_currency,
            "proceeds_currency":proceeds_currency,"units":0,
            "gross":Decimal(0),"refund":Decimal(0),"proceeds":Decimal(0),
            "fee":None,"fee_status":"commission_invoice_required",
            "source":"apple_finance_consolidated",
        })
        item["units"] += units
        if units < 0: item["refund"] -= customer_amount
        else: item["gross"] += customer_amount
        item["proceeds"] += proceeds
    result = []
    for item in grouped.values():
        for field in ("gross","refund","proceeds"):
            item[field] = str(item[field].quantize(Decimal(".01")))
        result.append(item)
    return sorted(result,key=lambda item:tuple(str(item[k]) for k in
                  ("fiscal_month","app_slug","country","customer_currency","proceeds_currency")))

def report_months(earliest, as_of):
    month = date(earliest.year, earliest.month, 1)
    end = date(as_of.year, as_of.month, 1)
    result = []
    while month < end:
        result.append(month.isoformat()[:7])
        month = date(month.year + (month.month == 12),
                     1 if month.month == 12 else month.month + 1, 1)
    return result

def fetch_finance(token, vendor, apps, earliest, as_of, previous=None, opener=None, sku_reconciled=True):
    opener = opener or urllib.request.urlopen
    prior = previous if isinstance(previous,dict) else {}
    months = report_months(earliest, as_of)
    done = set(prior.get("completed_months",[])) & set(months)
    missing = set(prior.get("missing_months",[])) & set(months)
    rolling = set(months[-2:]) if prior.get("sku_reconciliation_version") == 1 else set(months)
    stats = {"rows_with_quantity":0, "matched_app_rows":0, "unmatched_app_rows":0}
    changed = []
    rows = []
    errors = []
    for month in months:
        if month not in rolling and month in done | missing:
            continue
        query = urllib.parse.urlencode({
            "filter[regionCode]":"ZZ", "filter[reportDate]":month,
            "filter[reportType]":"FINANCIAL", "filter[vendorNumber]":vendor})
        request = urllib.request.Request(
            "https://api.appstoreconnect.apple.com/v1/financeReports?"+query,
            headers={"Authorization":"Bearer "+token, "Accept":"application/a-gzip"})
        try:
            with opener(request, timeout=50) as response:
                parsed = parse_finance(response.read(),month,apps,stats)
            done.add(month)
            missing.discard(month)
            changed.append(month)
            rows.extend(parsed)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                missing.add(month)
                done.discard(month)
            else:
                errors.append(month+": HTTP "+str(error.code))
                if error.code in {400,401,403,429}:
                    break
        except (ValueError,OSError) as error:
            errors.append(month+": invalid report ("+type(error).__name__+")")
            break
    return rows, {"status":"partial" if errors else "no_reports" if not done else "ok",
                  "completed_months":sorted(done), "missing_months":sorted(missing),
                  "refreshed_months":changed, "reports_available":len(done),
                  "reports_missing":len(missing), "new_reports":len(changed),
                  "sku_reconciliation_version":1 if sku_reconciled and not errors else 0,
                  "errors":errors[:8], "fee_status":"requires_independent_invoice",
                  **stats}

def merge_monthly(old, new, changed):
    refreshed = set(changed)
    fields = ('fiscal_month','app_slug','country','customer_currency','proceeds_currency')
    result = {tuple(str(row.get(f,'')) for f in fields):row for row in old
              if isinstance(row,dict) and row.get('fiscal_month') not in refreshed}
    for row in new:
        result[tuple(str(row.get(f,'')) for f in fields)] = row
    return sorted(result.values(),key=lambda row:tuple(str(row.get(f,'')) for f in fields),reverse=True)

def add_app_sku_aliases(token, known, opener=None):
    """Map Apple Finance vendor SKUs to known registered app IDs, never by fuzzy title."""
    import json
    opener = opener or urllib.request.urlopen
    aliases = dict(known)
    seen = set()
    url = "https://api.appstoreconnect.apple.com/v1/apps?limit=200"
    pages = 0
    while url and pages < 20:
        if url in seen: raise ValueError("Repeated Apple Apps API page")
        seen.add(url)
        req = urllib.request.Request(url,headers={"Authorization":"Bearer "+token})
        try:
            with opener(req, timeout=30) as response:
                payload=json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return aliases, {"status":"http_"+str(error.code),
                             "sku_aliases":len(aliases)-len(known)}
        for entry in payload.get("data",[]):
            app_id=str(entry.get("id",""))
            attributes=entry.get("attributes",{})
            sku=str(attributes.get("sku","")).strip() if isinstance(attributes,dict) else ""
            if app_id in known and sku:
                if sku in aliases and aliases[sku]["app_slug"] != known[app_id]["app_slug"]:
                    raise ValueError("Apple SKU collision across apps")
                aliases[sku]=known[app_id]
        next_url=(payload.get("links") or {}).get("next")
        url=next_url if isinstance(next_url,str) and next_url.startswith(
            "https://api.appstoreconnect.apple.com/") else ""
        pages += 1
    return aliases, {"status":"ok","sku_aliases":len(aliases)-len(known)}
