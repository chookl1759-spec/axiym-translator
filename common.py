# -*- coding: utf-8 -*-
import os
import re
import sys
import time

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
    # 가끔 연결이 끊기는 경우가 있어 최대 5번 재시도
    for attempt in range(5):
        try:
            return requests.post(f"https://api.telegram.org/bot{token}/{method}", data=data, timeout=60)
        except requests.exceptions.RequestException:
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))


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


LAST_ERROR = []


def _gtx(chunk):
    # 구글 번역 공개 엔드포인트 (서버에서도 비교적 잘 동작)
    r = requests.post(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": "auto", "tl": "ko", "dt": "t"},
        data={"q": chunk},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    r.raise_for_status()
    return "".join(part[0] for part in r.json()[0] if part and part[0])


def _deep(chunk):
    return GoogleTranslator(source="auto", target="ko").translate(chunk) or ""


def _mymemory(chunk):
    from deep_translator import MyMemoryTranslator
    return MyMemoryTranslator(source="en-GB", target="ko-KR").translate(chunk) or ""


def translate_ko(text):
    out = []
    for i in range(0, len(text), 1800):
        chunk = text[i:i + 1800]
        for fn in (_gtx, _gtx, _deep, _mymemory):
            try:
                out.append(fn(chunk))
                break
            except Exception as e:  # 내용은 남기지 않고 오류 종류만 기록
                LAST_ERROR.append(f"{fn.__name__}:{type(e).__name__}:{getattr(getattr(e, 'response', None), 'status_code', '')}")
                time.sleep(1)
        else:
            raise RuntimeError("all translators failed")
    return "".join(out)


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
