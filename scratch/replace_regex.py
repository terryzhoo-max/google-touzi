import re

file_path = r'd:\FIONA\google touzi\static\index.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern for <h3>ENGLISH <span ...>中文</span></h3>
# Group 1: <h3> or <h3 ...>
# Group 2: English text (main header)
# Group 3: <span ...>
# Group 4: Chinese text (sub header)
pattern = re.compile(r'(<h3[^>]*>)\s*([^<]+?)\s*(<span[^>]*>)\s*([^<]+?)\s*(</span>)\s*</h3>')

def replacer(match):
    h3_start = match.group(1)
    en_text = match.group(2).strip()
    span_tag = match.group(3)
    zh_text = match.group(4).strip()
    span_close = match.group(5)
    
    # Do not swap if the text is already Chinese-first. We can heuristically check if the outer text contains Chinese chars or the inner text contains english chars.
    # Actually, all english letters in en_text means it's english.
    if re.search(r'[\u4e00-\u9fa5]', en_text):
        # Already Chinese first, skip
        return match.group(0)
    
    return f"{h3_start}{zh_text} {span_tag}{en_text}{span_close}</h3>"

new_content = pattern.sub(replacer, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Regex replace completed!")
