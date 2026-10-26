#!/usr/bin/env python3
"""
Auto-commit & auto-push watcher untuk GlassPin.
Memantau perubahan file di folder proyek, lalu otomatis:
  git add -A && git commit && git push origin main
Berjalan terus-menerus di background.
"""
import os
import subprocess
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
INTERVAL = 2   # detik: frekuensi cek
SETTLE = 4     # detik: diam sebelum commit (hindari commit setengah jadi)
IGNORE = {".git", "__pycache__", ".DS_Store"}


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, shell=True, capture_output=True, text=True)


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


def commit_and_push():
    status = run("git status --porcelain")
    if not status.stdout.strip():
        return
    run("git add -A")
    run('git commit -m "update: auto-commit perubahan otomatis (autopush watcher)"')
    r = run("git push origin main")
    if r.returncode == 0:
        print("[autopush] pushed:", time.strftime("%Y-%m-%d %H:%M:%S"), flush=True)
    else:
        print("[autopush] push gagal:", (r.stderr or r.stdout).strip()[:200], flush=True)


def main():
    print("[autopush] watcher aktif di", ROOT, flush=True)
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
