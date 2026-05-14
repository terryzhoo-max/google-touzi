import os
import re
import json

def classify_asset(symbol: str, name: str) -> tuple[str, str]:
    if 'ETF' in name.upper():
        if '黄金' in name: return ('gold', 'China')
        if '恒生' in name: return ('equity', 'HongKong')
        if '纳斯达克' in name or '标普' in name: return ('equity', 'US')
        return ('equity', 'China')
    
    # HK Stocks
    if symbol.startswith('0') and len(symbol) == 5:
        return ('equity', 'HongKong')
    
    return ('equity', 'China')

def parse_tdx_export(file_path: str) -> dict:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"TDX export file not found: {file_path}")
        
    with open(file_path, 'r', encoding='gbk', errors='replace') as f:
        lines = f.readlines()
        
    if not lines:
        raise ValueError("Empty TDX file")
        
    header_line = lines[0]
    cash_match = re.search(r'可用:([\d\.]+)', header_line)
    cash = float(cash_match.group(1)) if cash_match else 0.0
    
    positions = []
    
    if cash > 0:
        positions.append({
            'symbol': 'CASH',
            'name': '人民币现金',
            'asset_class': 'cash',
            'currency': 'CNY',
            'region': 'China',
            'strategy': 'core',
            'market_value': cash,
            'quantity': cash,
            'current_price': 1.0,
            'cost_basis': cash,
            'float_pnl': 0.0,
            'pnl_pct': 0.0
        })

    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 11 and parts[0].isdigit():
            try:
                symbol = parts[0]
                name = parts[1]
                quantity = float(parts[2])
                market_value = float(parts[10])
                
                # Additional PnL fields
                try:
                    current_price = float(parts[5])
                except (IndexError, ValueError):
                    current_price = market_value / quantity if quantity > 0 else 0.0
                    
                try:
                    float_pnl = float(parts[11])
                except (IndexError, ValueError):
                    float_pnl = 0.0
                    
                try:
                    pnl_pct = float(parts[12].replace('%', ''))
                except (IndexError, ValueError):
                    pnl_pct = 0.0
                
                # TDX cost calculation: column 6 is usually cost
                # For safety, we just derive it if possible, but market_value is what matters
                try:
                    cost = float(parts[6])
                except (IndexError, ValueError):
                    cost = market_value
                
                if quantity <= 0 or market_value <= 0:
                    continue
                    
                asset_class, region = classify_asset(symbol, name)
                
                positions.append({
                    'symbol': symbol,
                    'name': name,
                    'asset_class': asset_class,
                    'currency': 'CNY',
                    'region': region,
                    'strategy': 'core',
                    'market_value': market_value,
                    'quantity': quantity,
                    'current_price': current_price,
                    'cost_basis': cost,
                    'float_pnl': float_pnl,
                    'pnl_pct': pnl_pct
                })
            except ValueError:
                pass
                
    return {"positions": positions}

def import_tdx_to_portfolio(file_path: str, output_json_path: str):
    data = parse_tdx_export(file_path)
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data
