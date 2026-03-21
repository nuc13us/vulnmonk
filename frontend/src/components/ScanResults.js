
import React, { useState, useEffect, useRef } from "react";
import { getScans, getScanDetail, triggerScan, markFalsePositive, unmarkFalsePositive, getScanStatus, getPRScans, getPRScanDetail } from "../api";

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
  const [activeTab, setActiveTab] = useState("full"); // "full" | "pr"
  const [scanHistory, setScanHistory] = useState([]);
  const [scanDetail, setScanDetail] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [showFalsePositives, setShowFalsePositives] = useState(false);
  const [showLogs, setShowLogs] = useState(true);
  const pollRef = useRef(null);

  // PR scans state
  const [prScans, setPrScans] = useState([]);
  const [prScanDetail, setPrScanDetail] = useState(null);

  // Poll server scan status so the banner shows even after re-navigation
  useEffect(() => {
    if (!project) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const { scanning: active } = await getScanStatus(project.id);
        if (cancelled) return;
        setScanning(active);
        if (active) {
          pollRef.current = setTimeout(poll, 5000);
        } else {
          // Scan just finished — refresh history
          getScans(project.id).then(setScanHistory);
        }
      } catch {
        // ignore transient errors
      }
    };

    poll();
    return () => {
      cancelled = true;
      clearTimeout(pollRef.current);
    };
  }, [project]);

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
      getPRScans(project.id).then(setPrScans).catch(() => setPrScans([]));
      setScanDetail(null);
      setPrScanDetail(null);
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
      clearTimeout(pollRef.current);
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

  const handleSelectPRScan = async (prScan) => {
    setPrScanDetail(null);
    const detail = await getPRScanDetail(prScan.id);
    setPrScanDetail(detail);
  };

  const prStatusBadge = (status) => {
    const map = {
      pending:  { bg: '#fef9c3', color: '#92400e', label: '⏳ Pending' },
      success:  { bg: '#dcfce7', color: '#166534', label: '✅ Passed' },
      failure:  { bg: '#fee2e2', color: '#991b1b', label: '❌ Blocked' },
      error:    { bg: '#f1f5f9', color: '#475569', label: '⚠️ Error' },
    };
    const s = map[status] || map.error;
    return (
      <span style={{ padding: '2px 10px', borderRadius: '12px', fontSize: '0.8rem',
        fontWeight: 600, background: s.bg, color: s.color }}>
        {s.label}
      </span>
    );
  };

  const handleMarkFalsePositive = async (uniqueKey) => {
    await markFalsePositive(project.id, uniqueKey);
    setLogs(l => [
      { type: 'success', msg: 'Marked as false positive' },
      ...l.slice(0, 4)
    ]);
    if (scanDetail) {
      const detail = await getScanDetail(scanDetail.id);
      setScanDetail(detail);
    }
  };

  const handleUnmarkFalsePositive = async (uniqueKey) => {
    await unmarkFalsePositive(project.id, uniqueKey);
    setLogs(l => [
      { type: 'success', msg: 'Removed from false positives' },
      ...l.slice(0, 4)
    ]);
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
          // Extract project name as org/repo
          if (project.github_url) {
            const parts = project.github_url.replace(/\.git$/, '').split('/').filter(s => s && !s.includes(':'));
            return parts.slice(-2).join('/') || 'Unnamed';
          } else if (project.local_path) {
            return project.local_path.split('/').filter(part => part).pop();
          } else if (project.name) {
            return project.name;
          }
          return 'Unnamed';
        })()}</h2>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span style={{ fontSize: '0.9rem', color: '#64748b', fontWeight: 500 }}>
            📋 {scanHistory.length} {scanHistory.length === 1 ? 'scan' : 'scans'} in history
          </span>
          {scanHistory.length > 0 && (
            <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
              • Last scan: {formatDate(scanHistory[0].scan_date)}
            </span>
          )}
        </div>
      </div>

      {/* Tab switcher */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '20px', borderBottom: '2px solid #e5e7eb', paddingBottom: '0' }}>
        {['full', 'pr'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '8px 20px',
              border: 'none',
              borderBottom: activeTab === tab ? '2px solid #2563eb' : '2px solid transparent',
              marginBottom: '-2px',
              background: 'transparent',
              fontWeight: activeTab === tab ? 700 : 400,
              color: activeTab === tab ? '#2563eb' : '#64748b',
              cursor: 'pointer',
              fontSize: '0.95rem',
            }}
          >
            {tab === 'full' ? '🔍 Full Scans' : `🔔 PR Scans${prScans.length > 0 ? ` (${prScans.length})` : ''}`}
          </button>
        ))}
      </div>

      {/* ─── FULL SCANS TAB ─── */}
      {activeTab === 'full' && (<>

      <div className="project-controls">
        {scanning && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '10px 16px', marginBottom: '12px',
            background: '#eff6ff', border: '1px solid #bfdbfe',
            borderRadius: '8px', color: '#1e40af', fontSize: '0.9rem', fontWeight: 500
          }}>
            <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
            Scan in progress — this may take a few minutes...
          </div>
        )}
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
                    <th>Actions</th>
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
                        <td>
                          <button
                            onClick={() => handleUnmarkFalsePositive(vul.unique_key)}
                            style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                            className="secondary"
                            disabled={!isAdmin}
                            title={!isAdmin ? "Admin access required" : "Remove from false positives"}
                          >
                            Remove FP
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
        </>
      )}

      {/* ─── PR SCANS TAB ─── */}
      {activeTab === 'pr' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ margin: 0 }}>PR Scan History</h3>
            <button
              className="secondary"
              style={{ fontSize: '0.85rem', padding: '6px 14px' }}
              onClick={() => getPRScans(project.id).then(setPrScans).catch(() => {})}
            >
              ↻ Refresh
            </button>
          </div>

          {prScans.length === 0 ? (
            <p className="empty-message">
              No PR scans yet. Enable PR Checks in Configurations, add the webhook to your GitHub repo, then open a PR.
            </p>
          ) : (
            <div className="scan-history-compact" style={{ maxHeight: '320px', overflowY: 'auto' }}>
              {prScans.map(pr => (
                <button
                  key={pr.id}
                  className={`scan-history-row${prScanDetail && prScanDetail.id === pr.id ? ' active' : ''}`}
                  onClick={() => handleSelectPRScan(pr)}
                  style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '4px', height: 'auto', padding: '10px 14px' }}
                >
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center', width: '100%' }}>
                    <span style={{ fontWeight: 700, color: '#2563eb' }}>#{pr.pr_number}</span>
                    <span style={{ flex: 1, textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {pr.pr_title || '(no title)'}
                    </span>
                    {prStatusBadge(pr.status)}
                  </div>
                  <div style={{ display: 'flex', gap: '12px', fontSize: '0.8rem', color: '#64748b' }}>
                    <span>🌿 {pr.head_branch} → {pr.base_branch}</span>
                    <span>📂 {(pr.changed_files || []).length} files</span>
                    <span>🔍 {pr.findings_count} finding{pr.findings_count !== 1 ? 's' : ''}</span>
                    <span>{formatDate(pr.created_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          )}

          {prScanDetail && (
            <div className="scan-detail-section" style={{ marginTop: '24px' }}>
              <div style={{ marginBottom: '16px' }}>
                <h4 style={{ margin: '0 0 4px 0' }}>
                  PR #{prScanDetail.pr_number}: {prScanDetail.pr_title}
                </h4>
                <div style={{ display: 'flex', gap: '12px', fontSize: '0.85rem', color: '#64748b', flexWrap: 'wrap' }}>
                  <span>🌿 {prScanDetail.head_branch} → {prScanDetail.base_branch}</span>
                  <span>🔗 {prScanDetail.head_sha?.slice(0, 8)}</span>
                  <span>Status: {prStatusBadge(prScanDetail.status)}</span>
                </div>
                <div style={{ marginTop: '8px', fontSize: '0.85rem', color: '#64748b' }}>
                  <strong>Changed files scanned:</strong>{' '}
                  {(prScanDetail.changed_files || []).join(', ') || 'none'}
                </div>
                <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '6px' }}>
                  ℹ️ Only findings on lines changed in this PR are shown.
                </p>
              </div>

              {prScanDetail.result_json?.error ? (
                <div style={{ padding: '12px', background: '#fef2f2', borderRadius: '8px', color: '#dc2626' }}>
                  Scan error: {prScanDetail.result_json.error}
                </div>
              ) : (prScanDetail.result_json?.results || []).length === 0 ? (
                <p className="empty-message">✅ No security issues found in the changed lines.</p>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Path</th>
                      <th>Line</th>
                      <th>Class</th>
                      <th>Severity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(prScanDetail.result_json.results || []).map((vul, idx) => {
                      const semgrepUrl = buildSemgrepUrl(vul.check_id);
                      const vulClass = Array.isArray(vul.extra?.metadata?.vulnerability_class)
                        ? vul.extra.metadata.vulnerability_class.join(', ')
                        : vul.extra?.metadata?.vulnerability_class || '';
                      const githubUrl = buildGitHubUrl(vul.path, vul.start?.line);
                      return (
                        <tr key={idx}>
                          <td>
                            {githubUrl
                              ? <a href={githubUrl} target="_blank" rel="noopener noreferrer" className="github-link">{vul.path}</a>
                              : vul.path}
                          </td>
                          <td>{vul.start?.line}</td>
                          <td>
                            {semgrepUrl && vulClass
                              ? <a href={semgrepUrl} target="_blank" rel="noopener noreferrer" className="github-link">{vulClass}</a>
                              : vulClass}
                          </td>
                          <td><span className={badgeColor(vul.extra?.severity)}>{vul.extra?.severity}</span></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}

    </div>
  );
}
