"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "../../lib/api";
import { useLocalStorage } from "../../lib/useLocalStorage";

type Source = {
  id: number;
  title: string;
  source_type: string;
  uri?: string | null;
  content?: string | null;
  created_at: string;
};

export default function SourcesPage() {
  const [token] = useLocalStorage("contentzavod-token", "");
  const [projectId] = useLocalStorage("contentzavod-project", "1");
  const [apiBaseUrl] = useLocalStorage(
    "contentzavod-api-base",
    "http://localhost:8000"
  );

  const [sources, setSources] = useState<Source[]>([]);
  const [form, setForm] = useState({
    title: "",
    source_type: "link",
    uri: "",
    content: "",
  });
  const [error, setError] = useState<string | null>(null);

  const loadSources = useCallback(async () => {
    if (!projectId) return;
    try {
      setError(null);
      const data = await apiFetch<Source[]>(
        `/projects/${projectId}/sources`,
        {},
        token,
        apiBaseUrl
      );
      setSources(data);
    } catch (err) {
      setError((err as { message: string }).message);
    }
  }, [projectId, token, apiBaseUrl]);

  useEffect(() => {
    loadSources();
  }, [loadSources]);

  const submitSource = async () => {
    if (!projectId) return;
    try {
      await apiFetch<Source>(
        `/projects/${projectId}/sources`,
        {
          method: "POST",
          body: JSON.stringify({
            title: form.title,
            source_type: form.source_type,
            uri: form.uri || null,
            content: form.content || null,
          }),
        },
        token,
        apiBaseUrl
      );
      setForm({ title: "", source_type: "link", uri: "", content: "" });
      loadSources();
    } catch (err) {
      setError((err as { message: string }).message);
    }
  };

  return (
    <div className="section-grid">
      <section className="card">
        <h3>Источники</h3>
        {error && <div className="notice">Ошибка: {error}</div>}
        <table className="table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Тип</th>
              <th>URI</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((source) => (
              <tr key={source.id}>
                <td>{source.title}</td>
                <td>{source.source_type}</td>
                <td>{source.uri ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3>Добавить источник</h3>
        <input
          placeholder="Название"
          value={form.title}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, title: event.target.value }))
          }
        />
        <select
          value={form.source_type}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, source_type: event.target.value }))
          }
        >
          <option value="link">Ссылка</option>
          <option value="file">Файл</option>
          <option value="text">Текст</option>
          <option value="audio">Аудио</option>
          <option value="video">Видео</option>
        </select>
        <input
          placeholder="URI"
          value={form.uri}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, uri: event.target.value }))
          }
        />
        <textarea
          placeholder="Текст / заметка"
          value={form.content}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, content: event.target.value }))
          }
        />
        <button onClick={submitSource}>Добавить источник</button>
      </section>
    </div>
  );
}
