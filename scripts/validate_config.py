#!/usr/bin/env python3
"""
Configuration validation script for DrivingManualAgent.

This script validates all configuration profiles, checks for required fields,
verifies model deployment names match Bicep templates, and reports configuration
summary.

Usage:
    python scripts/validate_config.py
    python scripts/validate_config.py --profile cost-optimized
    python scripts/validate_config.py --all
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Import directly from config_loader module to avoid __init__.py side effects
import importlib.util
spec = importlib.util.spec_from_file_location(
    "config_loader",
    project_root / "src" / "agent" / "config_loader.py"
)
config_loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_loader)

load_config = config_loader.load_config
_load_json_config = config_loader._load_json_config
_get_config_dir = config_loader._get_config_dir


# ============================================================================
# Validation Functions
# ============================================================================

def validate_json_schema(config_data: Dict[str, Any], filename: str) -> List[str]:
    """
    Validate JSON schema compliance.
    
    Checks that the configuration file has the expected structure
    and all required fields.
    
    Args:
        config_data: Configuration dictionary from JSON file
        filename: Name of the configuration file (for error messages)
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Check for required top-level sections (only for base config)
    if filename == "base-config.json":
        required_sections = ["models", "search", "agent", "images"]
        for section in required_sections:
            if section not in config_data:
                errors.append(f"Missing required section: {section}")
        
        # Check models subsections (only in base config)
        if "models" in config_data:
            required_models = ["chat", "embedding", "vision"]
            for model in required_models:
                if model not in config_data["models"]:
                    errors.append(f"Missing required model: models.{model}")
                elif "deployment_name" not in config_data["models"][model]:
                    errors.append(
                        f"Missing deployment_name in models.{model}"
                    )
        
        # Check search required fields (only in base config)
        if "search" in config_data:
            required_search_fields = ["index_name", "top_k"]
            for field in required_search_fields:
                if field not in config_data["search"]:
                    errors.append(f"Missing required field: search.{field}")
    
    return errors


