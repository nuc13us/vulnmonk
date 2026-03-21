// In Docker (production): REACT_APP_API_BASE_URL is empty/unset → falls back to "/api".
// nginx proxies /api/* → backend:8000/* on the internal Docker network.
// In local dev (npm start): setupProxy.js forwards /api/* → localhost:8000/* automatically.
const API_BASE = process.env.REACT_APP_API_BASE_URL || "/api";

// ==================== AUTH TOKEN MANAGEMENT ====================

export function getAuthToken() {
  return localStorage.getItem("auth_token");
}

export function setAuthToken(token) {
  localStorage.setItem("auth_token", token);
}

export function removeAuthToken() {
  localStorage.removeItem("auth_token");
}

export function isAuthenticated() {
  return !!getAuthToken();
}

// Helper to get headers with auth token
function getHeaders(includeAuth = true) {
  const headers = {
    "Content-Type": "application/json"
  };
  
  if (includeAuth) {
    const token = getAuthToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  
  return headers;
}

// Central fetch wrapper — automatically handles 401 auth expiry
// Sentinel error thrown on 401 — suppressed from the dev overlay in index.js
export class AuthExpiredError extends Error {
  constructor() {
    super("Session expired. Please log in again.");
    this.name = "AuthExpiredError";
  }
}

async function apiFetch(url, options = {}) {
  const res = await fetch(url, options);
  if (res.status === 401) {
    removeAuthToken();
    window.dispatchEvent(new CustomEvent("auth:expired"));
    throw new AuthExpiredError();
  }
  return res;
}

// ==================== AUTH ENDPOINTS ====================

export async function login(username, password) {
  const formData = new URLSearchParams();
  formData.append("username", username);
  formData.append("password", password);
  
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body: formData
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Login failed");
  }
  
  return res.json();
}

export async function getCurrentUser() {
  const res = await apiFetch(`${API_BASE}/auth/me`, {
    headers: getHeaders()
  });
  
  if (!res.ok) {
    throw new Error("Failed to get user info");
  }
  
  return res.json();
}

export async function changePassword(oldPassword, newPassword) {
  const res = await apiFetch(`${API_BASE}/auth/change-password`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({
      old_password: oldPassword,
      new_password: newPassword
    })
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Password change failed");
  }
  
  return res.json();
}

// ==================== USER MANAGEMENT ENDPOINTS (ADMIN ONLY) ====================

export async function getUsers() {
  const res = await apiFetch(`${API_BASE}/users/`, {
    headers: getHeaders()
  });
  return res.json();
}

export async function createUser(username, password, role) {
  const res = await apiFetch(`${API_BASE}/users/`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ username, password, role })
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to create user");
  }
  
  return res.json();
}

export async function updateUserRole(userId, role, isActive) {
  const res = await apiFetch(`${API_BASE}/users/${userId}/role`, {
    method: "PUT",
    headers: getHeaders(),
    body: JSON.stringify({ role, is_active: isActive })
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to update user");
  }
  
  return res.json();
}

// ==================== PROJECT ENDPOINTS ====================

export async function getProjects(page = 1, perPage = 100, search = "") {
  let url = `${API_BASE}/projects/?page=${page}&per_page=${perPage}`;
  if (search && search.trim()) {
    url += `&search=${encodeURIComponent(search.trim())}`;
  }
  
  const res = await apiFetch(url, {
    headers: getHeaders()
  });
  const data = await res.json();
  return data;
}

export async function getProjectById(projectId) {
  const res = await apiFetch(`${API_BASE}/projects/${projectId}`, {
    headers: getHeaders()
  });
  if (!res.ok) {
    throw new Error("Project not found");
  }
  return res.json();
}

export async function addGithubProject(github_url) {
  const headers = getHeaders();
  
  const res = await apiFetch(`${API_BASE}/projects/github/`, {
    method: "POST",
    headers: headers,
    body: JSON.stringify({ github_url })
  });
  
  
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(errorData.detail || `Error: ${res.status}`);
  }
  
  return res.json();
}

export async function updateExcludeRules(projectId, rules) {
  const res = await apiFetch(`${API_BASE}/projects/${projectId}/exclude_rules/`, {
    method: "PUT",
    headers: getHeaders(),
    body: JSON.stringify(rules)
  });

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to update exclude rules");
  }

  return res.json();
}

// ==================== SCAN ENDPOINTS ====================

export async function getScans(projectId) {
  const res = await apiFetch(`${API_BASE}/projects/${projectId}/scans/`, {
    headers: getHeaders()
  });
  return res.json();
}

export async function getScanDetail(scanId) {
  const res = await apiFetch(`${API_BASE}/scans/${scanId}/`, {
    headers: getHeaders()
  });
  return res.json();
}

export async function getScanStatus(projectId) {
  const res = await apiFetch(`${API_BASE}/projects/${projectId}/scan/status`, {
    headers: getHeaders()
  });
  return res.json(); // { scanning: bool }
}

export async function triggerScan(projectId) {
  const res = await apiFetch(`${API_BASE}/projects/${projectId}/scan/`, {
    method: "POST",
    headers: getHeaders()
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Scan failed" }));
    throw new Error(errorData.detail || `Scan failed with status ${res.status}`);
  }
  return res.json();
}

// ==================== FALSE POSITIVE ENDPOINTS ====================

export async function markFalsePositive(projectId, uniqueKey) {
  const res = await apiFetch(`${API_BASE}/projects/${projectId}/false-positives/`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ unique_key: uniqueKey })
  });
  return res.json();
}

