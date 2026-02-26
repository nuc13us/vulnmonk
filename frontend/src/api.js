const API_BASE = process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000";

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
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: getHeaders()
  });
  
  if (!res.ok) {
    throw new Error("Failed to get user info");
  }
  
  return res.json();
}

export async function changePassword(oldPassword, newPassword) {
  const res = await fetch(`${API_BASE}/auth/change-password`, {
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
  const res = await fetch(`${API_BASE}/users/`, {
    headers: getHeaders()
  });
  return res.json();
}

export async function createUser(username, password, role) {
  const res = await fetch(`${API_BASE}/users/`, {
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
  const res = await fetch(`${API_BASE}/users/${userId}/role`, {
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
  
  const res = await fetch(url, {
    headers: getHeaders()
  });
  const data = await res.json();
  console.log(`[DEBUG] Fetched page ${data.page}/${data.total_pages}: ${data.projects?.length} projects (total: ${data.total}${search ? `, search: "${search}"` : ''})`);
  return data;
}

export async function addGithubProject(github_url) {
  const headers = getHeaders();
  console.log("[DEBUG] addGithubProject headers:", headers);
  console.log("[DEBUG] Auth token:", getAuthToken());
  
  const res = await fetch(`${API_BASE}/projects/github/`, {
    method: "POST",
    headers: headers,
    body: JSON.stringify({ github_url })
  });
  
  console.log("[DEBUG] Response status:", res.status);
  
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "Unknown error" }));
    console.error("[DEBUG] Error response:", errorData);
    throw new Error(errorData.detail || `Error: ${res.status}`);
  }
  
  return res.json();
}

export async function updateExcludeRules(projectId, rules) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/exclude_rules/`, {
    method: "PUT",
    headers: getHeaders(),
    body: JSON.stringify(rules)
  });
  return res.json();
}

// ==================== SCAN ENDPOINTS ====================

export async function getScans(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/scans/`, {
    headers: getHeaders()
  });
  return res.json();
}

export async function getScanDetail(scanId) {
  const res = await fetch(`${API_BASE}/scans/${scanId}/`, {
    headers: getHeaders()
  });
  return res.json();
}

export async function triggerScan(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/scan/`, {
    method: "POST",
    headers: getHeaders()
  });
  return res.json();
}

// ==================== FALSE POSITIVE ENDPOINTS ====================

export async function markFalsePositive(projectId, uniqueKey) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/false-positives/`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ unique_key: uniqueKey })
  });
  return res.json();
}

export async function getFalsePositives(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/false-positives/`, {
    headers: getHeaders()
  });
  return res.json();
}

export async function unmarkFalsePositive(projectId, uniqueKey) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/false-positives/${encodeURIComponent(uniqueKey)}`, {
    method: "DELETE",
    headers: getHeaders()
  });
  return res.json();
}

// ==================== INCLUDE RULES ENDPOINTS ====================

export async function updateIncludeRules(projectId, yamlContent, applyGlobalInclude) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/include_rules/`, {
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

export async function updateGlobalPreferences(projectId, applyGlobalExclude, applyGlobalInclude) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/global_preferences/`, {
    method: "PUT",
    headers: getHeaders(),
    body: JSON.stringify({ 
      apply_global_exclude: applyGlobalExclude,
      apply_global_include: applyGlobalInclude
    })
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to update global preferences");
  }
  
  return res.json();
}

// ==================== GLOBAL CONFIGURATION ENDPOINTS ====================

export async function getGlobalConfig(key) {
  const res = await fetch(`${API_BASE}/configurations/global/${key}`, {
    headers: getHeaders()
  });
  return res.json();
}

export async function updateGlobalConfig(key, value) {
  const res = await fetch(`${API_BASE}/configurations/global/${key}`, {
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
  const res = await fetch(`${API_BASE}/configurations/global`, {
    headers: getHeaders()
  });
  return res.json();
}

// ==================== GITHUB INTEGRATION ENDPOINTS ====================

export async function getGitHubAuthUrl() {
  const res = await fetch(`${API_BASE}/integrations/github/auth-url`, {
    headers: getHeaders()
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to get GitHub auth URL");
  }
  
  return res.json();
}

export async function handleGitHubCallback(code) {
  const res = await fetch(`${API_BASE}/integrations/github/callback`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ code: code })
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to complete GitHub authentication");
  }
  
  return res.json();
}

export async function getGitHubIntegrations() {
  const res = await fetch(`${API_BASE}/integrations/github`, {
    headers: getHeaders()
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to fetch integrations");
  }
  
  return res.json();
}

export async function createGitHubIntegration(integrationData) {
  const res = await fetch(`${API_BASE}/integrations/github`, {
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
  const res = await fetch(`${API_BASE}/integrations/github/${integrationId}`, {
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
  const res = await fetch(`${API_BASE}/integrations/github/${integrationId}/repositories?page=${page}&per_page=${perPage}`, {
    headers: getHeaders()
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to fetch repositories");
  }
  
  const data = await res.json();
  console.log(`[DEBUG] Received page ${data.page}/${data.total_pages}: ${data.repositories.length} repos (total: ${data.total})`);
  return data;
}

export async function importGitHubProjects(integrationId, repoUrls) {
  const res = await fetch(`${API_BASE}/integrations/github/${integrationId}/import-projects`, {
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
