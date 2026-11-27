# -*- coding: utf-8 -*-
"""기록 저장소에서 '(번역 실패)' 로 남은 메시지를 다시 번역해서 채웁니다."""
import base64
import re
import time

import requests

from common import LAST_ERROR, env, translate_ko

TOKEN = env("HISTORY_TOKEN")
REPO = env("HISTORY_REPO", required=False, default="chookl1759-spec/axiym-history")
H = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}
API = f"https://api.github.com/repos/{REPO}"


def files():
    r = requests.get(f"{API}/git/trees/HEAD?recursive=1", headers=H, timeout=30)
    r.raise_for_status()
    return sorted(t["path"] for t in r.json()["tree"] if t["path"].startswith("history/") and t["path"].endswith(".md"))


def fix_block(block):
    if "(번역 실패)" not in block or "> 원문:" not in block:
        return block, False
    orig_lines = []
    started = False
    for line in block.split("\n"):
        if line.startswith("> 원문: "):
            started = True
            orig_lines.append(line[len("> 원문: "):])
        elif started and line.startswith("> "):
            orig_lines.append(line[2:])
        elif started and line == ">":
            orig_lines.append("")
        elif started:
            break
    ko = translate_ko("\n".join(orig_lines))
    return block.replace("(번역 실패)", ko, 1), True


def main():
    info = requests.get(API, headers=H, timeout=30).json()
    if not info.get("private"):
        raise SystemExit("기록 저장소가 비공개가 아닙니다.")
    fixed_total = 0
    for path in files():
        r = requests.get(f"{API}/contents/{path}", headers=H, timeout=30).json()
        text = base64.b64decode(r["content"]).decode("utf-8")
        if "(번역 실패)" not in text:
            continue
        parts = re.split(r"(?m)^(?=### )", text)
        changed = 0
        for i, block in enumerate(parts):
            try:
                parts[i], did = fix_block(block)
                changed += did
            except Exception:
                pass
            time.sleep(0.3)
        if changed:
            new = "".join(parts)
            w = requests.put(f"{API}/contents/{path}", headers=H, timeout=30, json={
                "message": f"번역 보완 {path[-13:-3]}", "sha": r["sha"],
                "content": base64.b64encode(new.encode("utf-8")).decode()})
            w.raise_for_status()
            fixed_total += changed
            print(f"{path[-13:-3]}: {changed}건 보완")
    print(f"총 {fixed_total}건 보완. 오류 종류: {sorted(set(LAST_ERROR))[:10]}")


main()
