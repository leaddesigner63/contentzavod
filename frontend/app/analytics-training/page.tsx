"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { getRolesFromToken, hasAnyRole, type Role } from "../../lib/auth";
import { apiFetch, parseCsv } from "../../lib/api";
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

type AutoLearningConfig = {
  max_changes_per_week: number;
  rollback_threshold: number;
  rollback_window: number;
  protected_parameters: string[];
};

type AutoLearningState = {
  parameters: Record<string, string>;
  stable_parameters: Record<string, string>;
  window_started_at?: string | null;
  changes_in_window: number;
  last_change_at?: string | null;
  last_rollback_at?: string | null;
};

export default function AnalyticsTrainingPage() {
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

  const [metrics, setMetrics] = useState<MetricSnapshot[]>([]);
  const [events, setEvents] = useState<LearningEvent[]>([]);
  const [config, setConfig] = useState<AutoLearningConfig | null>(null);
  const [state, setState] = useState<AutoLearningState | null>(null);
  const [configForm, setConfigForm] = useState({
    max_changes_per_week: "2",
    rollback_threshold: "0.02",
    rollback_window: "20",
    protected_parameters: "",
  });
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [isCollecting, setIsCollecting] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAnalytics = useCallback(async () => {
    if (!projectId) return;
    try {
      setError(null);
      const [metricsData, eventData, configData, stateData] = await Promise.all([
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
        apiFetch<AutoLearningConfig>(
          `/projects/${projectId}/auto-learning/config`,
          {},
          token,
          apiBaseUrl
        ),
        apiFetch<AutoLearningState>(
          `/projects/${projectId}/auto-learning/state`,
          {},
          token,
          apiBaseUrl
        ),
      ]);
      setMetrics(metricsData);
      setEvents(eventData);
      setConfig(configData);
      setState(stateData);
      setConfigForm({
        max_changes_per_week: String(configData.max_changes_per_week),
        rollback_threshold: String(configData.rollback_threshold),
        rollback_window: String(configData.rollback_window),
        protected_parameters: configData.protected_parameters.join(", "),
      });
    } catch (err) {
      setError((err as { message: string }).message);
    }
  }, [projectId, token, apiBaseUrl]);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  const stats = useMemo(() => {
    const impressions = metrics.reduce(
      (acc, metric) => acc + metric.impressions,
      0
    );
    const clicks = metrics.reduce((acc, metric) => acc + metric.clicks, 0);
    const ctr = impressions > 0 ? (clicks / impressions) * 100 : 0;
    return { impressions, clicks, ctr: ctr.toFixed(2) };
  }, [metrics]);

  const updateConfig = async () => {
    if (!projectId || !canEdit) return;
    try {
      setError(null);
      const payload = {
        max_changes_per_week: Number(configForm.max_changes_per_week),
        rollback_threshold: Number(configForm.rollback_threshold),
        rollback_window: Number(configForm.rollback_window),
        protected_parameters: parseCsv(configForm.protected_parameters),
      };
      const data = await apiFetch<AutoLearningConfig>(
        `/projects/${projectId}/auto-learning/config`,
        {
          method: "PUT",
          body: JSON.stringify(payload),
        },
        token,
        apiBaseUrl
      );
      setConfig(data);
      setRunMessage("Конфигурация обновлена.");
    } catch (err) {
      setError((err as { message: string }).message);
    }
  };

  const runAutoLearning = async () => {
    if (!projectId || !canEdit) return;
    setIsRunning(true);
    try {
      setError(null);
      const result = await apiFetch<{
        state: string;
        applied_changes: Record<string, string>;
        rollback_applied: boolean;
      }>(
        `/projects/${projectId}/auto-learning/run`,
        { method: "POST" },
        token,
        apiBaseUrl
      );
      setRunMessage(
        `Запуск завершён: ${result.state}. Изменения: ${
          Object.keys(result.applied_changes).length
        }, rollback: ${result.rollback_applied ? "да" : "нет"}.`
      );
      await loadAnalytics();
    } catch (err) {
      setError((err as { message: string }).message);
    } finally {
      setIsRunning(false);
    }
  };

  const collectMetrics = async () => {
    if (!projectId || !canEdit) return;
    setIsCollecting(true);
    try {
      setError(null);
      await apiFetch(
        `/projects/${projectId}/metrics/collect`,
        { method: "POST" },
        token,
        apiBaseUrl
      );
      setRunMessage("Метрики собраны.");
      await loadAnalytics();
    } catch (err) {
      setError((err as { message: string }).message);
    } finally {
      setIsCollecting(false);
    }
  };

  return (
    <div className="section-grid">
      <section className="card">
        <h3>Сводка метрик</h3>
        <div className="stats-grid">
          <div className="stat-card">
            <span className="label">Показы</span>
            <strong>{stats.impressions}</strong>
          </div>
          <div className="stat-card">
            <span className="label">Клики</span>
            <strong>{stats.clicks}</strong>
          </div>
          <div className="stat-card">
            <span className="label">CTR</span>
            <strong>{stats.ctr}%</strong>
          </div>
        </div>
        <div className="actions-row">
          <button onClick={collectMetrics} disabled={!canEdit || isCollecting}>
            {isCollecting ? "Сбор..." : "Собрать метрики"}
          </button>
          <button onClick={runAutoLearning} disabled={!canEdit || isRunning}>
            {isRunning ? "Запуск..." : "Запустить автообучение"}
          </button>
        </div>
        {!canEdit && (
          <div className="notice">
            Управление доступно только ролям Admin и Editor.
          </div>
        )}
        {runMessage && <div className="notice">{runMessage}</div>}
      </section>

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
        <h3>Конфигурация автообучения</h3>
        {config ? (
          <>
            <div className="grid">
              <label>
                Лимит изменений в неделю
                <input
                  value={configForm.max_changes_per_week}
                  onChange={(event) =>
                    setConfigForm((prev) => ({
                      ...prev,
                      max_changes_per_week: event.target.value,
                    }))
                  }
                  disabled={!canEdit}
                />
              </label>
              <label>
                Порог rollback
                <input
                  value={configForm.rollback_threshold}
                  onChange={(event) =>
                    setConfigForm((prev) => ({
                      ...prev,
                      rollback_threshold: event.target.value,
                    }))
                  }
                  disabled={!canEdit}
                />
              </label>
              <label>
                Окно rollback (публикации)
                <input
                  value={configForm.rollback_window}
                  onChange={(event) =>
                    setConfigForm((prev) => ({
                      ...prev,
                      rollback_window: event.target.value,
                    }))
                  }
                  disabled={!canEdit}
                />
              </label>
            </div>
            <label>
              Защищённые параметры
              <input
                value={configForm.protected_parameters}
                onChange={(event) =>
                  setConfigForm((prev) => ({
                    ...prev,
                    protected_parameters: event.target.value,
                  }))
                }
                disabled={!canEdit}
              />
            </label>
            <button onClick={updateConfig} disabled={!canEdit}>
              Сохранить конфиг
            </button>
          </>
        ) : (
          <span className="muted">Нет данных.</span>
        )}
      </section>

      <section className="card">
        <h3>Состояние автообучения</h3>
        {state ? (
          <div className="list">
            <div className="row">
              <span>Окно изменений</span>
              <span className="badge">{state.changes_in_window}</span>
            </div>
            <div className="row">
              <span>Старт окна</span>
              <span className="muted">
                {state.window_started_at
                  ? new Date(state.window_started_at).toLocaleString("ru-RU")
                  : "—"}
              </span>
            </div>
            <div className="row">
              <span>Последнее изменение</span>
              <span className="muted">
                {state.last_change_at
                  ? new Date(state.last_change_at).toLocaleString("ru-RU")
                  : "—"}
              </span>
            </div>
            <div className="row">
              <span>Последний rollback</span>
              <span className="muted">
                {state.last_rollback_at
                  ? new Date(state.last_rollback_at).toLocaleString("ru-RU")
                  : "—"}
              </span>
            </div>
          </div>
        ) : (
          <span className="muted">Нет данных.</span>
        )}
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
