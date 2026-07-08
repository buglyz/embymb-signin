#!/usr/bin/env python3
"""embymb 每日自动签到 — GitHub Actions 版"""
import json, os, sys, urllib.error, urllib.request

BASE = "https://embymb.ichinosekotomi.com"
USER = os.environ.get("EMBYMB_USER")
PASS = os.environ.get("EMBYMB_PASS")


def api(method, path, data=None, token=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; embymb-signin/1.0)",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(f"{BASE}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read()) if e.code != 429 else {"success": False, "message": "429 Too Many Requests"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def main():
    if not USER or not PASS:
        print("❌ 未设置 EMBYMB_USER / EMBYMB_PASS")
        sys.exit(1)

    # 登录
    r = api("POST", "/api/v1/auth/login", {"username": USER, "password": PASS})
    if not r.get("success"):
        print(f"❌ 登录失败: {r.get('message', '?')}")
        sys.exit(1)
    user = r["data"]["user"]
    token = r["data"]["token"]
    print(f"✅ 登录成功 | {user['username']} | Emby 到期: {user.get('expire_status','?')}")

    # 签到
    si = api("POST", "/api/v1/signin", {}, token=token)
    if si.get("success"):
        d = si.get("data", {})
        print(f"✅ 签到成功 | 当前 {d.get('current_points', 0)} 小兔 | 连签 {d.get('current_streak', 0)} 天")
    elif "今天已经签过到了" in si.get("message", ""):
        print(f"ℹ️ 今日已签到")
    else:
        print(f"⚠️ {si.get('message', json.dumps(si))}")

    # 输出简短摘要到 stdout（会被 GHA 捕获）
    print(f"---EMBYMB_SIGNIN_RESULT: {user.get('expire_status', '?')}")


if __name__ == "__main__":
    main()