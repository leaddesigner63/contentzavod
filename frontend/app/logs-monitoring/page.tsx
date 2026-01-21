"use client";

import { useCallback, useEffect, useState } from "react";

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

export default function LogsMonitoringPage() {
  const [token] = useLocalStorage("contentzavod-token", "");
  const [projectId] = useLocalStorage("contentzavod-project", "1");
  const [apiBaseUrl] = useLocalStorage(
    "contentzavod-api-base",
    "http://localhost:8000"
  );

  const [qcReports, setQcReports] = useState<QcReport[]>([]);
  const [budgetUsages, setBudgetUsages] = useState<BudgetUsage[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadLogs = useCallback(async () => {
    if (!projectId) return;
    try {
      setError(null);
      const [qcData, budgetData] = await Promise.all([
        apiFetch<QcReport[]>(
          `/projects/${projectId}/qc-reports`,
          {},
          token,
          apiBaseUrl
        ),
        apiFetch<BudgetUsage[]>(
          `/projects/${projectId}/budget-usages`,
          {},
          token,
          apiBaseUrl
        ),
      ]);
      setQcReports(qcData);
      setBudgetUsages(budgetData);
    } catch (err) {
      setError((err as { message: string }).message);
    }
  }, [projectId, token, apiBaseUrl]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  return (
    <div className="section-grid">
      <section className="card">
        <h3>QC отчёты</h3>
        {error && <div className="notice">Ошибка: {error}</div>}
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
                <td>{new Date(usage.usage_date).toLocaleDateString("ru-RU")}</td>
                <td>{usage.token_used}</td>
                <td>{usage.video_seconds_used}</td>
                <td>{usage.publications_used}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
