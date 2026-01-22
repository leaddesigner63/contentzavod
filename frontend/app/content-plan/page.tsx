"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { getRolesFromToken, hasAnyRole, type Role } from "../../lib/auth";
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
  const roles = useMemo<Role[]>(
    () => getRolesFromToken(token),
    [token]
  );
  const canEdit = hasAnyRole(roles, ["Admin", "Editor"]);

  const [topics, setTopics] = useState<Topic[]>([]);
  const [form, setForm] = useState({
    title: "",
    angle: "",
    rubric: "",
    planned_for: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [rubricFilter, setRubricFilter] = useState("all");

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

  const rubrics = useMemo(
    () =>
      Array.from(
        new Set(topics.map((topic) => topic.rubric).filter(Boolean))
      ) as string[],
    [topics]
  );
  const filteredTopics = useMemo(() => {
    return topics.filter((topic) => {
      const statusOk = statusFilter === "all" || topic.status === statusFilter;
      const rubricOk =
        rubricFilter === "all" || topic.rubric === rubricFilter;
      return statusOk && rubricOk;
    });
  }, [topics, statusFilter, rubricFilter]);
  const stats = useMemo(() => {
    const total = topics.length;
    const scheduled = topics.filter((topic) => topic.planned_for).length;
    const ready = topics.filter((topic) => topic.status === "ready").length;
    const draft = topics.filter((topic) => topic.status === "draft").length;
    return { total, scheduled, ready, draft };
  }, [topics]);
  const upcoming = useMemo(() => {
    return topics
      .filter((topic) => topic.planned_for)
      .sort((a, b) => {
        const left = new Date(a.planned_for ?? 0).getTime();
        const right = new Date(b.planned_for ?? 0).getTime();
        return left - right;
      })
      .slice(0, 5);
  }, [topics]);

  const runPipeline = async (topicId: number) => {
    if (!projectId || !canEdit) return;
    try {
      setError(null);
      await apiFetch(
        `/projects/${projectId}/pipelines/run?topic_id=${topicId}`,
        {
          method: "POST",
        },
        token,
        apiBaseUrl
      );
    } catch (err) {
      setError((err as { message: string }).message);
    }
  };

  const submitTopic = async () => {
    if (!projectId || !canEdit) return;
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
        <h3>Сводка контент-плана</h3>
        <div className="stats-grid">
          <div className="stat-card">
            <span className="label">Всего тем</span>
            <strong>{stats.total}</strong>
          </div>
          <div className="stat-card">
            <span className="label">Запланировано</span>
            <strong>{stats.scheduled}</strong>
          </div>
          <div className="stat-card">
            <span className="label">Готово к продакшену</span>
            <strong>{stats.ready}</strong>
          </div>
          <div className="stat-card">
            <span className="label">Черновики</span>
            <strong>{stats.draft}</strong>
          </div>
        </div>
        <div className="filter-row">
          <label>
            Статус
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="all">Все</option>
              <option value="draft">draft</option>
              <option value="ready">ready</option>
              <option value="scheduled">scheduled</option>
              <option value="done">done</option>
            </select>
          </label>
          <label>
            Рубрика
            <select
              value={rubricFilter}
              onChange={(event) => setRubricFilter(event.target.value)}
            >
              <option value="all">Все</option>
              {rubrics.map((rubric) => (
                <option key={rubric} value={rubric}>
                  {rubric}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="list">
          <strong>Ближайшие темы</strong>
          {upcoming.length === 0 && <span className="muted">Нет данных.</span>}
          {upcoming.map((topic) => (
            <div key={`upcoming-${topic.id}`} className="row">
              <span>{topic.title}</span>
              <span className="muted">
                {topic.planned_for
                  ? new Date(topic.planned_for).toLocaleString("ru-RU")
                  : "без даты"}
              </span>
            </div>
          ))}
        </div>
      </section>

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
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {filteredTopics.map((topic) => (
              <tr key={topic.id}>
                <td>{topic.title}</td>
                <td>{topic.angle}</td>
                <td>{topic.rubric ?? "—"}</td>
                <td>
                  <span className="badge">{topic.status}</span>
                </td>
                <td>
                  {canEdit ? (
                    <button
                      className="button secondary"
                      onClick={() => runPipeline(topic.id)}
                    >
                      Запустить пайплайн
                    </button>
                  ) : (
                    <span className="muted">Нет доступа</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3>Создать тему</h3>
        {!canEdit && (
          <div className="notice">
            Доступно только для ролей Admin и Editor.
          </div>
        )}
        <input
          placeholder="Название темы"
          value={form.title}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, title: event.target.value }))
          }
          disabled={!canEdit}
        />
        <input
          placeholder="Угол подачи"
          value={form.angle}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, angle: event.target.value }))
          }
          disabled={!canEdit}
        />
        <input
          placeholder="Рубрика"
          value={form.rubric}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, rubric: event.target.value }))
          }
          disabled={!canEdit}
        />
        <input
          type="datetime-local"
          value={form.planned_for}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, planned_for: event.target.value }))
          }
          disabled={!canEdit}
        />
        <button onClick={submitTopic} disabled={!canEdit}>
          Запланировать
        </button>
      </section>
    </div>
  );
}
