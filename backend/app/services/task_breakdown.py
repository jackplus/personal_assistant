from __future__ import annotations

import json
import re

from app.config import settings
from app.models import Task


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"[。.!?\n;；]+", text)
    return [p.strip() for p in parts if p.strip()]


def _heuristic_breakdown(task: Task, source_message: str | None) -> tuple[str, list[str], list[str]]:
    context = " ".join(x for x in [task.title, task.description or "", source_message or ""]).strip()
    sentences = _split_sentences(context)

    summary = sentences[0] if sentences else task.title
    todo_items: list[str] = []
    for sentence in sentences:
        lower = sentence.lower()
        if any(k in lower for k in ["follow", "need", "todo", "prepare", "send", "review", "安排", "跟进", "整理", "确认", "提交"]):
            todo_items.append(sentence)
    if not todo_items:
        todo_items = [
            f"澄清任务目标：{task.title}",
            "拆分执行步骤并确定负责人与截止时间",
            "执行后同步结果并关闭任务",
        ]

    stakeholders = []
    if task.assignee_name:
        stakeholders.append(task.assignee_name)

    for match in re.findall(r"@([A-Za-z0-9_]+)", context):
        if match not in stakeholders:
            stakeholders.append(match)

    for keyword, name in [
        ("客户", "客户方"),
        ("finance", "Finance"),
        ("财务", "Finance"),
        ("legal", "Legal"),
        ("法务", "Legal"),
        ("产品", "Product"),
        ("运营", "Operations"),
    ]:
        if keyword.lower() in context.lower() and name not in stakeholders:
            stakeholders.append(name)

    if not stakeholders:
        stakeholders = ["Task Owner"]

    return summary, todo_items[:8], stakeholders[:8]


def _openai_breakdown(task: Task, source_message: str | None) -> tuple[str, list[str], list[str]] | None:
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        prompt = (
            "You create execution breakdown for a task. Return strict JSON with keys: "
            "summary(string), todo_items(array of string), stakeholders(array of string). "
            "Keep todo_items specific and actionable."
        )
        user_context = {
            "task": {
                "title": task.title,
                "description": task.description,
                "assignee_name": task.assignee_name,
                "due_at": task.due_at.isoformat() if task.due_at else None,
                "work_category": task.work_category,
            },
            "source_message": source_message,
        }
        response = client.responses.create(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(user_context, ensure_ascii=False)},
            ],
        )
        data = json.loads(response.output_text)
        summary = str(data.get("summary") or task.title)
        todo_items = [str(x).strip() for x in data.get("todo_items", []) if str(x).strip()]
        stakeholders = [str(x).strip() for x in data.get("stakeholders", []) if str(x).strip()]
        if not todo_items:
            return None
        if not stakeholders:
            stakeholders = [task.assignee_name or "Task Owner"]
        return summary, todo_items[:8], stakeholders[:8]
    except Exception:
        return None


def build_task_breakdown(task: Task, source_message: str | None) -> tuple[str, list[str], list[str]]:
    return _openai_breakdown(task, source_message) or _heuristic_breakdown(task, source_message)
