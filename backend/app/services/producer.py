from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Sequence

from .. import models, schemas
from ..storage_db import DatabaseStore


class TaskQueue(Protocol):
    def enqueue(self, task_name: str, payload: dict) -> str:
        ...


class LlmClient(Protocol):
    def generate(self, prompt: str, metadata: dict) -> str:
        ...


class MockLlmClient:
    def generate(self, prompt: str, metadata: dict) -> str:
        topic = metadata.get("topic_title", "Контент")
        channel = metadata.get("channel", "канал")
        tone = metadata.get("tone", "нейтральный")
        angle = metadata.get("angle")
        intro = f"{topic} — {channel} ({tone})."
        if angle:
            intro = f"{intro} Угол: {angle}."
        return f"{intro}\n\n{prompt}\n\nCTA: {metadata.get('cta', 'Напишите нам')}"


@dataclass(frozen=True)
class ProductionResult:
    content_items: List[schemas.ContentItem]


class ProducerService:
    """Сервис генерации контента: тексты, промпты изображений и видео."""

    def __init__(
        self,
        store: DatabaseStore,
        task_queue: Optional[TaskQueue] = None,
        llm_client: Optional[LlmClient] = None,
    ) -> None:
        self.store = store
        self.task_queue = task_queue
        self.llm_client = llm_client or MockLlmClient()

    def enqueue_production(self, project_id: int, pack_id: int) -> Optional[str]:
        if not self.task_queue:
            return None
        return self.task_queue.enqueue(
            "produce_pack", {"project_id": project_id, "pack_id": pack_id}
        )

    def produce_pack(
        self,
        project_id: int,
        pack_id: int,
        topic_id: int,
        channels: Optional[Sequence[str]] = None,
    ) -> ProductionResult:
        channels = list(channels or ["telegram", "vk", "blog"])
        brand_config = self._get_active_brand_config(project_id)
        topic = self.store.session.get(models.Topic, topic_id)
        topic_title = topic.title if topic else f"Тема {topic_id}"
        topic_angle = topic.angle if topic else None
        items: List[schemas.ContentItem] = []
        for channel in channels:
            fmt = "longread" if channel == "blog" else "post"
            text_prompt_key = f"producer:text:{channel}"
            text_prompt = self._build_prompt(
                project_id,
                prompt_key=text_prompt_key,
                fallback=f"Создай {fmt} для канала {channel}.",
                brand_config=brand_config,
                topic_title=topic_title,
                topic_angle=topic_angle,
            )
            image_prompt = self._build_prompt(
                project_id,
                prompt_key="producer:image",
                fallback=f"Обложка для темы {topic_title}.",
                brand_config=brand_config,
                topic_title=topic_title,
                topic_angle=topic_angle,
            )
            video_prompt = self._build_prompt(
                project_id,
                prompt_key="producer:video",
                fallback=f"Видео по теме {topic_title}.",
                brand_config=brand_config,
                topic_title=topic_title,
                topic_angle=topic_angle,
            )
            cta = brand_config.cta_policy if brand_config else "Подпишитесь и задайте вопрос"
            hashtags = self._hashtags_from_brand(brand_config)
            metadata: Dict[str, str] = {
                "cta": cta,
                "hashtags": hashtags,
                "alt": f"Иллюстрация для темы {topic_title}",
                "video_prompt": self.llm_client.generate(
                    video_prompt,
                    {
                        "channel": channel,
                        "tone": brand_config.tone if brand_config else "нейтральный",
                        "topic_title": topic_title,
                        "angle": topic_angle,
                        "cta": cta,
                    },
                ),
                "image_prompt": self.llm_client.generate(
                    image_prompt,
                    {
                        "channel": channel,
                        "tone": brand_config.tone if brand_config else "нейтральный",
                        "topic_title": topic_title,
                        "angle": topic_angle,
                        "cta": cta,
                    },
                ),
            }
            if brand_config:
                metadata["brand_config_id"] = str(brand_config.id)
                metadata["brand_config_version"] = str(brand_config.version)
            prompt_version = self._get_prompt_version(project_id, text_prompt_key)
            if prompt_version:
                metadata["prompt_version_id"] = str(prompt_version.id)
                metadata["prompt_key"] = prompt_version.prompt_key
            item = self.store.create_content_item(
                project_id,
                schemas.ContentItemCreate(
                    pack_id=pack_id,
                    channel=channel,
                    format=fmt,
                    body=self.llm_client.generate(
                        text_prompt,
                        {
                            "channel": channel,
                            "tone": brand_config.tone if brand_config else "нейтральный",
                            "topic_title": topic_title,
                            "angle": topic_angle,
                            "cta": cta,
                        },
                    ),
                    metadata=metadata,
                ),
            )
            items.append(item)
        return ProductionResult(content_items=items)

    def _get_active_brand_config(self, project_id: int) -> Optional[schemas.BrandConfig]:
        configs = self.store.list_brand_configs(project_id)
        for config in configs:
            if config.is_active:
                return config
        return configs[-1] if configs else None

    def _get_prompt_version(
        self, project_id: int, prompt_key: str
    ) -> Optional[schemas.PromptVersion]:
        prompts = self.store.list_prompt_versions(project_id)
        matching = [prompt for prompt in prompts if prompt.prompt_key == prompt_key]
        for prompt in matching:
            if prompt.is_active:
                return prompt
        return matching[-1] if matching else None

    def _build_prompt(
        self,
        project_id: int,
        prompt_key: str,
        fallback: str,
        brand_config: Optional[schemas.BrandConfig],
        topic_title: str,
        topic_angle: Optional[str],
    ) -> str:
        prompt_version = self._get_prompt_version(project_id, prompt_key)
        base = prompt_version.content if prompt_version else fallback
        brand_context = ""
        if brand_config:
            offers = ", ".join(brand_config.offers) if brand_config.offers else "нет"
            rubrics = ", ".join(brand_config.rubrics) if brand_config.rubrics else "нет"
            forbidden = (
                ", ".join(brand_config.forbidden) if brand_config.forbidden else "нет"
            )
            brand_context = (
                "\n".join(
                    [
                        f"Тон: {brand_config.tone}.",
                        f"Аудитория: {brand_config.audience}.",
                        f"Офферы: {offers}.",
                        f"Рубрики: {rubrics}.",
                        f"Запреты: {forbidden}.",
                        f"CTA-политика: {brand_config.cta_policy}.",
                    ]
                )
                + "\n"
            )
        angle_line = f"Угол подачи: {topic_angle}." if topic_angle else ""
        return f"{base}\n{brand_context}Тема: {topic_title}. {angle_line}".strip()

    @staticmethod
    def _hashtags_from_brand(brand_config: Optional[schemas.BrandConfig]) -> str:
        if not brand_config:
            return "#контент"
        tags = brand_config.rubrics or brand_config.offers
        if not tags:
            return "#контент"
        return " ".join(f"#{tag.strip().replace(' ', '_')}" for tag in tags if tag.strip())
