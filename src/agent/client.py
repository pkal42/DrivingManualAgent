"""
Azure AI Project Client initialization module.

This module provides a centralized way to initialize and manage the
Azure AI Project client using the Azure AI Agent Framework v2.

The client is initialized with DefaultAzureCredential for secure,
keyless authentication using managed identities in production and
development credentials locally.

Key Features:
- Managed identity authentication (no keys required)
- Connection to Azure AI Foundry project
- Singleton pattern for efficient resource usage
- Comprehensive error handling and logging

Usage:
    from agent.client import get_project_client
    
    client = get_project_client()
    # Use client to create agents, threads, etc.
"""

import logging
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.core.exceptions import AzureError

from .config_loader import load_agent_config, AgentConfig

# Configure module logger
logger = logging.getLogger(__name__)

# Global client instance for singleton pattern
_project_client: Optional[AIProjectClient] = None


class ProjectClientError(Exception):
    """Exception raised for errors in project client initialization."""
    pass


def get_project_client(
    config: Optional[AgentConfig] = None,
    force_refresh: bool = False
) -> AIProjectClient:
    """
    Get or create Azure AI Project client with managed identity authentication.
    
    This function implements a singleton pattern to reuse the same client
    instance across the application, avoiding unnecessary authentication
    and connection overhead. The client is initialized with DefaultAzureCredential
    which automatically selects the appropriate authentication method:
    
    - Managed Identity in Azure (production)
    - Azure CLI credentials (local development)
    - Visual Studio Code credentials (local development)
    - Environment variables (testing)
    
    Args:
        config: Optional AgentConfig instance. If not provided, loads from environment.
        force_refresh: If True, creates a new client even if one exists.
    
    Returns:
        AIProjectClient instance connected to Azure AI Foundry project
    
    Raises:
        ProjectClientError: If client initialization fails
        ValueError: If required configuration is missing
    
    Example:
        >>> # Get client with automatic configuration
        >>> client = get_project_client()
        >>> 
        >>> # Get client with custom configuration
        >>> from agent.config_loader import AgentConfig
        >>> config = AgentConfig(
        ...     project_endpoint="https://my-project.api.azureml.ms",
        ...     search_endpoint="https://my-search.search.windows.net"
        ... )
        >>> client = get_project_client(config=config)
    """
    global _project_client
    
    # Return existing client if available and not forcing refresh
    if _project_client is not None and not force_refresh:
        logger.debug("Returning existing project client")
        return _project_client
    
    try:
        # Load configuration if not provided
        if config is None:
            logger.info("Loading agent configuration from environment")
            config = load_agent_config()
        
        logger.info(f"Initializing Azure AI Project client for: {config.project_endpoint}")
        
        # Initialize DefaultAzureCredential for managed identity authentication
        # This credential type tries multiple authentication methods in order:
        # 1. Environment variables (AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET)
        # 2. Managed Identity (in Azure environments)
        # 3. Azure CLI (for local development)
        # 4. Visual Studio Code (for local development)
        credential = DefaultAzureCredential()
        
        # Create AI Project client
        # The client connects to an Azure AI Foundry project and provides
        # access to agents, threads, and other AI services
        _project_client = AIProjectClient(
            endpoint=config.project_endpoint,
            credential=credential
        )
        
        logger.info("Successfully initialized Azure AI Project client")
        return _project_client
        
    except ValueError as e:
        # Configuration validation failed
        error_msg = f"Invalid configuration: {e}"
        logger.error(error_msg)
        raise ProjectClientError(error_msg) from e
    
    except AzureError as e:
        # Azure SDK error (network, authentication, etc.)
        error_msg = f"Failed to initialize Azure AI Project client: {e}"
        logger.error(error_msg)
        raise ProjectClientError(error_msg) from e
    
    except Exception as e:
        # Unexpected error
        error_msg = f"Unexpected error initializing project client: {e}"
        logger.error(error_msg)
        raise ProjectClientError(error_msg) from e


def close_project_client() -> None:
    """
    Close and cleanup the global project client.
    
    This function should be called when shutting down the application
    to ensure proper cleanup of resources. After calling this function,
    the next call to get_project_client() will create a new client.
    
    Example:
        >>> client = get_project_client()
        >>> # ... use client ...
        >>> close_project_client()  # Cleanup on shutdown
    """
    global _project_client
    
    if _project_client is not None:
        logger.info("Closing Azure AI Project client")
        # Note: AIProjectClient doesn't require explicit cleanup in v2
        # but we set to None to allow garbage collection
        _project_client = None
        logger.info("Project client closed successfully")
    else:
        logger.debug("No project client to close")


# Example usage and testing
if __name__ == "__main__":
    """
    Test the project client initialization.
    
    This script demonstrates client initialization and validates
    the configuration. Run with appropriate environment variables set.
    """
    import sys
    
    # Configure logging for the test
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Try to load .env file if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print("Loaded .env file\n")
        except ImportError:
            print("python-dotenv not installed, using environment variables only\n")
        
        # Initialize client
        print("Initializing Azure AI Project client...")
        client = get_project_client()
        
        print("\n" + "="*60)
        print("Azure AI Project Client Initialized Successfully")
        print("="*60)
        print(f"\nClient type: {type(client).__name__}")
        print(f"Endpoint: {client._endpoint if hasattr(client, '_endpoint') else 'N/A'}")
        print("="*60 + "\n")
        
        # Test singleton pattern
        print("Testing singleton pattern...")
        client2 = get_project_client()
        if client is client2:
            print("✓ Singleton pattern working correctly (same instance returned)\n")
        else:
            print("✗ Warning: Different instances returned\n")
        
        # Cleanup
        close_project_client()
        print("✓ Client cleanup successful!")
        
        sys.exit(0)
        
    except ProjectClientError as e:
        print(f"\n✗ Project client error: {e}\n", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}\n", file=sys.stderr)
        sys.exit(1)
