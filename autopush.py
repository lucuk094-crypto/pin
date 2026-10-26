#!/usr/bin/env python3
"""
Auto-commit & auto-push watcher untuk GlassPin (self-healing).
- Memantau perubahan file, lalu otomatis: git add -A && git commit && git push
- Otomatis memulihkan identitas git & remote (token) bila hilang antar sesi.
Token disimpan di /home/user/.glasspin_token (di LUAR repo, tidak ikut ter-commit).
"""
import os
import subprocess
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(os.path.expanduser("~"), ".glasspin_token")
REPO_URL = "https://github.com/lucuk094-crypto/pin.git"
INTERVAL = 2   # detik: frekuensi cek
SETTLE = 4     # detik: diam sebelum commit (hindari commit setengah jadi)
IGNORE = {".git", "__pycache__", ".DS_Store"}


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, shell=True, capture_output=True, text=True)


def read_token():
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    except OSError:
        return ""


def ensure_git_setup():
    """Pulihkan identitas & remote bila hilang (config sering ter-reset antar sesi)."""
    if not run("git config user.name").stdout.strip():
        run('git config user.name "van313"')
    if not run("git config user.email").stdout.strip():
        run('git config user.email "van313@users.noreply.github.com"')
    remote = run("git remote get-url origin").stdout.strip()
    token = read_token()
    auth = f"https://{token}@" if token else "https://"
    want = f"{auth}github.com/lucuk094-crypto/pin.git"
    if not remote:
        run(f'git remote add origin "{want}"')
    elif token and token not in remote and want != remote:
        run(f'git remote set-url origin "{want}"')


def snapshot():
    state = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in IGNORE]
        for fn in filenames:
            if fn in IGNORE:
                continue
            p = os.path.join(dirpath, fn)
            try:
                st = os.stat(p)
                state[p] = (st.st_mtime_ns, st.st_size)
            except OSError:
                pass
    return state


def commit_and_push(msg="update: auto-commit perubahan otomatis (autopush watcher)"):
    ensure_git_setup()
    status = run("git status --porcelain")
    if not status.stdout.strip():
        return
    run("git add -A")
    r = run(f'git commit -m "{msg}"')
    if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
        print("[autopush] commit gagal:", (r.stdout + r.stderr).strip()[:200], flush=True)
    p = run("git push origin main")
    if p.returncode == 0:
        print("[autopush] pushed:", time.strftime("%Y-%m-%d %H:%M:%S"), flush=True)
    else:
        print("[autopush] push gagal:", (p.stderr or p.stdout).strip()[:200], flush=True)


def main():
    print("[autopush] watcher aktif di", ROOT, flush=True)
    ensure_git_setup()
    last = snapshot()
    quiet_since = time.time()
    pending = False
    while True:
        time.sleep(INTERVAL)
        try:
            now = snapshot()
            if now != last:
                last = now
                quiet_since = time.time()
                pending = True
                continue
            if pending and time.time() - quiet_since >= SETTLE:
                pending = False
                commit_and_push()
        except Exception as e:
            print("[autopush] error:", e, flush=True)


if __name__ == "__main__":
    main()
