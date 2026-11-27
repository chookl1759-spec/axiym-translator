# axiym-translator

텔레그램 axiym 방의 새 메시지를 10분마다 한국어로 번역해서 개인 봇으로 알려 줍니다 (GitHub Actions, 무료).

- `login` 워크플로: 처음 한 번 텔레그램 로그인 → 세션 문자열을 봇으로 받음 → Secret `TG_SESSION`에 저장
- `translate` 워크플로: 10분마다 실행

필요한 Secrets: `API_ID`, `API_HASH`, `BOT_TOKEN`, `TG_PHONE`, `TG_SESSION` (2단계 인증을 쓰면 `TG_2FA`)
메시지 내용과 비밀값은 저장소와 로그에 남지 않습니다.
