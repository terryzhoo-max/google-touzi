import subprocess

def main():
    res = subprocess.run(["git", "diff", "HEAD", "--", "static/index.html"], capture_output=True, text=True, encoding="utf-8")
    diff = res.stdout
    lines = diff.splitlines()
    
    with open("scratch/diff_output.txt", "w", encoding="utf-8") as f:
        f.write(f"DIFF LENGTH: {len(diff)}\n")
        for i, line in enumerate(lines):
            if any(x in line for x in ["simu", "rp-maxdd", "drawdown", "trades-body"]):
                start = max(0, i - 12)
                end = min(len(lines), i + 12)
                f.write(f"--- Match at line {i} ---\n")
                for j in range(start, end):
                    f.write(f"{j:4d}: {lines[j]}\n")
                f.write("-" * 50 + "\n")

if __name__ == "__main__":
    main()
