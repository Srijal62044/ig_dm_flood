# language: Python 3.11+, file: ig_dm_flood.py
# deps: pip install instagrapi
# note: private API — challenges can appear on first login

from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired,
    ChallengeRequired,
    FeedbackRequired,
    PleaseWaitFewMinutes,
    ClientError,
)
import time
import sys
import getpass
from concurrent.futures import ThreadPoolExecutor, as_completed

SESSION_FILE = "ig_session.json"
THREADS = 8
MAX_RETRIES = 2
cl = Client()
cl.delay_range = [0, 0]  # no artificial delay

def login(username: str, password: str):
    try:
        cl.load_settings(SESSION_FILE)
        cl.login(username, password)
        cl.get_timeline_feed()
        print("[+] session loaded")
    except Exception:
        print("[*] fresh login...")
        cl.login(username, password)
        cl.dump_settings(SESSION_FILE)
        print("[+] logged in + session saved")

def resolve_user(username: str) -> int | None:
    try:
        return cl.user_id_from_username(username.strip())
    except Exception as e:
        print(f"[-] resolve fail {username}: {e}")
        return None

def send_to_user(user_id: int, label: str, message: str) -> bool:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            cl.direct_send(message, user_ids=[user_id])
            print(f"[+] sent → {label}")
            return True
        except (PleaseWaitFewMinutes, FeedbackRequired) as e:
            print(f"[!] rate/feedback on {label}: {e} — sleep 30s")
            time.sleep(30)
        except ChallengeRequired:
            print("[!] challenge required — solve in the app then re-run")
            sys.exit(1)
        except LoginRequired:
            print("[!] session dead")
            return False
        except ClientError as e:
            print(f"[-] client error {label} (try {attempt}): {e}")
            time.sleep(1)
        except Exception as e:
            print(f"[-] unknown {label}: {e}")
            time.sleep(0.5)
    return False

def send_to_thread(thread_id: int, label: str, message: str) -> bool:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            cl.direct_send(message, thread_ids=[thread_id])
            print(f"[+] sent → group/thread {label}")
            return True
        except (PleaseWaitFewMinutes, FeedbackRequired) as e:
            print(f"[!] rate/feedback on thread {label}: {e} — sleep 30s")
            time.sleep(30)
        except ChallengeRequired:
            print("[!] challenge required — solve in the app then re-run")
            sys.exit(1)
        except LoginRequired:
            print("[!] session dead")
            return False
        except ClientError as e:
            print(f"[-] client error thread {label} (try {attempt}): {e}")
            time.sleep(1)
        except Exception as e:
            print(f"[-] unknown thread {label}: {e}")
            time.sleep(0.5)
    return False

def flood_users(targets: list[str], message: str, count: int):
    print("[*] resolving targets...")
    id_map = {}
    for u in targets:
        uid = resolve_user(u)
        if uid:
            id_map[u] = uid
            print(f"  {u} → {uid}")

    if not id_map:
        print("[-] no valid targets")
        return

    print(f"[*] flooding {len(id_map)} users × {count} times with {THREADS} threads...")
    start = time.time()
    success = 0
    jobs = []

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        for _ in range(count):
            for uname, uid in id_map.items():
                jobs.append(pool.submit(send_to_user, uid, uname, message))

        for fut in as_completed(jobs):
            if fut.result():
                success += 1

    elapsed = time.time() - start
    print(f"\n[done] {success} messages sent in {elapsed:.1f}s")

def flood_group(thread_id: int, message: str, count: int):
    print(f"[*] flooding thread {thread_id} × {count} times with {THREADS} threads...")
    start = time.time()
    success = 0

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        futures = [
            pool.submit(send_to_thread, thread_id, str(thread_id), message)
            for _ in range(count)
        ]
        for fut in as_completed(futures):
            if fut.result():
                success += 1

    elapsed = time.time() - start
    print(f"\n[done] {success}/{count} messages sent to group in {elapsed:.1f}s")

def list_recent_threads(limit: int = 20):
    """helper so you can find the group thread_id"""
    print("[*] fetching recent direct threads...")
    try:
        threads = cl.direct_threads(amount=limit)
        for t in threads:
            users = ", ".join([u.username for u in t.users]) if t.users else "unknown"
            title = t.thread_title or "(no title)"
            print(f"  thread_id={t.id} | title={title} | users=[{users}]")
    except Exception as e:
        print(f"[-] failed to list threads: {e}")

def main():
    print("=== IG DM Flood ===")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    login(username, password)

    print("\nMode:")
    print("  1 = flood individual users")
    print("  2 = flood a group / existing thread")
    print("  3 = list recent threads (to find group thread_id)")
    mode = input("Choice [1/2/3]: ").strip()

    if mode == "3":
        list_recent_threads()
        return

    message = input("Message to spam: ").strip()
    if not message:
        print("[-] empty message")
        return

    count = input("How many times to send (default 1): ").strip()
    count = int(count) if count.isdigit() and int(count) > 0 else 1

    if mode == "1":
        raw = input("Target usernames (comma separated): ").strip()
        targets = [t.strip() for t in raw.split(",") if t.strip()]
        if not targets:
            print("[-] no targets")
            return
        flood_users(targets, message, count)

    elif mode == "2":
        tid = input("Thread ID of the group: ").strip()
        if not tid.isdigit():
            print("[-] thread_id must be a number")
            return
        flood_group(int(tid), message, count)

    else:
        print("[-] invalid mode")

if __name__ == "__main__":
    main()