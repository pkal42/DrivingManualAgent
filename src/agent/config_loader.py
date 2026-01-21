"""
Configuration module for Azure AI Agent Framework v2.

This module provides type-safe configuration loading with hierarchical profile support
and environment variable overrides using Pydantic for validation.

Configuration Sources (in order of precedence):
1. Environment variables (highest priority)
2. Profile-specific configuration files (cost-optimized.json, performance-optimized.json)
3. Base configuration file (base-config.json)

Configuration Profiles:
- base: Default balanced configuration
- cost-optimized: Reduced costs (~70-80% savings) with acceptable quality
- performance-optimized: Maximum quality at higher cost (~2-3x base)

Required Environment Variables:
- AZURE_AI_PROJECT_ENDPOINT: Azure AI Foundry project endpoint URL
- AZURE_SEARCH_ENDPOINT: Azure AI Search service endpoint URL

Optional Environment Variables (override config file values):
- CONFIG_PROFILE: Configuration profile to load (base, cost-optimized, performance-optimized)
- CHAT_MODEL_DEPLOYMENT: Chat model deployment name
- EMBEDDING_MODEL_DEPLOYMENT: Embedding model deployment name
- VISION_MODEL_DEPLOYMENT: Vision model deployment name
- AZURE_SEARCH_INDEX_NAME: Search index name
- SEARCH_TOP_K: Number of search results
- AGENT_TEMPERATURE: Model temperature (0.0-1.0)
- AGENT_MAX_TOKENS: Maximum tokens in response
- IMAGE_RELEVANCE_THRESHOLD: Image inclusion threshold (0.0-1.0)
- MAX_IMAGES_PER_RESPONSE: Maximum images per response
- ENABLE_LLM_JUDGE: Enable vision model for image validation
- ENABLE_STREAMING: Enable streaming responses
- ENABLE_SEMANTIC_RERANKING: Enable semantic ranker
- ENABLE_HYBRID_SEARCH: Enable hybrid search

Usage:
    from agent.config_loader import load_config
    
    # Load default (base) configuration
    config = load_config()
    
    # Load cost-optimized profile
    config = load_config(profile="cost-optimized")
    
    # Load with environment variable overrides
    import os
    os.environ['CONFIG_PROFILE'] = 'performance-optimized'
    config = load_config()
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ============================================================================
# Pydantic Models for Type-Safe Configuration
# ============================================================================

class ModelConfig(BaseModel):
    """
    Model deployment configuration.
    
    Defines which Azure OpenAI model deployments to use for different tasks.
    """
    model_config = ConfigDict(extra='allow')  # Allow extra fields from JSON
    
    deployment_name: str = Field(
        ...,
        description="Azure OpenAI deployment name (must match Bicep deployment)"
    )
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Model temperature (0.0=deterministic, 1.0=creative)"
    )
    max_tokens: Optional[int] = Field(
        default=None,
        gt=0,
        description="Maximum tokens in generated response"
    )
    dimensions: Optional[int] = Field(
        default=None,
        gt=0,
        description="Embedding dimensions (for embedding models only)"
    )


class SearchConfig(BaseModel):
    """
    Azure AI Search configuration.
    
    Controls search behavior including index selection, result count, and search modes.
    """
    model_config = ConfigDict(extra='allow')
    
    index_name: str = Field(
        default="driving-manual-index",
        description="Name of the Azure AI Search index (contains character-based chunks)"
    )
    top_k: int = Field(
        default=5,
        gt=0,
        description="Number of search results to retrieve"
    )
    hybrid_search: bool = Field(
        default=True,
        description="Enable hybrid search (keyword + vector)"
    )
    semantic_reranking: bool = Field(
        default=True,
        description="Enable semantic reranking for better relevance"
    )


class AgentRuntimeConfig(BaseModel):
    """
    Agent runtime and behavior configuration.
    
    Controls agent behavior, threading, and system prompt settings.
    """
    model_config = ConfigDict(extra='allow')
    
    instructions_file: str = Field(
        default="config/agent-instructions.txt",
        description="Path to system prompt file"
    )
    streaming: bool = Field(
        default=True,
        description="Enable streaming responses"
    )
    max_thread_age_hours: int = Field(
        default=24,
        gt=0,
        description="Maximum age of conversation threads in hours"
    )


class ImageConfig(BaseModel):
    """
    Image inclusion and filtering configuration.
    
    Controls which images are included in responses and how they're validated.
    """
    model_config = ConfigDict(extra='allow')
    
    relevance_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score for image inclusion"
    )
    max_images_per_response: int = Field(
        default=3,
        gt=0,
        description="Maximum images to include per response"
    )
    enable_llm_judge: bool = Field(
        default=False,
        description="Use vision model to validate image relevance"
    )


class AgentConfig(BaseModel):
    """
    Complete agent configuration with all settings.
    
    This is the main configuration class that combines all sub-configurations
    and provides validation for the entire configuration hierarchy.
    
    Attributes:
        project_endpoint: Azure AI Foundry project endpoint (required)
        search_endpoint: Azure AI Search endpoint (required)
        chat_model: Chat model configuration
        embedding_model: Embedding model configuration
        vision_model: Vision model configuration
        search: Search configuration
        agent: Agent runtime configuration
        images: Image inclusion configuration
        storage_account: Azure Storage account name
        storage_container_images: Container for extracted images
        enable_telemetry: Enable OpenTelemetry tracing
        use_managed_identity: Use managed identity for auth
    """
    model_config = ConfigDict(extra='allow')
    
    # Required Azure endpoints
    project_endpoint: str = Field(
        ...,
        description="Azure AI Foundry project endpoint URL"
    )
    search_endpoint: str = Field(
        ...,
        description="Azure AI Search service endpoint URL"
    )
    
    # Model configurations
    chat_model: ModelConfig
    embedding_model: ModelConfig
    vision_model: ModelConfig
    
    # Sub-configurations
    search: SearchConfig
    agent: AgentRuntimeConfig
    images: ImageConfig
    
    # Storage settings
    storage_account: str = Field(
        default="",
        description="Azure Storage account name for blob access"
    )
    storage_container_images: str = Field(
        default="extracted-images",
        description="Container name for extracted images"
    )
    
    # Observability and auth
    enable_telemetry: bool = Field(
        default=True,
        description="Enable OpenTelemetry tracing"
    )
    use_managed_identity: bool = Field(
        default=True,
        description="Use managed identity for authentication"
    )
    
    @field_validator('project_endpoint', 'search_endpoint')
    @classmethod
    def validate_endpoint_format(cls, v: str, info) -> str:
        """
        Validate that endpoints are HTTPS URLs.
        
        Args:
            v: Endpoint URL to validate
            info: Validation context with field name
            
        Returns:
            Validated endpoint URL
            
        Raises:
            ValueError: If endpoint is not a valid HTTPS URL
        """
        if not v:
            raise ValueError(
                f"{info.field_name} is required. "
                "Set it in environment variables or config file"
            )
        
        if not v.startswith("https://"):
            raise ValueError(
                f"Invalid {info.field_name}: {v}. "
                "Must start with 'https://'"
            )
        
        return v
    
    # Backward compatibility properties for existing code
    @property
    def search_index_name(self) -> str:
        """Backward compatibility: search.index_name"""
        return self.search.index_name
    
    @property
    def search_top_k(self) -> int:
        """Backward compatibility: search.top_k"""
        return self.search.top_k
    
    @property
    def model_deployment(self) -> str:
        """Backward compatibility: chat_model.deployment_name"""
        return self.chat_model.deployment_name
    
    @property
    def temperature(self) -> float:
        """Backward compatibility: chat_model.temperature"""
        return self.chat_model.temperature or 0.7
    
    @property
    def top_p(self) -> float:
        """Backward compatibility: top_p parameter (deprecated)"""
        return 0.95
    
    @property
    def max_tokens(self) -> int:
        """Backward compatibility: chat_model.max_tokens"""
        return self.chat_model.max_tokens or 4096
    
    @property
    def image_relevance_threshold(self) -> float:
        """Backward compatibility: images.relevance_threshold"""
        return self.images.relevance_threshold
    
    def validate(self) -> None:
        """
        Validate configuration (for backward compatibility).
        
        Pydantic automatically validates on construction, but this method
        is kept for backward compatibility with existing code.
        """
        # Validation is automatic with Pydantic
        pass


# ============================================================================
# Configuration Loading Functions
# ============================================================================

def _get_config_dir() -> Path:
    """
    Get the configuration directory path.
    
    Returns absolute path to config directory relative to project root.
    
    Returns:
        Path to config directory
    """
    # Config directory is at project root / config
    project_root = Path(__file__).parent.parent.parent
    return project_root / "config"


def _load_json_config(filename: str) -> Dict[str, Any]:
    """
    Load a JSON configuration file.
    
    Args:
        filename: Name of the JSON file (e.g., 'base-config.json')
        
    Returns:
        Dictionary with configuration data
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is invalid JSON
    """
    config_dir = _get_config_dir()
    config_path = config_dir / filename
    
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Expected location: {config_dir}"
        )
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in configuration file {filename}: {e}"
        )


def _merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two configuration dictionaries.
    
    Override values take precedence over base values. Nested dictionaries
    are merged recursively.
    
    Args:
        base: Base configuration dictionary
        override: Override configuration dictionary
        
    Returns:
        Merged configuration dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = _merge_configs(result[key], value)
        else:
            # Override value
            result[key] = value
    
    return result


def _apply_env_overrides(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply environment variable overrides to configuration.
    
    Environment variables take highest precedence and override both
    base and profile configurations.
    
    Supported environment variables:
    - CHAT_MODEL_DEPLOYMENT: Overrides models.chat.deployment_name
    - EMBEDDING_MODEL_DEPLOYMENT: Overrides models.embedding.deployment_name
    - VISION_MODEL_DEPLOYMENT: Overrides models.vision.deployment_name
    - AZURE_SEARCH_INDEX_NAME: Overrides search.index_name
    - SEARCH_TOP_K: Overrides search.top_k
    - AGENT_TEMPERATURE: Overrides models.chat.temperature
    - AGENT_MAX_TOKENS: Overrides models.chat.max_tokens
    - IMAGE_RELEVANCE_THRESHOLD: Overrides images.relevance_threshold
    - MAX_IMAGES_PER_RESPONSE: Overrides images.max_images_per_response
    - ENABLE_LLM_JUDGE: Overrides images.enable_llm_judge
    - ENABLE_STREAMING: Overrides agent.streaming
    - ENABLE_SEMANTIC_RERANKING: Overrides search.semantic_reranking
    - ENABLE_HYBRID_SEARCH: Overrides search.hybrid_search
    
    Args:
        config_dict: Base configuration dictionary
        
    Returns:
        Configuration dictionary with environment overrides applied
    """
    # Ensure nested dicts exist
    if "models" not in config_dict:
        config_dict["models"] = {}
    if "chat" not in config_dict["models"]:
        config_dict["models"]["chat"] = {}
    if "embedding" not in config_dict["models"]:
        config_dict["models"]["embedding"] = {}
    if "vision" not in config_dict["models"]:
        config_dict["models"]["vision"] = {}
    if "search" not in config_dict:
        config_dict["search"] = {}
    if "agent" not in config_dict:
        config_dict["agent"] = {}
    if "images" not in config_dict:
        config_dict["images"] = {}
    
    # Model deployment overrides
    if chat_model := os.getenv("CHAT_MODEL_DEPLOYMENT"):
        config_dict["models"]["chat"]["deployment_name"] = chat_model
    
    if embedding_model := os.getenv("EMBEDDING_MODEL_DEPLOYMENT"):
        config_dict["models"]["embedding"]["deployment_name"] = embedding_model
    
    if vision_model := os.getenv("VISION_MODEL_DEPLOYMENT"):
        config_dict["models"]["vision"]["deployment_name"] = vision_model
    
    # Search configuration overrides
    if index_name := os.getenv("AZURE_SEARCH_INDEX_NAME") or os.getenv("AZURE_SEARCH_INDEX"):
        config_dict["search"]["index_name"] = index_name
    
    if top_k := os.getenv("SEARCH_TOP_K"):
        config_dict["search"]["top_k"] = int(top_k)
    
    if semantic_rerank := os.getenv("ENABLE_SEMANTIC_RERANKING"):
        config_dict["search"]["semantic_reranking"] = semantic_rerank.lower() in ("true", "1", "yes")
    
    if hybrid_search := os.getenv("ENABLE_HYBRID_SEARCH"):
        config_dict["search"]["hybrid_search"] = hybrid_search.lower() in ("true", "1", "yes")
    
    # Model parameter overrides
    if temperature := os.getenv("AGENT_TEMPERATURE"):
        config_dict["models"]["chat"]["temperature"] = float(temperature)
    
    if max_tokens := os.getenv("AGENT_MAX_TOKENS"):
        config_dict["models"]["chat"]["max_tokens"] = int(max_tokens)
    
    # Image configuration overrides
    if threshold := os.getenv("IMAGE_RELEVANCE_THRESHOLD"):
        config_dict["images"]["relevance_threshold"] = float(threshold)
    
    if max_images := os.getenv("MAX_IMAGES_PER_RESPONSE"):
        config_dict["images"]["max_images_per_response"] = int(max_images)
    
    if llm_judge := os.getenv("ENABLE_LLM_JUDGE"):
        config_dict["images"]["enable_llm_judge"] = llm_judge.lower() in ("true", "1", "yes")
    
    # Agent runtime overrides
    if streaming := os.getenv("ENABLE_STREAMING"):
        config_dict["agent"]["streaming"] = streaming.lower() in ("true", "1", "yes")
    
    return config_dict


