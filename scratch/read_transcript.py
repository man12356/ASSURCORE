import os
import sys

print("Current working directory:", os.getcwd())
print("Executable:", sys.executable)
print("Environment variables:")
for k, v in sorted(os.environ.items()):
    print(f"  {k}: {v}")

# Search for transcript.jsonl
print("\nSearching for transcript.jsonl in likely locations:")
possible_paths = [
    r"C:\Users\LENOVO\.gemini\antigravity-ide\brain\8e6001f6-5cdc-4bd7-a35e-1fc54738c295\.system_generated\logs\transcript.jsonl",
    r"C:\Users\LENOVO\.gemini\antigravity-ide\brain\8e6001f6-5cdc-4bd7-a35e-1fc54738c295\logs\transcript.jsonl",
]
for p in possible_paths:
    exists = os.path.exists(p)
    print(f"  {p} exists: {exists}")
    if exists:
        try:
            with open(p, 'r', encoding='utf-8') as f:
                print(f"    Size: {len(f.read())} chars")
        except Exception as e:
            print(f"    Error reading: {e}")
