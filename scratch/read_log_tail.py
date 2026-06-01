import os

log_path = 'd:\\Robot\\ASSURPROD\\import_assurcore_v2.log'
if os.path.exists(log_path):
    with open(log_path, 'rb') as f:
        # Seek to end minus 10000 bytes
        try:
            f.seek(-10000, os.SEEK_END)
        except IOError:
            pass # File is smaller than 10k
        lines = f.readlines()
        # Decode and print the last 50 lines
        last_lines = lines[-50:]
        for line in last_lines:
            try:
                print(line.decode('utf-8').strip())
            except Exception:
                print(line)
else:
    print("Log file not found.")
