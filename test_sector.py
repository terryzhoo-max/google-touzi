import datetime
from core.data_providers import _tushare_items
from core.sector_rotation import SW_SECTORS

def get_sector_rotation_fast():
    end = datetime.date.today()
    start = end - datetime.timedelta(days=120)
    
    # 1. Get trading days with ACTUAL data
    items = _tushare_items('sw_daily', {
        'ts_code': '801010.SI', 
        'start_date': start.strftime("%Y%m%d"), 
        'end_date': end.strftime("%Y%m%d")
    }, 'trade_date')
    
    dates = sorted([row[0] for row in items])
    if len(dates) < 61:
        return {"error": "Not enough trading days."}
        
    t0 = dates[-1]
    t5 = dates[-6]
    t20 = dates[-21]
    t60 = dates[-61]
    
    print(f"Target dates: {t0}, {t5}, {t20}, {t60}")
    
    # 2. Fetch data for these 4 dates
    data = {}
    for d in [t0, t5, t20, t60]:
        items = _tushare_items('sw_daily', {'trade_date': d}, 'ts_code,close')
        data[d] = {row[0]: float(row[1]) for row in items}
        
    # 3. Compute returns
    rows = []
    for code, name in SW_SECTORS.items():
        if code not in data[t0] or code not in data[t20]:
            print(f"Code {code} missing in {t0} or {t20}")
            continue
            
        last = data[t0][code]
        try:
            ret_5d = round((last / data[t5][code] - 1) * 100, 2) if code in data[t5] else 0
            ret_20d = round((last / data[t20][code] - 1) * 100, 2)
            ret_60d = round((last / data[t60][code] - 1) * 100, 2) if code in data[t60] else 0
        except ZeroDivisionError:
            ret_5d, ret_20d, ret_60d = 0, 0, 0
            
        rows.append({
            "code": code,
            "name": name,
            "ret_5d": ret_5d,
            "ret_20d": ret_20d,
            "ret_60d": ret_60d,
            "last_close": round(last, 2)
        })
    
    print(rows[:3])
    print("Fetched sectors:", len(rows))

if __name__ == "__main__":
    get_sector_rotation_fast()
