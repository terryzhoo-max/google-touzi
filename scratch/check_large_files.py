import os
import sys
import subprocess

def check_large_files():
    try:
        # Run git status --porcelain
        status = subprocess.check_output(['git', 'status', '--porcelain'], text=True)
    except Exception as e:
        # If Git is not initialized or fails, skip silently
        return 0

    large_files = []
    # Limit: 50MB (52,428,800 bytes)
    LIMIT_BYTES = 50 * 1024 * 1024

    for line in status.splitlines():
        if not line.strip():
            continue
        
        # Git porcelain format: 'XY path' or 'XY "path with spaces"'
        # Strip status columns (first 3 characters) and surrounding quotes/spaces
        path = line[3:].strip().strip('"').strip("'")
        
        if os.path.exists(path) and os.path.isfile(path):
            try:
                size = os.path.getsize(path)
                if size > LIMIT_BYTES:
                    large_files.append((path, size))
            except OSError:
                continue

    if large_files:
        print("\n      =====================================================")
        print("      [ALERT] DETECTED LARGE FILES EXCEEDING 50MB:")
        print("      =====================================================")
        for path, size in large_files:
            mb_size = size / (1024 * 1024)
            print(f"      - {path} ({mb_size:.2f} MB)")
        print("      =====================================================\n")
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(check_large_files())
