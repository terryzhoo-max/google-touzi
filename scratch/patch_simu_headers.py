import re

with open('d:\\FIONA\\google touzi\\static\\index.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. 'PROJECTED MKT VALUE'
text = text.replace('PROJECTED MKT VALUE', '试算后总市值 <span style="font-size:0.85em; opacity:0.8; margin-left:4px;">PROJECTED MKT VALUE</span>')

# 2. 'POST-TRADE NET CASH'
text = text.replace('POST-TRADE NET CASH\n', '交易后净现金 <span style="font-size:0.85em; opacity:0.8; margin-left:4px;">POST-TRADE NET CASH</span>\n')

# 3. 'Est. Friction: --' -> wait, the HTML could have dynamic value or span
# But the user's snippet says `<span id="simu-fric-cost">Est. Friction: ¥0.00</span>` 
# I will use Regex to replace the inner text prefix instead.
# Actually, the base HTML has `Est. Friction: --` or maybe just `Est. Friction:`. Let's just find `Est. Friction:`
text = text.replace('Est. Friction:', '预估摩擦成本 Est. Friction:')

# 4. 'COMPLIANCE STATUS'
text = text.replace('COMPLIANCE STATUS</div>', '合规风控状态 <span style="font-size:0.85em; opacity:0.8; margin-left:4px;">COMPLIANCE STATUS</span></div>')

with open('d:\\FIONA\\google touzi\\static\\index.html', 'w', encoding='utf-8') as f:
    f.write(text)

print('Successfully replaced target texts in index.html')
