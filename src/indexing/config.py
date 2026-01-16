"""
Configuration module for Azure AI Search indexing pipeline.

This module provides a type-safe configuration loader for the indexing scripts,
supporting environment variable overrides and sensible defaults for development
and production environments.

Configuration Sources (in order of precedence):
1. Environment variables (highest priority)
2. Default values defined in this module

Required Environment Variables:
- AZURE_STORAGE_ACCOUNT: Name of the Azure Storage account
- AZURE_SEARCH_ENDPOINT: Azure AI Search service endpoint URL

Optional Environment Variables:
- AZURE_STORAGE_CONTAINER_PDFS: PDF container name (default: 'pdfs')
- AZURE_STORAGE_CONTAINER_IMAGES: Images container name (default: 'extracted-images')
- AZURE_SEARCH_INDEX_NAME: Search index name (default: 'driving-manual-index')
- AZURE_SEARCH_INDEXER_NAME: Indexer name (default: 'driving-manual-indexer')
- AZURE_SEARCH_SKILLSET_NAME: Skillset name (default: 'driving-manual-skillset')
- AZURE_SEARCH_DATASOURCE_NAME: Data source name (default: 'driving-manual-datasource')
- INDEXER_POLL_INTERVAL: Polling interval in seconds (default: 10)
- INDEXER_TIMEOUT: Maximum indexer run time in seconds (default: 1800)

Usage:
    from indexing.config import load_config
    
    config = load_config()
    print(f"Storage account: {config.storage_account}")
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class IndexingConfig:
    """
    Configuration settings for Azure AI Search indexing pipeline.
    
    This dataclass holds all configuration values needed for the indexing
    automation scripts, with type hints for better IDE support and validation.
    
    Attributes:
        storage_account: Azure Storage account name (required)
        storage_container_pdfs: Container name for source PDF files
        storage_container_images: Container name for extracted images
        search_endpoint: Azure AI Search service endpoint URL (required)
        search_index_name: Name of the search index
        search_indexer_name: Name of the indexer
        search_skillset_name: Name of the skillset
        search_datasource_name: Name of the blob data source
        indexer_poll_interval: Seconds to wait between indexer status polls
        indexer_timeout: Maximum seconds to wait for indexer completion
        use_managed_identity: Whether to use managed identity for auth (default: True)
    """
    
    # Azure Storage settings
    storage_account: str
    storage_container_pdfs: str = "pdfs"
    storage_container_images: str = "extracted-images"
    
    # Azure AI Search settings
    search_endpoint: str = ""
    search_index_name: str = "driving-manual-index"
    search_indexer_name: str = "driving-manual-indexer"
    search_skillset_name: str = "driving-manual-skillset"
    search_datasource_name: str = "driving-manual-datasource"
    
    # Indexer monitoring settings
    indexer_poll_interval: int = 10  # seconds
    indexer_timeout: int = 1800  # 30 minutes
    
    # Authentication settings
    use_managed_identity: bool = True
    
    def validate(self) -> None:
        """
        Validate that required configuration values are present and valid.
        
        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Check required fields
        if not self.storage_account:
            raise ValueError(
                "AZURE_STORAGE_ACCOUNT is required. "
                "Set it in environment variables or .env file"
            )
        
        if not self.search_endpoint:
            raise ValueError(
                "AZURE_SEARCH_ENDPOINT is required. "
                "Set it in environment variables or .env file"
            )
        
        # Validate endpoint format
        if not self.search_endpoint.startswith("https://"):
            raise ValueError(
                f"Invalid search endpoint: {self.search_endpoint}. "
                "Must start with 'https://'"
            )
        
        # Validate numeric settings
        if self.indexer_poll_interval <= 0:
            raise ValueError(
                f"Invalid poll interval: {self.indexer_poll_interval}. "
                "Must be greater than 0"
            )
        
        if self.indexer_timeout <= 0:
            raise ValueError(
                f"Invalid timeout: {self.indexer_timeout}. "
                "Must be greater than 0"
            )
        
        # Validate container names (alphanumeric, hyphens, lowercase only)
        # Pattern allows 3-63 character names with no consecutive hyphens
        import re
        container_pattern = r'^(?!.*--)[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'
        
        for container_name, container_value in [
            ('pdfs', self.storage_container_pdfs),
            ('images', self.storage_container_images)
        ]:
            if not re.match(container_pattern, container_value):
                raise ValueError(
                    f"Invalid container name '{container_value}' for {container_name}. "
                    "Container names must be lowercase alphanumeric with hyphens, "
                    "3-63 characters, and cannot have consecutive hyphens"
                )
    
    def get_storage_connection_string(self) -> Optional[str]:
        """
        Get storage account connection string from environment.
        
        This is used for development/testing only. In production,
        managed identity should be used instead.
        
        Returns:
            Connection string if AZURE_STORAGE_CONNECTION_STRING is set,
            otherwise None (will use managed identity)
        """
        return os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    
    def get_search_api_key(self) -> Optional[str]:
        """
        Get Azure AI Search API key from environment.
        
        This is used for development/testing only. In production,
        managed identity should be used instead.
        
        Returns:
            API key if AZURE_SEARCH_API_KEY is set,
            otherwise None (will use managed identity)
        """
        return os.environ.get("AZURE_SEARCH_API_KEY")


