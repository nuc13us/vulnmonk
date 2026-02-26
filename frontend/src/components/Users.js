import React, { useState, useEffect } from "react";
import { getUsers, createUser, updateUserRole } from "../api";

export default function Users() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [message, setMessage] = useState(null);

  // New user form
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("user");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await getUsers();
      setUsers(data);
    } catch (error) {
      console.error("Failed to load users:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setMessage(null);
    setCreating(true);

    try {
      await createUser(newUsername, newPassword, newRole);
      setMessage({ type: "success", text: `User '${newUsername}' created successfully!` });
      setNewUsername("");
      setNewPassword("");
      setNewRole("user");
      setShowCreateModal(false);
      await loadUsers();
    } catch (error) {
      setMessage({ type: "error", text: error.message || "Failed to create user" });
    } finally {
      setCreating(false);
    }
  };

  const handleToggleRole = async (user) => {
    const newRole = user.role === "admin" ? "user" : "admin";
    try {
      await updateUserRole(user.id, newRole, user.is_active);
      setMessage({ type: "success", text: `User '${user.username}' role updated to ${newRole}` });
      await loadUsers();
    } catch (error) {
      setMessage({ type: "error", text: error.message || "Failed to update role" });
    }
  };

  const handleToggleStatus = async (user) => {
    const newStatus = !user.is_active;
    try {
      await updateUserRole(user.id, user.role, newStatus);
      setMessage({ 
        type: "success", 
        text: `User '${user.username}' ${newStatus ? 'activated' : 'deactivated'}` 
      });
      await loadUsers();
    } catch (error) {
      setMessage({ type: "error", text: error.message || "Failed to update status" });
    }
  };

  return (
    <div className="users-container">
      <div className="users-header">
        <div>
          <h2>User Management</h2>
          <p style={{ color: "#64748b", marginTop: "8px" }}>
            Manage user accounts and permissions
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="primary-btn"
        >
          ➕ Create User
        </button>
      </div>

      {message && (
        <div className={`message message-${message.type}`}>
          {message.text}
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: "40px" }}>
          <p style={{ color: "#64748b" }}>Loading users...</p>
        </div>
      ) : (
        <div className="users-table-container">
          <table className="users-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Username</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.id}</td>
                  <td>
                    <strong>{user.username}</strong>
                  </td>
                  <td>
                    <span className={`role-badge role-${user.role}`}>
                      {user.role === "admin" ? "👑 Admin" : "👤 User"}
                    </span>
                  </td>
                  <td>
                    <span className={`status-badge status-${user.is_active ? 'active' : 'inactive'}`}>
                      {user.is_active ? "✓ Active" : "✗ Inactive"}
                    </span>
                  </td>
                  <td>{new Date(user.created_at).toLocaleDateString()}</td>
                  <td>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        onClick={() => handleToggleRole(user)}
                        className="btn-small"
                        title={`Change to ${user.role === 'admin' ? 'user' : 'admin'}`}
                      >
                        {user.role === "admin" ? "Demote" : "Promote"}
                      </button>
                      <button
                        onClick={() => handleToggleStatus(user)}
                        className="btn-small btn-secondary"
                        title={user.is_active ? "Deactivate" : "Activate"}
                      >
                        {user.is_active ? "Deactivate" : "Activate"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {users.length === 0 && (
            <p className="empty-message">No users found.</p>
          )}
        </div>
      )}

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginTop: 0, marginBottom: "24px" }}>Create New User</h3>

            <form onSubmit={handleCreateUser}>
              <div className="form-group">
                <label>Username *</label>
                <input
                  type="text"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  required
                  minLength={3}
                  disabled={creating}
                  className="form-input"
                  placeholder="Enter username (min 3 characters)"
                />
              </div>

              <div className="form-group">
                <label>Password *</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={6}
                  disabled={creating}
                  className="form-input"
                  placeholder="Enter password (min 6 characters)"
                />
              </div>

              <div className="form-group">
                <label>Role *</label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  disabled={creating}
                  className="form-input"
                >
                  <option value="user">User (View Only)</option>
                  <option value="admin">Admin (Full Access)</option>
                </select>
              </div>

              <div style={{ display: "flex", gap: "12px", marginTop: "24px" }}>
                <button
                  type="submit"
                  disabled={creating}
                  className="primary-btn"
                  style={{ flex: 1 }}
                >
                  {creating ? "Creating..." : "Create User"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  disabled={creating}
                  className="secondary-btn"
                  style={{ flex: 1 }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
