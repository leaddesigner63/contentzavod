"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { getRolesFromToken, hasAnyRole, type Role } from "../../lib/auth";
import { apiFetch } from "../../lib/api";
import { useLocalStorage } from "../../lib/useLocalStorage";

type VideoMetadata = {
  video_status?: string;
  video_script?: string;
  video_storyboard?: {
    index: number;
    description: string;
    duration_seconds: number;
    shot_prompt: string;
  }[];
  video_clips?: {
    index: number;
    duration_seconds: number;
    storage_url: string;
  }[];
  video_final?: {
    storage_url: string;
  };
  video_cover?: {
    storage_url: string;
  } | null;
  video_error?: string;
};

type ContentItem = {
  id: number;
  pack_id: number;
  channel: string;
  format: string;
  status: string;
  body: string;
  metadata: VideoMetadata;
};

type ContentPack = {
  id: number;
  topic_id: number;
  status: string;
};

export default function VideoWorkshopPage() {
  const [token] = useLocalStorage("contentzavod-token", "");
  const [projectId] = useLocalStorage("contentzavod-project", "1");
  const [apiBaseUrl] = useLocalStorage(
    "contentzavod-api-base",
    "http://localhost:8000"
  );
  const roles = useMemo<Role[]>(
    () => getRolesFromToken(token),
    [token]
  );
  const canEdit = hasAnyRole(roles, ["Admin", "Editor"]);

  const [videoItems, setVideoItems] = useState<ContentItem[]>([]);
  const [packs, setPacks] = useState<ContentPack[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState<Record<number, boolean>>({});

  const defaultStyleAnchors = {
    camera: "cinematic",
    movement: "smooth",
    angle: "wide",
    lighting: "soft",
    palette: "warm",
    location: "studio",
    characters: [],
  };
  const [styleAnchors, setStyleAnchors] = useState(defaultStyleAnchors);
  const [clipDurations, setClipDurations] = useState("4,8,12");
  const [postprocess, setPostprocess] = useState({
    resolution: "1080p",
    video_codec: "h264",
    remove_audio: false,
    audio_path: "",
    cover_enabled: true,
  });
  const [manualContentItemId, setManualContentItemId] = useState("");

  const loadVideoData = useCallback(async () => {
    if (!projectId) return;
    try {
      setError(null);
      const [itemsData, packsData] = await Promise.all([
        apiFetch<ContentItem[]>(
          `/projects/${projectId}/content-items`,
          {},
          token,
          apiBaseUrl
        ),
        apiFetch<ContentPack[]>(
          `/projects/${projectId}/content-packs`,
          {},
          token,
          apiBaseUrl
        ),
      ]);
      const filtered = itemsData.filter((item) =>
        [item.channel, item.format].some((value) =>
          value.toLowerCase().includes("video")
        )
      );
      setVideoItems(filtered);
      setPacks(packsData);
    } catch (err) {
      setError((err as { message: string }).message);
    }
  }, [projectId, token, apiBaseUrl]);

  useEffect(() => {
    loadVideoData();
  }, [loadVideoData]);

  const runVideoWorkshop = async (contentItemId: number) => {
    if (!projectId || !canEdit) return;
    setIsRunning((prev) => ({ ...prev, [contentItemId]: true }));
    try {
      await apiFetch(
        `/projects/${projectId}/video-workshop/run`,
        {
          method: "POST",
          body: JSON.stringify({
            content_item_id: contentItemId,
            style_anchors: styleAnchors,
            clip_durations: clipDurations
              .split(",")
              .map((value) => Number(value.trim()))
              .filter((value) => !Number.isNaN(value)),
            postprocess: {
              resolution: postprocess.resolution,
              video_codec: postprocess.video_codec,
              remove_audio: postprocess.remove_audio,
              audio_path: postprocess.audio_path || null,
              cover_enabled: postprocess.cover_enabled,
            },
          }),
        },
        token,
        apiBaseUrl
      );
      await loadVideoData();
    } catch (err) {
      setError((err as { message: string }).message);
    } finally {
      setIsRunning((prev) => ({ ...prev, [contentItemId]: false }));
    }
  };

  return (
    <div className="section-grid">
      <section className="card">
        <h3>Очередь видео-цеха</h3>
        {error && <div className="notice">Ошибка: {error}</div>}
        {!canEdit && (
          <div className="notice">
            Запуск видео доступен только ролям Admin и Editor.
          </div>
        )}
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Формат</th>
              <th>Статус</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {videoItems.map((item) => (
              <tr key={item.id}>
                <td>{item.id}</td>
                <td>{item.format}</td>
                <td>
                  <span className="badge">
                    {item.metadata?.video_status ?? item.status}
                  </span>
                </td>
                <td>
                  <button
                    className="button"
                    onClick={() => runVideoWorkshop(item.id)}
                    disabled={isRunning[item.id] || !canEdit}
                  >
                    {isRunning[item.id] ? "Запуск..." : "Запустить"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="list">
          {videoItems.map((item) => (
            <div key={`artifact-${item.id}`} className="card">
              <strong>Видео #{item.id}</strong>
              {item.metadata?.video_error && (
                <div className="notice">
                  Ошибка: {item.metadata.video_error}
                </div>
              )}
              <div>
                <span className="badge">
                  {item.metadata?.video_status ?? item.status}
                </span>
              </div>
              {item.metadata?.video_script && (
                <p>Сценарий: {item.metadata.video_script}</p>
              )}
              {item.metadata?.video_storyboard && (
                <div>
                  <strong>Сториборд:</strong>
                  <ul>
                    {item.metadata.video_storyboard.map((frame) => (
                      <li key={frame.index}>
                        #{frame.index} ({frame.duration_seconds} сек) —{" "}
                        {frame.description}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {item.metadata?.video_final?.storage_url && (
                <div>
                  Финальный ролик:{" "}
                  <a
                    href={item.metadata.video_final.storage_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    открыть
                  </a>
                </div>
              )}
              {item.metadata?.video_cover?.storage_url && (
                <div>
                  Обложка:{" "}
                  <a
                    href={item.metadata.video_cover.storage_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    открыть
                  </a>
                </div>
              )}
              {item.metadata?.video_clips && (
                <div>
                  <strong>Клипы:</strong>
                  <ul>
                    {item.metadata.video_clips.map((clip) => (
                      <li key={clip.index}>
                        Клип #{clip.index} ({clip.duration_seconds} сек) —{" "}
                        <a
                          href={clip.storage_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          открыть
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h3>Настройки запуска</h3>
        {!canEdit && (
          <div className="notice">
            Доступно только для ролей Admin и Editor.
          </div>
        )}
        <div className="grid">
          <label>
            Камера
            <input
              value={styleAnchors.camera}
              onChange={(event) =>
                setStyleAnchors((prev) => ({
                  ...prev,
                  camera: event.target.value,
                }))
              }
              disabled={!canEdit}
            />
          </label>
          <label>
            Движение
            <input
              value={styleAnchors.movement}
              onChange={(event) =>
                setStyleAnchors((prev) => ({
                  ...prev,
                  movement: event.target.value,
                }))
              }
              disabled={!canEdit}
            />
          </label>
          <label>
            Ракурс
            <input
              value={styleAnchors.angle}
              onChange={(event) =>
                setStyleAnchors((prev) => ({
                  ...prev,
                  angle: event.target.value,
                }))
              }
              disabled={!canEdit}
            />
          </label>
          <label>
            Свет
            <input
              value={styleAnchors.lighting}
              onChange={(event) =>
                setStyleAnchors((prev) => ({
                  ...prev,
                  lighting: event.target.value,
                }))
              }
              disabled={!canEdit}
            />
          </label>
          <label>
            Палитра
            <input
              value={styleAnchors.palette}
              onChange={(event) =>
                setStyleAnchors((prev) => ({
                  ...prev,
                  palette: event.target.value,
                }))
              }
              disabled={!canEdit}
            />
          </label>
          <label>
            Локация
            <input
              value={styleAnchors.location}
              onChange={(event) =>
                setStyleAnchors((prev) => ({
                  ...prev,
                  location: event.target.value,
                }))
              }
              disabled={!canEdit}
            />
          </label>
        </div>
        <label>
          Персонажи (через запятую)
          <input
            value={styleAnchors.characters.join(", ")}
            onChange={(event) =>
              setStyleAnchors((prev) => ({
                ...prev,
                characters: event.target.value
                  .split(",")
                  .map((value) => value.trim())
                  .filter(Boolean),
              }))
            }
            disabled={!canEdit}
          />
        </label>
        <label>
          Длительности клипов (сек)
          <input
            value={clipDurations}
            onChange={(event) => setClipDurations(event.target.value)}
            disabled={!canEdit}
          />
        </label>
        <div className="grid">
          <label>
            Разрешение
            <input
              value={postprocess.resolution}
              onChange={(event) =>
                setPostprocess((prev) => ({
                  ...prev,
                  resolution: event.target.value,
                }))
              }
              disabled={!canEdit}
            />
          </label>
          <label>
            Кодек
            <input
              value={postprocess.video_codec}
              onChange={(event) =>
                setPostprocess((prev) => ({
                  ...prev,
                  video_codec: event.target.value,
                }))
              }
              disabled={!canEdit}
            />
          </label>
        </div>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={postprocess.remove_audio}
            onChange={(event) =>
              setPostprocess((prev) => ({
                ...prev,
                remove_audio: event.target.checked,
              }))
            }
            disabled={!canEdit}
          />
          Удалять аудио
        </label>
        <label>
          Путь к аудио (если заменяем)
          <input
            value={postprocess.audio_path}
            onChange={(event) =>
              setPostprocess((prev) => ({
                ...prev,
                audio_path: event.target.value,
              }))
            }
            disabled={!canEdit}
          />
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={postprocess.cover_enabled}
            onChange={(event) =>
              setPostprocess((prev) => ({
                ...prev,
                cover_enabled: event.target.checked,
              }))
            }
            disabled={!canEdit}
          />
          Генерировать обложку
        </label>
        <div className="row">
          <input
            placeholder="ID контент-единицы"
            value={manualContentItemId}
            onChange={(event) => setManualContentItemId(event.target.value)}
            disabled={!canEdit}
          />
          <button
            onClick={() => runVideoWorkshop(Number(manualContentItemId))}
            disabled={!canEdit || !manualContentItemId}
          >
            Запустить вручную
          </button>
        </div>
      </section>

      <section className="card">
        <h3>Контент-пакеты с видео</h3>
        <div className="list">
          {packs.map((pack) => (
            <div key={pack.id}>
              Пакет #{pack.id} (Тема #{pack.topic_id}) — {pack.status}
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h3>Рекомендации по Sora 2</h3>
        <ul>
          <li>Фиксируйте якоря стиля: камера, свет, палитра, локации.</li>
          <li>Проверяйте соответствие сториборда и клипов перед сборкой.</li>
          <li>Контролируйте расход видео-секунд по бюджету проекта.</li>
        </ul>
      </section>
    </div>
  );
}
