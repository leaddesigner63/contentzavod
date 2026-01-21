"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useLocalStorage } from "../lib/useLocalStorage";

const navItems = [
  { href: "/projects", label: "Проекты" },
  { href: "/sources", label: "Источники" },
  { href: "/content-plan", label: "Контент-план" },
  { href: "/production", label: "Производство" },
  { href: "/publications", label: "Публикации" },
  { href: "/video-workshop", label: "Видео-цех" },
  { href: "/analytics-training", label: "Аналитика/Обучение" },
  { href: "/logs-monitoring", label: "Логи/Мониторинг" },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [token, setToken] = useLocalStorage("contentzavod-token", "");
  const [projectId, setProjectId] = useLocalStorage("contentzavod-project", "1");
  const [apiBaseUrl, setApiBaseUrl] = useLocalStorage(
    "contentzavod-api-base",
    "http://localhost:8000"
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>ContentZavod Admin</h1>
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`nav-link${pathname === item.href ? " active" : ""}`}
          >
            {item.label}
          </Link>
        ))}
      </aside>
      <div className="content">
        <div className="topbar">
          <label>
            API Base URL
            <input
              value={apiBaseUrl}
              onChange={(event) => setApiBaseUrl(event.target.value)}
              placeholder="http://localhost:8000"
            />
          </label>
          <label>
            Project ID
            <input
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              placeholder="1"
            />
          </label>
          <label>
            Bearer Token
            <input
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="token"
            />
          </label>
        </div>
        <main>{children}</main>
      </div>
    </div>
  );
}
