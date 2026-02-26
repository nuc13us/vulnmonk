from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# User Schemas
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    role: str = "user"

class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

class User(UserBase):
    id: int
    role: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Existing Schemas
class ScanResultBase(BaseModel):
    scan_date: Optional[datetime] = None
    result_json: dict

class ScanResultCreate(ScanResultBase):
    pass

class ScanResult(ScanResultBase):
    id: int
    project_id: int
    class Config:
        from_attributes = True


class ProjectBase(BaseModel):
    github_url: str
    local_path: Optional[str] = None
    exclude_rules: str = ""
    include_rules_yaml: str = ""
    apply_global_exclude: bool = False
    apply_global_include: bool = False


class ProjectCreate(BaseModel):
    github_url: str
    exclude_rules: str = ""
    include_rules_yaml: str = ""
    apply_global_exclude: bool = False
    apply_global_include: bool = False
    integration_id: Optional[int] = None

class Project(ProjectBase):
    id: int
    created_at: datetime
    integration_id: Optional[int] = None
    scans: List[ScanResult] = []
    class Config:
        from_attributes = True

# Global Configuration Schemas
class GlobalConfigBase(BaseModel):
    key: str
    value: str

class GlobalConfigCreate(GlobalConfigBase):
    pass

class GlobalConfig(GlobalConfigBase):
    id: int
    updated_at: datetime
    class Config:
        from_attributes = True

# GitHub Integration Schemas
class GitHubIntegrationBase(BaseModel):
    org_name: str

class GitHubIntegrationCreate(GitHubIntegrationBase):
    access_token: str
    organizations: Optional[List[str]] = []

class GitHubIntegration(GitHubIntegrationBase):
    id: int
    organizations: Optional[List[str]] = []
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class GitHubRepository(BaseModel):
    name: str
    full_name: str
    html_url: str
    clone_url: str
    description: Optional[str] = None
    language: Optional[str] = None
    default_branch: str

class GitHubRepositoriesResponse(BaseModel):
    repositories: List[GitHubRepository]
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
