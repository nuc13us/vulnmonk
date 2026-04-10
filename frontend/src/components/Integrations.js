import React, { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import {
  getGitHubIntegrations,
  getGitHubAppInstallUrl,
  syncGitHubAppInstallations,
  deleteGitHubIntegration,
  getGitHubRepositories,
  importGitHubProjects,
  getCurrentUser,
  getGlobalPRCheckConfig,
  saveGlobalPRCheckConfig
} from "../api";

function Integrations() {
  const [searchParams, setSearchParams] = useSearchParams();
  // Capture installation_id from GitHub's redirect callback on initial render only
  const [initialInstallationId] = useState(() => searchParams.get("installation_id"));
  const [integrations, setIntegrations] = useState([]);
  const [selectedIntegration, setSelectedIntegration] = useState(null);
  const [repositories, setRepositories] = useState([]);
  const [selectedRepos, setSelectedRepos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [importing, setImporting] = useState(false);
  const [user, setUser] = useState(null);
  const [logs, setLogs] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalRepos, setTotalRepos] = useState(0);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [globalPrEnabled, setGlobalPrEnabled] = useState(false);
  const [globalPrSeverity, setGlobalPrSeverity] = useState("none");
  const [globalPrThBlockOn, setGlobalPrThBlockOn] = useState("none");
  const [savingPrEnabled, setSavingPrEnabled] = useState(false);

  const loadUser = useCallback(async () => {
    try {
      const userData = await getCurrentUser();
      setUser(userData);
    } catch (error) {
      addLog("error", "Failed to load user data");
    }
  }, []);

  const loadIntegrations = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getGitHubIntegrations();
      setIntegrations(data);
      if (data.length > 0) {
        addLog("info", `Loaded ${data.length} integration(s)`);
      }
    } catch (error) {
      addLog("error", "Failed to load integrations: " + error.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadGlobalPrConfig = useCallback(async () => {
    try {
      const cfg = await getGlobalPRCheckConfig();
      setGlobalPrEnabled(cfg.enabled || false);
      setGlobalPrSeverity(cfg.block_on_severity || "none");
      setGlobalPrThBlockOn(cfg.th_block_on || "none");
    } catch (error) {
      // Non-critical — default to false
    }
  }, []);

  useEffect(() => {
    loadUser();
    loadGlobalPrConfig();

    if (initialInstallationId) {
      // GitHub redirected back after App installation — strip the URL param and auto-sync
      setSearchParams({}, { replace: true });
      addLog("info", `GitHub App installation detected (ID: ${initialInstallationId}). Syncing...`);
      setLoading(true);
      syncGitHubAppInstallations()
        .then(result => {
          if (result.count > 0) {
            addLog("info", `Synced ${result.count} installation(s): ${result.synced.join(", ")}`);
          } else {
            addLog("warn", "Sync returned no installations. The App may not be fully installed yet.");
          }
        })
        .catch(err => {
          addLog("warn", "Auto-sync skipped: " + err.message);
        })
        .finally(() => loadIntegrations());
    } else {
      loadIntegrations();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadUser, loadIntegrations, loadGlobalPrConfig, setSearchParams]);

  const handleRefresh = async () => {
    try {
      setLoading(true);
      addLog("info", "Syncing installations from GitHub App API...");
      const result = await syncGitHubAppInstallations();
      if (result.count > 0) {
        addLog("info", `Synced ${result.count} installation(s): ${result.synced.join(", ")}`);
      } else {
        addLog("info", "No installations found on GitHub. Make sure the App is installed on your account or org.");
      }
    } catch (error) {
      // Sync may fail if App credentials aren't configured — fall through to a plain reload
      addLog("warn", "Sync skipped: " + error.message);
    } finally {
      await loadIntegrations();
    }
  };

  const handleInstallApp = async () => {
    try {
      setLoading(true);
      addLog("info", "Fetching GitHub App install URL...");
      const { install_url } = await getGitHubAppInstallUrl();
      addLog("info", "Opening GitHub App installation page in a new tab...");
      addLog("info", "After installing, come back here and click the refresh button.");
      window.open(install_url, '_blank');
    } catch (error) {
      addLog("error", "Failed to get install URL: " + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteIntegration = async (integrationId) => {
    if (!window.confirm("Are you sure you want to delete this integration?")) {
      return;
    }

    try {
      setLoading(true);
      await deleteGitHubIntegration(integrationId);
      addLog("success", "Integration deleted successfully");
      
      // Clear selected integration if it was deleted
      if (selectedIntegration?.id === integrationId) {
        setSelectedIntegration(null);
        setRepositories([]);
        setSelectedRepos([]);
      }
      
      await loadIntegrations();
    } catch (error) {
      addLog("error", "Failed to delete integration: " + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectIntegration = async (integration) => {
    setSelectedIntegration(integration);
    setRepositories([]);
    setSelectedRepos([]);
    setSearchQuery("");
    setCurrentPage(1);
    setTotalRepos(0);
    setHasNextPage(false);
    
    try {
      setLoadingRepos(true);
      addLog("info", `Fetching repositories from ${integration.org_name}...`);
      const data = await getGitHubRepositories(integration.id, 1, 100);
      setRepositories(data.repositories);
      setTotalRepos(data.total);
      setHasNextPage(data.has_next);
      setCurrentPage(1);
      addLog("success", `Found ${data.total} repositories (showing ${data.repositories.length})`);
    } catch (error) {
      addLog("error", "Failed to fetch repositories: " + error.message);
    } finally {
      setLoadingRepos(false);
    }
  };

  const loadMoreRepositories = async () => {
    if (!selectedIntegration || !hasNextPage) return;
    
    try {
      setLoadingRepos(true);
      const nextPage = currentPage + 1;
      addLog("info", `Loading more repositories (page ${nextPage})...`);
      const data = await getGitHubRepositories(selectedIntegration.id, nextPage, 100);
      setRepositories(prev => {
        const existingUrls = new Set(prev.map(r => r.html_url));
        const unique = data.repositories.filter(r => !existingUrls.has(r.html_url));
        return [...prev, ...unique];
      });
      setCurrentPage(nextPage);
      setHasNextPage(data.has_next);
      addLog("success", `Loaded ${data.repositories.length} more repositories`);
    } catch (error) {
      addLog("error", "Failed to load more repositories: " + error.message);
    } finally {
      setLoadingRepos(false);
    }
  };

  const handleLoadAll = async () => {
    if (!selectedIntegration) return;
    try {
      setLoadingRepos(true);
      addLog("info", "Loading all repositories...");
      // Track pagination locally — React state is stale inside async loops
      let page = currentPage + 1;
      let hasMore = hasNextPage;
      while (hasMore) {
        const data = await getGitHubRepositories(selectedIntegration.id, page, 100);
        setRepositories(prev => {
          const existingUrls = new Set(prev.map(r => r.html_url));
          const unique = data.repositories.filter(r => !existingUrls.has(r.html_url));
          return [...prev, ...unique];
        });
        setCurrentPage(page);
        setHasNextPage(data.has_next);
        hasMore = data.has_next;
        page++;
      }
      addLog("success", "All repositories loaded");
    } catch (error) {
      addLog("error", "Failed to load all repositories: " + error.message);
    } finally {
      setLoadingRepos(false);
    }
  };

  const handleToggleRepo = (repoUrl) => {
    setSelectedRepos(prev => {
      if (prev.includes(repoUrl)) {
        return prev.filter(url => url !== repoUrl);
      } else {
        return [...prev, repoUrl];
      }
    });
  };

  const handleSelectAllRepos = () => {
    const filteredRepoUrls = filteredRepositories.map(repo => repo.html_url);
    if (selectedRepos.length === filteredRepoUrls.length && filteredRepoUrls.every(url => selectedRepos.includes(url))) {
      // Deselect all filtered repos
      setSelectedRepos(prev => prev.filter(url => !filteredRepoUrls.includes(url)));
    } else {
      // Select all filtered repos (merge with existing selection)
      setSelectedRepos(prev => {
        const merged = [...prev];
        filteredRepoUrls.forEach(url => {
          if (!merged.includes(url)) {
            merged.push(url);
          }
        });
        return merged;
      });
    }
  };

  // Filter repositories based on search query
  const filteredRepositories = repositories.filter(repo => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      repo.name.toLowerCase().includes(query) ||
      repo.full_name.toLowerCase().includes(query) ||
      (repo.description && repo.description.toLowerCase().includes(query)) ||
      (repo.language && repo.language.toLowerCase().includes(query))
    );
  });

  const handleImportProjects = async () => {
    if (selectedRepos.length === 0) {
      addLog("error", "Please select at least one repository to import");
      return;
    }

    try {
      setImporting(true);
      addLog("info", `Importing ${selectedRepos.length} repositories...`);
      const result = await importGitHubProjects(selectedIntegration.id, selectedRepos);
      
      addLog("success", 
        `Successfully imported ${result.total_imported} projects. Skipped ${result.total_skipped}.`
      );
      
      if (result.skipped.length > 0) {
        result.skipped.forEach(item => {
          addLog("warning", `Skipped ${item.url}: ${item.reason}`);
        });
      }
      
      // Clear selection after import
      setSelectedRepos([]);
    } catch (error) {
      addLog("error", "Failed to import projects: " + error.message);
    } finally {
      setImporting(false);
    }
  };

  const handleToggleGlobalPr = async () => {
    if (!isAdmin) return;
    const newValue = !globalPrEnabled;
    setSavingPrEnabled(true);
    try {
      const cfg = await getGlobalPRCheckConfig();
      await saveGlobalPRCheckConfig({ ...cfg, enabled: newValue, block_on_severity: globalPrSeverity, th_block_on: globalPrThBlockOn });
      setGlobalPrEnabled(newValue);
      addLog("success", `PR scanning ${newValue ? "enabled" : "disabled"} for all imported projects`);
    } catch (error) {
      addLog("error", "Failed to update PR scanning setting: " + error.message);
    } finally {
      setSavingPrEnabled(false);
    }
  };

  const handleSavePrSettings = async () => {
    if (!isAdmin) return;
    setSavingPrEnabled(true);
    try {
      const cfg = await getGlobalPRCheckConfig();
      await saveGlobalPRCheckConfig({ ...cfg, enabled: globalPrEnabled, block_on_severity: globalPrSeverity, th_block_on: globalPrThBlockOn });
      addLog("success", "PR scan settings saved");
    } catch (error) {
      addLog("error", "Failed to save PR scan settings: " + error.message);
    } finally {
      setSavingPrEnabled(false);
    }
  };

  const addLog = (type, message) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prevLogs => [...prevLogs, { type, message, timestamp }]);
  };

  const clearLogs = () => {
    setLogs([]);
  };

  const isAdmin = user?.role === "admin";

  return (
    <div className="integrations-container">
      <div className="integrations-header">
        <h2>GitHub Integrations</h2>
        <div style={{ display: "flex", gap: "8px" }}>
          {isAdmin && (
            <button
              className="btn-primary github-connect-btn"
              onClick={handleInstallApp}
              disabled={loading}
            >
              {loading ? "Loading..." : "🔗 Install GitHub App"}
            </button>
          )}
          <button
            className="btn-secondary-small"
            onClick={handleRefresh}
            disabled={loading}
            title="Sync installations from GitHub and refresh"
          >
            ↻ Refresh
          </button>
        </div>
      </div>

      {isAdmin && integrations.length === 0 && !loading && (
        <div className="card" style={{ marginBottom: "20px", textAlign: "center", padding: "40px" }}>
          <div style={{ fontSize: "3rem", marginBottom: "20px" }}>📦</div>
          <h3>Install the VulnMonk GitHub App</h3>
          <p style={{ color: "#64748b", marginBottom: "8px" }}>
            Install the GitHub App on your personal account or organization. GitHub will
            automatically notify VulnMonk — no webhook or token setup needed.
          </p>
          <p style={{ color: "#64748b", marginBottom: "24px", fontSize: "0.9rem" }}>
            After installing, click <strong>↻ Refresh</strong> to see your installation here.
          </p>
          <button
            className="btn-primary"
            onClick={handleInstallApp}
            disabled={loading}
            style={{ fontSize: "1.125rem", padding: "12px 32px" }}
          >
            Install GitHub App
          </button>
          <p style={{ fontSize: "0.8rem", color: "#94a3b8", marginTop: "16px" }}>
            Requires a GitHub App to be registered and <code>GITHUB_APP_SLUG</code> set in the backend.
          </p>
        </div>
      )}

      <div className="integrations-content">
        <div className="integrations-list">
          <div className="card">
            <h3>GitHub Accounts & Organizations</h3>
            {loading ? (
              <p>Loading integrations...</p>
            ) : integrations.length === 0 ? (
              <p className="no-data">No installations yet. Click "Install GitHub App" and come back after installing.</p>
            ) : (
              <div className="integrations-items">
                {integrations.map(integration => (
                  <div
                    key={integration.id}
                    className={`integration-item ${selectedIntegration?.id === integration.id ? 'active' : ''}`}
                    onClick={() => handleSelectIntegration(integration)}
                  >
                    <div className="integration-info">
                      <div className="integration-name">
                        <strong>{integration.org_name}</strong>
                        {integration.account_type && (
                          <span style={{
                            marginLeft: "8px", fontSize: "0.75rem", padding: "2px 6px",
                            background: integration.account_type === "Organization" ? "#dbeafe" : "#f0fdf4",
                            color: integration.account_type === "Organization" ? "#1d4ed8" : "#15803d",
                            borderRadius: "4px", fontWeight: 600
                          }}>
                            {integration.account_type}
                          </span>
                        )}
                      </div>
                      <div className="integration-date">
                        {integration.installation_id
                          ? `App install #${integration.installation_id}`
                          : `Added: ${new Date(integration.created_at).toLocaleDateString()}`}
                      </div>
                    </div>
                    {isAdmin && (
                      <button
                        className="btn-delete-small"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteIntegration(integration.id);
                        }}
                        disabled={loading}
                        title="Delete integration"
                      >
                        ×
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="repositories-panel">
          {selectedIntegration ? (
            <>
            <div className="card">
              <div className="repositories-header">
                <h3>Repositories from {selectedIntegration.org_name}</h3>
                {repositories.length > 0 && isAdmin && (
                  <div className="repositories-actions">
                    {hasNextPage && (
                      <button 
                        className="btn-secondary-small"
                        onClick={handleLoadAll}
                        disabled={loadingRepos}
                        style={{ marginRight: '10px' }}
                      >
                        Load All ({repositories.length}/{totalRepos})
                      </button>
                    )}
                    <button 
                      className="btn-secondary-small"
                      onClick={handleSelectAllRepos}
                    >
                      {selectedRepos.length > 0 && 
                       filteredRepositories.every(repo => selectedRepos.includes(repo.html_url))
                        ? `Deselect All ${filteredRepositories.length}`
                        : `Select All ${filteredRepositories.length}`}
                    </button>
                    <button
                      className="btn-primary"
                      onClick={handleImportProjects}
                      disabled={selectedRepos.length === 0 || importing}
                    >
                      {importing ? "Importing..." : `Import ${selectedRepos.length} Selected`}
                    </button>
                  </div>
                )}
              </div>

              {repositories.length > 0 && (
                <div className="repositories-search">
                  <input
                    type="text"
                    placeholder="🔍 Search repositories by name, description, or language..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="search-input"
                  />
                  {searchQuery && (
                    <span className="search-results-count">
                      Showing {filteredRepositories.length} of {totalRepos || repositories.length} repositories
                    </span>
                  )}
                </div>
              )}

              {loadingRepos ? (
                <p>Loading repositories...</p>
              ) : repositories.length === 0 ? (
                <p className="no-data">No repositories found or failed to load.</p>
              ) : filteredRepositories.length === 0 ? (
                <p className="no-data">No repositories match your search.</p>
              ) : (
                <div className="repositories-list">
                  {filteredRepositories.map((repo, index) => (
                    <div key={index} className="repository-item">
                      {isAdmin && (
                        <input
                          type="checkbox"
                          checked={selectedRepos.includes(repo.html_url)}
                          onChange={() => handleToggleRepo(repo.html_url)}
                          className="repo-checkbox"
                        />
                      )}
                      <div className="repository-info">
                        <div className="repository-name">
                          <a href={repo.html_url} target="_blank" rel="noopener noreferrer">
                            {repo.full_name}
                          </a>
                          {repo.language && (
                            <span className="badge badge-language">{repo.language}</span>
                          )}
                        </div>
                        {repo.description && (
                          <div className="repository-description">{repo.description}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              
              {/* Load More Button */}
              {!loadingRepos && repositories.length > 0 && hasNextPage && (
                <div style={{ marginTop: '20px', textAlign: 'center' }}>
                  <button 
                    onClick={loadMoreRepositories}
                    className="button"
                    style={{ padding: '10px 20px' }}
                  >
                    Load More Repositories ({repositories.length} of {totalRepos})
                  </button>
                </div>
              )}
              
              {/* Show total count */}
              {!loadingRepos && repositories.length > 0 && !hasNextPage && totalRepos > 0 && (
                <div style={{ marginTop: '20px', textAlign: 'center', color: '#6b7280' }}>
                  All {totalRepos} repositories loaded
                </div>
              )}
            </div>

            {/* PR Scan Settings for this org */}
            <div className="card" style={{ marginTop: "16px", padding: "20px 24px" }}>
              <h3 style={{ margin: "0 0 4px", fontSize: "1rem", fontWeight: 700 }}>🔁 PR Scan Settings</h3>
              <p style={{ margin: "0 0 16px", fontSize: "0.85rem", color: "#6b7280" }}>
                Controls automatic PR scanning for all imported projects via the GitHub App.
                Individual repos can be opted out in <strong>Configurations → PR Checks</strong>.
              </p>

              {/* Enable / Disable toggle */}
              <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "20px" }}>
                <span style={{ fontWeight: 600, fontSize: "0.95rem", color: "#374151" }}>PR Scanning</span>
                <button
                  onClick={handleToggleGlobalPr}
                  disabled={!isAdmin || savingPrEnabled}
                  style={{
                    padding: "6px 20px",
                    borderRadius: "20px",
                    border: "none",
                    cursor: isAdmin && !savingPrEnabled ? "pointer" : "not-allowed",
                    fontWeight: 700,
                    fontSize: "0.9rem",
                    background: globalPrEnabled ? "#10b981" : "#e5e7eb",
                    color: globalPrEnabled ? "white" : "#6b7280",
                    minWidth: "70px",
                    transition: "all 0.2s"
                  }}
                  title={!isAdmin ? "Admin access required" : ""}
                >
                  {savingPrEnabled ? "…" : (globalPrEnabled ? "ON" : "OFF")}
                </button>
                {!isAdmin && <span style={{ fontSize: "0.85rem", color: "#dc2626" }}>🔒 Admin only</span>}
              </div>

              {/* Block on severity */}
              {globalPrEnabled && (
                <div style={{ marginBottom: "20px" }}>
                  <label style={{ display: "block", fontWeight: 600, fontSize: "0.9rem", marginBottom: "6px", color: "#374151" }}>
                    Block PR on Severity
                  </label>
                  <select
                    value={globalPrSeverity}
                    onChange={e => setGlobalPrSeverity(e.target.value)}
                    disabled={!isAdmin}
                    style={{
                      padding: "8px 14px", borderRadius: "6px",
                      border: "2px solid #e5e7eb", fontSize: "0.9rem",
                      background: "#fff", cursor: isAdmin ? "pointer" : "not-allowed"
                    }}
                  >
                    <option value="none">Don't block (report only)</option>
                    <option value="INFO">Block on INFO, WARNING or ERROR</option>
                    <option value="WARNING">Block on WARNING or ERROR</option>
                    <option value="ERROR">Block on ERROR only</option>
                  </select>
                  <p style={{ fontSize: "0.8rem", color: "#6b7280", marginTop: "4px" }}>
                    Per-project settings override this default.
                  </p>
                </div>
              )}

              {/* Block on TruffleHog secrets */}
              {globalPrEnabled && (
                <div style={{ marginBottom: "20px" }}>
                  <label style={{ display: "block", fontWeight: 600, fontSize: "0.9rem", marginBottom: "6px", color: "#374151" }}>
                    Block PR on Secrets (TruffleHog)
                  </label>
                  <select
                    value={globalPrThBlockOn}
                    onChange={e => setGlobalPrThBlockOn(e.target.value)}
                    disabled={!isAdmin}
                    style={{
                      padding: "8px 14px", borderRadius: "6px",
                      border: "2px solid #e5e7eb", fontSize: "0.9rem",
                      background: "#fff", cursor: isAdmin ? "pointer" : "not-allowed"
                    }}
                  >
                    <option value="none">Don't block (report only)</option>
                    <option value="verified">Block on Verified secrets only</option>
                    <option value="all">Block on all secrets (verified + unverified)</option>
                  </select>
                  <p style={{ fontSize: "0.8rem", color: "#6b7280", marginTop: "4px" }}>
                    Per-project settings override this default.
                  </p>
                </div>
              )}

              {isAdmin && globalPrEnabled && (
                <button
                  onClick={handleSavePrSettings}
                  disabled={savingPrEnabled}
                  style={{
                    padding: "9px 22px", background: "#2563eb", color: "white",
                    border: "none", borderRadius: "6px", cursor: savingPrEnabled ? "not-allowed" : "pointer",
                    fontWeight: 600, fontSize: "0.9rem"
                  }}
                >
                  {savingPrEnabled ? "Saving…" : "Save Settings"}
                </button>
              )}
            </div>
            </>
          ) : (
            <>
              <div className="card" style={{ marginBottom: "16px" }}>
                <p className="no-data">Select an integration to view repositories</p>
              </div>
              <div className="card" style={{ padding: "20px 24px" }}>
                <p style={{ color: "#9ca3af", fontSize: "0.9rem" }}>Select a GitHub account or organisation to configure PR scanning.</p>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Logs Section */}
      {logs.length > 0 && (
        <div className="card logs-section">
          <div className="logs-header">
            <h3>Activity Logs</h3>
            <button className="btn-secondary-small" onClick={clearLogs}>
              Clear Logs
            </button>
          </div>
          <div className="logs-container">
            {logs.map((log, index) => (
              <div key={index} className={`log-item log-${log.type}`}>
                <span className="log-timestamp">[{log.timestamp}]</span>
                <span className="log-message">{log.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default Integrations;
