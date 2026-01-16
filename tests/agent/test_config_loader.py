"""
Unit tests for hierarchical configuration loading with Pydantic validation.

Tests configuration profiles, environment variable overrides, validation,
and backward compatibility with existing agent code.
"""

import unittest
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

# Import directly from config_loader module to avoid __init__.py side effects
import importlib.util
spec = importlib.util.spec_from_file_location(
    "config_loader",
    project_root / "src" / "agent" / "config_loader.py"
)
config_loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_loader)

AgentConfig = config_loader.AgentConfig
ModelConfig = config_loader.ModelConfig
SearchConfig = config_loader.SearchConfig
ImageConfig = config_loader.ImageConfig
AgentRuntimeConfig = config_loader.AgentRuntimeConfig
load_config = config_loader.load_config
_merge_configs = config_loader._merge_configs
_apply_env_overrides = config_loader._apply_env_overrides


class TestModelConfig(unittest.TestCase):
    """Test ModelConfig Pydantic model."""
    
    def test_model_config_valid(self):
        """Test creating valid ModelConfig."""
        config = ModelConfig(
            deployment_name="gpt-4o",
            temperature=0.7,
            max_tokens=4000
        )
        
        self.assertEqual(config.deployment_name, "gpt-4o")
        self.assertEqual(config.temperature, 0.7)
        self.assertEqual(config.max_tokens, 4000)
    
    def test_model_config_temperature_validation(self):
        """Test temperature validation."""
        # Valid temperature
        config = ModelConfig(deployment_name="gpt-4o", temperature=0.5)
        self.assertEqual(config.temperature, 0.5)
        
        # Invalid temperature (too high)
        with self.assertRaises(Exception):  # Pydantic ValidationError
            ModelConfig(deployment_name="gpt-4o", temperature=1.5)
        
        # Invalid temperature (negative)
        with self.assertRaises(Exception):
            ModelConfig(deployment_name="gpt-4o", temperature=-0.1)
    
    def test_model_config_optional_fields(self):
        """Test optional fields."""
        config = ModelConfig(deployment_name="text-embedding-3-large")
        
        self.assertEqual(config.deployment_name, "text-embedding-3-large")
        self.assertIsNone(config.temperature)
        self.assertIsNone(config.max_tokens)


class TestSearchConfig(unittest.TestCase):
    """Test SearchConfig Pydantic model."""
    
    def test_search_config_defaults(self):
        """Test SearchConfig with defaults."""
        config = SearchConfig()
        
        self.assertEqual(config.index_name, "driving-rules-hybrid")
        self.assertEqual(config.top_k, 5)
        self.assertTrue(config.hybrid_search)
        self.assertTrue(config.semantic_reranking)
    
    def test_search_config_custom_values(self):
        """Test SearchConfig with custom values."""
        config = SearchConfig(
            index_name="custom-index",
            top_k=10,
            hybrid_search=False
        )
        
        self.assertEqual(config.index_name, "custom-index")
        self.assertEqual(config.top_k, 10)
        self.assertFalse(config.hybrid_search)
    
    def test_search_config_top_k_validation(self):
        """Test top_k must be positive."""
        with self.assertRaises(Exception):  # Pydantic ValidationError
            SearchConfig(top_k=0)
        
        with self.assertRaises(Exception):
            SearchConfig(top_k=-5)


class TestImageConfig(unittest.TestCase):
    """Test ImageConfig Pydantic model."""
    
    def test_image_config_defaults(self):
        """Test ImageConfig with defaults."""
        config = ImageConfig()
        
        self.assertEqual(config.relevance_threshold, 0.75)
        self.assertEqual(config.max_images_per_response, 3)
        self.assertFalse(config.enable_llm_judge)
    
    def test_image_config_threshold_validation(self):
        """Test relevance_threshold must be 0.0-1.0."""
        # Valid thresholds
        config1 = ImageConfig(relevance_threshold=0.0)
        self.assertEqual(config1.relevance_threshold, 0.0)
        
        config2 = ImageConfig(relevance_threshold=1.0)
        self.assertEqual(config2.relevance_threshold, 1.0)
        
        # Invalid thresholds
        with self.assertRaises(Exception):
            ImageConfig(relevance_threshold=1.5)
        
        with self.assertRaises(Exception):
            ImageConfig(relevance_threshold=-0.1)


