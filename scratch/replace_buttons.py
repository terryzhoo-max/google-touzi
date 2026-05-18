import os

file_path = r"d:\FIONA\google touzi\static\index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = {
    '[SYNC TDX PORTFOLIO]': '[同步持仓 SYNC TDX]',
    '[EXPORT CSV]': '[导出表格 EXPORT]',
    '[RESET]': '[重置 RESET]',
    '>INJECT<': '>注入 INJECT<',
    '>EXECUTE<': '>执行 EXECUTE<',
    '>BUY<': '>买入 BUY<',
    '>SELL<': '>卖出 SELL<',
    'TAKE PROFIT': '止盈 TAKE PROFIT',
    'STOP LOSS': '止损 STOP LOSS'
}

for old, new in replacements.items():
    content = content.replace(old, new)
    
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Buttons replaced successfully!")
