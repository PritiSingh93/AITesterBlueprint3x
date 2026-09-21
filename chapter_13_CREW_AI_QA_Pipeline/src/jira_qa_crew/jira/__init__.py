"""Jira integration: providers, deterministic gateway and ADF handling."""

from .adf import extract_text
from .base import HealthStatus, JiraProvider
from .fixture_provider import JiraFixtureProvider
from .gateway import GatewayHealth, JiraGateway
from .mcp_provider import JiraMCPProvider
from .rest_provider import JiraRestProvider

__all__ = [
    "GatewayHealth",
    "HealthStatus",
    "JiraFixtureProvider",
    "JiraGateway",
    "JiraMCPProvider",
    "JiraProvider",
    "JiraRestProvider",
    "extract_text",
]
