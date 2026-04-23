const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:6000";
const TOKEN_KEY = "nest_token";

export type Role = "admin" | "client" | "investor";

export type AuthUser = {
  id: string;
  email: string;
  role: Role;
  name: string;
  client_id: string | null;
  created_at: string;
};

export type AuthSession = {
  token: string;
  expires_at: string;
  user: AuthUser;
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export function authHeader(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export async function login(email: string, password: string): Promise<AuthSession> {
  const r = await fetch(`${BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const body = await r.json();
  if (!r.ok) throw new Error(body.error || `login failed (${r.status})`);
  setToken(body.token);
  return body;
}

export async function register(input: {
  email: string;
  password: string;
  name: string;
}): Promise<AuthSession> {
  const r = await fetch(`${BASE}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const body = await r.json();
  if (!r.ok) throw new Error(body.error || `register failed (${r.status})`);
  setToken(body.token);
  return body;
}

export async function fetchMe(): Promise<AuthUser | null> {
  const t = getToken();
  if (!t) return null;
  const r = await fetch(`${BASE}/api/auth/me`, {
    headers: { Authorization: `Bearer ${t}` },
    cache: "no-store",
  });
  if (r.status === 401) {
    setToken(null);
    return null;
  }
  if (!r.ok) return null;
  return r.json();
}

export function logout() {
  setToken(null);
}

export function roleLanding(role: Role): string {
  if (role === "admin") return "/admin/marketing";
  if (role === "client") return "/dashboard";
  return "/dashboard";
}

export async function changePassword(current_password: string, new_password: string): Promise<{ ok: boolean }> {
  const r = await fetch(`${BASE}/api/auth/password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: JSON.stringify({ current_password, new_password }),
  });
  const body = await r.json();
  if (!r.ok) throw new Error(body.error || `password change failed (${r.status})`);
  return body;
}
