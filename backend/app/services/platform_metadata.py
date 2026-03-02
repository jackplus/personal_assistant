from __future__ import annotations

from typing import Any


def parse_platform_metadata(platform: str, payload: dict[str, Any]) -> dict[str, str | None]:
    if platform == "telegram":
        from_user = payload.get("from") or {}
        chat = payload.get("chat") or {}
        return {
            "platform": "telegram",
            "platform_user_id": str(from_user.get("id")) if from_user.get("id") is not None else None,
            "platform_chat_id": str(chat.get("id")) if chat.get("id") is not None else None,
            "platform_message_id": str(payload.get("message_id")) if payload.get("message_id") is not None else None,
            "username": from_user.get("username"),
            "display_name": (
                " ".join(x for x in [from_user.get("first_name"), from_user.get("last_name")] if x).strip() or None
            ),
        }

    return {
        "platform": platform,
        "platform_user_id": None,
        "platform_chat_id": None,
        "platform_message_id": None,
        "username": None,
        "display_name": None,
    }
