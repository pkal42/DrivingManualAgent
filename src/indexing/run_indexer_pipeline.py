"""
Run Azure AI Search Indexer Pipeline.

This script runs the indexer pipeline and monitors execution status.
It can be run multiple times for reprocessing documents or testing changes.

Usage:
    # Run indexer and wait for completion
    python run_indexer_pipeline.py
    
    # Run indexer without waiting
    python run_indexer_pipeline.py --no-wait
    
    # Reset indexer before running (forces reprocessing all documents)
    python run_indexer_pipeline.py --reset
    
    # Just check status
    python run_indexer_pipeline.py --status-only
    
    # Custom timeout (default: 600 seconds)
    python run_indexer_pipeline.py --timeout 600

Requirements:
    azure-search-documents>=11.6.0
    azure-identity>=1.12.0
"""

import argparse
import logging
import os
import sys
import time
from typing import Dict, Any, Optional

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexerClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Version
API_VERSION = "2025-09-01"

# Default configuration
DEFAULT_CONFIG = {
    "search_service_name": os.environ.get("AZURE_SEARCH_SERVICE_NAME", ""),
    "indexer_name": os.environ.get("AZURE_SEARCH_INDEXER_NAME", "driving-manual-indexer"),
}


class IndexerPipelineRunner:
    """Runs and monitors Azure AI Search indexer pipeline execution."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the pipeline runner.
        
        Args:
            config: Optional configuration dictionary.
        """
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.search_endpoint = f"https://{self.config['search_service_name']}.search.windows.net"
        
        # Initialize credential and client
        self.credential = DefaultAzureCredential()
        self.indexer_client = SearchIndexerClient(
            endpoint=self.search_endpoint,
            credential=self.credential,
            api_version=API_VERSION
        )
        
        logger.info(f"Initialized indexer pipeline runner")
        logger.info(f"Search service: {self.config['search_service_name']}")
        logger.info(f"Indexer: {self.config['indexer_name']}")
    
    def reset_indexer(self) -> None:
        """
        Reset the indexer to clear change tracking state.
        
        This forces the indexer to reprocess ALL documents, regardless of
        whether they've been processed before.
        
        When to use:
        - Indexer shows success but processed 0 items (change tracking issue)
        - Need to reprocess documents after skillset changes
        - Want to force complete reindexing
        """
        logger.info(f"Resetting indexer: {self.config['indexer_name']}")
        
        try:
            self.indexer_client.reset_indexer(self.config['indexer_name'])
            logger.info(f"✓ Indexer reset successfully")
            logger.info("  ℹ Change tracking state cleared")
            logger.info("  ℹ All documents will be reprocessed on next run")
        except ResourceNotFoundError:
            logger.error(f"✗ Indexer '{self.config['indexer_name']}' not found")
            logger.error("  Run deploy_search_components.py first to create the indexer")
            raise
        except Exception as e:
            logger.error(f"✗ Failed to reset indexer: {e}")
            raise
    
    def run_indexer(self, wait: bool = True, timeout: int = 600) -> bool:
        """
        Run the indexer and optionally wait for completion.
        
        Args:
            wait: If True, wait for indexer to complete before returning
            timeout: Maximum seconds to wait for completion
        
        Returns:
            True if indexer completed successfully with no failures, False otherwise
        """
        logger.info(f"Starting indexer run: {self.config['indexer_name']}")
        
        try:
            # Trigger the indexer run
            self.indexer_client.run_indexer(self.config['indexer_name'])
            logger.info(f"✓ Indexer run triggered")
            
            if not wait:
                logger.info("  ℹ Not waiting for completion (use --wait to monitor)")
                return True
            
            # Wait for completion with status monitoring
            return self._monitor_execution(timeout)
            
        except ResourceNotFoundError:
            logger.error(f"✗ Indexer '{self.config['indexer_name']}' not found")
            logger.error("  Run deploy_search_components.py first to create the indexer")
            raise
        except Exception as e:
            logger.error(f"✗ Failed to run indexer: {e}")
            raise
    
    def _monitor_execution(self, timeout: int) -> bool:
        """
        Monitor indexer execution until completion or timeout.
        
        Args:
            timeout: Maximum seconds to wait
        
        Returns:
            True if successful, False if failed or timed out
        """
        logger.info(f"Monitoring execution (timeout: {timeout}s)...")
        start_time = time.time()
        last_status = None
        check_count = 0
        
        while time.time() - start_time < timeout:
            check_count += 1
            
            try:
                status = self.indexer_client.get_indexer_status(self.config['indexer_name'])
                
                # Show status updates periodically
                current_status = status.status
                if current_status != last_status:
                    logger.info(f"  Status: {current_status}")
                    last_status = current_status
                
                # Check if execution completed
                if status.last_result:
                    result_status = status.last_result.status
                    
                    # Success case
                    if result_status == "success":
                        elapsed = time.time() - start_time
                        logger.info(f"✓ Indexer completed successfully in {elapsed:.1f}s")
                        logger.info(f"  Items processed: {status.last_result.item_count}")
                        logger.info(f"  Items failed: {status.last_result.failed_item_count}")
                        
                        # Show warnings if any
                        if status.last_result.warnings:
                            logger.warning(f"  ⚠ {len(status.last_result.warnings)} warnings")
                            for warning in status.last_result.warnings[:3]:
                                logger.warning(f"    - {warning.key}: {warning.message}")
                        
                        # Show errors if any (but status is still success)
                        if status.last_result.errors:
                            logger.warning(f"  ⚠ {len(status.last_result.errors)} errors (partial success)")
                            for error in status.last_result.errors[:3]:
                                logger.warning(f"    - {error.key}: {error.error_message}")
                        
                        # Consider it success only if no items failed
                        return status.last_result.failed_item_count == 0
                    
                    # Failure cases
                    elif result_status in ["transientFailure", "persistentFailure"]:
                        logger.error(f"✗ Indexer failed with status: {result_status}")
                        logger.error(f"  Items processed: {status.last_result.item_count}")
                        logger.error(f"  Items failed: {status.last_result.failed_item_count}")
                        
                        # Show errors
                        if status.last_result.errors:
                            logger.error(f"  Errors ({len(status.last_result.errors)}):")
                            for error in status.last_result.errors[:5]:
                                logger.error(f"    - {error.key}")
                                logger.error(f"      {error.error_message}")
                                if hasattr(error, 'details') and error.details:
                                    logger.error(f"      Details: {error.details}")
                        
                        return False
                
                # Still running, wait before checking again
                # Use exponential backoff: 2s, 4s, 6s, 8s, then 10s
                sleep_time = min(2 + (check_count * 2), 10)
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error checking status: {e}")
                time.sleep(5)
        
        # Timeout reached
        logger.warning(f"⏱ Indexer did not complete within {timeout} seconds")
        logger.warning("  The indexer may still be running. Check status later with --status-only or rerun with --timeout to wait longer")
        return False
    
    def get_status(self, detailed: bool = True) -> Dict[str, Any]:
        """
        Get indexer status and display it.
        
        Args:
            detailed: If True, show detailed execution history
        
        Returns:
            Dictionary with status information
        """
        try:
            status = self.indexer_client.get_indexer_status(self.config['indexer_name'])
            
            logger.info("=" * 60)
            logger.info(f"Indexer Status: {self.config['indexer_name']}")
            logger.info("=" * 60)
            logger.info(f"Current Status: {status.status}")
            
            # Last execution result
            if status.last_result:
                logger.info("\nLast Execution:")
                logger.info(f"  Status: {status.last_result.status}")
                logger.info(f"  Start: {status.last_result.start_time}")
                logger.info(f"  End: {status.last_result.end_time}")
                logger.info(f"  Items Processed: {status.last_result.item_count}")
                logger.info(f"  Items Failed: {status.last_result.failed_item_count}")
                
                # Errors
                if status.last_result.errors:
                    logger.info(f"\n  Errors ({len(status.last_result.errors)}):")
                    for i, error in enumerate(status.last_result.errors[:5], 1):
                        logger.info(f"    {i}. Document: {error.key}")
                        logger.info(f"       Message: {error.error_message}")
                
                # Warnings
                if status.last_result.warnings:
                    logger.info(f"\n  Warnings ({len(status.last_result.warnings)}):")
                    for i, warning in enumerate(status.last_result.warnings[:5], 1):
                        logger.info(f"    {i}. Document: {warning.key}")
                        logger.info(f"       Message: {warning.message}")
            
            # Execution history
            if detailed and status.execution_history:
                logger.info("\nExecution History:")
                for i, execution in enumerate(status.execution_history[:5], 1):
                    status_symbol = "✓" if execution.status == "success" else "✗"
                    logger.info(f"  {i}. [{status_symbol}] {execution.status}")
                    logger.info(f"     Start: {execution.start_time}")
                    logger.info(f"     Processed: {execution.item_count} | Failed: {execution.failed_item_count}")
            
            logger.info("=" * 60)
            
            # Return structured data
            result = {
                "status": status.status,
                "last_result": None,
                "execution_history": []
            }
            
            if status.last_result:
                result["last_result"] = {
                    "status": status.last_result.status,
                    "items_processed": status.last_result.item_count,
                    "items_failed": status.last_result.failed_item_count,
                    "error_count": len(status.last_result.errors) if status.last_result.errors else 0
                }
            
            return result
            
        except ResourceNotFoundError:
            logger.error(f"✗ Indexer '{self.config['indexer_name']}' not found")
            logger.error("  Run deploy_search_components.py first to create the indexer")
            raise
        except Exception as e:
            logger.error(f"Failed to get indexer status: {e}")
            raise


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Run Azure AI Search indexer pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run indexer and wait for completion
  python run_indexer_pipeline.py
  
  # Reset and run indexer (reprocess all documents)
  python run_indexer_pipeline.py --reset
  
  # Just check current status
  python run_indexer_pipeline.py --status-only
  
  # Run with custom timeout
  python run_indexer_pipeline.py --timeout 600
        """
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset indexer before running (forces reprocessing all documents)"
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for indexer to complete"
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Only show indexer status, don't run"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout in seconds for waiting (default: 300)"
    )
    parser.add_argument(
        "--search-service",
        help=f"Search service name (default: {DEFAULT_CONFIG['search_service_name']})"
    )
    parser.add_argument(
        "--indexer-name",
        help=f"Indexer name (default: {DEFAULT_CONFIG['indexer_name']})"
    )
    
    args = parser.parse_args()
    
    # Build configuration
    config = DEFAULT_CONFIG.copy()
    if args.search_service:
        config['search_service_name'] = args.search_service
    if args.indexer_name:
        config['indexer_name'] = args.indexer_name
    
    # Initialize runner
    runner = IndexerPipelineRunner(config)
    
    try:
        # Status only mode
        if args.status_only:
            runner.get_status(detailed=True)
            sys.exit(0)
        
        # Reset if requested
        if args.reset:
            runner.reset_indexer()
            logger.info("")  # Blank line for readability
        
        # Run the indexer
        success = runner.run_indexer(wait=not args.no_wait, timeout=args.timeout)
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except ResourceNotFoundError:
        logger.error("\nIndexer not found. Deploy search components first:")
        logger.error("  python src/indexing/deploy_search_components.py --deploy-all")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\nOperation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
