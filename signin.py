#!/usr/bin/env python3
"""embymb 每日自动签到 — GitHub Actions 版（签到后积分够则自动续期）"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://embymb.ichinosekotomi.com"
USER = os.environ.get("EMBYMB_USER")
PASS = os.environ.get("EMBYMB_PASS")
# 默认续期门槛；也可被接口返回的 renewal.cost 覆盖
DEFAULT_RENEW_COST = 70


def api(method, path, data=None, token=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; embymb-signin/1.1)",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            return {"success": False, "message": f"HTTP {e.code}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def try_renew(token, points, renewal_meta=None):
    """积分够则 POST /api/v1/signin/renew；返回 (did_attempt, result_dict_or_None)。"""
    renewal = renewal_meta or {}
    if renewal.get("enabled") is False:
        print("ℹ️ 续期功能未启用，跳过")
        return False, None

    cost = renewal.get("cost")
    if cost is None:
        cost = DEFAULT_RENEW_COST
    try:
        cost = int(cost)
    except (TypeError, ValueError):
        cost = DEFAULT_RENEW_COST

    try:
        pts = int(points or 0)
    except (TypeError, ValueError):
        pts = 0

    if pts < cost:
        print(f"ℹ️ 积分不足续期 | 当前 {pts} 小兔 / 需要 {cost}")
        return False, None

    days = renewal.get("days", 30)
    print(f"🔄 尝试续期 | 当前 {pts} 小兔 ≥ {cost}，续 {days} 天…")
    rr = api("POST", "/api/v1/signin/renew", {}, token=token)
    if rr.get("success"):
        d = rr.get("data") or {}
        left = d.get("current_points", d.get("points", "?"))
        expire = d.get("expire_status") or d.get("expired_at") or "?"
        print(f"✅ 续期成功 | 剩余积分 {left} | 到期: {expire}")
        if d:
            print(f"   详情: {json.dumps(d, ensure_ascii=False)[:300]}")
        return True, rr
    msg = rr.get("message") or json.dumps(rr, ensure_ascii=False)
    print(f"⚠️ 续期失败: {msg}")
    return True, rr


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
    print(f"✅ 登录成功 | {user['username']} | Emby 到期: {user.get('expire_status', '?')}")

    # 签到
    si = api("POST", "/api/v1/signin", {}, token=token)
    points = None
    renewal_meta = None
    if si.get("success"):
        d = si.get("data") or {}
        points = d.get("current_points", d.get("total_points"))
        renewal_meta = d.get("renewal")
        # 今日已签到也可能 success=true + created=false
        if d.get("today_signed") and d.get("created") is False and d.get("daily_points", 0) == 0:
            print(
                f"ℹ️ 今日已签到 | 当前 {points} 小兔 | 连签 {d.get('current_streak', '?')} 天"
            )
        else:
            print(
                f"✅ 签到成功 | 获得 {d.get('daily_points', d.get('points_today', 0))} 小兔 | "
                f"当前 {points} 小兔 | 连签 {d.get('current_streak', 0)} 天"
            )
    elif "今天已经签过到了" in (si.get("message") or ""):
        d = si.get("data") or {}
        points = d.get("current_points", d.get("total_points"))
        renewal_meta = d.get("renewal")
        print(f"ℹ️ 今日已签到 | 当前 {points if points is not None else '?'} 小兔")
    else:
        print(f"⚠️ 签到结果: {si.get('message', json.dumps(si, ensure_ascii=False))}")
        # 仍尝试从 data 取积分/续期信息
        d = si.get("data") or {}
        points = d.get("current_points", d.get("total_points"))
        renewal_meta = d.get("renewal")

    # 签到响应里若没有积分，再打一次签到接口拿状态（不会重复得积分）
    if points is None or renewal_meta is None:
        status = api("POST", "/api/v1/signin", {}, token=token)
        d = (status or {}).get("data") or {}
        if points is None:
            points = d.get("current_points", d.get("total_points"))
        if renewal_meta is None:
            renewal_meta = d.get("renewal")

    # 自动续期：积分 ≥ cost（默认 70）
    try_renew(token, points, renewal_meta)

    # 续期后刷新到期状态
    me = api("GET", "/api/v1/auth/me", token=token)
    expire = "?"
    if me.get("success"):
        expire = (me.get("data") or {}).get("expire_status", "?")
        print(f"📅 当前 Emby 到期: {expire}")

    print(f"---EMBYMB_SIGNIN_RESULT: {expire} | points={points}")


if __name__ == "__main__":
    main()
