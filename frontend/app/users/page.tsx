"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { getRolesFromToken, hasAnyRole, type Role } from "../../lib/auth";
import { apiFetch } from "../../lib/api";
import { useLocalStorage } from "../../lib/useLocalStorage";

type User = {
  id: number;
  email: string;
  roles: string[];
  is_active: boolean;
  created_at: string;
};

type RoleItem = {
  id: number;
  name: string;
  created_at: string;
};

export default function UsersPage() {
  const [token] = useLocalStorage("contentzavod-token", "");
  const [apiBaseUrl] = useLocalStorage(
    "contentzavod-api-base",
    "http://localhost:8000"
  );
  const roles = useMemo<Role[]>(
    () => getRolesFromToken(token),
    [token]
  );
  const isAdmin = hasAnyRole(roles, ["Admin"]);

  const [users, setUsers] = useState<User[]>([]);
  const [roleOptions, setRoleOptions] = useState<RoleItem[]>([]);
  const [form, setForm] = useState({
    email: "",
    password: "",
    roles: ["Viewer"],
  });
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const loadUsers = useCallback(async () => {
    if (!isAdmin) return;
    try {
      setError(null);
      const [usersData, rolesData] = await Promise.all([
        apiFetch<User[]>(`/users`, {}, token, apiBaseUrl),
        apiFetch<RoleItem[]>(`/roles`, {}, token, apiBaseUrl),
      ]);
      setUsers(usersData);
      setRoleOptions(rolesData);
    } catch (err) {
      setError((err as { message: string }).message);
    }
  }, [isAdmin, token, apiBaseUrl]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const toggleRole = (roleName: string) => {
    setForm((prev) => {
      if (prev.roles.includes(roleName)) {
        return { ...prev, roles: prev.roles.filter((role) => role !== roleName) };
      }
      return { ...prev, roles: [...prev.roles, roleName] };
    });
  };

  const createUser = async () => {
    if (!isAdmin) return;
    setIsSaving(true);
    try {
      setError(null);
      await apiFetch<User>(
        `/users`,
        {
          method: "POST",
          body: JSON.stringify({
            email: form.email,
            password: form.password,
            roles: form.roles.length > 0 ? form.roles : ["Viewer"],
            is_active: true,
          }),
        },
        token,
        apiBaseUrl
      );
      setForm({ email: "", password: "", roles: ["Viewer"] });
      await loadUsers();
    } catch (err) {
      setError((err as { message: string }).message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="section-grid">
      <section className="card">
        <h3>Политика доступа</h3>
        <ul>
          <li>Admin: полный доступ, управление бюджетами, токенами и ролями.</li>
          <li>Editor: контент, контент-план, публикации без секретов.</li>
          <li>Viewer: только просмотр аналитики и статусов.</li>
        </ul>
        {!isAdmin && (
          <div className="notice">
            Управление пользователями доступно только для роли Admin.
          </div>
        )}
        {error && <div className="notice">Ошибка: {error}</div>}
      </section>

      <section className="card">
        <h3>Пользователи</h3>
        {isAdmin ? (
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Email</th>
                <th>Роли</th>
                <th>Статус</th>
                <th>Создан</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.id}</td>
                  <td>{user.email}</td>
                  <td>{user.roles.join(", ")}</td>
                  <td>
                    <span className={`badge ${user.is_active ? "success" : "danger"}`}>
                      {user.is_active ? "active" : "disabled"}
                    </span>
                  </td>
                  <td>{new Date(user.created_at).toLocaleString("ru-RU")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <span className="muted">Недостаточно прав для просмотра списка.</span>
        )}
      </section>

      <section className="card">
        <h3>Создать пользователя</h3>
        <input
          placeholder="Email"
          value={form.email}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, email: event.target.value }))
          }
          disabled={!isAdmin}
        />
        <input
          type="password"
          placeholder="Пароль (минимум 8 символов)"
          value={form.password}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, password: event.target.value }))
          }
          disabled={!isAdmin}
        />
        <div className="list">
          <strong>Роли</strong>
          {roleOptions.length === 0 && (
            <span className="muted">Справочник ролей не загружен.</span>
          )}
          {roleOptions.map((role) => (
            <label key={role.id} className="checkbox">
              <input
                type="checkbox"
                checked={form.roles.includes(role.name)}
                onChange={() => toggleRole(role.name)}
                disabled={!isAdmin}
              />
              {role.name}
            </label>
          ))}
        </div>
        <button onClick={createUser} disabled={!isAdmin || isSaving}>
          {isSaving ? "Создание..." : "Создать пользователя"}
        </button>
      </section>
    </div>
  );
}
