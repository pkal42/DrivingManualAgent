"""
Azure AI Search Indexer Trigger and Monitor Script.

This script provides functionality to trigger Azure AI Search indexer runs,
monitor their execution status, and retrieve execution statistics with
comprehensive error reporting.

Key Features:
- Trigger indexer runs via Azure AI Search REST API
- Poll indexer status with configurable intervals
- Monitor execution lifecycle (queued → running → success/error)
- Retrieve detailed execution statistics (documents, errors, warnings)
- Timeout handling with graceful termination
- Comprehensive logging and error reporting

Indexer States:
- queued: Indexer run is waiting to start
- running: Indexer is currently processing documents
- success: Indexer completed successfully
- transientFailure: Temporary failure, will retry
- persistentFailure: Permanent failure, requires intervention
- reset: Indexer was reset, state cleared

Usage:
    # Trigger indexer and wait for completion
    python trigger_indexer.py --indexer driving-manual-indexer --wait
    
    # Trigger and monitor with custom timeout
    python trigger_indexer.py --indexer driving-manual-indexer --wait --timeout 3600
    
    # From Python code
    from indexing.trigger_indexer import IndexerRunner
    
    runner = IndexerRunner()
    success, stats = runner.run_and_wait(timeout=1800)

Requirements:
- azure-search-documents>=11.4.0
- azure-identity>=1.12.0
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexerClient

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexing.config import load_config, IndexingConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IndexerRunner:
    """
    Manages Azure AI Search indexer execution and monitoring.
    
    This class provides methods to trigger indexer runs, monitor their
    execution status, and retrieve detailed execution statistics including
    document counts, errors, and warnings.
    
    Attributes:
        config: IndexingConfig instance with search settings
        indexer_client: Azure SearchIndexerClient for indexer operations
        indexer_name: Name of the indexer to manage
    """
    
    def __init__(
        self,
        config: Optional[IndexingConfig] = None,
        indexer_name: Optional[str] = None
    ):
        """
        Initialize the indexer runner.
        
        Args:
            config: Optional IndexingConfig instance. If not provided,
                   loads from environment variables.
            indexer_name: Optional indexer name. If not provided,
                         uses config.search_indexer_name.
        
        Raises:
            ValueError: If configuration is invalid
        """
        self.config = config or load_config()
        self.indexer_name = indexer_name or self.config.search_indexer_name
        
        logger.info(f"Initializing indexer runner for: {self.indexer_name}")
        
        # Initialize search indexer client with managed identity or API key
        if self.config.use_managed_identity:
            credential = DefaultAzureCredential()
            logger.info("Using managed identity for authentication")
        else:
            api_key = self.config.get_search_api_key()
            if not api_key:
                raise ValueError(
                    "USE_MANAGED_IDENTITY is False but AZURE_SEARCH_API_KEY is not set"
                )
            credential = AzureKeyCredential(api_key)
            logger.info("Using API key for authentication")
        
        self.indexer_client = SearchIndexerClient(
            endpoint=self.config.search_endpoint,
            credential=credential
        )
    
    def trigger_run(self) -> bool:
        """
        Trigger an indexer run.
        
        Starts the indexer execution asynchronously. The indexer will begin
        processing documents from the configured data source.
        
        Returns:
            True if the indexer run was triggered successfully, False otherwise.
        
        Raises:
            ResourceNotFoundError: If the indexer does not exist
            AzureError: If there's an error communicating with the search service
        
        Example:
            >>> runner = IndexerRunner()
            >>> if runner.trigger_run():
            ...     print("Indexer started successfully")
        """
        try:
            logger.info(f"Triggering indexer run: {self.indexer_name}")
            
            # Run the indexer (asynchronous operation)
            self.indexer_client.run_indexer(self.indexer_name)
            
            logger.info(f"✓ Indexer run triggered successfully: {self.indexer_name}")
            return True
            
        except ResourceNotFoundError:
            logger.error(f"Indexer not found: {self.indexer_name}")
            return False
        
        except AzureError as e:
            logger.error(f"Error triggering indexer: {e}")
            return False
        
        except Exception as e:
            logger.error(f"Unexpected error triggering indexer: {e}")
            return False
    
    def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Get current indexer status and execution information.
        
        Retrieves the current status of the indexer including the latest
        execution details, document counts, errors, and warnings.
        
        Returns:
            Dictionary containing indexer status information:
            - status: Current indexer status (running, success, error, etc.)
            - last_result: Latest execution result (if available)
              - status: Execution status
              - start_time: Execution start timestamp
              - end_time: Execution end timestamp (if completed)
              - items_processed: Number of documents processed
              - items_failed: Number of documents that failed
              - initial_tracking_state: Initial change tracking state
              - final_tracking_state: Final change tracking state
              - errors: List of error messages
              - warnings: List of warning messages
            - execution_history: List of recent execution results
            
            Returns None if the indexer cannot be found or there's an error.
        
        Example:
            >>> runner = IndexerRunner()
            >>> status = runner.get_status()
            >>> if status:
            ...     print(f"Status: {status['status']}")
            ...     if status.get('last_result'):
            ...         print(f"Items processed: {status['last_result']['items_processed']}")
        """
        try:
            # Get indexer status from Azure AI Search
            indexer_status = self.indexer_client.get_indexer_status(self.indexer_name)
            
            # Build status dictionary
            status = {
                "indexer_name": self.indexer_name,
                "status": indexer_status.status.value if indexer_status.status else "unknown",
                "execution_history": []
            }
            
            # Get latest execution result
            if indexer_status.execution_history:
                latest = indexer_status.execution_history[0]
                
                status["last_result"] = {
                    "status": latest.status.value if latest.status else "unknown",
                    "start_time": latest.start_time.isoformat() if latest.start_time else None,
                    "end_time": latest.end_time.isoformat() if latest.end_time else None,
                    "items_processed": getattr(latest, 'items_processed', 0),
                    "items_failed": getattr(latest, 'items_failed', 0),
                    "initial_tracking_state": latest.initial_tracking_state,
                    "final_tracking_state": latest.final_tracking_state,
                    "errors": [self._format_error(e) for e in (latest.errors or [])],
                    "warnings": [self._format_warning(w) for w in (latest.warnings or [])]
                }
                
                # Add execution history
                for execution in indexer_status.execution_history[:10]:  # Last 10 executions
                    status["execution_history"].append({
                        "status": execution.status.value if execution.status else "unknown",
                        "start_time": execution.start_time.isoformat() if execution.start_time else None,
                        "end_time": execution.end_time.isoformat() if execution.end_time else None,
                        "items_processed": getattr(execution, 'items_processed', 0),
                        "items_failed": getattr(execution, 'items_failed', 0)
                    })
            
            return status
            
        except ResourceNotFoundError:
            logger.error(f"Indexer not found: {self.indexer_name}")
            return None
        
        except AzureError as e:
            logger.error(f"Error getting indexer status: {e}")
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error getting indexer status: {e}")
            return None
    
    def _format_error(self, error) -> Dict[str, str]:
        """
        Format an indexer error for logging and reporting.
        
        Args:
            error: Error object from indexer execution
        
        Returns:
            Dictionary with formatted error information
        """
        return {
            "message": str(error),
            "key": getattr(error, 'key', None),
            "error_message": getattr(error, 'error_message', str(error)),
            "status_code": getattr(error, 'status_code', None),
            "name": getattr(error, 'name', None)
        }
    
    def _format_warning(self, warning) -> Dict[str, str]:
        """
        Format an indexer warning for logging and reporting.
        
        Args:
            warning: Warning object from indexer execution
        
        Returns:
            Dictionary with formatted warning information
        """
        return {
            "message": str(warning),
            "key": getattr(warning, 'key', None),
            "warning_message": getattr(warning, 'message', str(warning)),
            "name": getattr(warning, 'name', None)
        }
    
    def wait_for_completion(
        self,
        timeout: Optional[int] = None,
        poll_interval: Optional[int] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Wait for the current indexer run to complete.
        
        Polls the indexer status at regular intervals until it completes
        (successfully or with errors) or until the timeout is reached.
        
        Args:
            timeout: Maximum time to wait in seconds. If None, uses
                    config.indexer_timeout (default: 1800 = 30 minutes)
            poll_interval: Seconds to wait between status checks. If None,
                          uses config.indexer_poll_interval (default: 10)
        
        Returns:
            Tuple of (success: bool, final_status: Dict)
            - success: True if indexer completed successfully, False otherwise
            - final_status: Final status dictionary with execution details
        
        Example:
            >>> runner = IndexerRunner()
            >>> runner.trigger_run()
            >>> success, status = runner.wait_for_completion(timeout=600)
            >>> if success:
            ...     print(f"Processed {status['last_result']['items_processed']} items")
        """
        timeout = timeout or self.config.indexer_timeout
        poll_interval = poll_interval or self.config.indexer_poll_interval
        
        logger.info(f"Waiting for indexer completion (timeout: {timeout}s, poll: {poll_interval}s)")
        
        start_time = time.time()
        last_status = None
        
        while True:
            elapsed = time.time() - start_time
            
            # Check timeout
            if elapsed > timeout:
                logger.error(f"Timeout waiting for indexer (elapsed: {elapsed:.0f}s)")
                return False, last_status
            
            # Get current status
            status = self.get_status()
            
            if status is None:
                logger.error("Failed to get indexer status")
                return False, None
            
            last_status = status
            current_state = status.get("status", "unknown")
            
            # Check if execution is complete
            if status.get("last_result"):
                result_status = status["last_result"]["status"]
                
                # Terminal states
                if result_status in ["success", "persistentFailure"]:
                    # Log final statistics
                    self._log_execution_summary(status)
                    
                    if result_status == "success":
                        logger.info("✓ Indexer completed successfully")
                        return True, status
                    else:
                        logger.error("✗ Indexer failed with persistent errors")
                        return False, status
                
                # Transient failure - keep waiting
                elif result_status == "transientFailure":
                    logger.warning("Indexer encountered transient failure, will retry...")
                
                # In progress states
                elif result_status in ["inProgress", "running"]:
                    items_processed = status["last_result"].get("items_processed", 0)
                    logger.info(f"Indexer running... ({items_processed} items processed)")
            
            # If no last_result, indexer may be queued or just starting
            else:
                logger.info(f"Indexer status: {current_state} (waiting to start...)")
            
            # Wait before next poll
            logger.debug(f"Sleeping {poll_interval}s before next status check...")
            time.sleep(poll_interval)
    
    def _log_execution_summary(self, status: Dict[str, Any]) -> None:
        """
        Log a summary of the indexer execution results.
        
        Args:
            status: Status dictionary from get_status()
        """
        if not status.get("last_result"):
            return
        
        result = status["last_result"]
        
        logger.info("="*60)
        logger.info("Indexer Execution Summary")
        logger.info("="*60)
        logger.info(f"Indexer:         {status['indexer_name']}")
        logger.info(f"Status:          {result['status']}")
        logger.info(f"Start time:      {result.get('start_time', 'N/A')}")
        logger.info(f"End time:        {result.get('end_time', 'N/A')}")
        logger.info(f"Items processed: {result['items_processed']}")
        logger.info(f"Items failed:    {result['items_failed']}")
        
        # Log errors
        errors = result.get("errors", [])
        if errors:
            logger.info(f"\nErrors ({len(errors)}):")
            for i, error in enumerate(errors[:10], 1):  # Show first 10 errors
                logger.error(f"  {i}. {error.get('message', 'Unknown error')}")
                if error.get('key'):
                    logger.error(f"     Document: {error['key']}")
            
            if len(errors) > 10:
                logger.error(f"  ... and {len(errors) - 10} more errors")
        
        # Log warnings
        warnings = result.get("warnings", [])
        if warnings:
            logger.info(f"\nWarnings ({len(warnings)}):")
            for i, warning in enumerate(warnings[:10], 1):  # Show first 10 warnings
                logger.warning(f"  {i}. {warning.get('message', 'Unknown warning')}")
            
            if len(warnings) > 10:
                logger.warning(f"  ... and {len(warnings) - 10} more warnings")
        
        logger.info("="*60)
    
    def run_and_wait(
        self,
        timeout: Optional[int] = None,
        poll_interval: Optional[int] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Trigger an indexer run and wait for it to complete.
        
        This is a convenience method that combines trigger_run() and
        wait_for_completion() into a single call.
        
        Args:
            timeout: Maximum time to wait in seconds
            poll_interval: Seconds to wait between status checks
        
        Returns:
            Tuple of (success: bool, final_status: Dict)
        
        Example:
            >>> runner = IndexerRunner()
            >>> success, status = runner.run_and_wait(timeout=1800)
            >>> if success:
            ...     print("Indexing completed successfully!")
        """
        # Trigger the indexer run
        if not self.trigger_run():
            logger.error("Failed to trigger indexer run")
            return False, None
        
        # Wait a moment for the indexer to start
        logger.info("Waiting 5 seconds for indexer to start...")
        time.sleep(5)
        
        # Wait for completion
        return self.wait_for_completion(timeout=timeout, poll_interval=poll_interval)
    
    def reset_indexer(self) -> bool:
        """
        Reset the indexer state.
        
        This clears the indexer's change tracking state, causing it to
        reprocess all documents on the next run. Use with caution.
        
        Returns:
            True if reset was successful, False otherwise
        
        Example:
            >>> runner = IndexerRunner()
            >>> if runner.reset_indexer():
            ...     print("Indexer reset successfully")
        """
        try:
            logger.info(f"Resetting indexer: {self.indexer_name}")
            self.indexer_client.reset_indexer(self.indexer_name)
            logger.info(f"✓ Indexer reset successfully: {self.indexer_name}")
            return True
            
        except ResourceNotFoundError:
            logger.error(f"Indexer not found: {self.indexer_name}")
            return False
        
        except AzureError as e:
            logger.error(f"Error resetting indexer: {e}")
            return False


def main():
    """
    Command-line interface for indexer trigger and monitoring.
    
    Provides CLI for triggering indexer runs, monitoring status, and
    displaying execution statistics.
    """
    parser = argparse.ArgumentParser(
        description="Trigger and monitor Azure AI Search indexer runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Trigger indexer and exit
  %(prog)s --indexer driving-manual-indexer
  
  # Trigger and wait for completion
  %(prog)s --indexer driving-manual-indexer --wait
  
  # Check status without triggering
  %(prog)s --indexer driving-manual-indexer --status-only
  
  # Reset and run
  %(prog)s --indexer driving-manual-indexer --reset --wait
  
Environment Variables:
  AZURE_SEARCH_ENDPOINT        - Search service endpoint (required)
  AZURE_SEARCH_INDEXER_NAME    - Indexer name (default: driving-manual-indexer)
  INDEXER_POLL_INTERVAL        - Poll interval in seconds (default: 10)
  INDEXER_TIMEOUT              - Timeout in seconds (default: 1800)
        """
    )
    
    parser.add_argument(
        '--indexer',
        type=str,
        help='Indexer name (default: from config)'
    )
    parser.add_argument(
        '--wait',
        action='store_true',
        help='Wait for indexer to complete'
    )
    parser.add_argument(
        '--status-only',
        action='store_true',
        help='Check status without triggering run'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset indexer before running'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        help='Maximum wait time in seconds (default: 1800)'
    )
    parser.add_argument(
        '--poll-interval',
        type=int,
        help='Status poll interval in seconds (default: 10)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Initialize runner
        runner = IndexerRunner(indexer_name=args.indexer)
        
        # Handle status-only mode
        if args.status_only:
            status = runner.get_status()
            if status:
                runner._log_execution_summary(status)
                return 0
            else:
                print("Failed to get indexer status", file=sys.stderr)
                return 1
        
        # Reset if requested
        if args.reset:
            if not runner.reset_indexer():
                print("Failed to reset indexer", file=sys.stderr)
                return 1
        
        # Trigger indexer run
        if args.wait:
            # Run and wait for completion
            success, status = runner.run_and_wait(
                timeout=args.timeout,
                poll_interval=args.poll_interval
            )
            
            if success:
                print("\n✓ Indexer completed successfully")
                return 0
            else:
                print("\n✗ Indexer failed or timed out", file=sys.stderr)
                return 1
        else:
            # Just trigger and exit
            if runner.trigger_run():
                print("\n✓ Indexer run triggered successfully")
                print("Use --wait to monitor completion or --status-only to check status")
                return 0
            else:
                print("\n✗ Failed to trigger indexer run", file=sys.stderr)
                return 1
    
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\n✗ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
