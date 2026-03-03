from __future__ import annotations

import getpass

from telethon import TelegramClient
from telethon.sessions import StringSession


def main() -> None:
    api_id = int(input("Telegram API ID: ").strip())
    api_hash = input("Telegram API HASH: ").strip()
    phone = input("Phone number (e.g. +86138xxxx): ").strip()

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        client.send_code_request(phone)
        code = input("Login code: ").strip()
        try:
            client.sign_in(phone=phone, code=code)
        except Exception:
            password = getpass.getpass("2FA password (if enabled): ")
            client.sign_in(password=password)
        print("\nTELEGRAM_USER_STRING_SESSION=")
        print(client.session.save())


if __name__ == "__main__":
    main()
