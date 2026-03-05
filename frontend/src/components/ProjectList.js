import React, { useEffect, useState } from "react";
import { getProjects, addGithubProject } from "../api";

export default function ProjectList({ onSelect }) {
  const [projects, setProjects] = useState([]);
  const [githubUrl, setGithubUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getProjects().then(data => {
      const projectsList = data.projects || data;
      setProjects(projectsList);
    });
  }, []);

  const handleAddGithub = async () => {
    if (!githubUrl) return;
    setError("");
    try {
      const proj = await addGithubProject(githubUrl);
      setProjects([...projects, proj]);
      setGithubUrl("");
    } catch (err) {
      console.error("Error adding project:", err);
      setError(err.message || "Failed to add project");
    }
  };

  return (
    <div>
      <h2>Projects</h2>
      <ul>
        {projects.map((p) => {
          // Extract project name safely
          let repoName = 'Unnamed';
          if (p.github_url) {
            const parts = p.github_url.split('/').filter(part => part && !part.includes(':'));
            repoName = parts.length >= 2
              ? `${parts[parts.length - 2]}/${parts[parts.length - 1].replace('.git', '')}`
              : parts[parts.length - 1]?.replace('.git', '') || 'Unnamed';
          } else if (p.local_path) {
            repoName = p.local_path.split('/').filter(part => part).pop();
          } else if (p.name) {
            repoName = p.name;
          }
          
          return (
            <li key={p.id}>
              <button style={{ width: '100%', textAlign: 'left', marginBottom: 4 }} onClick={() => onSelect(p)}>{repoName}</button>
            </li>
          );
        })}
      </ul>
      <div className="input-row">
        <input
          value={githubUrl}
          onChange={e => setGithubUrl(e.target.value)}
          placeholder="GitHub repository URL"
        />
        <button onClick={handleAddGithub}>Add GitHub Project</button>
      </div>
      {error && (
        <div style={{ color: 'red', marginTop: '10px', padding: '10px', background: '#fee', border: '1px solid red', borderRadius: '4px' }}>
          Error: {error}
        </div>
      )}
    </div>
  );
}
