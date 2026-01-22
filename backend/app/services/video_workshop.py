from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Protocol, Sequence
from urllib import request

from ..observability import get_logger
from ..storage_db import DatabaseStore
from .budgets import BudgetLimitExceeded, BudgetService


@dataclass(frozen=True)
class StyleAnchors:
    camera: str
    movement: str
    angle: str
    lighting: str
    palette: str
    location: str
    characters: Sequence[str]


@dataclass(frozen=True)
class StoryboardFrame:
    index: int
    description: str
    duration_seconds: int
    shot_prompt: str


@dataclass(frozen=True)
class ClipPlan:
    index: int
    duration_seconds: int
    prompt: str


@dataclass(frozen=True)
class ClipArtifact:
    index: int
    duration_seconds: int
    storage_key: str
    storage_url: str


@dataclass(frozen=True)
class StorageObject:
    key: str
    url: str


@dataclass(frozen=True)
class PostProcessOptions:
    resolution: str = "1080x1920"
    video_codec: str = "libx264"
    remove_audio: bool = False
    audio_path: Optional[Path] = None
    cover_enabled: bool = True


@dataclass(frozen=True)
class WorkshopResult:
    content_item_id: int
    script: str
    storyboard: List[StoryboardFrame]
    clips: List[ClipArtifact]
    final_video: StorageObject
    cover: Optional[StorageObject]


