"""
Configuration module for Azure AI Agent Framework v2.

This module provides type-safe configuration loading for the agent implementation,
supporting hierarchical configuration with environment variable overrides.

Configuration Sources (in order of precedence):
1. Environment variables (highest priority)
2. Default values defined in this module

Required Environment Variables:
- AZURE_AI_PROJECT_ENDPOINT: Azure AI Foundry project endpoint URL
- AZURE_SEARCH_ENDPOINT: Azure AI Search service endpoint URL

Optional Environment Variables:
- AZURE_SEARCH_INDEX_NAME: Search index name (default: 'driving-rules-hybrid')
- AGENT_MODEL_DEPLOYMENT: Model deployment name (default: 'gpt-4o')
- AGENT_TEMPERATURE: Model temperature (default: 0.7)
- AGENT_TOP_P: Model top_p parameter (default: 0.95)
- AGENT_MAX_TOKENS: Maximum tokens in response (default: 4096)
- SEARCH_TOP_K: Number of search results to retrieve (default: 5)
- IMAGE_RELEVANCE_THRESHOLD: Threshold for image inclusion (default: 0.75)
- ENABLE_TELEMETRY: Enable OpenTelemetry (default: true)

Usage:
    from agent.config_loader import load_agent_config
    
    config = load_agent_config()
    print(f"Project endpoint: {config.project_endpoint}")
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentConfig:
    """
    Configuration settings for Azure AI Agent Framework v2.
    
    This dataclass holds all configuration values needed for the agent
    implementation, with type hints for better IDE support and validation.
    
    Attributes:
        project_endpoint: Azure AI Foundry project endpoint URL (required)
        search_endpoint: Azure AI Search service endpoint URL (required)
        search_index_name: Name of the search index to query
        model_deployment: Name of the GPT-4o deployment to use
        temperature: Model temperature (0.0-1.0, controls randomness)
        top_p: Model top_p (0.0-1.0, nucleus sampling)
        max_tokens: Maximum tokens in generated response
        search_top_k: Number of search results to retrieve
        image_relevance_threshold: Minimum score for including images (0.0-1.0)
        enable_telemetry: Whether to enable OpenTelemetry tracing
        storage_account: Azure Storage account name for blob access
        storage_container_images: Container name for extracted images
        use_managed_identity: Whether to use managed identity for auth
    """
    
    # Azure AI Foundry project settings
    project_endpoint: str
    
    # Azure AI Search settings
    search_endpoint: str
    search_index_name: str = "driving-rules-hybrid"
    search_top_k: int = 5
    
    # Model configuration
    model_deployment: str = "gpt-4o"
    temperature: float = 0.7
    top_p: float = 0.95
    max_tokens: int = 4096
    
    # Image inclusion settings
    image_relevance_threshold: float = 0.75
    
    # Storage settings (for image retrieval)
    storage_account: str = ""
    storage_container_images: str = "extracted-images"
    
    # Observability settings
    enable_telemetry: bool = True
    
    # Authentication settings
    use_managed_identity: bool = True
    
    def validate(self) -> None:
        """
        Validate that required configuration values are present and valid.
        
        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Check required fields
        if not self.project_endpoint:
            raise ValueError(
                "AZURE_AI_PROJECT_ENDPOINT is required. "
                "Set it in environment variables or .env file"
            )
        
        if not self.search_endpoint:
            raise ValueError(
                "AZURE_SEARCH_ENDPOINT is required. "
                "Set it in environment variables or .env file"
            )
        
        # Validate endpoint formats
        if not self.project_endpoint.startswith("https://"):
            raise ValueError(
                f"Invalid project endpoint: {self.project_endpoint}. "
                "Must start with 'https://'"
            )
        
        if not self.search_endpoint.startswith("https://"):
            raise ValueError(
                f"Invalid search endpoint: {self.search_endpoint}. "
                "Must start with 'https://'"
            )
        
        # Validate numeric ranges
        if not 0.0 <= self.temperature <= 1.0:
            raise ValueError(
                f"Invalid temperature: {self.temperature}. "
                "Must be between 0.0 and 1.0"
            )
        
        if not 0.0 <= self.top_p <= 1.0:
            raise ValueError(
                f"Invalid top_p: {self.top_p}. "
                "Must be between 0.0 and 1.0"
            )
        
        if self.max_tokens <= 0:
            raise ValueError(
                f"Invalid max_tokens: {self.max_tokens}. "
                "Must be greater than 0"
            )
        
        if self.search_top_k <= 0:
            raise ValueError(
                f"Invalid search_top_k: {self.search_top_k}. "
                "Must be greater than 0"
            )
        
        if not 0.0 <= self.image_relevance_threshold <= 1.0:
            raise ValueError(
                f"Invalid image_relevance_threshold: {self.image_relevance_threshold}. "
                "Must be between 0.0 and 1.0"
            )