def load_config(
    profile: Optional[str] = None,
    validate: bool = True
) -> AgentConfig:
    """
    Load hierarchical agent configuration with profile and environment overrides.
    
    Configuration loading order (later sources override earlier):
    1. Base configuration (config/base-config.json)
    2. Profile configuration if specified (config/{profile}.json)
    3. Environment variables (highest precedence)
    
    Required environment variables:
    - AZURE_AI_PROJECT_ENDPOINT: Azure AI Foundry endpoint
    - AZURE_SEARCH_ENDPOINT: Azure AI Search endpoint
    
    Optional profile selection:
    - Set CONFIG_PROFILE environment variable, or
    - Pass profile parameter to this function
    
    Available profiles:
    - base: Default balanced configuration (loaded automatically)
    - cost-optimized: ~70-80% cost reduction
    - performance-optimized: Maximum quality at ~2-3x cost
    
    Args:
        profile: Configuration profile name (e.g., 'cost-optimized').
                If None, uses CONFIG_PROFILE env var or defaults to 'base'.
        validate: Whether to validate configuration with Pydantic.
                 Set to False for testing with partial configs.
    
    Returns:
        AgentConfig instance with loaded and validated configuration
        
    Raises:
        FileNotFoundError: If config files are missing
        ValueError: If configuration is invalid
        
    Example:
        >>> # Load base configuration
        >>> config = load_config()
        
        >>> # Load cost-optimized profile
        >>> config = load_config(profile="cost-optimized")
        
        >>> # Load with environment variable
        >>> import os
        >>> os.environ['CONFIG_PROFILE'] = 'performance-optimized'
        >>> config = load_config()
    """
    # Determine which profile to load
    if profile is None:
        profile = os.getenv("CONFIG_PROFILE", "base")
    
    # Load base configuration
    base_config = _load_json_config("base-config.json")
    
    # Merge profile configuration if not base
    if profile != "base":
        try:
            profile_config = _load_json_config(f"{profile}.json")
            base_config = _merge_configs(base_config, profile_config)
        except FileNotFoundError:
            raise ValueError(
                f"Unknown configuration profile: {profile}\n"
                f"Available profiles: base, cost-optimized, performance-optimized"
            )
    
    # Apply environment variable overrides
    config_dict = _apply_env_overrides(base_config)
    
    # Add required environment variables
    config_dict["project_endpoint"] = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "")
    config_dict["search_endpoint"] = os.getenv("AZURE_SEARCH_ENDPOINT", "")
    
    # Optional environment variables
    if storage_account := os.getenv("AZURE_STORAGE_ACCOUNT"):
        config_dict["storage_account"] = storage_account
    
    if storage_container := os.getenv("AZURE_STORAGE_CONTAINER_IMAGES"):
        config_dict["storage_container_images"] = storage_container
    
    if telemetry := os.getenv("ENABLE_TELEMETRY"):
        config_dict["enable_telemetry"] = telemetry.lower() in ("true", "1", "yes")
    else:
        config_dict.setdefault("enable_telemetry", True)
    
    if managed_id := os.getenv("USE_MANAGED_IDENTITY"):
        config_dict["use_managed_identity"] = managed_id.lower() in ("true", "1", "yes")
    else:
        config_dict.setdefault("use_managed_identity", True)
    
    # Build Pydantic models from configuration
    config_dict["chat_model"] = ModelConfig(**config_dict["models"]["chat"])
    config_dict["embedding_model"] = ModelConfig(**config_dict["models"]["embedding"])
    config_dict["vision_model"] = ModelConfig(**config_dict["models"]["vision"])
    config_dict["search"] = SearchConfig(**config_dict["search"])
    config_dict["agent"] = AgentRuntimeConfig(**config_dict["agent"])
    config_dict["images"] = ImageConfig(**config_dict["images"])
    
    # Remove the old 'models' key since we've extracted the submodels
    config_dict.pop("models", None)
    
    # Create and validate AgentConfig
    if validate:
        return AgentConfig(**config_dict)
    else:
        # For testing: skip validation
        return AgentConfig.model_construct(**config_dict)


