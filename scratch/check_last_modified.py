import os
import time

for root, dirs, files in os.walk('d:\\Robot\\ASSURPROD'):
    # Avoid walking into .git, data_db, etc.
    if '.git' in root or 'data_db' in root:
        continue
    for file in files:
        filepath = os.path.join(root, file)
        try:
            mtime = os.path.getmtime(filepath)
            # If modified in the last 2 hours
            if time.time() - mtime < 7200:
                print(f"{filepath} : modified {time.ctime(mtime)} ({time.time() - mtime:.1f} seconds ago)")
        except OSError:
            pass
