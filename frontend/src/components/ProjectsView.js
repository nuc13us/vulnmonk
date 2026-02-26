import React, { useState } from "react";
import { addGithubProject } from "../api";

function ProjectsView({ 
  projects, 
  onSelectProject, 
  onProjectsChange, 
  user,
  currentPage = 1,
  totalProjects = 0,
  totalPages = 1,
  hasNextPage = false,
  hasPrevPage = false,
  onPageChange,
  onSearch,
  searchQuery = ""
}) {
  const [githubUrl, setGithubUrl] = useState("");
  const [addingProject, setAddingProject] = useState(false);
  const [message, setMessage] = useState(null);
  const [localSearchInput, setLocalSearchInput] = useState(searchQuery);

  const isAdmin = user && user.role === "admin";

  const handleSearchChange = (e) => {
    const value = e.target.value;
    setLocalSearchInput(value);
    
    // Debounce the search - wait for user to stop typing
    if (value.trim() === "" || value.length >= 2) {
      onSearch(value);
    }
  };

  const handleAddProject = async () => {
    if (!githubUrl.trim()) {
      setMessage({ type: "error", text: "Please enter a GitHub URL" });
      return;
    }

    setAddingProject(true);
    setMessage({ type: "info", text: "Adding project..." });

    try {
      await addGithubProject(githubUrl);
      setMessage({ type: "success", text: "Project added successfully!" });
      setGithubUrl("");
      // Refresh projects list
      window.location.reload();
    } catch (error) {
      setMessage({ type: "error", text: error.message || "Failed to add project" });
    } finally {
      setAddingProject(false);
    }
  };

  return (
    <div className="projects-view">
      <div className="view-header">
        <h1>Projects</h1>
        <p className="view-subtitle">Manage your security scan projects</p>
      </div>

      {isAdmin && (
        <div className="card" style={{ marginBottom: "32px" }}>
          <h2 style={{ margin: "0 0 20px 0", fontSize: "1.3rem", fontWeight: "700", color: "#0f172a" }}>
            Add New Project
          </h2>
          <div className="input-row">
            <label style={{ fontWeight: "600", color: "#334155", minWidth: "120px" }}>
              GitHub URL:
            </label>
            <input
              type="text"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              placeholder="https://github.com/user/repo"
              style={{ flex: 1, marginLeft: "0" }}
              disabled={addingProject}
            />
            <button
              className="primary"
              onClick={handleAddProject}
              disabled={addingProject}
              style={{ marginLeft: "12px" }}
            >
              {addingProject ? "Adding..." : "Add Project"}
            </button>
          </div>
          {message && (
            <div style={{ marginTop: "16px" }}>
              <div className={`log log-${message.type}`}>{message.text}</div>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h2 style={{ margin: "0 0 20px 0", fontSize: "1.3rem", fontWeight: "700", color: "#0f172a" }}>
          All Projects ({totalProjects > 0 ? totalProjects : projects.length})
          {totalProjects > 100 && (
            <span style={{ fontSize: "0.9rem", fontWeight: "400", color: "#64748b", marginLeft: "10px" }}>
              (Page {currentPage} of {totalPages})
            </span>
          )}
        </h2>
        <div style={{ marginBottom: "20px" }}>
          <input
            type="text"
            placeholder="Search all projects (min 2 characters)..."
            value={localSearchInput}
            onChange={handleSearchChange}
            style={{ 
              width: "100%", 
              maxWidth: "400px",
              padding: "10px 14px",
              border: "2px solid #e5e7eb",
              borderRadius: "8px",
              fontSize: "0.9rem"
            }}
          />
          {searchQuery && (
            <div style={{ marginTop: "8px", fontSize: "0.85rem", color: "#64748b" }}>
              Searching across all projects for "{searchQuery}"
            </div>
          )}
        </div>
        {projects.length === 0 ? (
          <p className="empty-message">
            {searchQuery ? `No projects found matching "${searchQuery}"` : "No projects yet. Add a project using the form above to get started."}
          </p>
        ) : (
          <div className="projects-grid">
            {projects.map((project) => {
              // Extract project name safely
              let repoName = 'Unnamed';
              if (project.github_url) {
                repoName = project.github_url.split('/').filter(part => part).pop().replace('.git', '');
              } else if (project.local_path) {
                repoName = project.local_path.split('/').filter(part => part).pop();
              } else if (project.name) {
                repoName = project.name;
              }

              return (
                <div
                  key={project.id}
                  className="project-card"
                  onClick={() => onSelectProject(project)}
                >
                  <div className="project-icon">📦</div>
                  <div className="project-name">{repoName}</div>
                  <div className="project-meta">
                    <small style={{ color: "#64748b" }}>Click to view details</small>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        
        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div style={{ 
            marginTop: '30px', 
            paddingTop: '20px', 
            borderTop: '1px solid #e5e7eb',
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center' 
          }}>
            <div style={{ color: '#64748b', fontSize: '0.9rem' }}>
              Showing {((currentPage - 1) * 100) + 1} - {Math.min(currentPage * 100, totalProjects)} of {totalProjects} projects
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <button
                onClick={() => onPageChange(currentPage - 1)}
                disabled={!hasPrevPage}
                style={{
                  padding: '8px 16px',
                  backgroundColor: hasPrevPage ? '#2563eb' : '#e5e7eb',
                  color: hasPrevPage ? 'white' : '#94a3b8',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: hasPrevPage ? 'pointer' : 'not-allowed',
                  fontWeight: '500',
                  fontSize: '0.9rem'
                }}
              >
                ← Previous
              </button>
              
              <div style={{ display: 'flex', gap: '5px' }}>
                {/* Show page numbers */}
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let pageNum;
                  if (totalPages <= 5) {
                    pageNum = i + 1;
                  } else if (currentPage <= 3) {
                    pageNum = i + 1;
                  } else if (currentPage >= totalPages - 2) {
                    pageNum = totalPages - 4 + i;
                  } else {
                    pageNum = currentPage - 2 + i;
                  }
                  
                  return (
                    <button
                      key={pageNum}
                      onClick={() => onPageChange(pageNum)}
                      style={{
                        padding: '8px 12px',
                        backgroundColor: currentPage === pageNum ? '#2563eb' : 'white',
                        color: currentPage === pageNum ? 'white' : '#334155',
                        border: '1px solid #e5e7eb',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontWeight: currentPage === pageNum ? '600' : '400',
                        fontSize: '0.9rem',
                        minWidth: '40px'
                      }}
                    >
                      {pageNum}
                    </button>
                  );
                })}
              </div>
              
              <button
                onClick={() => onPageChange(currentPage + 1)}
                disabled={!hasNextPage}
                style={{
                  padding: '8px 16px',
                  backgroundColor: hasNextPage ? '#2563eb' : '#e5e7eb',
                  color: hasNextPage ? 'white' : '#94a3b8',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: hasNextPage ? 'pointer' : 'not-allowed',
                  fontWeight: '500',
                  fontSize: '0.9rem'
                }}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ProjectsView;
