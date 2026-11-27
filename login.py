# -*- coding: utf-8 -*-
"""텔레그램 로그인 (두 번 실행)
1) code 칸을 비우고 실행 → 텔레그램으로 로그인 코드가 옵니다.
2) code 칸에 받은 코드를 넣고 다시 실행 → 세션 문자열을 봇으로 보내 줍니다.
텔레그램은 코드를 텔레그램 채팅으로 보내면 무효화하므로, 코드는 GitHub에만 입력하세요.
"""
import asyncio
import base64
import hashlib
import json
import os
import re

from cryptography.fernet import Fernet
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from common import bot_send, env

API_ID = int(env("API_ID"))
API_HASH = env("API_HASH")
BOT_TOKEN = env("BOT_TOKEN")
PHONE = env("TG_PHONE")
PASSWORD = env("TG_2FA", required=False)
CODE = re.sub(r"\D", "", os.environ.get("LOGIN_CODE", ""))
TMP = "login_tmp/pending.bin"

# 임시 로그인 정보는 비밀값으로 만든 키로 암호화해서 저장 (공개 저장소 대비)
FERNET = Fernet(base64.urlsafe_b64encode(hashlib.sha256((API_HASH + BOT_TOKEN).encode()).digest()))


async def step1():
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    sent = await client.send_code_request(PHONE)
    data = json.dumps({"s": client.session.save(), "h": sent.phone_code_hash}).encode()
    os.makedirs(os.path.dirname(TMP), exist_ok=True)
    with open(TMP, "wb") as f:
        f.write(FERNET.encrypt(data))
    await client.disconnect()
    print("텔레그램으로 로그인 코드를 보냈습니다. 코드를 텔레그램 채팅에 보내지 말고, "
          "login 워크플로를 다시 실행하면서 code 칸에 입력하세요. (몇 분 안에)")


async def step2():
    try:
        with open(TMP, "rb") as f:
            data = json.loads(FERNET.decrypt(f.read()))
    except Exception:
        raise SystemExit("1단계 정보가 없습니다. code 칸을 비우고 다시 1단계부터 실행해 주세요.")
    client = TelegramClient(StringSession(data["s"]), API_ID, API_HASH)
    await client.connect()
    try:
        await client.sign_in(PHONE, CODE, phone_code_hash=data["h"])
    except SessionPasswordNeededError:
        if not PASSWORD:
            raise SystemExit("2단계 인증 비밀번호가 필요합니다. Secret TG_2FA 를 추가한 뒤 1단계부터 다시 해 주세요.")
        await client.sign_in(password=PASSWORD)
    me = await client.get_me()
    session = client.session.save()
    bot_send(BOT_TOKEN, me.id, "✅ 로그인 성공. 다음 메시지의 문자열 전체를 복사해서 GitHub Secret 'TG_SESSION' 에 넣으세요. "
                                "계정 열쇠이니 공유하지 마시고, 넣은 뒤 두 메시지 모두 삭제하세요.")
    bot_send(BOT_TOKEN, me.id, session)
    await client.disconnect()
    os.remove(TMP)
    print("완료: 세션 문자열을 봇으로 보냈습니다.")


asyncio.run(step2() if CODE else step1())
