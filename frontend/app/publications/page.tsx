"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { apiFetch } from "../../lib/api";
import { useLocalStorage } from "../../lib/useLocalStorage";

type Publication = {
  id: number;
  content_item_id: number;
  platform: string;
  scheduled_at: string;
  status: string;
  platform_post_id?: string | null;
  published_at?: string | null;
};

type CalendarDay = {
  date: Date;
  label: string;
  entries: Publication[];
};

function buildCalendar(publications: Publication[]) {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth();
  const firstDay = new Date(year, month, 1);
  const startDay = new Date(firstDay);
  startDay.setDate(firstDay.getDate() - firstDay.getDay());
  const days: CalendarDay[] = [];

  for (let i = 0; i < 42; i += 1) {
    const date = new Date(startDay);
    date.setDate(startDay.getDate() + i);
    const label = `${date.getDate()}.${date.getMonth() + 1}`;
    const entries = publications.filter((pub) => {
      const scheduled = new Date(pub.scheduled_at);
      return (
        scheduled.getFullYear() === date.getFullYear() &&
        scheduled.getMonth() === date.getMonth() &&
        scheduled.getDate() === date.getDate()
      );
    });
    days.push({ date, label, entries });
  }

  return days;
}

export default function PublicationsPage() {
  const [token] = useLocalStorage("contentzavod-token", "");
  const [projectId] = useLocalStorage("contentzavod-project", "1");
  const [apiBaseUrl] = useLocalStorage(
    "contentzavod-api-base",
    "http://localhost:8000"
  );

  const [publications, setPublications] = useState<Publication[]>([]);
  const [form, setForm] = useState({
    content_item_id: "",
    platform: "Telegram",
    scheduled_at: "",
  });
  const [error, setError] = useState<string | null>(null);

  const loadPublications = useCallback(async () => {
    if (!projectId) return;
    try {
      setError(null);
      const data = await apiFetch<Publication[]>(
        `/projects/${projectId}/publications`,
        {},
        token,
        apiBaseUrl
      );
      setPublications(data);
    } catch (err) {
      setError((err as { message: string }).message);
    }
  }, [projectId, token, apiBaseUrl]);

  useEffect(() => {
    loadPublications();
  }, [loadPublications]);

  const submitPublication = async () => {
    if (!projectId) return;
    try {
      await apiFetch<Publication>(
        `/projects/${projectId}/publications`,
        {
          method: "POST",
          body: JSON.stringify({
            content_item_id: Number(form.content_item_id),
            platform: form.platform,
            scheduled_at: form.scheduled_at,
            status: "scheduled",
          }),
        },
        token,
        apiBaseUrl
      );
      setForm({ content_item_id: "", platform: "Telegram", scheduled_at: "" });
      loadPublications();
    } catch (err) {
      setError((err as { message: string }).message);
    }
  };

  const calendarDays = useMemo(
    () => buildCalendar(publications),
    [publications]
  );

  return (
    <div className="section-grid">
      <section className="card">
        <h3>Календарь публикаций</h3>
        {error && <div className="notice">Ошибка: {error}</div>}
        <div className="calendar">
          {calendarDays.map((day) => (
            <div key={day.date.toISOString()} className="calendar-day">
              <span>{day.label}</span>
              {day.entries.map((entry) => (
                <div key={entry.id} className="badge">
                  {entry.platform} #{entry.content_item_id}
                </div>
              ))}
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h3>Журнал публикаций</h3>
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Контент</th>
              <th>Платформа</th>
              <th>Статус</th>
              <th>Ссылка</th>
            </tr>
          </thead>
          <tbody>
            {publications.map((pub) => (
              <tr key={pub.id}>
                <td>{pub.id}</td>
                <td>{pub.content_item_id}</td>
                <td>{pub.platform}</td>
                <td>
                  <span className="badge">{pub.status}</span>
                </td>
                <td>{pub.platform_post_id ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3>Запланировать публикацию</h3>
        <input
          placeholder="ID контент-единицы"
          value={form.content_item_id}
          onChange={(event) =>
            setForm((prev) => ({
              ...prev,
              content_item_id: event.target.value,
            }))
          }
        />
        <select
          value={form.platform}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, platform: event.target.value }))
          }
        >
          <option value="Telegram">Telegram</option>
          <option value="VK">VK</option>
          <option value="Longread">Longread</option>
          <option value="Video">Video</option>
        </select>
        <input
          type="datetime-local"
          value={form.scheduled_at}
          onChange={(event) =>
            setForm((prev) => ({
              ...prev,
              scheduled_at: event.target.value,
            }))
          }
        />
        <button onClick={submitPublication}>Запланировать</button>
      </section>
    </div>
  );
}
