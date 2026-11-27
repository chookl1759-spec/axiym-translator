# -*- coding: utf-8 -*-
import os
import re
import sys

import requests
from deep_translator import GoogleTranslator

HANGUL = re.compile(r"[가-힣]")
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


def env(name, required=True, default=None):
    v = os.environ.get(name, "").strip()
    if not v and required:
        sys.exit(f"GitHub Secret '{name}' 이(가) 비어 있습니다.")
    return v or default


def bot_api(token, method, **data):
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", data=data, timeout=60)
    return r


def bot_send(token, chat_id, text):
    for i in range(0, len(text), 4000):
        r = bot_api(token, "sendMessage", chat_id=chat_id, text=text[i:i + 4000])
        if not r.ok:
            raise RuntimeError(f"봇 전송 실패: HTTP {r.status_code}")


def mostly_korean(text):
    letters = LETTER.findall(text)
    if not letters:
        return False
    return len(HANGUL.findall(text)) / len(letters) > 0.5


def translate_ko(text):
    tr = GoogleTranslator(source="auto", target="ko")
    return "".join(tr.translate(text[i:i + 4500]) or "" for i in range(0, len(text), 4500))


def media_label(msg):
    if msg.photo:
        return "[사진]"
    if msg.video:
        return "[동영상]"
    if msg.voice or msg.audio:
        return "[음성]"
    if msg.sticker:
        return "[스티커]"
    if msg.document:
        name = getattr(msg.file, "name", None) or "파일"
        return f"[파일: {name}]"
    return ""
