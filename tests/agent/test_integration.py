"""
Integration tests for the agent system.

These tests require a live Azure AI Foundry project and Azure AI Search
index to be configured. They test end-to-end functionality.

To run these tests:
1. Set up required environment variables (see .env.example)
2. Deploy infrastructure (Azure AI Foundry project, Search index)
3. Run: pytest tests/agent/test_integration.py

These tests are skipped by default if environment is not configured.
"""

import unittest
import os
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from agent.config_loader import load_agent_config


class TestIntegration(unittest.TestCase):
    """Integration tests for agent system."""
    
    def setUp(self):
        """Check if environment is configured for integration tests."""
        try:
            # Try to load configuration
            self.config = load_agent_config(validate=False)
            
            # Check if required environment variables are set
            self.env_configured = bool(
                os.environ.get("AZURE_AI_PROJECT_ENDPOINT") and
                os.environ.get("AZURE_SEARCH_ENDPOINT")
            )
        except Exception:
            self.env_configured = False
    
    @unittest.skipIf(
        not os.environ.get("RUN_INTEGRATION_TESTS"),
        "Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable."
    )
    def test_agent_creation(self):
        """Test creating an agent with live Azure services."""
        from agent.agent_factory import create_driving_rules_agent, delete_agent
        
        # Create agent
        agent = create_driving_rules_agent()
        
        # Verify agent was created
        self.assertIsNotNone(agent)
        self.assertIsNotNone(agent.id)
        self.assertEqual(agent.model, self.config.model_deployment)
        
        # Cleanup
        delete_agent(agent.id)
    
    @unittest.skipIf(
        not os.environ.get("RUN_INTEGRATION_TESTS"),
        "Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable."
    )
    def test_thread_creation_and_messaging(self):
        """Test creating threads and adding messages."""
        from agent.conversation import (
            create_thread,
            add_message,
            get_conversation_history,
            delete_thread
        )
        
        # Create thread
        thread = create_thread(metadata={"test": "integration"})
        self.assertIsNotNone(thread)
        self.assertIsNotNone(thread.id)
        
        # Add message
        message = add_message(thread.id, "What does a stop sign mean?")
        self.assertIsNotNone(message)
        
        # Get history
        history = get_conversation_history(thread.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['content'], "What does a stop sign mean?")
        
        # Cleanup
        delete_thread(thread.id)
    
    @unittest.skipIf(
        not os.environ.get("RUN_INTEGRATION_TESTS"),
        "Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable."
    )
    def test_search_query(self):
        """Test searching the index directly."""
        from agent.search_tool import search_with_filter
        
        # Perform search
        results = search_with_filter(
            query="stop sign",
            state=None,
            top_k=5
        )
        
        # Verify results structure
        self.assertIsInstance(results, list)
        if results:
            result = results[0]
            # Check for expected fields
            self.assertIn("content", result or "chunk" in result)
    
    @unittest.skipIf(
        not os.environ.get("RUN_INTEGRATION_TESTS"),
        "Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable."
    )
    def test_end_to_end_query(self):
        """Test complete query flow from question to response."""
        from agent.app import run_agent_query
        
        # Run query
        response = run_agent_query(
            query="What does a stop sign mean?",
            state=None,
            include_images=False,
            verbose=True
        )
        
        # Verify response
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)
        # Response should mention stop sign
        self.assertTrue(
            "stop" in response.lower(),
            "Response should mention stop sign"
        )
    
    @unittest.skipIf(
        not os.environ.get("RUN_INTEGRATION_TESTS"),
        "Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable."
    )
    def test_state_specific_query(self):
        """Test state-specific filtering."""
        from agent.app import run_agent_query
        
        # Run query with state filter
        response = run_agent_query(
            query="Parking rules near fire hydrants",
            state="California",
            include_images=False,
            verbose=True
        )
        
        # Verify response
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)
    
    def test_configuration_loading(self):
        """Test that configuration can be loaded."""
        # This test runs even without full environment
        # It just checks that the config system works
        try:
            config = load_agent_config(validate=False)
            self.assertIsNotNone(config)
            
            # Check defaults are set
            self.assertEqual(config.search_index_name, "driving-rules-hybrid")
            self.assertEqual(config.model_deployment, "gpt-4o")
        except Exception as e:
            # Configuration loading should work even without environment
            self.fail(f"Configuration loading failed: {e}")


class TestImageInclusion(unittest.TestCase):
    """Test image inclusion in responses."""
    
    @unittest.skipIf(
        not os.environ.get("RUN_INTEGRATION_TESTS"),
        "Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable."
    )
    def test_query_with_images(self):
        """Test query that should include images."""
        from agent.app import run_agent_query
        
        # Query about visual element
        response = run_agent_query(
            query="What does a stop sign look like?",
            state=None,
            include_images=True,  # Force image inclusion
            verbose=True
        )
        
        # Verify response exists
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)
    
    @unittest.skipIf(
        not os.environ.get("RUN_INTEGRATION_TESTS"),
        "Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable."
    )
    def test_query_without_images(self):
        """Test query that should not include images."""
        from agent.app import run_agent_query
        
        # Query about text rule
        response = run_agent_query(
            query="When should I use turn signals?",
            state=None,
            include_images=False,  # Disable images
            verbose=True
        )
        
        # Verify response exists
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)


if __name__ == '__main__':
    # Print information about running integration tests
    if not os.environ.get("RUN_INTEGRATION_TESTS"):
        print("\n" + "="*70)
        print("Integration tests are SKIPPED by default")
        print("="*70)
        print("\nTo run integration tests:")
        print("1. Set up .env file with Azure credentials")
        print("2. Deploy infrastructure (AI Foundry project, Search index)")
        print("3. Run: RUN_INTEGRATION_TESTS=1 pytest tests/agent/test_integration.py")
        print("\nRunning unit tests only...\n")
    
    unittest.main()
