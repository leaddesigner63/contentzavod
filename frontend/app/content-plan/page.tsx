"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "../../lib/api";
import { useLocalStorage } from "../../lib/useLocalStorage";

type Topic = {
  id: number;
  title: string;
  angle: string;
  rubric?: string | null;
  planned_for?: string | null;
  status: string;
};

export default function ContentPlanPage() {
  const [token] = useLocalStorage("contentzavod-token", "");
  const [projectId] = useLocalStorage("contentzavod-project", "1");
  const [apiBaseUrl] = useLocalStorage(
    "contentzavod-api-base",
    "http://localhost:8000"
  );

  const [topics, setTopics] = useState<Topic[]>([]);
  const [form, setForm] = useState({
    title: "",
    angle: "",
    rubric: "",
    planned_for: "",
  });
  const [error, setError] = useState<string | null>(null);

  const loadTopics = useCallback(async () => {
    if (!projectId) return;
    try {
      setError(null);
      const data = await apiFetch<Topic[]>(
        `/projects/${projectId}/topics`,
        {},
        token,
        apiBaseUrl
      );
      setTopics(data);
    } catch (err) {
      setError((err as { message: string }).message);
    }
  }, [projectId, token, apiBaseUrl]);

  useEffect(() => {
    loadTopics();
  }, [loadTopics]);

  const submitTopic = async () => {
    if (!projectId) return;
    try {
      await apiFetch<Topic>(
        `/projects/${projectId}/topics`,
        {
          method: "POST",
          body: JSON.stringify({
            title: form.title,
            angle: form.angle,
            rubric: form.rubric || null,
            planned_for: form.planned_for || null,
          }),
        },
        token,
        apiBaseUrl
      );
      setForm({ title: "", angle: "", rubric: "", planned_for: "" });
      loadTopics();
    } catch (err) {
      setError((err as { message: string }).message);
    }
  };

  return (
    <div className="section-grid">
      <section className="card">
        <h3>Темы контент-плана</h3>
        {error && <div className="notice">Ошибка: {error}</div>}
        <table className="table">
          <thead>
            <tr>
              <th>Тема</th>
              <th>Угол</th>
              <th>Рубрика</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            {topics.map((topic) => (
              <tr key={topic.id}>
                <td>{topic.title}</td>
                <td>{topic.angle}</td>
                <td>{topic.rubric ?? "—"}</td>
                <td>
                  <span className="badge">{topic.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3>Создать тему</h3>
        <input
          placeholder="Название темы"
          value={form.title}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, title: event.target.value }))
          }
        />
        <input
          placeholder="Угол подачи"
          value={form.angle}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, angle: event.target.value }))
          }
        />
        <input
          placeholder="Рубрика"
          value={form.rubric}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, rubric: event.target.value }))
          }
        />
        <input
          type="datetime-local"
          value={form.planned_for}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, planned_for: event.target.value }))
          }
        />
        <button onClick={submitTopic}>Запланировать</button>
      </section>
    </div>
  );
}
