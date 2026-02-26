import React, { useState, useEffect, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  getGitHubIntegrations,
  getGitHubAuthUrl,
  handleGitHubCallback,
  deleteGitHubIntegration,
  getGitHubRepositories,
  importGitHubProjects,
  getCurrentUser
} from "../api";

function Integrations() {
  const location = useLocation();
  const navigate = useNavigate();
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

  const handleOAuthCallback = useCallback(async (code) => {
    try {
      setLoading(true);
      addLog("info", "Completing GitHub authentication...");
      console.log("OAuth code received:", code);
      const result = await handleGitHubCallback(code);
      console.log("OAuth callback result:", result);
      addLog("success", result.message || "Connected to GitHub successfully");
      if (result.github_user) {
        addLog("info", `Authenticated as: ${result.github_user}`);
      }
      if (result.total_integrations) {
        addLog("info", `Created/updated ${result.total_integrations} integration(s)`);
      }
      if (result.created && result.created.length > 0) {
        addLog("success", `Created: ${result.created.join(", ")}`);
      }
      if (result.updated && result.updated.length > 0) {
        addLog("info", `Updated: ${result.updated.join(", ")}`);
      }
      await loadIntegrations();
    } catch (error) {
      console.error("OAuth callback error:", error);
      addLog("error", "Failed to complete GitHub authentication: " + error.message);
    } finally {
      setLoading(false);
    }
  }, [loadIntegrations]);

  useEffect(() => {
    loadUser();
    loadIntegrations();
    
    // Check if we're returning from GitHub OAuth
    const params = new URLSearchParams(location.search);
    const code = params.get('code');
    if (code) {
      handleOAuthCallback(code);
      // Clean up URL
      navigate('/integrations', { replace: true });
    }
  }, [location, navigate, loadUser, loadIntegrations, handleOAuthCallback]);

  const handleConnectGitHub = async () => {
    try {
      setLoading(true);
      addLog("info", "Opening GitHub authentication in new tab...");
      const { auth_url } = await getGitHubAuthUrl();
      window.open(auth_url, '_blank');
      addLog("info", "Complete authentication in the new tab, then refresh this page");
      setLoading(false);
    } catch (error) {
      addLog("error", "Failed to start GitHub authentication: " + error.message);
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
      console.log(`[DEBUG] Received ${data.repositories.length} repos in component`);
      console.log(`[DEBUG] Total repos: ${data.total}, Has next: ${data.has_next}`);
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
      console.log(`[DEBUG] Loaded page ${nextPage}: ${data.repositories.length} repos`);
      setRepositories(prev => [...prev, ...data.repositories]);
      setCurrentPage(nextPage);
      setHasNextPage(data.has_next);
      addLog("success", `Loaded ${data.repositories.length} more repositories`);
    } catch (error) {
      addLog("error", "Failed to load more repositories: " + error.message);
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
        {isAdmin && (
          <button 
            className="btn-primary github-connect-btn" 
            onClick={handleConnectGitHub}
            disabled={loading}
          >
            {loading ? "Connecting..." : "🔗 Connect with GitHub"}
          </button>
        )}
      </div>

      {isAdmin && integrations.length === 0 && !loading && (
        <div className="card" style={{ marginBottom: "20px", textAlign: "center", padding: "40px" }}>
          <div style={{ fontSize: "3rem", marginBottom: "20px" }}>🔗</div>
          <h3>Connect Your GitHub Account</h3>
          <p style={{ color: "#64748b", marginBottom: "24px" }}>
            Authenticate with GitHub to create separate integrations for your personal account and each organization you belong to.
            This provides better access control and management.
          </p>
          <button 
            className="btn-primary" 
            onClick={handleConnectGitHub}
            disabled={loading}
            style={{ fontSize: "1.125rem", padding: "12px 32px" }}
          >
            Connect with GitHub
          </button>
          <p style={{ fontSize: "0.875rem", color: "#94a3b8", marginTop: "16px" }}>
            Separate integrations will be created for your personal account and each organization.
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
              <p className="no-data">No integrations configured yet. Click "Connect with GitHub" to add your accounts and organizations.</p>
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
                      </div>
                      <div className="integration-date">
                        Added: {new Date(integration.created_at).toLocaleDateString()}
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
            <div className="card">
              <div className="repositories-header">
                <h3>Repositories from {selectedIntegration.org_name}</h3>
                {repositories.length > 0 && isAdmin && (
                  <div className="repositories-actions">
                    {hasNextPage && (
                      <button 
                        className="btn-secondary-small"
                        onClick={async () => {
                          addLog("info", "Loading all repositories...");
                          while (hasNextPage) {
                            await loadMoreRepositories();
                          }
                          addLog("success", "All repositories loaded");
                        }}
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
                            {repo.name}
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
          ) : (
            <div className="card">
              <p className="no-data">Select an integration to view repositories</p>
            </div>
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
