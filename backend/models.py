from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True, index=True)
    github_url = Column(String, unique=True, index=True)
    local_path = Column(String, nullable=True)  # No longer used, kept for backward compatibility
    exclude_rules = Column(String, default="")  # Comma-separated rule IDs
    include_rules_yaml = Column(String, default="")  # YAML content for include rules
    apply_global_exclude = Column(Integer, default=0)  # Apply global exclude rules (disabled by default)
    apply_global_include = Column(Integer, default=0)  # Apply global include rules (disabled by default)
    trufflehog_exclude_detectors = Column(String, default="")  # Comma-separated detector names
    integration_id = Column(Integer, ForeignKey('github_integrations.id'), nullable=True)  # Link to GitHub integration for authenticated cloning
    # Scheduled scan: NULL=inherit global, 1=enabled, 0=disabled
    scheduled_scan_enabled = Column(Integer, nullable=True, default=None)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    scans = relationship("ScanResult", back_populates="project")

class ScanResult(Base):
    __tablename__ = 'scan_results'
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    scan_date = Column(DateTime, default=datetime.datetime.utcnow)
    result_json = Column(JSON)
    # Stored at scan time and updated when FPs are marked/unmarked — avoids
    # deserialising result_json just to count open findings on every list request.
    findings_count = Column(Integer, nullable=True, default=None)
    project = relationship("Project", back_populates="scans")

class FalsePositive(Base):
    __tablename__ = 'false_positives'
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    unique_key = Column(String, index=True)  # path@line@rule-id
    marked_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('project_id', 'unique_key', name='uix_project_unique_key'),
    )

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")  # "admin" or "user"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Integer, default=1)  # SQLite uses INTEGER for boolean

class GlobalConfiguration(Base):
    __tablename__ = 'global_configurations'
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)  # e.g., "global_exclude_rules", "global_include_rules_yaml"
    value = Column(String, default="")  # Store string/JSON data
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class GitHubIntegration(Base):
    __tablename__ = 'github_integrations'
    id = Column(Integer, primary_key=True, index=True)
    org_name = Column(String, nullable=False, index=True)
    # GitHub App installs: installation_id is set; access_token is left empty.
    # Legacy OAuth integrations: access_token is set; installation_id is None.
    installation_id = Column(Integer, nullable=True, unique=True, index=True)
    account_type = Column(String, default="User")  # "User" or "Organization"
    access_token = Column(String, nullable=True, default="")  # Legacy OAuth token
    organizations = Column(JSON, default=list)  # Legacy OAuth org list
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class PRCheckConfig(Base):
    """Per-project PR check configuration."""
    __tablename__ = 'pr_check_configs'
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), unique=True, nullable=False)
    # Default enabled=0: per-project custom settings are off by default; scanning
    # is governed by the global PR scan toggle in Integrations.
    # Set to 1 to use this project's own severity settings instead of the global default.
    enabled = Column(Integer, default=0)
    webhook_secret = Column(String, nullable=True) # Legacy / unused with GitHub App
    block_on_severity = Column(String, default="none")  # none | INFO | WARNING | ERROR
    th_block_on = Column(String, default="none")  # none | verified | all
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class TrufflehogScanResult(Base):
    __tablename__ = 'trufflehog_scan_results'
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    scan_date = Column(DateTime, default=datetime.datetime.utcnow)
    result_json = Column(JSON)
    findings_count = Column(Integer, nullable=True, default=None)
    project = relationship("Project", backref="trufflehog_scans")

class TrufflehogFalsePositive(Base):
    __tablename__ = 'trufflehog_false_positives'
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    unique_key = Column(String, index=True)  # path@raw@detector
    marked_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('project_id', 'unique_key', name='uix_th_project_unique_key'),
    )

class PRScanResult(Base):
    """Stores scan results triggered by a GitHub PR webhook event."""
    __tablename__ = 'pr_scan_results'
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    pr_number = Column(Integer, nullable=False)
    pr_title = Column(String, default="")
    head_sha = Column(String, nullable=False)
    base_branch = Column(String, default="")
    head_branch = Column(String, default="")
    repo_full_name = Column(String, default="")  # e.g. "org/repo"
    # pending → running → success | failure | error
    status = Column(String, default="pending")
    findings_count = Column(Integer, default=0)
    result_json = Column(JSON, nullable=True)       # filtered findings
    changed_files = Column(JSON, nullable=True)     # list of changed file paths
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