class TestAgentConfig(unittest.TestCase):
    """Test AgentConfig Pydantic model."""
    
    def test_agent_config_valid(self):
        """Test creating valid AgentConfig."""
        config = AgentConfig(
            project_endpoint="https://test.api.azureml.ms",
            search_endpoint="https://test.search.windows.net",
            chat_model=ModelConfig(deployment_name="gpt-4o"),
            embedding_model=ModelConfig(deployment_name="text-embedding-3-large"),
            vision_model=ModelConfig(deployment_name="gpt-4o"),
            search=SearchConfig(),
            agent=AgentRuntimeConfig(),
            images=ImageConfig()
        )
        
        self.assertEqual(config.project_endpoint, "https://test.api.azureml.ms")
        self.assertEqual(config.search_endpoint, "https://test.search.windows.net")
        self.assertEqual(config.chat_model.deployment_name, "gpt-4o")
    
    def test_agent_config_endpoint_validation(self):
        """Test endpoint URL validation."""
        # Valid HTTPS endpoints
        config = AgentConfig(
            project_endpoint="https://test.api.azureml.ms",
            search_endpoint="https://test.search.windows.net",
            chat_model=ModelConfig(deployment_name="gpt-4o"),
            embedding_model=ModelConfig(deployment_name="text-embedding-3-large"),
            vision_model=ModelConfig(deployment_name="gpt-4o"),
            search=SearchConfig(),
            agent=AgentRuntimeConfig(),
            images=ImageConfig()
        )
        self.assertTrue(config.project_endpoint.startswith("https://"))
        
        # Invalid endpoint (not HTTPS)
        with self.assertRaises(Exception):  # Pydantic ValidationError
            AgentConfig(
                project_endpoint="http://test.api.azureml.ms",
                search_endpoint="https://test.search.windows.net",
                chat_model=ModelConfig(deployment_name="gpt-4o"),
                embedding_model=ModelConfig(deployment_name="text-embedding-3-large"),
                vision_model=ModelConfig(deployment_name="gpt-4o"),
                search=SearchConfig(),
                agent=AgentRuntimeConfig(),
                images=ImageConfig()
            )
    
    def test_agent_config_backward_compatibility(self):
        """Test backward compatibility properties."""
        config = AgentConfig(
            project_endpoint="https://test.api.azureml.ms",
            search_endpoint="https://test.search.windows.net",
            chat_model=ModelConfig(
                deployment_name="gpt-4o",
                temperature=0.8,
                max_tokens=5000
            ),
            embedding_model=ModelConfig(deployment_name="text-embedding-3-large"),
            vision_model=ModelConfig(deployment_name="gpt-4o"),
            search=SearchConfig(index_name="my-index", top_k=7),
            agent=AgentRuntimeConfig(),
            images=ImageConfig(relevance_threshold=0.85)
        )
        
        # Backward compatibility properties
        self.assertEqual(config.search_index_name, "my-index")
        self.assertEqual(config.search_top_k, 7)
        self.assertEqual(config.model_deployment, "gpt-4o")
        self.assertEqual(config.temperature, 0.8)
        self.assertEqual(config.max_tokens, 5000)
        self.assertEqual(config.image_relevance_threshold, 0.85)
        self.assertEqual(config.top_p, 0.95)  # Deprecated but still available


