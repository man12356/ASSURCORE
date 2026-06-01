import os
import shutil

src = "d:\\Robot\\ASSURPROD\\assurcore"
dst = "d:\\Robot\\ASSURPROD\\addons\\assurcore"

if not os.path.exists(src):
    print(f"Error: Source {src} does not exist!")
    exit(1)

# Recursive copy function
def sync_dirs(src_dir, dst_dir):
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
    for item in os.listdir(src_dir):
        s = os.path.join(src_dir, item)
        d = os.path.join(dst_dir, item)
        if os.path.isdir(s):
            if item == "__pycache__":
                continue
            sync_dirs(s, d)
        else:
            shutil.copy2(s, d)
            print(f"Copied: {item}")

print(f"Syncing from {src} to {dst}...")
sync_dirs(src, dst)
print("Sync complete!")
