"use client";

import { useCallback, useEffect, useState } from "react";

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
    if (!projectId) return;
    setIsRunning((prev) => ({ ...prev, [contentItemId]: true }));
    try {
      await apiFetch(
        `/projects/${projectId}/video-workshop/run`,
        {
          method: "POST",
          body: JSON.stringify({
            content_item_id: contentItemId,
            style_anchors: defaultStyleAnchors,
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
                    disabled={isRunning[item.id]}
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