class ObjectStorage(Protocol):
    def upload_file(
        self,
        file_path: Path,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> StorageObject:
        ...


class Sora2Client:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def generate_clip(
        self,
        prompt: str,
        duration_seconds: int,
        style_anchors: StyleAnchors,
        output_path: Path,
    ) -> Path:
        payload = {
            "prompt": prompt,
            "duration_seconds": duration_seconds,
            "style_anchors": {
                "camera": style_anchors.camera,
                "movement": style_anchors.movement,
                "angle": style_anchors.angle,
                "lighting": style_anchors.lighting,
                "palette": style_anchors.palette,
                "location": style_anchors.location,
                "characters": list(style_anchors.characters),
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/v2/video/generate",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=180) as response:
            output_path.write_bytes(response.read())
        return output_path


class VideoWorkshopService:
    """Сервис генерации видео: сценарий, сториборд, клипы, пост-обработка."""

    def __init__(
        self,
        store: DatabaseStore,
        sora_client: Sora2Client,
        storage: ObjectStorage,
        workdir: Path,
        ffmpeg_path: str = "ffmpeg",
    ) -> None:
        self.store = store
        self.sora_client = sora_client
        self.storage = storage
        self.workdir = workdir
        self.ffmpeg_path = ffmpeg_path
        self.logger = get_logger()
        self.budgets = BudgetService(store)
        self.workdir.mkdir(parents=True, exist_ok=True)

    def generate_script_and_storyboard(
        self,
        topic_title: str,
        topic_angle: str,
        style_anchors: StyleAnchors,
        clip_durations: Sequence[int] = (4, 8, 12),
    ) -> tuple[str, List[StoryboardFrame]]:
        script = (
            "Сценарий:\n"
            f"Тема: {topic_title}.\n"
            f"Угол: {topic_angle}.\n"
            "1) Хук.\n"
            "2) Боль аудитории.\n"
            "3) Решение.\n"
            "4) Демонстрация.\n"
            "5) Результат.\n"
            "6) CTA."
        )
        frames: List[StoryboardFrame] = []
        beats = [
            "Хук: короткое утверждение и интрига.",
            "Проблема аудитории и контекст.",
            "Ключевое решение и объяснение.",
            "Визуальная демонстрация шага.",
            "Фиксация результата и выгоды.",
            "Призыв к действию.",
        ]
        for idx, beat in enumerate(beats, start=1):
            duration = clip_durations[(idx - 1) % len(clip_durations)]
            shot_prompt = (
                f"{beat} Стиль: {style_anchors.camera}, {style_anchors.movement}, "
                f"{style_anchors.angle}, свет {style_anchors.lighting}, палитра "
                f"{style_anchors.palette}, локация {style_anchors.location}."
            )
            frames.append(
                StoryboardFrame(
                    index=idx,
                    description=beat,
                    duration_seconds=duration,
                    shot_prompt=shot_prompt,
                )
            )
        return script, frames

    def plan_clips(self, storyboard: Iterable[StoryboardFrame]) -> List[ClipPlan]:
        plans: List[ClipPlan] = []
        for frame in storyboard:
            plans.append(
                ClipPlan(
                    index=frame.index,
                    duration_seconds=frame.duration_seconds,
                    prompt=frame.shot_prompt,
                )
            )
        return plans

    def generate_clips(
        self, plans: Sequence[ClipPlan], style_anchors: StyleAnchors
    ) -> List[Path]:
        clip_paths: List[Path] = []
        for plan in plans:
            clip_path = self.workdir / f"clip_{plan.index}_{uuid.uuid4().hex}.mp4"
            self.sora_client.generate_clip(
                plan.prompt, plan.duration_seconds, style_anchors, clip_path
            )
            clip_paths.append(clip_path)
        return clip_paths

    def post_process(
        self,
        clips: Sequence[Path],
        options: PostProcessOptions,
    ) -> tuple[Path, Optional[Path]]:
        list_file = self.workdir / f"concat_{uuid.uuid4().hex}.txt"
        list_file.write_text(
            "\n".join([f"file '{clip.as_posix()}'" for clip in clips]),
            encoding="utf-8",
        )
        output_path = self.workdir / f"video_{uuid.uuid4().hex}.mp4"
        filters = [f"scale={options.resolution}"]
        ffmpeg_args = [
            self.ffmpeg_path,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-vf",
            ",".join(filters),
            "-c:v",
            options.video_codec,
        ]
        if options.remove_audio:
            ffmpeg_args.extend(["-an"])
        elif options.audio_path:
            ffmpeg_args.extend(["-i", str(options.audio_path), "-shortest"])
        ffmpeg_args.append(str(output_path))
        self._run_ffmpeg(ffmpeg_args)

        cover_path: Optional[Path] = None
        if options.cover_enabled:
            cover_path = self.workdir / f"cover_{uuid.uuid4().hex}.jpg"
            cover_args = [
                self.ffmpeg_path,
                "-y",
                "-i",
                str(output_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(cover_path),
            ]
            self._run_ffmpeg(cover_args)
        return output_path, cover_path

    def build_video_package(
        self,
        project_id: int,
        content_item_id: int,
        topic_title: str,
        topic_angle: str,
        style_anchors: StyleAnchors,
        postprocess: Optional[PostProcessOptions] = None,
        clip_durations: Optional[Sequence[int]] = None,
    ) -> WorkshopResult:
        script, storyboard = self.generate_script_and_storyboard(
            topic_title, topic_angle, style_anchors, clip_durations or (4, 8, 12)
        )
        total_seconds = sum(frame.duration_seconds for frame in storyboard)
        try:
            self.budgets.record_usage(
                project_id,
                video_seconds_used=total_seconds,
            )
        except BudgetLimitExceeded:
            self.logger.warning(
                "video_budget_blocked",
                extra={
                    "event": "video_budget_blocked",
                    "project_id": project_id,
                    "content_item_id": content_item_id,
                    "video_seconds": total_seconds,
                },
            )
            raise
        plans = self.plan_clips(storyboard)
        clip_paths = self.generate_clips(plans, style_anchors)
        output_path, cover_path = self.post_process(
            clip_paths, postprocess or PostProcessOptions()
        )

        clip_artifacts: List[ClipArtifact] = []
        for index, clip_path in enumerate(clip_paths, start=1):
            clip_obj = self.storage.upload_file(
                clip_path, "video/mp4", metadata={"content_item_id": content_item_id}
            )
            clip_artifacts.append(
                ClipArtifact(
                    index=index,
                    duration_seconds=plans[index - 1].duration_seconds,
                    storage_key=clip_obj.key,
                    storage_url=clip_obj.url,
                )
            )

        final_obj = self.storage.upload_file(
            output_path, "video/mp4", metadata={"content_item_id": content_item_id}
        )
        cover_obj = None
        if cover_path:
            cover_obj = self.storage.upload_file(
                cover_path, "image/jpeg", metadata={"content_item_id": content_item_id}
            )

        metadata_update = {
            "video_script": script,
            "video_storyboard": [
                {
                    "index": frame.index,
                    "description": frame.description,
                    "duration_seconds": frame.duration_seconds,
                    "shot_prompt": frame.shot_prompt,
                }
                for frame in storyboard
            ],
            "video_clips": [
                {
                    "index": clip.index,
                    "duration_seconds": clip.duration_seconds,
                    "storage_key": clip.storage_key,
                    "storage_url": clip.storage_url,
                }
                for clip in clip_artifacts
            ],
            "video_final": {"storage_key": final_obj.key, "storage_url": final_obj.url},
            "video_cover": (
                {"storage_key": cover_obj.key, "storage_url": cover_obj.url}
                if cover_obj
                else None
            ),
            "video_updated_at": datetime.utcnow().isoformat(),
        }
        self.store.update_content_item_metadata(
            project_id, content_item_id, metadata_update
        )

        return WorkshopResult(
            content_item_id=content_item_id,
            script=script,
            storyboard=storyboard,
            clips=clip_artifacts,
            final_video=final_obj,
            cover=cover_obj,
        )

    def run_workshop(
        self,
        project_id: int,
        content_item_id: int,
        topic_title: str,
        topic_angle: str,
        style_anchors: StyleAnchors,
        postprocess: Optional[PostProcessOptions] = None,
        clip_durations: Optional[Sequence[int]] = None,
    ) -> WorkshopResult:
        self.store.update_content_item_status(
            project_id, content_item_id, "running"
        )
        self.store.update_content_item_metadata(
            project_id,
            content_item_id,
            {
                "video_status": "running",
                "video_started_at": datetime.utcnow().isoformat(),
            },
        )
        try:
            result = self.build_video_package(
                project_id,
                content_item_id,
                topic_title,
                topic_angle,
                style_anchors,
                postprocess,
                clip_durations,
            )
        except Exception as exc:
            self.store.update_content_item_status(
                project_id, content_item_id, "failed"
            )
            self.store.update_content_item_metadata(
                project_id,
                content_item_id,
                {
                    "video_status": "failed",
                    "video_error": str(exc),
                    "video_failed_at": datetime.utcnow().isoformat(),
                },
            )
            raise
        self.store.update_content_item_status(project_id, content_item_id, "done")
        self.store.update_content_item_metadata(
            project_id,
            content_item_id,
            {
                "video_status": "done",
                "video_completed_at": datetime.utcnow().isoformat(),
            },
        )
        return result

    def _run_ffmpeg(self, args: Sequence[str]) -> None:
        result = subprocess.run(
            list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "ffmpeg_failed",
                result.stderr.decode("utf-8", errors="ignore"),
            )
