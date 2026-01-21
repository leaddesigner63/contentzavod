"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "../../lib/api";
import { useLocalStorage } from "../../lib/useLocalStorage";

type ContentPack = {
  id: number;
  topic_id: number;
  description?: string | null;
  status: string;
  created_at: string;
};

type ContentItem = {
  id: number;
  pack_id: number;
  channel: string;
  format: string;
  body: string;
  status: string;
};

export default function ProductionPage() {
  const [token] = useLocalStorage("contentzavod-token", "");
  const [projectId] = useLocalStorage("contentzavod-project", "1");
  const [apiBaseUrl] = useLocalStorage(
    "contentzavod-api-base",
    "http://localhost:8000"
  );

  const [packs, setPacks] = useState<ContentPack[]>([]);
  const [items, setItems] = useState<ContentItem[]>([]);
  const [topicId, setTopicId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const loadProduction = useCallback(async () => {
    if (!projectId) return;
    try {
      setError(null);
      const [packsData, itemsData] = await Promise.all([
        apiFetch<ContentPack[]>(
          `/projects/${projectId}/content-packs`,
          {},
          token,
          apiBaseUrl
        ),
        apiFetch<ContentItem[]>(
          `/projects/${projectId}/content-items`,
          {},
          token,
          apiBaseUrl
        ),
      ]);
      setPacks(packsData);
      setItems(itemsData);
    } catch (err) {
      setError((err as { message: string }).message);
    }
  }, [projectId, token, apiBaseUrl]);

  useEffect(() => {
    loadProduction();
  }, [loadProduction]);

  const runPipeline = async () => {
    if (!projectId || !topicId) return;
    setRunning(true);
    try {
      await apiFetch(
        `/projects/${projectId}/pipelines/run?topic_id=${topicId}`,
        { method: "POST" },
        token,
        apiBaseUrl
      );
      setTopicId("");
      loadProduction();
    } catch (err) {
      setError((err as { message: string }).message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="section-grid">
      <section className="card">
        <h3>Статусы пайплайна</h3>
        {error && <div className="notice">Ошибка: {error}</div>}
        <table className="table">
          <thead>
            <tr>
              <th>ID пакета</th>
              <th>ID темы</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            {packs.map((pack) => (
              <tr key={pack.id}>
                <td>{pack.id}</td>
                <td>{pack.topic_id}</td>
                <td>
                  <span className="badge">{pack.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3>Контент-единицы</h3>
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Канал</th>
              <th>Формат</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.id}</td>
                <td>{item.channel}</td>
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
        <h3>Запуск пайплайна</h3>
        <input
          placeholder="ID темы"
          value={topicId}
          onChange={(event) => setTopicId(event.target.value)}
        />
        <button onClick={runPipeline} disabled={running}>
          {running ? "Запуск..." : "Запустить"}
        </button>
      </section>
    </div>
  );
}
