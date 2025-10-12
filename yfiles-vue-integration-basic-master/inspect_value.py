from pathlib import Path
import re
text = Path('src/components/GraphComponent.vue').read_text(encoding='utf-8')
match = re.search(r"return text.replace\(/\\n/g, '([^']*)'\)", text)
if match:
    print(repr(match.group(1)))
else:
    print('not found')
