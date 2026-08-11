"""Provider layer: one OpenAI-compatible interface over cloud, local, and Routstr.

Every driver talks to a Provider; the only thing that changes between the cloud
arm, the local arm, and the sovereign (Routstr) arm is the base URL and auth.
"""
from .base import Provider, ChatResult, get_provider

__all__ = ["Provider", "ChatResult", "get_provider"]
