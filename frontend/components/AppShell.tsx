"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";

import { getRolesFromToken, hasAnyRole, type Role } from "../lib/auth";
import { useLocalStorage } from "../lib/useLocalStorage";

const navItems: Array<{
  href: string;
  label: string;
  roles: Role[];
}> = [
  { href: "/projects", label: "Проекты", roles: ["Admin", "Editor", "Viewer"] },
  { href: "/sources", label: "Источники", roles: ["Admin", "Editor", "Viewer"] },
  {
    href: "/content-plan",
    label: "Контент-план",
    roles: ["Admin", "Editor", "Viewer"],
  },
  {
    href: "/production",
    label: "Производство",
    roles: ["Admin", "Editor", "Viewer"],
  },
  {
    href: "/publications",
    label: "Публикации",
    roles: ["Admin", "Editor", "Viewer"],
  },
  {
    href: "/video-workshop",
    label: "Видео-цех",
    roles: ["Admin", "Editor", "Viewer"],
  },
  {
    href: "/analytics-training",
    label: "Аналитика/Обучение",
    roles: ["Admin", "Editor", "Viewer"],
  },
  {
    href: "/logs-monitoring",
    label: "Логи/Мониторинг",
    roles: ["Admin", "Editor", "Viewer"],
  },
  {
    href: "/users",
    label: "Пользователи и роли",
    roles: ["Admin"],
  },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [token, setToken] = useLocalStorage("contentzavod-token", "");
  const [projectId, setProjectId] = useLocalStorage("contentzavod-project", "1");
  const [apiBaseUrl, setApiBaseUrl] = useLocalStorage(
    "contentzavod-api-base",
    "http://localhost:8000"
  );
  const roles = useMemo(() => {
    const resolved = getRolesFromToken(token);
    return resolved.length > 0 ? resolved : ["Viewer"];
  }, [token]);
  const visibleNavItems = useMemo(
    () => navItems.filter((item) => hasAnyRole(roles, item.roles)),
    [roles]
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>ContentZavod Admin</h1>
        {visibleNavItems.map((item) => (
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
          <div className="role-info">
            <span className="label">Роль</span>
            <div className="role-badges">
              {roles.map((role) => (
                <span key={role} className="badge">
                  {role}
                </span>
              ))}
            </div>
          </div>
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
