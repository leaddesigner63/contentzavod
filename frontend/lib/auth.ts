"use client";

export type Role = "Admin" | "Editor" | "Viewer";

type JwtPayload = {
  sub?: string;
  roles?: string[];
};

const roleValues: Role[] = ["Admin", "Editor", "Viewer"];

function decodeBase64(value: string): string | null {
  if (!value) return null;
  try {
    if (typeof window !== "undefined" && typeof window.atob === "function") {
      return window.atob(value.replace(/-/g, "+").replace(/_/g, "/"));
    }
  } catch {
    return null;
  }

  if (typeof Buffer !== "undefined") {
    try {
      return Buffer.from(value, "base64").toString("utf-8");
    } catch {
      return null;
    }
  }

  return null;
}

export function decodeJwtPayload(token: string): JwtPayload | null {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length < 2) return null;
  const decoded = decodeBase64(parts[1]);
  if (!decoded) return null;
  try {
    return JSON.parse(decoded) as JwtPayload;
  } catch {
    return null;
  }
}

export function getRolesFromToken(token: string): Role[] {
  const payload = decodeJwtPayload(token);
  if (!payload?.roles) return [];
  return payload.roles.filter((role): role is Role =>
    roleValues.includes(role as Role)
  );
}

export function hasAnyRole(userRoles: Role[], required: Role[]): boolean {
  return required.some((role) => userRoles.includes(role));
}