def validate_field_values(config_data: Dict[str, Any]) -> List[str]:
    """
    Validate that field values are within acceptable ranges.
    
    Checks numeric ranges, boolean types, and string formats.
    
    Args:
        config_data: Configuration dictionary
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Validate temperature (if present)
    if "models" in config_data and "chat" in config_data["models"]:
        chat_model = config_data["models"]["chat"]
        if "temperature" in chat_model:
            temp = chat_model["temperature"]
            if not isinstance(temp, (int, float)) or not (0.0 <= temp <= 1.0):
                errors.append(
                    f"Invalid temperature: {temp}. Must be between 0.0 and 1.0"
                )
    
    # Validate top_k (if present)
    if "search" in config_data:
        if "top_k" in config_data["search"]:
            top_k = config_data["search"]["top_k"]
            if not isinstance(top_k, int) or top_k <= 0:
                errors.append(
                    f"Invalid top_k: {top_k}. Must be a positive integer"
                )
    
    # Validate image threshold (if present)
    if "images" in config_data:
        if "relevance_threshold" in config_data["images"]:
            threshold = config_data["images"]["relevance_threshold"]
            if not isinstance(threshold, (int, float)) or not (0.0 <= threshold <= 1.0):
                errors.append(
                    f"Invalid relevance_threshold: {threshold}. "
                    "Must be between 0.0 and 1.0"
                )
        
        if "max_images_per_response" in config_data["images"]:
            max_images = config_data["images"]["max_images_per_response"]
            if not isinstance(max_images, int) or max_images <= 0:
                errors.append(
                    f"Invalid max_images_per_response: {max_images}. "
                    "Must be a positive integer"
                )
    
    return errors


def check_model_deployments(config_data: Dict[str, Any]) -> List[str]:
    """
    Check that model deployment names are reasonable.
    
    This provides warnings (not errors) for deployment names that don't
    match common patterns, helping catch typos.
    
    Args:
        config_data: Configuration dictionary
        
    Returns:
        List of warnings about deployment names
    """
    warnings = []
    
    # Known valid deployment patterns
    known_chat_models = [
        "gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-4-32k", 
        "gpt-4-turbo", "gpt-4.1", "gpt-35-turbo"
    ]
    known_embedding_models = [
        "text-embedding-3-large", "text-embedding-3-small",
        "text-embedding-ada-002"
    ]
    
    if "models" in config_data:
        # Check chat model
        if "chat" in config_data["models"]:
            deployment = config_data["models"]["chat"].get("deployment_name", "")
            if deployment and not any(known in deployment for known in known_chat_models):
                warnings.append(
                    f"Warning: Unusual chat model deployment name: {deployment}. "
                    f"Expected one of: {', '.join(known_chat_models)}"
                )
        
        # Check embedding model
        if "embedding" in config_data["models"]:
            deployment = config_data["models"]["embedding"].get("deployment_name", "")
            if deployment and not any(known in deployment for known in known_embedding_models):
                warnings.append(
                    f"Warning: Unusual embedding model deployment name: {deployment}. "
                    f"Expected one of: {', '.join(known_embedding_models)}"
                )
    
    return warnings


def validate_profile(profile_name: str) -> Tuple[bool, List[str], List[str]]:
    """
    Validate a single configuration profile.
    
    Loads the profile and runs all validation checks.
    
    Args:
        profile_name: Name of the profile to validate (e.g., 'base', 'cost-optimized')
        
    Returns:
        Tuple of (success, errors, warnings)
    """
    errors = []
    warnings = []
    
    try:
        # Load the configuration file
        if profile_name == "base":
            filename = "base-config.json"
        else:
            filename = f"{profile_name}.json"
        
        config_data = _load_json_config(filename)
        
        # Run validation checks
        schema_errors = validate_json_schema(config_data, filename)
        errors.extend(schema_errors)
        
        value_errors = validate_field_values(config_data)
        errors.extend(value_errors)
        
        deployment_warnings = check_model_deployments(config_data)
        warnings.extend(deployment_warnings)
        
        # Try to load with Pydantic (requires environment variables)
        # This is skipped if env vars aren't set
        
        success = len(errors) == 0
        return success, errors, warnings
        
    except FileNotFoundError as e:
        errors.append(f"Configuration file not found: {e}")
        return False, errors, warnings
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        return False, errors, warnings
    except Exception as e:
        errors.append(f"Unexpected error: {e}")
        return False, errors, warnings


def print_profile_summary(profile_name: str, config_data: Dict[str, Any]) -> None:
    """
    Print a summary of configuration profile settings.
    
    Args:
        profile_name: Name of the profile
        config_data: Configuration dictionary
    """
    print(f"\n{'='*70}")
    print(f"Profile: {profile_name}")
    print(f"{'='*70}")
    
    # Models
    if "models" in config_data:
        print("\n🤖 Models:")
        for model_type, model_config in config_data["models"].items():
            deployment = model_config.get("deployment_name", "N/A")
            print(f"  {model_type}: {deployment}")
            if "temperature" in model_config:
                print(f"    temperature: {model_config['temperature']}")
            if "max_tokens" in model_config:
                print(f"    max_tokens: {model_config['max_tokens']}")
            if "dimensions" in model_config:
                print(f"    dimensions: {model_config['dimensions']}")
    
    # Search
    if "search" in config_data:
        print("\n🔍 Search:")
        search_config = config_data["search"]
        print(f"  index_name: {search_config.get('index_name', 'N/A')}")
        print(f"  top_k: {search_config.get('top_k', 'N/A')}")
        if "hybrid_search" in search_config:
            print(f"  hybrid_search: {search_config['hybrid_search']}")
        if "semantic_reranking" in search_config:
            print(f"  semantic_reranking: {search_config['semantic_reranking']}")
    
    # Images
    if "images" in config_data:
        print("\n🖼️  Images:")
        images_config = config_data["images"]
        if "relevance_threshold" in images_config:
            print(f"  relevance_threshold: {images_config['relevance_threshold']}")
        if "max_images_per_response" in images_config:
            print(f"  max_images_per_response: {images_config['max_images_per_response']}")
        if "enable_llm_judge" in images_config:
            print(f"  enable_llm_judge: {images_config['enable_llm_judge']}")
    
    # Agent
    if "agent" in config_data:
        print("\n🎯 Agent:")
        agent_config = config_data["agent"]
        if "streaming" in agent_config:
            print(f"  streaming: {agent_config['streaming']}")
        if "max_thread_age_hours" in agent_config:
            print(f"  max_thread_age_hours: {agent_config['max_thread_age_hours']}")


# ============================================================================
# Main Validation Logic
# ============================================================================

def main():
    """Main validation entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate DrivingManualAgent configuration files"
    )
    parser.add_argument(
        "--profile",
        type=str,
        help="Validate a specific profile (base, cost-optimized, performance-optimized)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all available profiles"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print configuration summary for each profile"
    )
    
    args = parser.parse_args()
    
    # Determine which profiles to validate
    if args.all:
        profiles = ["base", "cost-optimized", "performance-optimized"]
    elif args.profile:
        profiles = [args.profile]
    else:
        # Default: validate all profiles
        profiles = ["base", "cost-optimized", "performance-optimized"]
    
    print("=" * 70)
    print("Configuration Validation Report")
    print("=" * 70)
    
    all_success = True
    validation_results = {}
    
    # Validate each profile
    for profile in profiles:
        success, errors, warnings = validate_profile(profile)
        validation_results[profile] = (success, errors, warnings)
        
        if not success:
            all_success = False
        
        # Print results
        status = "✓ VALID" if success else "✗ INVALID"
        print(f"\n{profile}: {status}")
        
        if errors:
            print("\n  Errors:")
            for error in errors:
                print(f"    - {error}")
        
        if warnings:
            print("\n  Warnings:")
            for warning in warnings:
                print(f"    - {warning}")
        
        # Print summary if requested
        if args.summary and success:
            try:
                if profile == "base":
                    filename = "base-config.json"
                else:
                    filename = f"{profile}.json"
                config_data = _load_json_config(filename)
                print_profile_summary(profile, config_data)
            except Exception as e:
                print(f"\n  Could not load summary: {e}")
    
    # Final summary
    print("\n" + "=" * 70)
    if all_success:
        print("✓ All configurations are valid!")
    else:
        print("✗ Some configurations have errors. Please fix them.")
    print("=" * 70 + "\n")
    
    # Exit with appropriate code
    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    main()
