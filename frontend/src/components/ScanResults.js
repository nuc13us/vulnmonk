
import React, { useState, useEffect } from "react";
import { getScans, getScanDetail, triggerScan, markFalsePositive } from "../api";

// Parse date string from backend (may be missing Z suffix) and format in user's local timezone
function formatDate(dateStr) {
  if (!dateStr) return '';
  // Append 'Z' if no timezone info present so JS treats it as UTC
  const iso = /[Zz]|[+-]\d{2}:?\d{2}$/.test(dateStr) ? dateStr : dateStr + 'Z';
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

export default function ScanResults({ project, user }) {
  const [scanHistory, setScanHistory] = useState([]);
  const [scanDetail, setScanDetail] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [showFalsePositives, setShowFalsePositives] = useState(false);
  const [showLogs, setShowLogs] = useState(true);
  
  const isAdmin = user && user.role === "admin";
  
  // Filter states
  const [filters, setFilters] = useState({
    severity: 'all',
    searchText: '',
    vulnerabilityClass: 'all'
  });
  
  // Sort states
  const [sortBy, setSortBy] = useState('severity-desc'); // severity-desc, severity-asc, path-asc, path-desc, line-asc, line-desc

  useEffect(() => {
    if (project) {
      getScans(project.id).then(setScanHistory);
      setScanDetail(null);
      setLogs([]);
    }
  }, [project]);

  const handleScan = async () => {
    setScanning(true);
    setLogs(l => [
      { type: 'info', msg: 'Scan started...' },
      ...l.slice(0, 4)
    ]);
    try {
      await triggerScan(project.id);
      setScanHistory(await getScans(project.id));
      setLogs(l => [
        { type: 'success', msg: 'Scan completed.' },
        ...l.slice(0, 4)
      ]);
    } catch (err) {
      setLogs(l => [
        { type: 'error', msg: `Scan failed: ${err.message}` },
        ...l.slice(0, 4)
      ]);
    } finally {
      setScanning(false);
    }
  };

  const handleSelectScan = async (scan) => {
    setScanDetail(null);
    setLogs(l => [
      { type: 'info', msg: `Viewing scan from ${new Date(scan.scan_date).toLocaleString()}` },
      ...l.slice(0, 4)
    ]);
    const detail = await getScanDetail(scan.id);
    setScanDetail(detail);
  };

  const handleMarkFalsePositive = async (uniqueKey) => {
    await markFalsePositive(project.id, uniqueKey);
    setLogs(l => [
      { type: 'success', msg: 'Marked as false positive' },
      ...l.slice(0, 4)
    ]);
    // Refresh scan detail
    if (scanDetail) {
      const detail = await getScanDetail(scanDetail.id);
      setScanDetail(detail);
    }
  };

  const buildGitHubUrl = (path, line) => {
    if (!project.github_url || !path) return null;
    // Remove .git suffix and construct file URL
    const baseUrl = project.github_url.replace(/\.git$/, "");
    const lineFragment = line ? `#L${line}` : "";
    return `${baseUrl}/blob/master/${path}${lineFragment}`;
  };

  const buildSemgrepUrl = (checkId) => {
    if (!checkId) return null;
    return `https://semgrep.dev/r/${checkId}`;
  };

  const badgeColor = (sev) => {
    if (!sev) return '';
    const sevLower = sev.toLowerCase();
    if (sevLower === 'error' || sevLower === 'critical' || sevLower === 'c') return 'badge badge-error';
    if (sevLower === 'warning' || sevLower === 'high' || sevLower === 'h' || sevLower === 'medium' || sevLower === 'm') return 'badge badge-warning';
    if (sevLower === 'info' || sevLower === 'low' || sevLower === 'l') return 'badge badge-info';
    return 'badge';
  };

  return (
    <div className="project-detail">
      <div style={{ marginBottom: '20px' }}>
        <h2 style={{ marginBottom: '8px' }}>{(() => {
          // Extract project name safely
          if (project.github_url) {
            return project.github_url.split('/').filter(part => part).pop().replace('.git', '');
          } else if (project.local_path) {
            return project.local_path.split('/').filter(part => part).pop();
          } else if (project.name) {
            return project.name;
          }
          return 'Unnamed';
        })()}</h2>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span style={{ 
            fontSize: '0.9rem', 
            color: '#64748b',
            fontWeight: 500 
          }}>
            📋 {scanHistory.length} {scanHistory.length === 1 ? 'scan' : 'scans'} in history
          </span>
          {scanHistory.length > 0 && (
            <span style={{ 
              fontSize: '0.85rem', 
              color: '#94a3b8' 
            }}>
              • Last scan: {formatDate(scanHistory[0].scan_date)}
            </span>
          )}
        </div>
      </div>

      <div className="project-controls">
        <button 
          onClick={handleScan} 
          disabled={scanning || !isAdmin} 
          className="primary-btn"
          title={!isAdmin ? "Admin access required" : ""}
        >
          {scanning ? "Scanning..." : "Run Security Scan"}
        </button>
        {!isAdmin && (
          <span style={{ fontSize: '0.9rem', color: '#dc2626', marginLeft: '12px' }}>
            🔒 View-only mode (Admin access required for scans)
          </span>
        )}
      </div>

      {logs.length > 0 && (
        <div className="scan-logs-container">
          <div 
            className="scan-logs-header" 
            onClick={() => setShowLogs(!showLogs)}
            style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: showLogs ? '12px' : '0' }}
          >
            <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#334155' }}>
              Recent Activity ({logs.length})
            </span>
            <span style={{ fontSize: '1.2rem', color: '#64748b' }}>
              {showLogs ? '▼' : '▶'}
            </span>
          </div>
          {showLogs && (
            <div className="scan-logs-list">
              {logs.slice(0, 3).map((log, i) => (
                <div key={i} className={`log log-${log.type}`}>{log.msg}</div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="scan-history-section">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <h3 style={{ margin: 0 }}>Scan History</h3>
        </div>
        {scanHistory.length > 0 ? (
        <div className="scan-history-compact">
          {scanHistory.map((scan, idx) => (
            <button
              key={scan.id}
              className={`scan-history-row${scanDetail && scanDetail.id === scan.id ? ' active' : ''}`}
              onClick={() => handleSelectScan(scan)}
            >
              <span className="scan-history-row-num">#{idx + 1}</span>
              <span className="scan-history-row-date">{formatDate(scan.scan_date)}</span>
              <span className="finding-count">{scan.findings_count} findings</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="empty-message">No scans yet. Click "Run Security Scan" to trigger a scan.</p>
      )}
      </div>

      {scanDetail && (
        <>
          <div className="scan-detail-section">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h4 style={{ margin: 0 }}>Open Findings</h4>
              <button 
                onClick={() => setShowFalsePositives(!showFalsePositives)}
                className="secondary"
                style={{ fontSize: "0.9rem", padding: "8px 16px" }}
              >
                {showFalsePositives ? "Hide" : "Show"} False Positives ({scanDetail.result_json?.false_positives?.length || 0})
              </button>
            </div>
            
            {/* Filter Controls */}
            <div className="filters-container">
              <div className="filter-group">
                <label>Severity:</label>
                <select 
                  value={filters.severity} 
                  onChange={(e) => setFilters({...filters, severity: e.target.value})}
                  className="filter-select"
                >
                  <option value="all">All Severities</option>
                  <option value="error">ERROR</option>
                  <option value="warning">WARNING</option>
                  <option value="info">INFO</option>
                </select>
              </div>
              
              <div className="filter-group">
                <label>Search:</label>
                <input 
                  type="text"
                  placeholder="Filter by path, line, or class..."
                  value={filters.searchText}
                  onChange={(e) => setFilters({...filters, searchText: e.target.value})}
                  className="filter-input"
                />
              </div>
              
              <div className="filter-group">
                <label>Sort By:</label>
                <select 
                  value={sortBy} 
                  onChange={(e) => setSortBy(e.target.value)}
                  className="filter-select"
                >
                  <option value="severity-desc">Severity (High → Low)</option>
                  <option value="severity-asc">Severity (Low → High)</option>
                  <option value="path-asc">Path (A → Z)</option>
                  <option value="path-desc">Path (Z → A)</option>
                  <option value="line-asc">Line (Low → High)</option>
                  <option value="line-desc">Line (High → Low)</option>
                </select>
              </div>
              
              {filters.severity !== 'all' || filters.searchText ? (
                <button 
                  onClick={() => setFilters({ severity: 'all', searchText: '', vulnerabilityClass: 'all' })}
                  className="clear-filters-btn"
                >
                  Clear Filters
                </button>
              ) : null}
            </div>
            
            {Array.isArray(scanDetail.result_json?.results) && scanDetail.result_json.results.length > 0 ? (
              <table>
                <thead>
                  <tr>
                    <th>Path</th>
                    <th>Line</th>
                    <th>Class</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {scanDetail.result_json.results
                    .filter(vul => {
                      // Filter by severity
                      if (filters.severity !== 'all') {
                        const vulSeverity = (vul.extra?.severity || '').toLowerCase();
                        const filterSev = filters.severity.toLowerCase();
                        
                        // Map old severity values to new ones for compatibility
                        let normalizedVulSev = vulSeverity;
                        if (vulSeverity === 'critical' || vulSeverity === 'c') normalizedVulSev = 'error';
                        if (vulSeverity === 'high' || vulSeverity === 'h' || vulSeverity === 'medium' || vulSeverity === 'm') normalizedVulSev = 'warning';
                        if (vulSeverity === 'low' || vulSeverity === 'l') normalizedVulSev = 'info';
                        
                        if (normalizedVulSev !== filterSev && vulSeverity !== filterSev) {
                          return false;
                        }
                      }
                      
                      // Filter by search text
                      if (filters.searchText) {
                        const searchLower = filters.searchText.toLowerCase();
                        const path = (vul.path || '').toLowerCase();
                        const line = (vul.start?.line || '').toString();
                        const vulClass = Array.isArray(vul.extra?.metadata?.vulnerability_class) 
                          ? vul.extra.metadata.vulnerability_class.join(', ').toLowerCase()
                          : (vul.extra?.metadata?.vulnerability_class || '').toLowerCase();
                        const checkId = (vul.check_id || '').toLowerCase();
                        
                        if (!path.includes(searchLower) && 
                            !line.includes(searchLower) && 
                            !vulClass.includes(searchLower) &&
                            !checkId.includes(searchLower)) {
                          return false;
                        }
                      }
                      
                      return true;
                    })
                    .sort((a, b) => {
                      // Sort logic
                      const [field, direction] = sortBy.split('-');
                      let comparison = 0;
                      
                      if (field === 'severity') {
                        // Define severity order (ERROR > WARNING > INFO)
                        const severityOrder = { error: 3, warning: 2, info: 1 };
                        const getSeverityValue = (vul) => {
                          const sev = (vul.extra?.severity || '').toLowerCase();
                          // Map old values to new
                          if (sev === 'critical' || sev === 'c') return severityOrder.error;
                          if (sev === 'high' || sev === 'h' || sev === 'medium' || sev === 'm') return severityOrder.warning;
                          if (sev === 'low' || sev === 'l' || sev === 'info') return severityOrder.info;
                          if (sev === 'error') return severityOrder.error;
                          if (sev === 'warning') return severityOrder.warning;
                          return 0;
                        };
                        comparison = getSeverityValue(b) - getSeverityValue(a);
                        if (direction === 'asc') comparison = -comparison;
                      } else if (field === 'path') {
                        const pathA = (a.path || '').toLowerCase();
                        const pathB = (b.path || '').toLowerCase();
                        comparison = pathA.localeCompare(pathB);
                        if (direction === 'desc') comparison = -comparison;
                      } else if (field === 'line') {
                        const lineA = a.start?.line || 0;
                        const lineB = b.start?.line || 0;
                        comparison = lineA - lineB;
                        if (direction === 'desc') comparison = -comparison;
                      }
                      
                      return comparison;
                    })
                    .map((vul, idx) => {
                    const githubUrl = buildGitHubUrl(vul.path, vul.start?.line);
                    const semgrepUrl = buildSemgrepUrl(vul.check_id);
                    const vulClass = Array.isArray(vul.extra?.metadata?.vulnerability_class) 
                      ? vul.extra.metadata.vulnerability_class.join(", ") 
                      : vul.extra?.metadata?.vulnerability_class || '';
                    
                    return (
                      <tr key={idx}>
                        <td>
                          {githubUrl ? (
                            <a href={githubUrl} target="_blank" rel="noopener noreferrer" className="github-link">
                              {vul.path}
                            </a>
                          ) : (
                            vul.path
                          )}
                        </td>
                        <td>{vul.start?.line}</td>
                        <td>
                          {semgrepUrl && vulClass ? (
                            <a href={semgrepUrl} target="_blank" rel="noopener noreferrer" className="github-link">
                              {vulClass}
                            </a>
                          ) : (
                            vulClass
                          )}
                        </td>
                        <td><span className={badgeColor(vul.extra?.severity)}>{vul.extra?.severity}</span></td>
                        <td><span className="badge" style={{ background: "#10b981" }}>{vul.status || "open"}</span></td>
                        <td>
                          <button 
                            onClick={() => handleMarkFalsePositive(vul.unique_key)}
                            style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                            className="secondary"
                            disabled={!isAdmin}
                            title={!isAdmin ? "Admin access required" : ""}
                          >
                            Mark as FP
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <span className="empty-message">No open vulnerabilities found.</span>
            )}
          </div>

          {showFalsePositives && scanDetail.result_json?.false_positives && scanDetail.result_json.false_positives.length > 0 && (
            <div className="scan-detail-section" style={{ marginTop: "32px" }}>
              <h4>False Positives</h4>
              <table>
                <thead>
                  <tr>
                    <th>Path</th>
                    <th>Line</th>
                    <th>Class</th>
                    <th>Severity</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {scanDetail.result_json.false_positives.map((vul, idx) => {
                    const semgrepUrl = buildSemgrepUrl(vul.check_id);
                    const vulClass = Array.isArray(vul.extra?.metadata?.vulnerability_class) 
                      ? vul.extra.metadata.vulnerability_class.join(", ") 
                      : vul.extra?.metadata?.vulnerability_class || '';
                    
                    return (
                      <tr key={idx} style={{ background: "#fef2f2" }}>
                        <td>{vul.path}</td>
                        <td>{vul.start?.line}</td>
                        <td>
                          {semgrepUrl && vulClass ? (
                            <a href={semgrepUrl} target="_blank" rel="noopener noreferrer" className="github-link">
                              {vulClass}
                            </a>
                          ) : (
                            vulClass
                          )}
                        </td>
                        <td><span className={badgeColor(vul.extra?.severity)}>{vul.extra?.severity}</span></td>
                        <td><span className="badge" style={{ background: "#64748b" }}>False Positive</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
