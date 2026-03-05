import React, { useEffect, useState } from "react";
import { getScans } from "../api";

export default function Dashboard({ projects, totalProjects = 0, onSelectProject, onNavigate }) {
  const [stats, setStats] = useState({
    totalProjects: 0,
    totalVulnerabilities: 0,
    recentScans: [],
    projectsWithScans: new Map()
  });

  useEffect(() => {
    // Calculate stats - fetch latest scans for each project
    const fetchStats = async () => {
      let totalVulnerabilities = 0;
      let recentScans = [];
      let projectsWithScans = new Map(); // project_id -> findings_count

      if (projects && projects.length > 0) {
        // Fetch scans for each project to get accurate counts
        const scanPromises = projects.map(p => getScans(p.id).catch(() => []));
        const projectScans = await Promise.all(scanPromises);
        
        projects.forEach((p, idx) => {
          const scans = projectScans[idx] || [];
          if (scans.length > 0) {
            // Get the latest scan
            const latestScan = scans[0]; // scans are already sorted by date
            const findingsCount = latestScan.findings_count || 0;
            totalVulnerabilities += findingsCount;
            projectsWithScans.set(p.id, findingsCount);
            
            // Extract project name as org/repo
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
              projectName: projectName,
              date: latestScan.scan_date,
              findings: findingsCount
            });
          } else {
            projectsWithScans.set(p.id, 0);
          }
        });
        
        recentScans = recentScans.sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 5);
      }

      setStats({
        totalProjects: totalProjects > 0 ? totalProjects : (projects ? projects.length : 0),
        totalVulnerabilities,
        recentScans,
        projectsWithScans  // Add this to state
      });
    };
    
    fetchStats();
  }, [projects, totalProjects]);

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
                <div key={idx} className="scan-item">
                  <div className="scan-info">
                    <div className="scan-name">{scan.projectName}</div>
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
