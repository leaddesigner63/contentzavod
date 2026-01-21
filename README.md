# Универсальный контент-завод (MVP)

Минимальный каркас сервиса по ТЗ: FastAPI API для админки, базовая модель данных и заглушки пайплайна (ingest → planner → producer → QC → publisher).

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

## Структура

- `backend/app/main.py` — FastAPI приложение и маршруты.
- `backend/app/schemas.py` — Pydantic-схемы данных.
- `backend/app/storage.py` — in-memory хранилище (изоляция по проектам).
- `backend/app/services/pipeline.py` — заглушка пайплайна генерации.

## Статус

Этот репозиторий содержит минимальный исполнимый MVP-каркас, который можно развивать до полнофункциональной системы.