# Backward compatibility alias
def load_agent_config(validate: bool = True) -> AgentConfig:
    """
    Load agent configuration (backward compatibility wrapper).
    
    This function maintains backward compatibility with existing code
    that uses load_agent_config(). New code should use load_config().
    
    Args:
        validate: Whether to validate the configuration
        
    Returns:
        AgentConfig instance
    """
    return load_config(validate=validate)


# ============================================================================
# Example Usage and Testing
# ============================================================================

if __name__ == "__main__":
    """
    Example usage and configuration display.
    
    Run this module directly to test configuration loading and display
    the current configuration values:
        python -m agent.config_loader
    """
    import sys
    
    try:
        # Try to load .env file if python-dotenv is available
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print("✓ Loaded .env file")
        except ImportError:
            print("ℹ python-dotenv not installed, using environment variables only")
        
        # Determine profile
        profile = os.getenv("CONFIG_PROFILE", "base")
        print(f"ℹ Loading configuration profile: {profile}\n")
        
        # Load configuration
        config = load_config()
        
        # Display configuration
        print("=" * 70)
        print("Agent Configuration")
        print("=" * 70)
        
        print("\n📁 Profile Information:")
        print(f"  Active profile:    {profile}")
        
        print("\n🔗 Azure Endpoints:")
        print(f"  Project endpoint:  {config.project_endpoint}")
        print(f"  Search endpoint:   {config.search_endpoint}")
        
        print("\n🤖 Model Deployments:")
        print(f"  Chat model:        {config.chat_model.deployment_name}")
        if config.chat_model.temperature:
            print(f"    Temperature:     {config.chat_model.temperature}")
        if config.chat_model.max_tokens:
            print(f"    Max tokens:      {config.chat_model.max_tokens}")
        print(f"  Embedding model:   {config.embedding_model.deployment_name}")
        if config.embedding_model.dimensions:
            print(f"    Dimensions:      {config.embedding_model.dimensions}")
        print(f"  Vision model:      {config.vision_model.deployment_name}")
        
        print("\n🔍 Search Configuration:")
        print(f"  Index name:        {config.search.index_name}")
        print(f"  Top K results:     {config.search.top_k}")
        print(f"  Hybrid search:     {config.search.hybrid_search}")
        print(f"  Semantic reranking: {config.search.semantic_reranking}")
        
        print("\n🎯 Agent Runtime:")
        print(f"  Instructions file: {config.agent.instructions_file}")
        print(f"  Streaming enabled: {config.agent.streaming}")
        print(f"  Max thread age:    {config.agent.max_thread_age_hours}h")
        
        print("\n🖼️  Image Settings:")
        print(f"  Relevance threshold: {config.images.relevance_threshold}")
        print(f"  Max images/response: {config.images.max_images_per_response}")
        print(f"  LLM judge enabled:   {config.images.enable_llm_judge}")
        
        print("\n💾 Storage:")
        print(f"  Storage account:   {config.storage_account or '(not set)'}")
        print(f"  Images container:  {config.storage_container_images}")
        
        print("\n⚙️  Runtime Settings:")
        print(f"  Telemetry enabled: {config.enable_telemetry}")
        print(f"  Managed identity:  {config.use_managed_identity}")
        
        print("\n" + "=" * 70)
        print("✓ Configuration loaded and validated successfully!")
        print("=" * 70 + "\n")
        
        sys.exit(0)
        
    except FileNotFoundError as e:
        print(f"\n✗ Configuration file error: {e}\n", file=sys.stderr)
        print("Make sure config files exist in the config/ directory:", file=sys.stderr)
        print("  - config/base-config.json", file=sys.stderr)
        print("  - config/cost-optimized.json (optional)", file=sys.stderr)
        print("  - config/performance-optimized.json (optional)\n", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"\n✗ Configuration validation error: {e}\n", file=sys.stderr)
        print("Check your configuration files and environment variables.\n", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}\n", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

