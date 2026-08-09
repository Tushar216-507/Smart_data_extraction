import re
from pathlib import Path

# Fix university_pipeline.py
up = Path("pipelines/university_pipeline.py")
content = up.read_text(encoding="utf-8")
content = content.replace('\\u2550', '=')
content = content.replace('\\u2500', '-')
content = content.replace('\u2550', '=')
content = content.replace('\u2500', '-')
content = content.replace('✓', '[PASS]')
content = content.replace('✗', '[FAIL]')
content = content.replace('⚠', '[WARN]')
up.write_text(content, encoding="utf-8")

# Fix run_batch_test.py
rbt = Path("run_batch_test.py")
content = rbt.read_text(encoding="utf-8")
content = content.replace('\\U0001f4a5', '[CRASH]')
content = content.replace('\U0001f4a5', '[CRASH]')
content = content.replace('✅', '[OK]')
content = content.replace('❌', '[FAIL]')
rbt.write_text(content, encoding="utf-8")

print("Fixed unicode symbols in both files.")
