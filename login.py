# -*- coding: utf-8 -*-
"""한 번만 실행: 텔레그램 로그인 후 세션 문자열을 봇으로 보내 줍니다."""
import asyncio
import re
import time

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from common import bot_api, bot_send, env

API_ID = int(env("API_ID"))
API_HASH = env("API_HASH")
BOT_TOKEN = env("BOT_TOKEN")
PHONE = env("TG_PHONE")
PASSWORD = env("TG_2FA", required=False)
WAIT_SEC = 300


def updates(offset=None):
    r = bot_api(BOT_TOKEN, "getUpdates", timeout=0, **({"offset": offset} if offset else {}))
    if r.status_code == 409:  # 웹훅이 걸려 있으면 해제
        bot_api(BOT_TOKEN, "deleteWebhook")
        r = bot_api(BOT_TOKEN, "getUpdates", timeout=0, **({"offset": offset} if offset else {}))
    r.raise_for_status()
    return r.json()["result"]


def wait_for_code():
    old = updates()
    offset = old[-1]["update_id"] + 1 if old else None
    deadline = time.time() + WAIT_SEC
    while time.time() < deadline:
        for u in updates(offset):
            offset = u["update_id"] + 1
            text = (u.get("message") or {}).get("text") or ""
            digits = re.sub(r"\D", "", text)
            if 5 <= len(digits) <= 6:
                return digits, u["message"]["chat"]["id"]
        time.sleep(3)
    raise SystemExit("5분 안에 인증코드가 오지 않았습니다. 다시 실행해 주세요.")


async def main():
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    sent = await client.send_code_request(PHONE)
    print("인증코드를 보냈습니다. 텔레그램 봇에게 숫자 사이를 띄어 보내 주세요 (예: 1 2 3 4 5). 5분 기다립니다.")
    code, chat_id = wait_for_code()
    print("::add-mask::" + code)
    try:
        await client.sign_in(PHONE, code, phone_code_hash=sent.phone_code_hash)
    except SessionPasswordNeededError:
        if not PASSWORD:
            bot_send(BOT_TOKEN, chat_id, "2단계 인증 비밀번호가 필요합니다. GitHub Secret TG_2FA 를 추가하고 다시 실행해 주세요.")
            raise SystemExit("2단계 인증 비밀번호(TG_2FA) 필요")
        await client.sign_in(password=PASSWORD)
    me = await client.get_me()
    session = client.session.save()
    bot_send(BOT_TOKEN, me.id, "✅ 로그인 성공. 아래 문자열 전체를 복사해서 GitHub Secret 'TG_SESSION' 에 넣으세요. "
                                "계정 열쇠이니 다른 곳에 공유하지 마시고, 넣은 뒤 이 메시지는 삭제하세요.")
    bot_send(BOT_TOKEN, me.id, session)
    await client.disconnect()
    print("완료: 세션 문자열을 봇으로 보냈습니다.")


asyncio.run(main())
