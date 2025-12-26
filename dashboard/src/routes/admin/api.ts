// frontend/src/admin/api.ts
import { adminAuthHeader, clearAdminToken } from "./auth";

export type AdminMe = {
  admin_id: number;
  email: string;
  is_active: boolean;
  created_at: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function fetchAdminMe(): Promise<AdminMe> {
  const res = await fetch(`${API_BASE}/api/admin/me`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      ...adminAuthHeader(),
    },
  });

  if (res.status === 401) {
    // silent logout
    clearAdminToken();
    throw new Error("UNAUTHORIZED");
  }

  if (!res.ok) {
    throw new Error(`admin/me failed (${res.status})`);
  }

  return res.json();
}