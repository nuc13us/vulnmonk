import React, { useEffect, useState } from "react";

export default function Dashboard({ projects, totalProjects = 0, totalVulnerabilities = 0, totalSecrets = 0, onSelectProject, onNavigate }) {
  const [stats, setStats] = useState({
    totalProjects: 0,
    totalVulnerabilities: 0,
    totalSecrets: 0,
    recentScans: [],
    projectsWithScans: new Map()
  });

  useEffect(() => {
    // Use latest_scan embedded in each project — no extra API calls needed
    let recentScans = [];
    let projectsWithScans = new Map();

    if (projects && projects.length > 0) {
      projects.forEach((p) => {
        // Support both new format (latest_scan object) and old format (scans array)
        const latestScan = p.latest_scan
          ?? (Array.isArray(p.scans) && p.scans.length > 0 ? p.scans[0] : null);
        const findingsCount = latestScan?.findings_count ?? 0;
        projectsWithScans.set(p.id, findingsCount);

        if (latestScan) {
          let projectName = 'Unnamed';
          if (p.github_url) {
            const parts = p.github_url.replace(/\.git$/, '').split('/').filter(s => s && !s.includes(':'));
            projectName = parts.slice(-2).join('/') || 'Unnamed';
          } else if (p.local_path) {
            projectName = p.local_path.split('/').filter(part => part).pop();
          } else if (p.name) {
            projectName = p.name;
          }
          recentScans.push({
            projectId: p.id,
            project: p,
            projectName,
            date: latestScan.scan_date,
            findings: findingsCount
          });
        }
      });

      recentScans = recentScans.sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 5);
    }

    setStats({
      totalProjects: totalProjects > 0 ? totalProjects : (projects ? projects.length : 0),
      totalVulnerabilities,
      totalSecrets,
      recentScans,
      projectsWithScans
    });
  }, [projects, totalProjects, totalVulnerabilities, totalSecrets]);

  return (
    <div className="dashboard-view">
      <div className="dashboard-header">
        <h1>Security Dashboard</h1>
        <p className="dashboard-subtitle">Monitor and manage your SAST scan results</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card" onClick={() => onNavigate && onNavigate('projects')} style={{ cursor: 'pointer' }}>
          <div className="stat-icon">📁</div>
          <div className="stat-content">
            <div className="stat-number">{stats.totalProjects}</div>
            <div className="stat-label">Total Projects</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🔴</div>
          <div className="stat-content">
            <div className="stat-number">{stats.totalVulnerabilities}</div>
            <div className="stat-label">Total Vulnerabilities</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🔑</div>
          <div className="stat-content">
            <div className="stat-number">{stats.totalSecrets}</div>
            <div className="stat-label">Total Secrets</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">⚡</div>
          <div className="stat-content">
            <div className="stat-number">{stats.recentScans.length}</div>
            <div className="stat-label">Recent Scans</div>
          </div>
        </div>
      </div>

      <div className="dashboard-sections">
        <div className="section">
          <h2>Recent Scans</h2>
          {stats.recentScans.length > 0 ? (
            <div className="recent-scans-list">
              {stats.recentScans.map((scan, idx) => (
                <div key={idx} className="scan-item" onClick={() => onSelectProject && onSelectProject(scan.project)} style={{ cursor: 'pointer' }}>
                  <div className="scan-info">
                    <div className="scan-name" style={{ color: 'var(--accent, #4f8ef7)' }}>{scan.projectName}</div>
                    <div className="scan-date">{new Date(scan.date).toLocaleString()}</div>
                  </div>
                  <div className="scan-findings">
                    <span className="finding-badge">{scan.findings} findings</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-message">No recent scans. Start by adding a project and running a scan.</p>
          )}
        </div>

        <div className="section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ margin: 0 }}>Recent Projects</h2>
            {(totalProjects > 10 || (projects && projects.length > 10)) && (
              <button 
                className="btn-secondary" 
                onClick={() => onNavigate && onNavigate('projects')}
                style={{ padding: '6px 12px', fontSize: '0.85rem' }}
              >
                View All ({totalProjects > 0 ? totalProjects : projects.length})
              </button>
            )}
          </div>
          {projects && projects.length > 0 ? (
            <div className="projects-grid">
              {projects
                .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
                .slice(0, 8)
                .map(p => {
                // Extract project name as org/repo
                let name = 'Unnamed';
                if (p.github_url) {
                  const parts = p.github_url.replace(/\.git$/, '').split('/').filter(s => s && !s.includes(':'));
                  name = parts.slice(-2).join('/') || 'Unnamed';
                } else if (p.local_path) {
                  name = p.local_path.split('/').filter(part => part).pop();
                } else if (p.name) {
                  name = p.name;
                }
                
                const findingsCount = stats.projectsWithScans.get(p.id) || 0;
                return (
                  <div key={p.id} className="project-card" onClick={() => onSelectProject(p)}>
                    <div className="project-icon">📦</div>
                    <div className="project-name">{name}</div>
                    <div className="project-meta">
                      <span className="project-finding">{findingsCount} issues</span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="empty-message">No projects yet. Add your first project to get started.</p>
          )}
        </div>
      </div>
    </div>
  );
}
