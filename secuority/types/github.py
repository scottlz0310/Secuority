"""TypedDict definitions for GitHub client/integration structures."""

from __future__ import annotations

from typing import TypedDict

from ..models.interfaces import DependabotConfig, GitHubSecuritySettings, GitHubWorkflowSummary

type JSONDict = dict[str, object]


class SecurityFeatureStatus(TypedDict, total=False):
    """Represents the enablement status returned by GitHub."""

    status: str


class SecurityAnalysisSection(TypedDict, total=False):
    """Subset of repo.security_and_analysis we care about."""

    secret_scanning: SecurityFeatureStatus
    secret_scanning_push_protection: SecurityFeatureStatus
    private_vulnerability_reporting: SecurityFeatureStatus


class RepositorySecurityResponse(TypedDict, total=False):
    """Root repository payload for security inspection."""

    security_and_analysis: SecurityAnalysisSection
    private: bool
    has_vulnerability_alerts: bool


class PushProtectionResponse(TypedDict, total=False):
    """Response for the push protection endpoint."""

    enabled: bool


class RenovateConfig(TypedDict, total=False):
    """Normalized Renovate configuration summary."""

    enabled: bool
    config_file: str | None
    config_file_exists: bool
    config_content: str


class GitHubApiStatus(TypedDict, total=True):
    """Connection/authentication status for GitHub API."""

    has_token: bool
    authenticated: bool
    api_accessible: bool
    user: str
    rate_limit_info: JSONDict | None
    errors: list[str]


class DependencyManagementReport(TypedDict, total=True):
    """Combined Renovate/Dependabot state."""

    renovate: RenovateConfig
    dependabot: DependabotConfig
    recommendations: list[str]


class SecurityAnalysisReport(TypedDict, total=True):
    """Result of security checks."""

    security_settings: GitHubSecuritySettings
    push_protection: bool
    recommendations: list[str]


class WorkflowAnalysisReport(TypedDict, total=True):
    """Result of workflow inspection."""

    workflows: list[GitHubWorkflowSummary]
    security_workflows: list[GitHubWorkflowSummary]
    quality_workflows: list[GitHubWorkflowSummary]
    has_security_workflows: bool
    has_quality_workflows: bool
    recommendations: list[str]


class ComprehensiveAnalysisResult(TypedDict, total=True):
    """Top-level aggregation returned by GitHubIntegration."""

    owner: str
    repo: str
    api_status: GitHubApiStatus
    security_analysis: SecurityAnalysisReport
    workflow_analysis: WorkflowAnalysisReport
    dependency_analysis: DependencyManagementReport
    errors: list[JSONDict]
    warnings: list[str]
    total_errors: int
    analysis_complete: bool
