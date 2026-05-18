import json

path = r"C:\Users\LENOVO\.gemini\antigravity\brain\a67fdf7f-32ca-40b9-8e2f-4e7662af5673\.system_generated\logs\overview.txt"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# line 19 is index 18
data = json.loads(lines[18])
content = data.get("content", "")
print("--- USER REQUEST ---")
print(content)
print("--- END ---")