def load_agent_config(validate: bool = True) -> AgentConfig:
    """
    Load agent configuration from environment variables.
    
    Reads configuration values from environment variables with fallback
    to default values. Optionally validates the configuration.
    
    Args:
        validate: Whether to validate the configuration after loading.
                 Set to False if you need to load partial config for testing.
    
    Returns:
        AgentConfig instance with loaded values
    
    Raises:
        ValueError: If validation is enabled and required config is missing
    
    Example:
        >>> import os
        >>> os.environ['AZURE_AI_PROJECT_ENDPOINT'] = 'https://my-project.api.azureml.ms'
        >>> os.environ['AZURE_SEARCH_ENDPOINT'] = 'https://mysearch.search.windows.net'
        >>> config = load_agent_config()
        >>> print(config.model_deployment)
        'gpt-4o'
    """
    # Load configuration from environment with defaults
    config = AgentConfig(
        # Required settings (no defaults)
        project_endpoint=os.environ.get("AZURE_AI_PROJECT_ENDPOINT", ""),
        search_endpoint=os.environ.get("AZURE_SEARCH_ENDPOINT", ""),
        
        # Optional settings (with defaults)
        search_index_name=os.environ.get(
            "AZURE_SEARCH_INDEX_NAME",
            "driving-rules-hybrid"
        ),
        model_deployment=os.environ.get(
            "AGENT_MODEL_DEPLOYMENT",
            "gpt-4o"
        ),
        temperature=float(os.environ.get(
            "AGENT_TEMPERATURE",
            "0.7"
        )),
        top_p=float(os.environ.get(
            "AGENT_TOP_P",
            "0.95"
        )),
        max_tokens=int(os.environ.get(
            "AGENT_MAX_TOKENS",
            "4096"
        )),
        search_top_k=int(os.environ.get(
            "SEARCH_TOP_K",
            "5"
        )),
        image_relevance_threshold=float(os.environ.get(
            "IMAGE_RELEVANCE_THRESHOLD",
            "0.75"
        )),
        storage_account=os.environ.get("AZURE_STORAGE_ACCOUNT", ""),
        storage_container_images=os.environ.get(
            "AZURE_STORAGE_CONTAINER_IMAGES",
            "extracted-images"
        ),
        enable_telemetry=os.environ.get(
            "ENABLE_TELEMETRY",
            "true"
        ).lower() in ("true", "1", "yes"),
        use_managed_identity=os.environ.get(
            "USE_MANAGED_IDENTITY",
            "true"
        ).lower() in ("true", "1", "yes")
    )
    
    # Validate if requested
    if validate:
        config.validate()
    
    return config


# Example usage and testing
if __name__ == "__main__":
    """
    Example usage of the agent configuration module.
    
    This demonstrates how to load and use the configuration,
    and serves as a simple test when running the module directly.
    """
    import sys
    
    try:
        # Try to load .env file if python-dotenv is available
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print("Loaded .env file")
        except ImportError:
            print("python-dotenv not installed, using environment variables only")
        
        # Load configuration
        config = load_agent_config()
        
        # Display configuration
        print("\n" + "="*60)
        print("Agent Configuration")
        print("="*60)
        print(f"\nAzure AI Foundry:")
        print(f"  Project endpoint:  {config.project_endpoint}")
        print(f"\nSearch Settings:")
        print(f"  Endpoint:          {config.search_endpoint}")
        print(f"  Index:             {config.search_index_name}")
        print(f"  Top K:             {config.search_top_k}")
        print(f"\nModel Settings:")
        print(f"  Deployment:        {config.model_deployment}")
        print(f"  Temperature:       {config.temperature}")
        print(f"  Top P:             {config.top_p}")
        print(f"  Max tokens:        {config.max_tokens}")
        print(f"\nImage Settings:")
        print(f"  Relevance threshold: {config.image_relevance_threshold}")
        print(f"  Storage account:     {config.storage_account}")
        print(f"  Images container:    {config.storage_container_images}")
        print(f"\nObservability:")
        print(f"  Telemetry enabled: {config.enable_telemetry}")
        print(f"\nAuthentication:")
        print(f"  Managed identity:  {config.use_managed_identity}")
        print("="*60 + "\n")
        
        print("✓ Configuration loaded and validated successfully!")
        sys.exit(0)
        
    except ValueError as e:
        print(f"\n✗ Configuration error: {e}\n", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}\n", file=sys.stderr)
        sys.exit(1)
