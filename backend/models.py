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
    integration_id = Column(Integer, ForeignKey('github_integrations.id'), nullable=True)  # Link to GitHub integration for authenticated cloning
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    scans = relationship("ScanResult", back_populates="project")

class ScanResult(Base):
    __tablename__ = 'scan_results'
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    scan_date = Column(DateTime, default=datetime.datetime.utcnow)
    result_json = Column(JSON)
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
    access_token = Column(String, nullable=False)  # GitHub Personal Access Token
    organizations = Column(JSON, default=list)  # List of organization names user has access to
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