def load_config(validate: bool = True) -> IndexingConfig:
    """
    Load configuration from environment variables.
    
    Reads configuration values from environment variables with fallback
    to default values. Optionally validates the configuration.
    
    Args:
        validate: Whether to validate the configuration after loading.
                 Set to False if you need to load partial config for testing.
    
    Returns:
        IndexingConfig instance with loaded values
    
    Raises:
        ValueError: If validation is enabled and required config is missing
    
    Example:
        >>> import os
        >>> os.environ['AZURE_STORAGE_ACCOUNT'] = 'mystorageacct'
        >>> os.environ['AZURE_SEARCH_ENDPOINT'] = 'https://mysearch.search.windows.net'
        >>> config = load_config()
        >>> print(config.storage_account)
        'mystorageacct'
    """
    # Load configuration from environment with defaults
    config = IndexingConfig(
        # Required settings (no defaults)
        storage_account=os.environ.get("AZURE_STORAGE_ACCOUNT", ""),
        search_endpoint=os.environ.get("AZURE_SEARCH_ENDPOINT", ""),
        
        # Optional settings (with defaults)
        storage_container_pdfs=os.environ.get(
            "AZURE_STORAGE_CONTAINER_PDFS",
            "pdfs"
        ),
        storage_container_images=os.environ.get(
            "AZURE_STORAGE_CONTAINER_IMAGES",
            "extracted-images"
        ),
        search_index_name=os.environ.get(
            "AZURE_SEARCH_INDEX_NAME",
            "driving-manual-index"
        ),
        search_indexer_name=os.environ.get(
            "AZURE_SEARCH_INDEXER_NAME",
            "driving-manual-indexer"
        ),
        search_skillset_name=os.environ.get(
            "AZURE_SEARCH_SKILLSET_NAME",
            "driving-manual-skillset"
        ),
        search_datasource_name=os.environ.get(
            "AZURE_SEARCH_DATASOURCE_NAME",
            "driving-manual-datasource"
        ),
        indexer_poll_interval=int(os.environ.get(
            "INDEXER_POLL_INTERVAL",
            "10"
        )),
        indexer_timeout=int(os.environ.get(
            "INDEXER_TIMEOUT",
            "1800"
        )),
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
    Example usage of the configuration module.
    
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
        config = load_config()
        
        # Display configuration
        print("\n" + "="*60)
        print("Indexing Pipeline Configuration")
        print("="*60)
        print(f"\nStorage Settings:")
        print(f"  Account:           {config.storage_account}")
        print(f"  PDFs container:    {config.storage_container_pdfs}")
        print(f"  Images container:  {config.storage_container_images}")
        print(f"\nSearch Settings:")
        print(f"  Endpoint:          {config.search_endpoint}")
        print(f"  Index:             {config.search_index_name}")
        print(f"  Indexer:           {config.search_indexer_name}")
        print(f"  Skillset:          {config.search_skillset_name}")
        print(f"  Data Source:       {config.search_datasource_name}")
        print(f"\nMonitoring Settings:")
        print(f"  Poll interval:     {config.indexer_poll_interval}s")
        print(f"  Timeout:           {config.indexer_timeout}s ({config.indexer_timeout // 60}m)")
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
