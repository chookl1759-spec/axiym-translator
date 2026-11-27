# -*- coding: utf-8 -*-
"""10분마다 실행: axiym 방의 새 메시지를 번역해서 봇으로 보냅니다.
공개 저장소이므로 메시지 내용은 로그에 절대 출력하지 않습니다."""
import asyncio
import json
import os
from datetime import timedelta, timezone

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

    count = 0
    async for msg in client.iter_messages(chat.entity, min_id=state["last_id"], reverse=True, limit=200):
        state["last_id"] = max(state["last_id"], msg.id)
        text = (msg.raw_text or "").strip()
        label = media_label(msg)
        if not text and not label:
            continue
        if text and SKIP_KOREAN and mostly_korean(text):
            continue
        sender = await msg.get_sender()
        name = getattr(sender, "first_name", None) or getattr(sender, "title", None) or "알 수 없음"
        if getattr(sender, "last_name", None):
            name = f"{name} {sender.last_name}"
        when = msg.date.astimezone(KST).strftime("%m/%d %H:%M")
        if text:
            try:
                ko = translate_ko(text)
            except Exception:
                ko = "(번역 실패)"
            body = f"{label}\n{ko}".strip() + f"\n\n— 원문 —\n{text}"
        else:
            body = label
        bot_send(BOT_TOKEN, me.id, f"💬 {chat.name} | {name} | {when}\n\n{body}")
        count += 1
        save_state(state)
    save_state(state)
    await client.disconnect()
    print(f"보낸 알림 {count}건")


asyncio.run(main())
