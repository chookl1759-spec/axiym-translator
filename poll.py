# -*- coding: utf-8 -*-
"""10분마다 실행: axiym 방의 새 메시지를 번역해서 봇으로 보냅니다.
공개 저장소이므로 메시지 내용은 로그에 절대 출력하지 않습니다."""
import asyncio
import base64
import json
import os
import re
from datetime import timedelta, timezone

import requests
from telethon import TelegramClient
from telethon.sessions import StringSession

from common import bot_send, env, media_label, mostly_korean, translate_ko

if not os.environ.get("TG_SESSION", "").strip():
    print("TG_SESSION 이 아직 없습니다. login 워크플로를 먼저 실행해 주세요. (이번 실행은 건너뜀)")
    raise SystemExit(0)

KST = timezone(timedelta(hours=9))
STATE = "state/state.json"

API_ID = int(env("API_ID"))
API_HASH = env("API_HASH")
BOT_TOKEN = env("BOT_TOKEN")
SESSION = env("TG_SESSION")
CHAT_NAME = env("CHAT_NAME", required=False, default="axiym")
HISTORY_TOKEN = env("HISTORY_TOKEN", required=False, default="")
HISTORY_REPO = env("HISTORY_REPO", required=False, default="chookl1759-spec/axiym-history")
BACKFILL = 300
SKIP_KOREAN = env("SKIP_KOREAN", required=False, default="yes").lower() in ("yes", "y", "true", "1")


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(s, f)


async def find_chat(client):
    async for d in client.iter_dialogs():
        if CHAT_NAME.lower() in (d.name or "").lower():
            return d
    raise SystemExit("이름에 CHAT_NAME 이 들어간 방을 찾지 못했습니다.")


async def main():
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        raise SystemExit("TG_SESSION 이 만료됐습니다. login 워크플로를 다시 실행해 주세요.")
    me = await client.get_me()
    state = load_state()

    chat = await find_chat(client)
    if state.get("chat_id") != chat.id:
        latest = await client.get_messages(chat.entity, limit=1)
        state = {"chat_id": chat.id, "last_id": latest[0].id if latest else 0}
        save_state(state)
        bot_send(BOT_TOKEN, me.id, f"✅ '{chat.name}' 방 번역 알림을 시작합니다. 약 10~15분 간격으로 새 메시지를 보내 드려요.")
        print("시작 상태 저장")
        return

    entries = []
    if HISTORY_TOKEN and not state.get("backfilled"):
        # 기록 저장을 처음 켤 때 한 번: 최근 메시지를 과거 기록으로 채움
        async for msg in client.iter_messages(chat.entity, max_id=state["last_id"] + 1, limit=BACKFILL):
            e = await to_entry(msg)
            if e:
                entries.append(e)
        entries.reverse()
        state["backfilled"] = True

    count = 0
    async for msg in client.iter_messages(chat.entity, min_id=state["last_id"], reverse=True, limit=200):
        state["last_id"] = max(state["last_id"], msg.id)
        e = await to_entry(msg)
        if not e:
            continue
        entries.append(e)
        if e["korean"] and SKIP_KOREAN:
            continue
        body = e["ko"] if e["korean"] else (f"{e['label']}\n{e['ko']}".strip() + (f"\n\n— 원문 —\n{e['text']}" if e["text"] else ""))
        bot_send(BOT_TOKEN, me.id, f"💬 {chat.name} | {e['name']} | {e['time'][5:]}\n\n{body}")
        count += 1

    if HISTORY_TOKEN and entries:
        try:
            save_history(chat.name, entries)
        except Exception as e:
            print("기록 저장 실패:", type(e).__name__, str(e)[:100])
            state.pop("backfilled", None) if count == 0 and not state.get("last_saved") else None
        else:
            state["last_saved"] = True
    save_state(state)
    await client.disconnect()
    print(f"보낸 알림 {count}건, 기록 {len(entries)}건")


async def to_entry(msg):
    text = (msg.raw_text or "").strip()
    label = media_label(msg)
    if not text and not label:
        return None
    sender = await msg.get_sender()
    name = getattr(sender, "first_name", None) or getattr(sender, "title", None) or "알 수 없음"
    if getattr(sender, "last_name", None):
        name = f"{name} {sender.last_name}"
    korean = bool(text) and mostly_korean(text)
    ko = text if korean else ""
    if text and not korean:
        try:
            ko = translate_ko(text)
        except Exception:
            ko = "(번역 실패)"
    return {"id": msg.id, "time": msg.date.astimezone(KST).strftime("%Y-%m-%d %H:%M"),
            "name": name, "label": label, "text": text, "ko": ko or label, "korean": korean}


def save_history(chat_name, entries):
    """비공개 기록 저장소에 날짜별 마크다운으로 추가 (메시지 내용은 공개 저장소·로그에 남기지 않음)"""
    by_day = {}
    for e in entries:
        by_day.setdefault(e["time"][:10], []).append(e)
    headers = {"Authorization": f"Bearer {HISTORY_TOKEN}", "Accept": "application/vnd.github+json"}
    for day, items in sorted(by_day.items()):
        path = f"history/{day[:7]}/{day}.md"
        url = f"https://api.github.com/repos/{HISTORY_REPO}/contents/{path}"
        r = requests.get(url, headers=headers, timeout=30)
        sha, old = None, f"# {chat_name} 대화 기록 {day}\n"
        if r.status_code == 200:
            sha = r.json()["sha"]
            old = base64.b64decode(r.json()["content"]).decode("utf-8")
        seen = set(re.findall(r"<!-- id:(\d+) -->", old))
        add = ""
        for e in items:
            if str(e["id"]) in seen:
                continue
            add += f"\n### {e['time'][11:]} {e['name']} <!-- id:{e['id']} -->\n"
            if e["korean"] or not e["text"]:
                add += f"{e['ko']}\n"
            else:
                add += f"{(e['label'] + ' ') if e['label'] else ''}{e['ko']}\n\n> 원문: {e['text'].replace(chr(10), chr(10) + '> ')}\n"
        if not add:
            continue
        body = {"message": f"기록 {day}", "content": base64.b64encode((old + add).encode("utf-8")).decode()}
        if sha:
            body["sha"] = sha
        w = requests.put(url, headers=headers, json=body, timeout=30)
        if not w.ok:
            raise RuntimeError(f"기록 저장 실패: HTTP {w.status_code}")


asyncio.run(main())
