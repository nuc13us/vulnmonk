import React, { useState } from "react";
import { login, setAuthToken } from "../api";

export default function Login({ onLoginSuccess }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await login(username, password);
      setAuthToken(response.access_token);
      onLoginSuccess();
    } catch (err) {
      setError(err.message || "Login failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
    }}>
      <div style={{
        background: "white",
        padding: "48px",
        borderRadius: "16px",
        boxShadow: "0 20px 60px rgba(0, 0, 0, 0.3)",
        width: "100%",
        maxWidth: "420px"
      }}>
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <div style={{ fontSize: "3rem", marginBottom: "12px" }}>🔒</div>
          <h1 style={{ 
            fontSize: "1.8rem", 
            fontWeight: 700, 
            color: "#1e293b", 
            margin: 0,
            marginBottom: "8px"
          }}>
            VulnMonk
          </h1>
          <p style={{ color: "#64748b", fontSize: "0.95rem", margin: 0 }}>
            Sign in to your account
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          {error && (
            <div style={{
              background: "#fee2e2",
              color: "#991b1b",
              padding: "12px 16px",
              borderRadius: "8px",
              marginBottom: "20px",
              fontSize: "0.9rem",
              fontWeight: 500
            }}>
              {error}
            </div>
          )}

          <div style={{ marginBottom: "20px" }}>
            <label style={{
              display: "block",
              marginBottom: "8px",
              color: "#334155",
              fontWeight: 600,
              fontSize: "0.9rem"
            }}>
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              disabled={loading}
              style={{
                width: "100%",
                height: "44px",
                padding: "12px 14px",
                border: "2px solid #e2e8f0",
                borderRadius: "8px",
                fontSize: "1rem",
                transition: "all 0.2s",
                outline: "none",
                boxSizing: "border-box",
                marginLeft: 0,
                WebkitAppearance: "none",
                appearance: "none"
              }}
              onFocus={(e) => e.target.style.borderColor = "#667eea"}
              onBlur={(e) => e.target.style.borderColor = "#e2e8f0"}
              placeholder="Enter your username"
            />
          </div>

          <div style={{ marginBottom: "20px"  }}>
            <label style={{
              display: "block",
              marginBottom: "8px",
              color: "#334155",
              fontWeight: 600,
              fontSize: "0.9rem"
            }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
              style={{
                width: "100%",
                height: "44px",
                padding: "12px 14px",
                border: "2px solid #e2e8f0",
                borderRadius: "8px",
                fontSize: "1rem",
                transition: "all 0.2s",
                outline: "none",
                boxSizing: "border-box",
                WebkitAppearance: "none",
                appearance: "none"
              }}
              onFocus={(e) => e.target.style.borderColor = "#667eea"}
              onBlur={(e) => e.target.style.borderColor = "#e2e8f0"}
              placeholder="Enter your password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%",
              padding: "14px",
              background: loading ? "#cbd5e1" : "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
              color: "white",
              border: "none",
              borderRadius: "8px",
              fontSize: "1rem",
              fontWeight: 600,
              cursor: loading ? "not-allowed" : "pointer",
              transition: "all 0.2s",
              boxShadow: loading ? "none" : "0 4px 12px rgba(102, 126, 234, 0.4)"
            }}
            onMouseEnter={(e) => {
              if (!loading) {
                e.target.style.transform = "translateY(-2px)";
                e.target.style.boxShadow = "0 6px 16px rgba(102, 126, 234, 0.5)";
              }
            }}
            onMouseLeave={(e) => {
              e.target.style.transform = "translateY(0)";
              e.target.style.boxShadow = "0 4px 12px rgba(102, 126, 234, 0.4)";
            }}
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
