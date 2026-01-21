"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "../../lib/api";
import { useLocalStorage } from "../../lib/useLocalStorage";

type MetricSnapshot = {
  id: number;
  content_item_id: number;
  impressions: number;
  clicks: number;
  likes: number;
  comments: number;
  shares: number;
  collected_at: string;
};

type LearningEvent = {
  id: number;
  parameter: string;
  previous_value: string;
  new_value: string;
  reason: string;
  created_at: string;
};

export default function AnalyticsTrainingPage() {
  const [token] = useLocalStorage("contentzavod-token", "");
  const [projectId] = useLocalStorage("contentzavod-project", "1");
  const [apiBaseUrl] = useLocalStorage(
    "contentzavod-api-base",
    "http://localhost:8000"
  );

  const [metrics, setMetrics] = useState<MetricSnapshot[]>([]);
  const [events, setEvents] = useState<LearningEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadAnalytics = useCallback(async () => {
    if (!projectId) return;
    try {
      setError(null);
      const [metricsData, eventData] = await Promise.all([
        apiFetch<MetricSnapshot[]>(
          `/projects/${projectId}/metrics`,
          {},
          token,
          apiBaseUrl
        ),
        apiFetch<LearningEvent[]>(
          `/projects/${projectId}/learning-events`,
          {},
          token,
          apiBaseUrl
        ),
      ]);
      setMetrics(metricsData);
      setEvents(eventData);
    } catch (err) {
      setError((err as { message: string }).message);
    }
  }, [projectId, token, apiBaseUrl]);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  return (
    <div className="section-grid">
      <section className="card">
        <h3>Метрики</h3>
        {error && <div className="notice">Ошибка: {error}</div>}
        <table className="table">
          <thead>
            <tr>
              <th>ID контента</th>
              <th>Показы</th>
              <th>Клики</th>
              <th>Лайки</th>
              <th>Комментарии</th>
              <th>Репосты</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric) => (
              <tr key={metric.id}>
                <td>{metric.content_item_id}</td>
                <td>{metric.impressions}</td>
                <td>{metric.clicks}</td>
                <td>{metric.likes}</td>
                <td>{metric.comments}</td>
                <td>{metric.shares}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3>Автообучение</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Параметр</th>
              <th>Было</th>
              <th>Стало</th>
              <th>Причина</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.id}>
                <td>{event.parameter}</td>
                <td>{event.previous_value}</td>
                <td>{event.new_value}</td>
                <td>{event.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3>Рекомендации</h3>
        <ul>
          <li>Отслеживайте качество CTR и вовлечения по рубрикам.</li>
          <li>Сравнивайте слоты публикаций и результативность.</li>
          <li>Фиксируйте автозамены и причины в журнале.</li>
        </ul>
      </section>
    </div>
  );
}
