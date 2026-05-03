from __future__ import annotations


class ApiServiceError(Exception):
    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class DependencyConfigurationError(ApiServiceError):
    pass


class ProviderError(ApiServiceError):
    pass


class PipelineExecutionError(ApiServiceError):
    pass


class ResourceNotFoundError(ApiServiceError):
    pass
