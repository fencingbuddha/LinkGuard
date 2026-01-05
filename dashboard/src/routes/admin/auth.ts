// dashboard/src/routes/admin/auth.ts

export const ADMIN_API_KEY_STORAGE = "linkguard_admin_api_key";

export function getAdminApiKey(): string | null {
  return localStorage.getItem(ADMIN_API_KEY_STORAGE);
}

export function setAdminApiKey(apiKey: string): void {
  localStorage.setItem(ADMIN_API_KEY_STORAGE, apiKey);
}

export function clearAdminApiKey(): void {
  localStorage.removeItem(ADMIN_API_KEY_STORAGE);
}

export function adminAuthHeader(): Record<string, string> {
  const apiKey = getAdminApiKey();
  return apiKey ? { "X-API-Key": apiKey } : {};
}