class TestConfigMerging(unittest.TestCase):
    """Test configuration merging logic."""
    
    def test_merge_configs_simple(self):
        """Test merging simple configurations."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        
        result = _merge_configs(base, override)
        
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"], 3)  # Overridden
        self.assertEqual(result["c"], 4)  # Added
    
    def test_merge_configs_nested(self):
        """Test merging nested configurations."""
        base = {
            "models": {
                "chat": {"deployment_name": "gpt-4o", "temperature": 0.7},
                "embedding": {"deployment_name": "text-embedding-3-large"}
            },
            "search": {"top_k": 5}
        }
        
        override = {
            "models": {
                "chat": {"deployment_name": "gpt-4o-mini"}  # Partial override
            },
            "search": {"top_k": 3}
        }
        
        result = _merge_configs(base, override)
        
        # Chat model deployment overridden
        self.assertEqual(result["models"]["chat"]["deployment_name"], "gpt-4o-mini")
        # Chat temperature preserved from base
        self.assertEqual(result["models"]["chat"]["temperature"], 0.7)
        # Embedding model preserved from base
        self.assertEqual(result["models"]["embedding"]["deployment_name"], "text-embedding-3-large")
        # Search top_k overridden
        self.assertEqual(result["search"]["top_k"], 3)


class TestEnvironmentOverrides(unittest.TestCase):
    """Test environment variable override logic."""
    
    def test_apply_env_overrides_models(self):
        """Test model deployment overrides."""
        config_dict = {
            "models": {
                "chat": {"deployment_name": "gpt-4o"},
                "embedding": {"deployment_name": "text-embedding-3-large"},
                "vision": {"deployment_name": "gpt-4o"}
            }
        }
        
        with patch.dict(os.environ, {
            "CHAT_MODEL_DEPLOYMENT": "gpt-4o-mini",
            "EMBEDDING_MODEL_DEPLOYMENT": "text-embedding-3-small"
        }):
            result = _apply_env_overrides(config_dict)
        
        self.assertEqual(result["models"]["chat"]["deployment_name"], "gpt-4o-mini")
        self.assertEqual(result["models"]["embedding"]["deployment_name"], "text-embedding-3-small")
        self.assertEqual(result["models"]["vision"]["deployment_name"], "gpt-4o")  # Not overridden
    
    def test_apply_env_overrides_search(self):
        """Test search configuration overrides."""
        config_dict = {
            "search": {
                "index_name": "default-index",
                "top_k": 5,
                "semantic_reranking": True
            }
        }
        
        with patch.dict(os.environ, {
            "AZURE_SEARCH_INDEX": "custom-index",
            "SEARCH_TOP_K": "10",
            "ENABLE_SEMANTIC_RERANKING": "false"
        }):
            result = _apply_env_overrides(config_dict)
        
        self.assertEqual(result["search"]["index_name"], "custom-index")
        self.assertEqual(result["search"]["top_k"], 10)
        self.assertFalse(result["search"]["semantic_reranking"])
    
    def test_apply_env_overrides_images(self):
        """Test image configuration overrides."""
        config_dict = {
            "images": {
                "relevance_threshold": 0.75,
                "max_images_per_response": 3,
                "enable_llm_judge": False
            }
        }
        
        with patch.dict(os.environ, {
            "IMAGE_RELEVANCE_THRESHOLD": "0.9",
            "MAX_IMAGES_PER_RESPONSE": "5",
            "ENABLE_LLM_JUDGE": "true"
        }):
            result = _apply_env_overrides(config_dict)
        
        self.assertEqual(result["images"]["relevance_threshold"], 0.9)
        self.assertEqual(result["images"]["max_images_per_response"], 5)
        self.assertTrue(result["images"]["enable_llm_judge"])


class TestProfileLoading(unittest.TestCase):
    """Test loading different configuration profiles."""
    
    @patch.dict(os.environ, {
        "AZURE_AI_PROJECT_ENDPOINT": "https://test.api.azureml.ms",
        "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net"
    })
    def test_load_base_profile(self):
        """Test loading base profile."""
        config = load_config(profile="base")
        
        # Base profile values
        self.assertEqual(config.chat_model.deployment_name, "gpt-4o")
        self.assertEqual(config.embedding_model.deployment_name, "text-embedding-3-large")
        self.assertEqual(config.search.top_k, 5)
        self.assertEqual(config.images.max_images_per_response, 3)
        self.assertFalse(config.images.enable_llm_judge)
    
    @patch.dict(os.environ, {
        "AZURE_AI_PROJECT_ENDPOINT": "https://test.api.azureml.ms",
        "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net"
    })
    def test_load_cost_optimized_profile(self):
        """Test loading cost-optimized profile."""
        config = load_config(profile="cost-optimized")
        
        # Cost-optimized overrides
        self.assertEqual(config.chat_model.deployment_name, "gpt-4o-mini")
        self.assertEqual(config.embedding_model.deployment_name, "text-embedding-3-small")
        self.assertEqual(config.embedding_model.dimensions, 1536)
        self.assertEqual(config.search.top_k, 3)
        self.assertEqual(config.images.max_images_per_response, 2)
        
        # Values preserved from base
        self.assertEqual(config.vision_model.deployment_name, "gpt-4o")
        self.assertTrue(config.agent.streaming)
    
    @patch.dict(os.environ, {
        "AZURE_AI_PROJECT_ENDPOINT": "https://test.api.azureml.ms",
        "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net"
    })
    def test_load_performance_optimized_profile(self):
        """Test loading performance-optimized profile."""
        config = load_config(profile="performance-optimized")
        
        # Performance-optimized overrides
        self.assertEqual(config.chat_model.deployment_name, "gpt-4.1")
        self.assertEqual(config.chat_model.max_tokens, 8000)
        self.assertEqual(config.search.top_k, 10)
        self.assertEqual(config.images.max_images_per_response, 5)
        self.assertTrue(config.images.enable_llm_judge)
        
        # Values preserved from base
        self.assertEqual(config.embedding_model.deployment_name, "text-embedding-3-large")
    
    @patch.dict(os.environ, {
        "AZURE_AI_PROJECT_ENDPOINT": "https://test.api.azureml.ms",
        "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
        "CONFIG_PROFILE": "cost-optimized"
    })
    def test_load_profile_from_env_var(self):
        """Test loading profile from CONFIG_PROFILE env var."""
        config = load_config()  # No profile specified
        
        # Should use cost-optimized from env var
        self.assertEqual(config.chat_model.deployment_name, "gpt-4o-mini")
    
    def test_load_invalid_profile(self):
        """Test loading non-existent profile raises error."""
        with patch.dict(os.environ, {
            "AZURE_AI_PROJECT_ENDPOINT": "https://test.api.azureml.ms",
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net"
        }):
            with self.assertRaises(ValueError) as ctx:
                load_config(profile="non-existent-profile")
            
            self.assertIn("Unknown configuration profile", str(ctx.exception))


class TestOverridePrecedence(unittest.TestCase):
    """Test that environment variables override profile configuration."""
    
    @patch.dict(os.environ, {
        "AZURE_AI_PROJECT_ENDPOINT": "https://test.api.azureml.ms",
        "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
        "CHAT_MODEL_DEPLOYMENT": "my-custom-model",
        "SEARCH_TOP_K": "15"
    })
    def test_env_vars_override_profile(self):
        """Test environment variables override profile settings."""
        config = load_config(profile="cost-optimized")
        
        # Env var overrides profile
        self.assertEqual(config.chat_model.deployment_name, "my-custom-model")
        self.assertEqual(config.search.top_k, 15)
        
        # Profile overrides base (not affected by env vars)
        self.assertEqual(config.embedding_model.deployment_name, "text-embedding-3-small")
        self.assertEqual(config.images.max_images_per_response, 2)


class TestValidationErrors(unittest.TestCase):
    """Test configuration validation error handling."""
    
    def test_missing_required_endpoint(self):
        """Test error when required endpoints are missing."""
        with patch.dict(os.environ, clear=True):
            with self.assertRaises(Exception):  # Pydantic ValidationError
                load_config(profile="base")
    
    @patch.dict(os.environ, {
        "AZURE_AI_PROJECT_ENDPOINT": "http://test.api.azureml.ms",  # Invalid (not HTTPS)
        "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net"
    })
    def test_invalid_endpoint_format(self):
        """Test error for invalid endpoint format."""
        with self.assertRaises(Exception):  # Pydantic ValidationError
            load_config(profile="base")


if __name__ == '__main__':
    unittest.main()
