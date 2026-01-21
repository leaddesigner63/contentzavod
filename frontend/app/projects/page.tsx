"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch, parseCsv } from "../../lib/api";
import { useLocalStorage } from "../../lib/useLocalStorage";

type Project = {
  id: number;
  name: string;
  description?: string | null;
  status: string;
  created_at: string;
};

type BrandConfig = {
  id: number;
  project_id: number;
  tone: string;
  audience: string;
  offers: string[];
  rubrics: string[];
  forbidden: string[];
  cta_policy: string;
  version: number;
};

type Budget = {
  id: number;
  project_id: number;
  daily: number;
  weekly: number;
  monthly: number;
  token_limit: number;
  video_seconds_limit: number;
  publication_limit: number;
};

type IntegrationToken = {
  id: number;
  project_id: number;
  provider: string;
  token: string;
  created_at: string;
};

export default function ProjectsPage() {
  const [token] = useLocalStorage("contentzavod-token", "");
  const [projectId] = useLocalStorage("contentzavod-project", "1");
  const [apiBaseUrl] = useLocalStorage(
    "contentzavod-api-base",
    "http://localhost:8000"
  );

  const [projects, setProjects] = useState<Project[]>([]);
  const [brandConfigs, setBrandConfigs] = useState<BrandConfig[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationToken[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [projectForm, setProjectForm] = useState({
    name: "",
    description: "",
  });
  const [brandForm, setBrandForm] = useState({
    tone: "",
    audience: "",
    offers: "",
    rubrics: "",
    forbidden: "",
    cta_policy: "",
  });
  const [budgetForm, setBudgetForm] = useState({
    daily: "",
    weekly: "",
    monthly: "",
    token_limit: "",
    video_seconds_limit: "",
    publication_limit: "",
  });
  const [integrationForm, setIntegrationForm] = useState({
    provider: "",
    token: "",
  });

  const loadProjects = useCallback(async () => {
    try {
      setError(null);
      const data = await apiFetch<Project[]>("/projects", {}, token, apiBaseUrl);
      setProjects(data);
    } catch (err) {
      setError((err as { message: string }).message);
    }
  }, [token, apiBaseUrl]);

  const loadProjectDetails = useCallback(async () => {
    if (!projectId) {
      return;
    }
    try {
      const [configs, budgetList, integrationList] = await Promise.all([
        apiFetch<BrandConfig[]>(
          `/projects/${projectId}/brand-configs`,
          {},
          token,
          apiBaseUrl
        ),
        apiFetch<Budget[]>(
          `/projects/${projectId}/budgets`,
          {},
          token,
          apiBaseUrl
        ),
        apiFetch<IntegrationToken[]>(
          `/projects/${projectId}/integration-tokens`,
          {},
          token,
          apiBaseUrl
        ),
      ]);
      setBrandConfigs(configs);
      setBudgets(budgetList);
      setIntegrations(integrationList);
    } catch (err) {
      setError((err as { message: string }).message);
    }
  }, [projectId, token, apiBaseUrl]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    loadProjectDetails();
  }, [loadProjectDetails]);

  const submitProject = async () => {
    try {
      await apiFetch<Project>(
        "/projects",
        {
          method: "POST",
          body: JSON.stringify({
            name: projectForm.name,
            description: projectForm.description || null,
          }),
        },
        token,
        apiBaseUrl
      );
      setProjectForm({ name: "", description: "" });
      loadProjects();
    } catch (err) {
      setError((err as { message: string }).message);
    }
  };

  const submitBrandConfig = async () => {
    if (!projectId) return;
    try {
      await apiFetch<BrandConfig>(
        `/projects/${projectId}/brand-configs`,
        {
          method: "POST",
          body: JSON.stringify({
            tone: brandForm.tone,
            audience: brandForm.audience,
            offers: parseCsv(brandForm.offers),
            rubrics: parseCsv(brandForm.rubrics),
            forbidden: parseCsv(brandForm.forbidden),
            cta_policy: brandForm.cta_policy,
          }),
        },
        token,
        apiBaseUrl
      );
      setBrandForm({
        tone: "",
        audience: "",
        offers: "",
        rubrics: "",
        forbidden: "",
        cta_policy: "",
      });
      loadProjectDetails();
    } catch (err) {
      setError((err as { message: string }).message);
    }
  };

  const submitBudget = async () => {
    if (!projectId) return;
    try {
      await apiFetch<Budget>(
        `/projects/${projectId}/budgets`,
        {
          method: "POST",
          body: JSON.stringify({
            daily: Number(budgetForm.daily),
            weekly: Number(budgetForm.weekly),
            monthly: Number(budgetForm.monthly),
            token_limit: Number(budgetForm.token_limit),
            video_seconds_limit: Number(budgetForm.video_seconds_limit),
            publication_limit: Number(budgetForm.publication_limit),
          }),
        },
        token,
        apiBaseUrl
      );
      setBudgetForm({
        daily: "",
        weekly: "",
        monthly: "",
        token_limit: "",
        video_seconds_limit: "",
        publication_limit: "",
      });
      loadProjectDetails();
    } catch (err) {
      setError((err as { message: string }).message);
    }
  };

  const submitIntegration = async () => {
    if (!projectId) return;
    try {
      await apiFetch<IntegrationToken>(
        `/projects/${projectId}/integration-tokens`,
        {
          method: "POST",
          body: JSON.stringify(integrationForm),
        },
        token,
        apiBaseUrl
      );
      setIntegrationForm({ provider: "", token: "" });
      loadProjectDetails();
    } catch (err) {
      setError((err as { message: string }).message);
    }
  };

  return (
    <div className="section-grid">
      <section className="card">
        <h3>Проекты</h3>
        {error && <div className="notice">Ошибка: {error}</div>}
        <div className="list">
          {projects.map((project) => (
            <div key={project.id}>
              <strong>{project.name}</strong> — {project.status}
            </div>
          ))}
        </div>
        <input
          placeholder="Название проекта"
          value={projectForm.name}
          onChange={(event) =>
            setProjectForm((prev) => ({ ...prev, name: event.target.value }))
          }
        />
        <textarea
          placeholder="Описание"
          value={projectForm.description}
          onChange={(event) =>
            setProjectForm((prev) => ({
              ...prev,
              description: event.target.value,
            }))
          }
        />
        <button onClick={submitProject}>Создать проект</button>
      </section>

      <section className="card">
        <h3>Brand Config</h3>
        <div className="list">
          {brandConfigs.map((config) => (
            <div key={config.id}>
              v{config.version}: {config.tone} / {config.audience}
            </div>
          ))}
        </div>
        <input
          placeholder="Тон"
          value={brandForm.tone}
          onChange={(event) =>
            setBrandForm((prev) => ({ ...prev, tone: event.target.value }))
          }
        />
        <input
          placeholder="Целевая аудитория"
          value={brandForm.audience}
          onChange={(event) =>
            setBrandForm((prev) => ({ ...prev, audience: event.target.value }))
          }
        />
        <input
          placeholder="Офферы (через запятую)"
          value={brandForm.offers}
          onChange={(event) =>
            setBrandForm((prev) => ({ ...prev, offers: event.target.value }))
          }
        />
        <input
          placeholder="Рубрики (через запятую)"
          value={brandForm.rubrics}
          onChange={(event) =>
            setBrandForm((prev) => ({ ...prev, rubrics: event.target.value }))
          }
        />
        <input
          placeholder="Запреты (через запятую)"
          value={brandForm.forbidden}
          onChange={(event) =>
            setBrandForm((prev) => ({ ...prev, forbidden: event.target.value }))
          }
        />
        <textarea
          placeholder="CTA политика"
          value={brandForm.cta_policy}
          onChange={(event) =>
            setBrandForm((prev) => ({ ...prev, cta_policy: event.target.value }))
          }
        />
        <button onClick={submitBrandConfig}>Сохранить конфиг</button>
      </section>

      <section className="card">
        <h3>Бюджеты</h3>
        <div className="list">
          {budgets.map((budget) => (
            <div key={budget.id}>
              Day {budget.daily} / Week {budget.weekly} / Month {budget.monthly}
            </div>
          ))}
        </div>
        <input
          placeholder="Дневной бюджет"
          value={budgetForm.daily}
          onChange={(event) =>
            setBudgetForm((prev) => ({ ...prev, daily: event.target.value }))
          }
        />
        <input
          placeholder="Недельный бюджет"
          value={budgetForm.weekly}
          onChange={(event) =>
            setBudgetForm((prev) => ({ ...prev, weekly: event.target.value }))
          }
        />
        <input
          placeholder="Месячный бюджет"
          value={budgetForm.monthly}
          onChange={(event) =>
            setBudgetForm((prev) => ({ ...prev, monthly: event.target.value }))
          }
        />
        <input
          placeholder="Лимит токенов"
          value={budgetForm.token_limit}
          onChange={(event) =>
            setBudgetForm((prev) => ({
              ...prev,
              token_limit: event.target.value,
            }))
          }
        />
        <input
          placeholder="Лимит видео секунд"
          value={budgetForm.video_seconds_limit}
          onChange={(event) =>
            setBudgetForm((prev) => ({
              ...prev,
              video_seconds_limit: event.target.value,
            }))
          }
        />
        <input
          placeholder="Лимит публикаций"
          value={budgetForm.publication_limit}
          onChange={(event) =>
            setBudgetForm((prev) => ({
              ...prev,
              publication_limit: event.target.value,
            }))
          }
        />
        <button onClick={submitBudget}>Добавить бюджет</button>
      </section>

      <section className="card">
        <h3>Интеграции</h3>
        <div className="list">
          {integrations.map((integration) => (
            <div key={integration.id}>
              {integration.provider}: {integration.token.slice(0, 6)}***
            </div>
          ))}
        </div>
        <input
          placeholder="Провайдер (TG/VK)"
          value={integrationForm.provider}
          onChange={(event) =>
            setIntegrationForm((prev) => ({
              ...prev,
              provider: event.target.value,
            }))
          }
        />
        <input
          placeholder="Токен"
          value={integrationForm.token}
          onChange={(event) =>
            setIntegrationForm((prev) => ({ ...prev, token: event.target.value }))
          }
        />
        <button onClick={submitIntegration}>Добавить интеграцию</button>
      </section>
    </div>
  );
}
