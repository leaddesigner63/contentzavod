from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Mapping, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import Request

from .. import schemas
from ..storage_db import DatabaseStore


@dataclass(frozen=True)
class RedirectResult:
    redirect_url: str
    click_event: schemas.ClickEvent


class RedirectService:
    def __init__(self, store: DatabaseStore, slug_length: int = 7) -> None:
        self.store = store
        self.slug_length = slug_length

    def create_link(
        self, project_id: int, payload: schemas.RedirectLinkCreate
    ) -> schemas.RedirectLink:
        slug = payload.slug or self._generate_slug()
        while self.store.get_redirect_link_by_slug(slug):
            slug = self._generate_slug()
        payload.slug = slug
        return self.store.create_redirect_link(project_id, payload)

    def resolve(self, slug: str, request: Request) -> RedirectResult:
        link = self.store.get_redirect_link_by_slug(slug)
        if not link or not link.is_active:
            raise KeyError("redirect_not_found")
        query_params = dict(request.query_params)
        utm_params = self._extract_utm_params(query_params, link.utm_params or {})
        redirect_url = self._build_redirect_url(link.target_url, utm_params, query_params)
        event = self.store.create_click_event(
            project_id=link.project_id,
            redirect_link_id=link.id,
            content_item_id=link.content_item_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            referrer=request.headers.get("referer"),
            utm_params=utm_params,
            query_params=query_params,
        )
        return RedirectResult(redirect_url=redirect_url, click_event=event)

    def _generate_slug(self) -> str:
        return secrets.token_urlsafe(self.slug_length)[: self.slug_length]

    @staticmethod
    def _extract_utm_params(
        query_params: Mapping[str, str], base_params: Mapping[str, str]
    ) -> dict:
        utm_params = dict(base_params)
        for key, value in query_params.items():
            if key.startswith("utm_"):
                utm_params[key] = value
        return utm_params

    @staticmethod
    def _build_redirect_url(
        target_url: str, utm_params: Mapping[str, str], query_params: Mapping[str, str]
    ) -> str:
        parsed = urlparse(target_url)
        merged = dict(parse_qsl(parsed.query))
        merged.update(query_params)
        merged.update(utm_params)
        return urlunparse(parsed._replace(query=urlencode(merged)))
