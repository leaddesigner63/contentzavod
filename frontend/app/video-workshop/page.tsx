"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "../../lib/api";
import { useLocalStorage } from "../../lib/useLocalStorage";

type ContentItem = {
  id: number;
  pack_id: number;
  channel: string;
  format: string;
  status: string;
  body: string;
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
            </tr>
          </thead>
          <tbody>
            {videoItems.map((item) => (
              <tr key={item.id}>
                <td>{item.id}</td>
                <td>{item.format}</td>
                <td>
                  <span className="badge">{item.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
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