export async function unmarkFalsePositive(projectId, uniqueKey) {
  const res = await apiFetch(`${API_BASE}/projects/${projectId}/false-positives?unique_key=${encodeURIComponent(uniqueKey)}`, {
    method: "DELETE",
    headers: getHeaders()
  });
  return res.json();
}

// ==================== INCLUDE RULES ENDPOINTS ====================

export async function updateIncludeRules(projectId, yamlContent, applyGlobalInclude) {
  const res = await apiFetch(`${API_BASE}/projects/${projectId}/include_rules/`, {
    method: "PUT",
    headers: getHeaders(),
    body: JSON.stringify({ 
      yaml_content: yamlContent,
      apply_global_include: applyGlobalInclude
    })
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to update include rules");
  }
  
  return res.json();
}

// ==================== GLOBAL CONFIGURATION ENDPOINTS ====================

export async function getGlobalConfig(key) {
  const res = await apiFetch(`${API_BASE}/configurations/global/${key}`, {
    headers: getHeaders()
  });
  return res.json();
}

export async function updateGlobalConfig(key, value) {
  const res = await apiFetch(`${API_BASE}/configurations/global/${key}`, {
    method: "PUT",
    headers: getHeaders(),
    body: JSON.stringify({ value })
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to update global configuration");
  }
  
  return res.json();
}

export async function getAllGlobalConfigs() {
  const res = await apiFetch(`${API_BASE}/configurations/global`, {
    headers: getHeaders()
  });
  return res.json();
}

// ==================== GITHUB INTEGRATION ENDPOINTS ====================

export async function getGitHubAppInstallUrl() {
  const res = await apiFetch(`${API_BASE}/integrations/github/app-install-url`, {
    headers: getHeaders()
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to get GitHub App install URL");
  }
  return res.json();
}

export async function getGitHubIntegrations() {
  const res = await apiFetch(`${API_BASE}/integrations/github`, {
    headers: getHeaders()
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to fetch integrations");
  }
  
  return res.json();
}

export async function createGitHubIntegration(integrationData) {
  const res = await apiFetch(`${API_BASE}/integrations/github`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(integrationData)
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to create integration");
  }
  
  return res.json();
}

export async function deleteGitHubIntegration(integrationId) {
  const res = await apiFetch(`${API_BASE}/integrations/github/${integrationId}`, {
    method: "DELETE",
    headers: getHeaders()
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to delete integration");
  }
  
  return res.json();
}

export async function getGitHubRepositories(integrationId, page = 1, perPage = 100) {
  const res = await apiFetch(`${API_BASE}/integrations/github/${integrationId}/repositories?page=${page}&per_page=${perPage}`, {
    headers: getHeaders()
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to fetch repositories");
  }
  
  const data = await res.json();
  return data;
}

export async function importGitHubProjects(integrationId, repoUrls) {
  const res = await apiFetch(`${API_BASE}/integrations/github/${integrationId}/import-projects`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(repoUrls)
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to import projects");
  }
  
  return res.json();
}

export async function syncGitHubAppInstallations() {
  const res = await apiFetch(`${API_BASE}/integrations/github/app/sync`, {
    method: "POST",
    headers: getHeaders()
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Sync failed");
  }
  return res.json();
}

// ==================== PR CHECK ENDPOINTS ====================

export async function getPRCheckConfig(projectId) {
  const res = await apiFetch(`${API_BASE}/projects/${projectId}/pr-check-config`, {
    headers: getHeaders()
  });
  if (!res.ok) throw new Error("Failed to load PR check config");
  return res.json();
}

export async function savePRCheckConfig(projectId, { enabled, webhook_secret, block_on_severity }) {
  const res = await apiFetch(`${API_BASE}/projects/${projectId}/pr-check-config`, {
    method: "PUT",
    headers: getHeaders(),
    body: JSON.stringify({ enabled, webhook_secret, block_on_severity })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to save PR check config");
  }
  return res.json();
}

export async function getPRScans(projectId) {
  const res = await apiFetch(`${API_BASE}/projects/${projectId}/pr-scans/`, {
    headers: getHeaders()
  });
  if (!res.ok) throw new Error("Failed to load PR scans");
  return res.json();
}

export async function getPRScanDetail(prScanId) {
  const res = await apiFetch(`${API_BASE}/pr-scans/${prScanId}/`, {
    headers: getHeaders()
  });
  if (!res.ok) throw new Error("Failed to load PR scan detail");
  return res.json();
}

export async function getGlobalPRCheckConfig() {
  const res = await apiFetch(`${API_BASE}/configurations/global/pr-checks`, {
    headers: getHeaders()
  });
  if (!res.ok) throw new Error("Failed to load global PR check config");
  return res.json();
}

export async function saveGlobalPRCheckConfig({ enabled, block_on_severity, webhook_secret }) {
  const res = await apiFetch(`${API_BASE}/configurations/global/pr-checks`, {
    method: "PUT",
    headers: getHeaders(),
    body: JSON.stringify({ enabled, block_on_severity, webhook_secret })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to save global PR config");
  }
  return res.json();
}
