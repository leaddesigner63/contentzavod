"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { getRolesFromToken, hasAnyRole, type Role } from "../../lib/auth";
import { apiFetch } from "../../lib/api";
import { useLocalStorage } from "../../lib/useLocalStorage";

type QcReport = {
  id: number;
  content_item_id: number;
  score: number;
  passed: boolean;
  reasons: string[];
};

type BudgetUsage = {
  id: number;
  budget_id: number;
  usage_date: string;
  token_used: number;
  video_seconds_used: number;
  publications_used: number;
};

type BudgetReport = {
  budget: {
    daily: number;
    weekly: number;
    monthly: number;
    token_limit: number;
    video_seconds_limit: number;
    publication_limit: number;
  };
  windows: {
    window: string;
    token_used: number;
    token_limit?: number | null;
    token_used_pct?: number | null;
    token_remaining?: number | null;
    video_seconds_used: number;
    video_seconds_limit?: number | null;
    video_seconds_used_pct?: number | null;
    video_seconds_remaining?: number | null;
    publications_used: number;
    publications_limit?: number | null;
    publications_used_pct?: number | null;
    publications_remaining?: number | null;
    budget_limit?: number | null;
  }[];
  is_blocked: boolean;
  generated_at: string;
};

export default function LogsMonitoringPage() {
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
  const isAdmin = hasAnyRole(roles, ["Admin"]);
  const canExport = hasAnyRole(roles, ["Admin", "Editor"]);

  const [qcReports, setQcReports] = useState<QcReport[]>([]);
  const [budgetUsages, setBudgetUsages] = useState<BudgetUsage[]>([]);
  const [budgetReport, setBudgetReport] = useState<BudgetReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadLogs = useCallback(async () => {
    if (!projectId) return;
    try {
      setError(null);
      const [qcData, reportData] = await Promise.all([
        apiFetch<QcReport[]>(
          `/projects/${projectId}/qc-reports`,
          {},
          token,
          apiBaseUrl
        ),
        apiFetch<BudgetReport>(
          `/projects/${projectId}/budget-report`,
          {},
          token,
          apiBaseUrl
        ),
      ]);
      setQcReports(qcData);
      setBudgetReport(reportData);
      if (isAdmin) {
        const budgetData = await apiFetch<BudgetUsage[]>(
          `/projects/${projectId}/budget-usages`,
          {},
          token,
          apiBaseUrl
        );
        setBudgetUsages(budgetData);
      } else {
        setBudgetUsages([]);
      }
    } catch (err) {
      setError((err as { message: string }).message);
    }
  }, [projectId, token, apiBaseUrl, isAdmin]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const failedReports = useMemo(
    () => qcReports.filter((report) => !report.passed),
    [qcReports]
  );

  const formatLimit = (value?: number | null) =>
    value === null || value === undefined ? "—" : value.toLocaleString("ru-RU");

  const formatPercent = (value?: number | null) =>
    value === null || value === undefined ? "—" : `${value.toFixed(1)}%`;

  const formatUsage = (
    used: number,
    limit?: number | null,
    pct?: number | null,
    remaining?: number | null
  ) =>
    `${used.toLocaleString("ru-RU")} / ${formatLimit(limit)} (${formatPercent(
      pct
    )}) · остаток ${formatLimit(remaining)}`;

  return (
    <div className="section-grid">
      <section className="card">
        <h3>Алерты и инциденты</h3>
        {error && <div className="notice">Ошибка: {error}</div>}
        <div className="list">
          {failedReports.length === 0 ? (
            <span className="muted">Критических QC ошибок нет.</span>
          ) : (
            failedReports.slice(0, 5).map((report) => (
              <div key={`alert-${report.id}`} className="row">
                <span>QC fail: контент #{report.content_item_id}</span>
                <span className="badge danger">{report.score}</span>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="card">
        <h3>QC отчёты</h3>
        <table className="table">
          <thead>
            <tr>
              <th>ID контента</th>
              <th>Score</th>
              <th>Статус</th>
              <th>Причины</th>
            </tr>
          </thead>
          <tbody>
            {qcReports.map((report) => (
              <tr key={report.id}>
                <td>{report.content_item_id}</td>
                <td>{report.score}</td>
                <td>
                  <span
                    className={`badge ${report.passed ? "success" : "danger"}`}
                  >
                    {report.passed ? "pass" : "fail"}
                  </span>
                </td>
                <td>{report.reasons.join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3>Использование бюджета</h3>
        {!isAdmin && (
          <div className="notice">
            Доступно только для роли Admin.
          </div>
        )}
        {isAdmin && (
          <table className="table">
            <thead>
              <tr>
                <th>ID бюджета</th>
                <th>Дата</th>
                <th>Токены</th>
                <th>Видео сек</th>
                <th>Публикации</th>
              </tr>
            </thead>
            <tbody>
              {budgetUsages.map((usage) => (
                <tr key={usage.id}>
                  <td>{usage.budget_id}</td>
                  <td>
                    {new Date(usage.usage_date).toLocaleDateString("ru-RU")}
                  </td>
                  <td>{usage.token_used}</td>
                  <td>{usage.video_seconds_used}</td>
                  <td>{usage.publications_used}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <h3>Отчёт по расходам</h3>
        {budgetReport ? (
          <>
            <div className="stats-grid">
              <div className="stat-card">
                <span className="label">Бюджет день</span>
                <strong>{formatLimit(budgetReport.budget.daily)}</strong>
              </div>
              <div className="stat-card">
                <span className="label">Бюджет неделя</span>
                <strong>{formatLimit(budgetReport.budget.weekly)}</strong>
              </div>
              <div className="stat-card">
                <span className="label">Бюджет месяц</span>
                <strong>{formatLimit(budgetReport.budget.monthly)}</strong>
              </div>
              <div className="stat-card">
                <span className="label">Блокировка</span>
                <strong>{budgetReport.is_blocked ? "да" : "нет"}</strong>
              </div>
              <div className="stat-card">
                <span className="label">Отчёт</span>
                <strong>
                  {new Date(budgetReport.generated_at).toLocaleString("ru-RU")}
                </strong>
              </div>
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th>Окно</th>
                  <th>Бюджет</th>
                  <th>Токены (использование)</th>
                  <th>Видео сек (использование)</th>
                  <th>Публикации (использование)</th>
                </tr>
              </thead>
              <tbody>
                {budgetReport.windows.map((window) => (
                  <tr key={window.window}>
                    <td>{window.window}</td>
                    <td>{formatLimit(window.budget_limit)}</td>
                    <td>
                      {formatUsage(
                        window.token_used,
                        window.token_limit,
                        window.token_used_pct,
                        window.token_remaining
                      )}
                    </td>
                    <td>
                      {formatUsage(
                        window.video_seconds_used,
                        window.video_seconds_limit,
                        window.video_seconds_used_pct,
                        window.video_seconds_remaining
                      )}
                    </td>
                    <td>
                      {formatUsage(
                        window.publications_used,
                        window.publications_limit,
                        window.publications_used_pct,
                        window.publications_remaining
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {canExport && (
              <a
                className="button secondary"
                href={`${apiBaseUrl}/projects/${projectId}/budget-report/export`}
                target="_blank"
                rel="noreferrer"
              >
                Экспорт CSV
              </a>
            )}
          </>
        ) : (
          <span className="muted">Нет данных.</span>
        )}
      </section>

      <section className="card">
        <h3>Мониторинг</h3>
        <ul>
          <li>Отслеживайте ошибки интеграций и алерты публикаций.</li>
          <li>Контролируйте лимиты бюджетов и автоприостановки.</li>
          <li>Используйте логи для поиска причин падений пайплайна.</li>
        </ul>
      </section>
    </div>
  );
}
