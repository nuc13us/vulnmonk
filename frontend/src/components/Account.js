import React, { useState } from "react";
import { changePassword } from "../api";

export default function Account({ user }) {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage(null);

    // Validate passwords
    if (newPassword.length < 6) {
      setMessage({ type: "error", text: "New password must be at least 6 characters long" });
      return;
    }

    if (newPassword !== confirmPassword) {
      setMessage({ type: "error", text: "New passwords do not match" });
      return;
    }

    setLoading(true);

    try {
      await changePassword(oldPassword, newPassword);
      setMessage({ type: "success", text: "Password changed successfully!" });
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setMessage({ type: "error", text: err.message || "Failed to change password" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="account-container">
      <div className="account-header">
        <h2>Account Settings</h2>
        <p style={{ color: "#64748b", marginTop: "8px" }}>
          Manage your account information and security settings
        </p>
      </div>

      <div className="account-content">
        {/* User Info Card */}
        <div className="account-card">
          <h3 style={{ marginTop: 0, marginBottom: "20px", fontSize: "1.2rem" }}>
            Profile Information
          </h3>
          <div className="account-info-grid">
            <div className="account-info-item">
              <label>Username</label>
              <div className="account-info-value">{user.username}</div>
            </div>
            <div className="account-info-item">
              <label>Role</label>
              <div className="account-info-value">
                <span className={`role-badge role-${user.role}`}>
                  {user.role === "admin" ? "👑 Admin" : "👤 User"}
                </span>
              </div>
            </div>
            <div className="account-info-item">
              <label>Account Created</label>
              <div className="account-info-value">
                {new Date(user.created_at).toLocaleDateString()}
              </div>
            </div>
            <div className="account-info-item">
              <label>Status</label>
              <div className="account-info-value">
                <span style={{
                  color: user.is_active ? "#059669" : "#dc2626",
                  fontWeight: 600
                }}>
                  {user.is_active ? "✓ Active" : "✗ Inactive"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Change Password Card */}
        <div className="account-card">
          <h3 style={{ marginTop: 0, marginBottom: "20px", fontSize: "1.2rem" }}>
            Change Password
          </h3>

          {message && (
            <div className={`message message-${message.type}`}>
              {message.text}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>Current Password</label>
              <input
                type="password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                required
                disabled={loading}
                className="form-input"
                placeholder="Enter current password"
              />
            </div>

            <div className="form-group">
              <label>New Password</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                disabled={loading}
                className="form-input"
                placeholder="Enter new password (min 6 characters)"
              />
            </div>

            <div className="form-group">
              <label>Confirm New Password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                disabled={loading}
                className="form-input"
                placeholder="Re-enter new password"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="primary-btn"
              style={{ marginTop: "8px" }}
            >
              {loading ? "Updating..." : "Update Password"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
