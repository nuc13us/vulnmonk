import React, { useState, useEffect } from "react";
import { 
  getProjects, 
  updateExcludeRules, 
  updateIncludeRules,
  updateGlobalConfig,
  getAllGlobalConfigs,
  getPRCheckConfig,
  savePRCheckConfig
} from "../api";

export default function Configurations({ user }) {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [newRule, setNewRule] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [totalProjects, setTotalProjects] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [hasPrevPage, setHasPrevPage] = useState(false);
  
  // Global configurations
  const [globalExcludeRules, setGlobalExcludeRules] = useState("");
  const [newGlobalExcludeRule, setNewGlobalExcludeRule] = useState("");
  
  // Include rules state - store as array of files
  const [includeYamlFiles, setIncludeYamlFiles] = useState([]);
  const [globalIncludeYamlFiles, setGlobalIncludeYamlFiles] = useState([]);

  // PR Check state
  const [prConfig, setPrConfig] = useState(null);  // { enabled, webhook_secret, block_on_severity }
  const [prSaving, setPrSaving] = useState(false);

  const isAdmin = user && user.role === "admin";

  useEffect(() => {
    loadProjects();
    loadGlobalConfigs();
  }, []);

  const loadProjects = async (page = 1, search = "") => {
    const data = await getProjects(page, 100, search);
    const projectsList = data.projects || [];
    setProjects(projectsList);
    setTotalProjects(data.total || projectsList.length);
    setCurrentPage(data.page || page);
    setTotalPages(data.total_pages || 1);
    setHasNextPage(data.has_next || false);
    setHasPrevPage(data.has_prev || false);
  };

  const handleSearch = (query) => {
    setSearchQuery(query);
    setCurrentPage(1);
    loadProjects(1, query);
  };

  const handlePageChange = (newPage) => {
    setCurrentPage(newPage);
    loadProjects(newPage, searchQuery);
  };

  const loadGlobalConfigs = async () => {
    try {
      const configs = await getAllGlobalConfigs();
      setGlobalExcludeRules(configs.global_exclude_rules || "");
      const includeYamlData = configs.global_include_rules_yaml || "";
      // Parse as JSON array or fallback to empty array
      try {
        const parsed = includeYamlData ? JSON.parse(includeYamlData) : [];
        setGlobalIncludeYamlFiles(Array.isArray(parsed) ? parsed : []);
      } catch {
        setGlobalIncludeYamlFiles([]);
      }
    } catch (error) {
      console.error("Failed to load global configs:", error);
    }
  };

  const handleSelectProject = (project) => {
    setSelectedProject(project);
    setNewRule("");
    setMessage(null);
    setPrConfig(null);
    // Load PR check config
    getPRCheckConfig(project.id)
      .then(cfg => setPrConfig(cfg))
      .catch(() => setPrConfig({ enabled: false, webhook_secret: "", block_on_severity: "none" }));
    // Parse include rules as JSON array
    try {
      const parsed = project.include_rules_yaml ? JSON.parse(project.include_rules_yaml) : [];
      setIncludeYamlFiles(Array.isArray(parsed) ? parsed : []);
    } catch {
      setIncludeYamlFiles([]);
    }
  };

  const handleAddRule = async () => {
    if (!selectedProject || !newRule.trim()) return;
    
    setSaving(true);
    setMessage(null);
    
    try {
      // Get existing rules
      const existingRules = selectedProject.exclude_rules 
        ? selectedProject.exclude_rules.split(",").map(r => r.trim()).filter(Boolean)
        : [];
      
      // Check if rule already exists
      if (existingRules.includes(newRule.trim())) {
        setMessage({ type: "error", text: "Rule already exists" });
        setSaving(false);
        return;
      }
      
      // Add new rule
      const updatedRules = [...existingRules, newRule.trim()];
      await updateExcludeRules(selectedProject.id, updatedRules);
      
      setMessage({ type: "success", text: "Rule added successfully!" });
      setNewRule("");
      
      // Refresh projects list
      await loadProjects();
      
      // Update selected project
      const updatedProject = { ...selectedProject, exclude_rules: updatedRules.join(",") };
      setSelectedProject(updatedProject);
    } catch (error) {
      setMessage({ type: "error", text: error.message || "Failed to add rule" });
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveRule = async (ruleToRemove) => {
    if (!selectedProject) return;
    
    setSaving(true);
    setMessage(null);
    
    try {
      // Remove the rule
      const existingRules = selectedProject.exclude_rules 
        ? selectedProject.exclude_rules.split(",").map(r => r.trim()).filter(Boolean)
        : [];
      const updatedRules = existingRules.filter(r => r !== ruleToRemove);
      
      await updateExcludeRules(selectedProject.id, updatedRules);
      
      setMessage({ type: "success", text: "Rule removed successfully!" });
      
      // Refresh projects list
      await loadProjects();
      
      // Update selected project
      const updatedProject = { ...selectedProject, exclude_rules: updatedRules.join(",") };
      setSelectedProject(updatedProject);
    } catch (error) {
      setMessage({ type: "error", text: "Failed to remove rule" });
    } finally {
      setSaving(false);
    }
  };

  const getRulesCount = (rules) => {
    if (!rules) return 0;
    return rules.split(",").map(r => r.trim()).filter(Boolean).length;
  };

  const getYamlRulesCount = (yamlData) => {
    if (!yamlData) return 0;
    try {
      // If it's a JSON string, parse it
      const files = typeof yamlData === 'string' ? JSON.parse(yamlData) : yamlData;
      if (!Array.isArray(files)) return 0;
      
      // Count rules across all files
      let totalCount = 0;
      files.forEach(file => {
        const matches = file.content.match(/^\s*-\s+id:/gm);
        totalCount += matches ? matches.length : 0;
      });
      return totalCount;
    } catch {
      return 0;
    }
  };

  // Global exclude rules handlers
  const handleAddGlobalExcludeRule = async () => {
    if (!newGlobalExcludeRule.trim()) return;
    
    setSaving(true);
    setMessage(null);
    
    try {
      const existingRules = globalExcludeRules
        ? globalExcludeRules.split(",").map(r => r.trim()).filter(Boolean)
        : [];
      
      // Check if this exact rule ID already exists in global rules
      if (existingRules.includes(newGlobalExcludeRule.trim())) {
        setMessage({ type: "error", text: `Rule "${newGlobalExcludeRule.trim()}" is already in global exclude rules` });
        setSaving(false);
        return;
      }
      
      const updatedRules = [...existingRules, newGlobalExcludeRule.trim()];
      await updateGlobalConfig("global_exclude_rules", updatedRules.join(","));
      
      // Refresh from backend to ensure consistency
      await loadGlobalConfigs();
      setNewGlobalExcludeRule("");
      setMessage({ type: "success", text: "Global exclude rule added successfully!" });
    } catch (error) {
      setMessage({ type: "error", text: error.message || "Failed to add global rule" });
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveGlobalExcludeRule = async (ruleToRemove) => {
    setSaving(true);
    setMessage(null);
    
    try {
      const existingRules = globalExcludeRules
        ? globalExcludeRules.split(",").map(r => r.trim()).filter(Boolean)
        : [];
      const updatedRules = existingRules.filter(r => r !== ruleToRemove);
      
      await updateGlobalConfig("global_exclude_rules", updatedRules.join(","));
      
      // Refresh from backend to ensure consistency
      await loadGlobalConfigs();
      setMessage({ type: "success", text: "Global exclude rule removed!" });
    } catch (error) {
      setMessage({ type: "error", text: "Failed to remove global rule" });
    } finally {
      setSaving(false);
    }
  };

  // Include rules handlers
  const handleIncludeFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      // Validate YAML file extension
      const fileName = file.name.toLowerCase();
      if (!fileName.endsWith('.yaml') && !fileName.endsWith('.yml')) {
        setMessage({ type: "error", text: "Please upload only YAML files (.yaml or .yml)" });
        event.target.value = null;
        return;
      }
      
      const reader = new FileReader();
      reader.onload = (e) => {
        const newFile = {
          filename: file.name,
          content: e.target.result,
          uploadedAt: new Date().toISOString()
        };
        setIncludeYamlFiles([...includeYamlFiles, newFile]);
        setMessage({ type: "success", text: `Added ${file.name}` });
      };
      reader.readAsText(file);
      event.target.value = null;
    }
  };

  const handleRemoveIncludeFile = (index) => {
    const newFiles = includeYamlFiles.filter((_, i) => i !== index);
    setIncludeYamlFiles(newFiles);
    setMessage({ type: "success", text: "File removed" });
  };

  const handleSaveIncludeRules = async () => {
    if (!selectedProject) return;
    
    setSaving(true);
    setMessage(null);
    
    try {
      const yamlJsonString = JSON.stringify(includeYamlFiles);
      await updateIncludeRules(
        selectedProject.id, 
        yamlJsonString,
        selectedProject.apply_global_include !== false
      );
      
      setMessage({ type: "success", text: "Include rules saved successfully!" });
      await loadProjects();
      
      // Update selected project
      const updatedProject = { 
        ...selectedProject, 
        include_rules_yaml: yamlJsonString 
      };
      setSelectedProject(updatedProject);
    } catch (error) {
      setMessage({ type: "error", text: "Failed to save include rules" });
    } finally {
      setSaving(false);
    }
  };

  const handleClearIncludeRules = () => {
    setIncludeYamlFiles([]);
  };

  const handleGlobalIncludeFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      const fileName = file.name.toLowerCase();
      if (!fileName.endsWith('.yaml') && !fileName.endsWith('.yml')) {
        setMessage({ type: "error", text: "Please upload only YAML files (.yaml or .yml)" });
        event.target.value = null;
        return;
      }
      
      const reader = new FileReader();
      reader.onload = (e) => {
        const newFile = {
          filename: file.name,
          content: e.target.result,
          uploadedAt: new Date().toISOString()
        };
        setGlobalIncludeYamlFiles([...globalIncludeYamlFiles, newFile]);
        setMessage({ type: "success", text: `Added global file ${file.name}` });
      };
      reader.readAsText(file);
      event.target.value = null;
    }
  };

  const handleRemoveGlobalIncludeFile = (index) => {
    const newFiles = globalIncludeYamlFiles.filter((_, i) => i !== index);
    setGlobalIncludeYamlFiles(newFiles);
    setMessage({ type: "success", text: "Global file removed" });
  };

  const handleSaveGlobalIncludeRules = async () => {
    setSaving(true);
    setMessage(null);
    
    try {
      const yamlDataJson = JSON.stringify(globalIncludeYamlFiles);
      await updateGlobalConfig("global_include_rules_yaml", yamlDataJson);
      setMessage({ type: "success", text: "Global include rules saved!" });
    } catch (error) {
      setMessage({ type: "error", text: "Failed to save global include rules" });
    } finally {
      setSaving(false);
    }
  };

  const handleClearGlobalIncludeRules = () => {
    setGlobalIncludeYamlFiles([]);
  };

  const handleSavePrConfig = async () => {
    if (!selectedProject || !prConfig) return;
    setPrSaving(true);
    setMessage(null);
    try {
      const updated = await savePRCheckConfig(selectedProject.id, prConfig);
      setPrConfig(updated);
      setMessage({ type: "success", text: "PR check settings saved!" });
    } catch (err) {
      setMessage({ type: "error", text: err.message || "Failed to save PR check settings" });
    } finally {
      setPrSaving(false);
    }
  };

  // Global rules are now always applied automatically - no toggle needed

  return (
    <div className="configurations-container">
      <div className="config-header">
        <h2>Project Configurations</h2>
        <p style={{ color: "#64748b", marginTop: "8px" }}>
          Manage exclude/include rules for security scans across all projects
          {!isAdmin && <span style={{ color: "#dc2626", fontWeight: 600, marginLeft: "8px" }}>🔒 View-only mode</span>}
        </p>
      </div>

      <div className="config-layout">
        {/* Projects List */}
        <div className="config-projects-list">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h3 style={{ margin: 0, fontSize: "1.1rem" }}>Projects ({totalProjects})</h3>
          </div>
          <input
            type="text"
            placeholder="Search all projects (min 2 characters)..."
            value={searchQuery}
            onChange={(e) => {
              const value = e.target.value;
              if (value.trim() === "" || value.length >= 2) {
                handleSearch(value);
              } else {
                setSearchQuery(value);
              }
            }}
            style={{ 
              width: "100%", 
              padding: "10px 14px", 
              marginBottom: "16px",
              border: "2px solid #e5e7eb",
              borderRadius: "8px",
              fontSize: "0.9rem"
            }}
          />
          {searchQuery && (
            <div style={{ marginBottom: "12px", fontSize: "0.85rem", color: "#64748b" }}>
              Searching across all projects for "{searchQuery}"
            </div>
          )}
          {projects.length === 0 ? (
            <p className="empty-message">
              {searchQuery ? `No projects found matching "${searchQuery}"` : "No projects yet."}
            </p>
          ) : (
            <>
              <div className="config-projects-grid">
                {projects.map((project) => {
                  // Extract project name as org/repo
                  let repoName = 'Unnamed';
                  if (project.github_url) {
                    const parts = project.github_url.replace(/\.git$/, '').split('/').filter(s => s && !s.includes(':'));
                    repoName = parts.slice(-2).join('/') || 'Unnamed';
                  } else if (project.local_path) {
                    repoName = project.local_path.split('/').filter(part => part).pop();
                  } else if (project.name) {
                    repoName = project.name;
                  }
                  
                  const excludeRulesCount = getRulesCount(project.exclude_rules);
                  const includeRulesCount = getYamlRulesCount(project.include_rules_yaml);
                  const isSelected = selectedProject?.id === project.id;
                
                return (
                  <div
                    key={project.id}
                    className={`config-project-card ${isSelected ? "selected" : ""}`}
                    onClick={() => handleSelectProject(project)}
                  >
                    <div className="config-project-icon">📦</div>
                    <div className="config-project-info">
                      <div className="config-project-name">{repoName}</div>
                      <div className="config-project-meta">
                        <span className="rule-count-badge" style={{ background: "#fee2e2", color: "#991b1b" }}>
                          🚫 {excludeRulesCount} exclude
                        </span>
                        {includeRulesCount > 0 && (
                          <span className="rule-count-badge" style={{ background: "#dcfce7", color: "#166534", marginLeft: "4px" }}>
                            ✅ {includeRulesCount} include
                          </span>
                        )}
                      </div>
                    </div>
                    {isSelected && <div className="selected-indicator">✓</div>}
                  </div>
                );
              })}
            </div>
            
            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div style={{ 
                marginTop: '20px', 
                paddingTop: '15px', 
                borderTop: '1px solid #e5e7eb',
                display: 'flex', 
                justifyContent: 'center',
                gap: '10px',
                flexWrap: 'wrap'
              }}>
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={!hasPrevPage}
                  style={{
                    padding: '6px 12px',
                    backgroundColor: hasPrevPage ? '#2563eb' : '#e5e7eb',
                    color: hasPrevPage ? 'white' : '#94a3b8',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: hasPrevPage ? 'pointer' : 'not-allowed',
                    fontWeight: '500',
                    fontSize: '0.85rem'
                  }}
                >
                  ← Prev
                </button>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: '#64748b' }}>
                  Page {currentPage} of {totalPages} ({totalProjects} total)
                </div>
                
                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={!hasNextPage}
                  style={{
                    padding: '6px 12px',
                    backgroundColor: hasNextPage ? '#2563eb' : '#e5e7eb',
                    color: hasNextPage ? 'white' : '#94a3b8',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: hasNextPage ? 'pointer' : 'not-allowed',
                    fontWeight: '500',
                    fontSize: '0.85rem'
                  }}
                >
                  Next →
                </button>
              </div>
            )}
          </>
          )}
        </div>

        {/* Rules Editor with Tabs */}
        <div className="config-rules-editor">
          {selectedProject ? (
            <>
              <h3 style={{ marginBottom: "8px", fontSize: "1.1rem" }}>
                Rules Configuration
              </h3>
              <p style={{ color: "#64748b", marginBottom: "16px", fontSize: "0.9rem" }}>
                Managing rules for: <strong>{selectedProject.github_url.replace(/\.git$/, "").split("/").filter(s => s && !s.includes(':')).slice(-2).join('/')}</strong>
              </p>

              {message && (
                <div className={`config-message config-message-${message.type}`}>
                  {message.text}
                </div>
              )}

              {/* Exclude Rules Section */}
              <div className="config-section">
                <h4 style={{ fontSize: "1rem", marginBottom: "16px", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                  🚫 Exclude Rules
                </h4>
                <div className="config-rules-form">
                  <label style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "8px", display: "block", color: "#374151" }}>
                    Project-Specific Exclude Rules {!isAdmin && <span style={{ color: "#dc2626", fontSize: "0.85rem" }}>(Admin only)</span>}
                  </label>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <input
                      type="text"
                      value={newRule}
                      onChange={e => setNewRule(e.target.value)}
                      placeholder="Enter rule ID (e.g., generic.secrets.security)"
                      onKeyPress={(e) => e.key === 'Enter' && isAdmin && handleAddRule()}
                      style={{ 
                        flex: 1, 
                        padding: "10px 14px",
                        border: "2px solid #e5e7eb",
                        borderRadius: "8px",
                        fontSize: "0.9rem"
                      }}
                      disabled={saving || !isAdmin}
                    />
                    <button 
                      onClick={handleAddRule} 
                      disabled={saving || !newRule.trim() || !isAdmin}
                      className="primary-btn"
                      style={{ padding: "10px 24px", whiteSpace: "nowrap" }}
                      title={!isAdmin ? "Admin access required" : ""}
                    >
                      {saving ? "Adding..." : "Add Rule"}
                    </button>
                  </div>
                  
                  {selectedProject.exclude_rules && getRulesCount(selectedProject.exclude_rules) > 0 && (
                    <div className="current-rules-display">
                      <h5 style={{ fontSize: "0.9rem", marginBottom: "8px", marginTop: "16px", fontWeight: 600 }}>
                        Project Rules ({getRulesCount(selectedProject.exclude_rules)})
                      </h5>
                      <div className="rules-tags">
                        {selectedProject.exclude_rules.split(",").map((rule, idx) => {
                          const trimmedRule = rule.trim();
                          if (!trimmedRule) return null;
                          return (
                            <span key={idx} className="rule-tag-removable">
                              {trimmedRule}
                              {isAdmin && (
                                <button 
                                  className="rule-remove-btn"
                                  onClick={() => handleRemoveRule(trimmedRule)}
                                  disabled={saving}
                                  title="Remove this rule"
                                >
                                  ×
                                </button>
                              )}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Include Rules Section */}
              <div className="config-section" style={{ marginTop: "32px" }}>
                <h4 style={{ fontSize: "1rem", marginBottom: "16px", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                  ✅ Include Rules (YAML)
                </h4>
                <div className="config-rules-form">
                  <label style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "8px", display: "block", color: "#374151" }}>
                    Project-Specific Include Rules {!isAdmin && <span style={{ color: "#dc2626", fontSize: "0.85rem" }}>(Admin only)</span>}
                  </label>
                  <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
                    <label 
                      htmlFor="include-file-upload" 
                      style={{ 
                        flex: 1, 
                        padding: "10px 14px",
                        border: "2px solid #e5e7eb",
                        borderRadius: "8px",
                        fontSize: "0.9rem",
                        cursor: isAdmin ? "pointer" : "not-allowed",
                        background: isAdmin ? "#fff" : "#f9fafb",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px"
                      }}
                    >
                      📁 Choose YAML file to add...
                      <input
                        id="include-file-upload"
                        type="file"
                        accept=".yaml,.yml"
                        onChange={handleIncludeFileUpload}
                        disabled={!isAdmin}
                        style={{ display: "none" }}
                      />
                    </label>
                    {includeYamlFiles.length > 0 && (
                      <button 
                        onClick={handleClearIncludeRules}
                        disabled={!isAdmin}
                        className="secondary"
                        style={{ padding: "10px 20px", whiteSpace: "nowrap" }}
                      >
                        Clear All
                      </button>
                    )}
                    <button 
                      onClick={handleSaveIncludeRules}
                      disabled={saving || !isAdmin}
                      className="primary-btn"
                      style={{ padding: "10px 24px", whiteSpace: "nowrap" }}
                      title={!isAdmin ? "Admin access required" : ""}
                    >
                      {saving ? "Saving..." : "Save"}
                    </button>
                  </div>
                  
                  {includeYamlFiles.length > 0 && (
                    <div style={{ marginTop: "12px" }}>
                      <h5 style={{ fontSize: "0.9rem", marginBottom: "8px", fontWeight: 600 }}>
                        Included YAML Files ({includeYamlFiles.length})
                      </h5>
                      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                        {includeYamlFiles.map((file, index) => {
                          return (
                            <div key={index} style={{ 
                              padding: "10px 12px", 
                              background: "#f0fdf4", 
                              border: "1px solid #bbf7d0", 
                              borderRadius: "6px",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between"
                            }}>
                              <div style={{ flex: 1 }}>
                                <div style={{ fontSize: "0.9rem", fontWeight: 600, color: "#166534" }}>
                                  📄 {file.filename}
                                </div>
                                <div style={{ fontSize: "0.8rem", color: "#16a34a", marginTop: "4px" }}>
                                  Added {new Date(file.uploadedAt).toLocaleDateString()}
                                </div>
                              </div>
                              {isAdmin && (
                                <button
                                  onClick={() => handleRemoveIncludeFile(index)}
                                  disabled={saving}
                                  style={{
                                    padding: "6px 12px",
                                    background: "#dc2626",
                                    color: "white",
                                    border: "none",
                                    borderRadius: "4px",
                                    cursor: "pointer",
                                    fontSize: "0.85rem",
                                    fontWeight: 600
                                  }}
                                  title="Remove this file"
                                >
                                  Remove
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* PR Checks Section */}
              <div className="config-section" style={{ marginTop: "32px" }}>
                <h4 style={{ fontSize: "1rem", marginBottom: "4px", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                  🔔 PR Checks
                </h4>
                <p style={{ fontSize: "0.8rem", color: "#6b7280", marginBottom: "16px" }}>
                  When <strong>ON</strong>: uses this project's custom severity settings below, overriding the global default.<br/>
                  When <strong>OFF</strong>: inherits the global PR scan setting from Integrations (scanning still runs if global is ON).
                </p>
                {!prConfig ? (
                  <p style={{ color: "#64748b", fontSize: "0.9rem" }}>Loading...</p>
                ) : (
                  <div className="config-rules-form">
                    {/* Enable toggle */}
                    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px" }}>
                      <label style={{ fontWeight: 600, fontSize: "0.95rem", color: "#374151" }}>
                        Use custom settings for this project
                      </label>
                      <button
                        onClick={() => isAdmin && setPrConfig({ ...prConfig, enabled: !prConfig.enabled })}
                        disabled={!isAdmin}
                        style={{
                          padding: "6px 18px",
                          borderRadius: "20px",
                          border: "none",
                          cursor: isAdmin ? "pointer" : "not-allowed",
                          fontWeight: 600,
                          fontSize: "0.9rem",
                          background: prConfig.enabled ? "#10b981" : "#e5e7eb",
                          color: prConfig.enabled ? "white" : "#6b7280",
                          transition: "all 0.2s"
                        }}
                        title={!isAdmin ? "Admin access required" : ""}
                      >
                        {prConfig.enabled ? "ON" : "OFF"}
                      </button>
                      {!isAdmin && <span style={{ fontSize: "0.85rem", color: "#dc2626" }}>(Admin only)</span>}
                    </div>

                    {prConfig.enabled && (
                      <>
                        {/* Block severity */}
                        <div style={{ marginBottom: "16px" }}>
                          <label style={{ fontSize: "0.9rem", fontWeight: 600, display: "block", marginBottom: "6px", color: "#374151" }}>
                            Block PR on Severity
                          </label>
                          <select
                            value={prConfig.block_on_severity || "none"}
                            onChange={e => isAdmin && setPrConfig({ ...prConfig, block_on_severity: e.target.value })}
                            disabled={!isAdmin}
                            style={{ padding: "9px 14px", border: "2px solid #e5e7eb", borderRadius: "8px", fontSize: "0.9rem", background: "#fff" }}
                          >
                            <option value="none">Do not block (report only)</option>
                            <option value="INFO">Block on INFO, WARNING or ERROR</option>
                            <option value="WARNING">Block on WARNING or ERROR</option>
                            <option value="ERROR">Block on ERROR only</option>
                          </select>
                          <p style={{ fontSize: "0.8rem", color: "#64748b", marginTop: "4px" }}>
                            Requires a branch protection rule in GitHub requiring the <code>vulnmonk/pr-scan</code> status check to pass.
                          </p>
                        </div>
                      </>
                    )}

                    {isAdmin && (
                      <button
                        className="primary-btn"
                        onClick={handleSavePrConfig}
                        disabled={prSaving}
                        style={{ padding: "10px 24px" }}
                      >
                        {prSaving ? "Saving..." : "Save PR Check Settings"}
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Global Rules Section (Admin Only) */}
              {isAdmin && (
                <>
                <div className="config-section" style={{ marginTop: "32px", borderTop: "2px solid #e5e7eb", paddingTop: "32px" }}>
                  <h4 style={{ fontSize: "1.05rem", marginBottom: "16px", fontWeight: 700, color: "#0f172a" }}>
                    🌍 Global Rules (All Projects)
                  </h4>
                  
                  {/* Global Exclude Rules */}
                  <div style={{ marginBottom: "24px" }}>
                    <h5 style={{ fontSize: "0.95rem", marginBottom: "12px", fontWeight: 600 }}>
                      Global Exclude Rules
                    </h5>
                    <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
                      <input
                        type="text"
                        value={newGlobalExcludeRule}
                        onChange={e => setNewGlobalExcludeRule(e.target.value)}
                        placeholder="Enter global exclude rule ID"
                        onKeyPress={(e) => e.key === 'Enter' && handleAddGlobalExcludeRule()}
                        style={{ 
                          flex: 1, 
                          padding: "10px 14px",
                          border: "2px solid #e5e7eb",
                          borderRadius: "8px",
                          fontSize: "0.9rem"
                        }}
                        disabled={saving}
                      />
                      <button 
                        onClick={handleAddGlobalExcludeRule}
                        disabled={saving || !newGlobalExcludeRule.trim()}
                        className="primary-btn"
                        style={{ padding: "10px 24px", whiteSpace: "nowrap" }}
                      >
                        {saving ? "Adding..." : "Add Global Rule"}
                      </button>
                    </div>
                    
                    {globalExcludeRules && getRulesCount(globalExcludeRules) > 0 && (
                      <div>
                        <div className="rules-tags">
                          {globalExcludeRules.split(",").map((rule, idx) => {
                            const trimmedRule = rule.trim();
                            if (!trimmedRule) return null;
                            return (
                              <span key={idx} className="rule-tag-removable" style={{ background: "#fef3c7", color: "#92400e" }}>
                                {trimmedRule}
                                <button 
                                  className="rule-remove-btn"
                                  onClick={() => handleRemoveGlobalExcludeRule(trimmedRule)}
                                  disabled={saving}
                                  title="Remove this global rule"
                                >
                                  ×
                                </button>
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* Global Include Rules */}
                  <div>
                    <h5 style={{ fontSize: "0.95rem", marginBottom: "12px", fontWeight: 600 }}>
                      Global Include Rules (YAML)
                    </h5>
                    <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
                      <label 
                        htmlFor="global-include-file-upload" 
                        style={{ 
                          flex: 1, 
                          padding: "10px 14px",
                          border: "2px solid #e5e7eb",
                          borderRadius: "8px",
                          fontSize: "0.9rem",
                          cursor: "pointer",
                          background: "#fff",
                          display: "flex",
                          alignItems: "center",
                          gap: "8px"
                        }}
                      >
                        📁 Choose YAML file to add...
                        <input
                          id="global-include-file-upload"
                          type="file"
                          accept=".yaml,.yml"
                          onChange={handleGlobalIncludeFileUpload}
                          disabled={saving}
                          style={{ display: "none" }}
                        />
                      </label>
                      {globalIncludeYamlFiles.length > 0 && (
                        <button 
                          onClick={handleClearGlobalIncludeRules}
                          disabled={saving}
                          className="secondary"
                          style={{ padding: "10px 20px", whiteSpace: "nowrap" }}
                        >
                          Clear All
                        </button>
                      )}
                      <button 
                        onClick={handleSaveGlobalIncludeRules}
                        disabled={saving}
                        className="primary-btn"
                        style={{ padding: "10px 24px", whiteSpace: "nowrap" }}
                      >
                        {saving ? "Saving..." : "Save"}
                      </button>
                    </div>
                    
                    {globalIncludeYamlFiles.length > 0 && (
                      <div style={{ marginTop: "12px" }}>
                        <h5 style={{ fontSize: "0.9rem", marginBottom: "8px", fontWeight: 600 }}>
                          Global YAML Files ({globalIncludeYamlFiles.length})
                        </h5>
                        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                          {globalIncludeYamlFiles.map((file, index) => {
                            return (
                              <div key={index} style={{ 
                                padding: "10px 12px", 
                                background: "#fef3c7", 
                                border: "1px solid #fcd34d", 
                                borderRadius: "6px",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between"
                              }}>
                                <div style={{ flex: 1 }}>
                                  <div style={{ fontSize: "0.9rem", fontWeight: 600, color: "#92400e" }}>
                                    🌍 {file.filename}
                                  </div>
                                  <div style={{ fontSize: "0.8rem", color: "#a16207", marginTop: "4px" }}>
                                    Added {new Date(file.uploadedAt).toLocaleDateString()}
                                  </div>
                                </div>
                                <button
                                  onClick={() => handleRemoveGlobalIncludeFile(index)}
                                  disabled={saving}
                                  style={{
                                    padding: "6px 12px",
                                    background: "#dc2626",
                                    color: "white",
                                    border: "none",
                                    borderRadius: "4px",
                                    cursor: "pointer",
                                    fontSize: "0.85rem",
                                    fontWeight: 600
                                  }}
                                  title="Remove this global file"
                                >
                                  Remove
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                </>
              )}
            </>
          ) : (
            <div className="config-empty-state">
              <div className="empty-icon">⚙️</div>
              <h3>Select a Project</h3>
              <p>Choose a project from the list to manage its rules and configurations</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
