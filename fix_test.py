from pathlib import Path

path = Path("test_final_output_builder.py")
content = path.read_text(encoding="utf-8")
content = content.replace("✓", "[PASS]")
content = content.replace("✗", "[FAIL]")
path.write_text(content, encoding="utf-8")
print("Replaced unicode symbols in test.")
