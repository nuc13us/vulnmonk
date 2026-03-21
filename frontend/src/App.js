import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, NavLink, useParams, useNavigate } from "react-router-dom";
import "./App.css";
import Login from "./components/Login";
import Dashboard from "./components/Dashboard";
import ProjectsView from "./components/ProjectsView";
import ScanResults from "./components/ScanResults";
import Configurations from "./components/Configurations";
import Integrations from "./components/Integrations";
import Account from "./components/Account";
import Users from "./components/Users";
import { getProjects, getCurrentUser, isAuthenticated, removeAuthToken, getProjectById } from "./api";

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

function AppContent() {
  const [projects, setProjects] = useState([]);
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalProjects, setTotalProjects] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [hasPrevPage, setHasPrevPage] = useState(false);
  const [totalVulnerabilities, setTotalVulnerabilities] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (user) {
      loadProjects();
    }
  }, [user]);

  // Redirect to login when any API call receives a 401 (token expired)
  useEffect(() => {
    const handleAuthExpired = () => {
      setUser(null);
      setProjects([]);
      navigate("/");
    };
    window.addEventListener("auth:expired", handleAuthExpired);
    return () => window.removeEventListener("auth:expired", handleAuthExpired);
  }, [navigate]);

  const checkAuth = async () => {
    if (isAuthenticated()) {
      try {
        const userData = await getCurrentUser();
        setUser(userData);
      } catch (error) {
        console.error("Auth check failed:", error);
        removeAuthToken();
        setUser(null);
      }
    }
    setAuthChecked(true);
  };

  const loadProjects = async (page = 1, search = "") => {
    try {
      const data = await getProjects(page, 100, search);
      const projectsList = data.projects || [];
      setProjects(projectsList);
      setCurrentPage(data.page || page);
      setTotalProjects(data.total || projectsList.length);
      setTotalPages(data.total_pages || 1);
      setHasNextPage(data.has_next || false);
      setHasPrevPage(data.has_prev || false);
      setTotalVulnerabilities(data.total_vulnerabilities || 0);
    } catch (error) {
      console.error("Failed to load projects:", error);
    }
  };

  const handlePageChange = (newPage) => {
    setCurrentPage(newPage);
    loadProjects(newPage, searchQuery);
    window.scrollTo(0, 0); // Scroll to top when changing pages
  };

  const handleSearch = (query) => {
    setSearchQuery(query);
    setCurrentPage(1);
    loadProjects(1, query);
  };

  const handleLoginSuccess = () => {
    checkAuth();
  };

  const handleLogout = () => {
    removeAuthToken();
    setUser(null);
    setProjects([]);
    navigate("/");
  };

  const handleSelectProject = (project) => {
    navigate(`/project/${project.id}`);
  };

  const handleNavigate = (view) => {
    navigate(`/${view}`);
  };

  // Show login screen if not authenticated
  if (!authChecked) {
    return (
      <div style={{ 
        display: "flex", 
        alignItems: "center", 
        justifyContent: "center", 
        minHeight: "100vh",
        background: "#f1f5f9"
      }}>
        <p style={{ color: "#64748b" }}>Loading...</p>
      </div>
    );
  }

  if (!user) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="dashboard-root">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-logo">🔒</div>
          <div className="brand-text">
            <div className="brand-name">VulnMonk</div>
            <div className="brand-tagline">SAST Dashboard</div>
          </div>
        </div>
        <nav className="sidebar-nav">
          <div className="nav-section">
            <div className="nav-section-title">MAIN MENU</div>
            <ul>
              <li>
                <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>
                  <span className="nav-icon">📊</span>
                  <span className="nav-label">Dashboard</span>
                </NavLink>
              </li>
              <li>
                <NavLink to="/projects" className={({ isActive }) => isActive ? 'active' : ''}>
                  <span className="nav-icon">📁</span>
                  <span className="nav-label">Projects</span>
                </NavLink>
              </li>
              <li>
                <NavLink to="/configurations" className={({ isActive }) => isActive ? 'active' : ''}>
                  <span className="nav-icon">⚙️</span>
                  <span className="nav-label">Configurations</span>
                </NavLink>
              </li>
              <li>
                <NavLink to="/integrations" className={({ isActive }) => isActive ? 'active' : ''}>
                  <span className="nav-icon">🔗</span>
                  <span className="nav-label">Integrations</span>
                </NavLink>
              </li>
              <li>
                <NavLink to="/account" className={({ isActive }) => isActive ? 'active' : ''}>
                  <span className="nav-icon">👤</span>
                  <span className="nav-label">Account</span>
                </NavLink>
              </li>
              {user.role === "admin" && (
                <li>
                  <NavLink to="/users" className={({ isActive }) => isActive ? 'active' : ''}>
                    <span className="nav-icon">👥</span>
                    <span className="nav-label">Users</span>
                  </NavLink>
                </li>
              )}
            </ul>
          </div>
        </nav>
        <div className="sidebar-footer">
          <div className="user-info-sidebar">
            <div className="user-avatar-sidebar">
              {user.role === "admin" ? "👑" : "👤"}
            </div>
            <div className="user-details-sidebar">
              <div className="user-name-sidebar">{user.username}</div>
              <div className="user-role-sidebar">{user.role}</div>
            </div>
          </div>
          <button onClick={handleLogout} className="logout-button">
            🚪 Logout
          </button>
        </div>
      </aside>
      <main className="main-content">
        <div className="main-area">
          <Routes>
            <Route path="/" element={
              <Dashboard projects={projects} totalProjects={totalProjects} totalVulnerabilities={totalVulnerabilities} onSelectProject={handleSelectProject} onNavigate={handleNavigate} />
            } />
            <Route path="/projects" element={
              <div className="content-wrapper">
                <ProjectsView 
                  projects={projects} 
                  onSelectProject={handleSelectProject} 
                  onProjectsChange={loadProjects} 
                  user={user}
                  currentPage={currentPage}
                  totalProjects={totalProjects}
                  totalPages={totalPages}
                  hasNextPage={hasNextPage}
                  hasPrevPage={hasPrevPage}
                  onPageChange={handlePageChange}
                  onSearch={handleSearch}
                  searchQuery={searchQuery}
                />
              </div>
            } />
            <Route path="/project/:id" element={
              <div className="content-wrapper">
                <ProjectDetailWrapper projects={projects} user={user} />
              </div>
            } />
            <Route path="/configurations" element={
              <div className="content-wrapper">
                <Configurations user={user} />
              </div>
            } />
            <Route path="/integrations" element={
              <div className="content-wrapper">
                <Integrations />
              </div>
            } />
            <Route path="/account" element={
              <div className="content-wrapper">
                <Account user={user} />
              </div>
            } />
            <Route path="/users" element={
              <div className="content-wrapper">
                {user.role === "admin" ? (
                  <Users />
                ) : (
                  <div className="card">
                    <h2>Access Denied</h2>
                    <p>You don't have permission to view this page.</p>
                  </div>
                )}
              </div>
            } />
          </Routes>
        </div>
      </main>
    </div>
  );
}

// Wrapper component to extract project ID from URL params
function ProjectDetailWrapper({ projects, user }) {
  const { id } = useParams();
  const [project, setProject] = React.useState(() => projects.find(p => p.id === parseInt(id)) || null);
  const [loading, setLoading] = React.useState(!project);
  const [notFound, setNotFound] = React.useState(false);

  React.useEffect(() => {
    const fromList = projects.find(p => p.id === parseInt(id));
    if (fromList) {
      setProject(fromList);
      setLoading(false);
      return;
    }
    // Not in local list (direct URL, refresh, or paginated out) — fetch directly
    setLoading(true);
    getProjectById(parseInt(id))
      .then(p => { setProject(p); setLoading(false); })
      .catch(() => { setNotFound(true); setLoading(false); });
  }, [id, projects]);

  if (loading) {
    return (
      <div className="card">
        <p style={{ color: "#64748b" }}>Loading project...</p>
      </div>
    );
  }

  if (notFound || !project) {
    return (
      <div className="card">
        <h2>Project Not Found</h2>
        <p>The requested project could not be found.</p>
      </div>
    );
  }

  return <ScanResults project={project} user={user} />;
}

export default App;
