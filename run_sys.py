import subprocess
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_sys.py <command>")
        return
    cmd = " ".join(sys.argv[1:])
    print(f"Running command: {cmd}")
    try:
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        print(f"Exit code: {res.returncode}")
        print("--- Output ---")
        print(res.stdout)
    except Exception as e:
        print(f"Error executing command: {e}")

if __name__ == '__main__':
    main()
