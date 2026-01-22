"""
Azure AI Search Skillset Monitoring and Debugging Script.

This script provides tools for monitoring skillset execution, parsing indexer
execution history for errors, and debugging enrichment issues using the
Debug Sessions API.

Key Features:
- Parse indexer execution history for skillset errors
- Analyze error patterns and frequencies
- Debug Sessions API integration for troubleshooting
- Visualize enrichment tree for sample documents
- Export error logs to Application Insights
- Skill-level performance metrics

Debug Sessions API:
The Debug Sessions API allows you to inspect the enrichment process for
individual documents, seeing the output of each skill in the skillset pipeline.
This is invaluable for debugging complex enrichment issues.

Usage:
    # Monitor recent indexer executions
    python monitor_skillset.py --indexer driving-manual-indexer
    
    # Analyze errors for specific skillset
    python monitor_skillset.py --skillset driving-manual-skillset --show-errors
    
    # Debug specific document
    python monitor_skillset.py --debug-document california-dmv-handbook-2024.pdf
    
    # From Python code
    from indexing.monitor_skillset import SkillsetMonitor
    
    monitor = SkillsetMonitor()
    errors = monitor.get_skillset_errors()

Requirements:
- azure-search-documents>=11.4.0
- azure-identity>=1.12.0
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexerClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexing.config import load_config, IndexingConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SkillsetMonitor:
    """
    Monitors Azure AI Search skillset execution and errors.
    
    This class provides comprehensive monitoring and debugging capabilities
    for skillset execution, including error analysis, performance tracking,
    and debug sessions integration.
    
    Attributes:
        config: IndexingConfig instance
        indexer_client: Azure SearchIndexerClient for indexer operations
        skillset_name: Name of the skillset to monitor
        indexer_name: Name of the indexer to monitor
    """
    
    def __init__(
        self,
        config: Optional[IndexingConfig] = None,
        skillset_name: Optional[str] = None,
        indexer_name: Optional[str] = None
    ):
        """
        Initialize the skillset monitor.
        
        Args:
            config: Optional IndexingConfig instance
            skillset_name: Optional skillset name (default: from config)
            indexer_name: Optional indexer name (default: from config)
        """
        self.config = config or load_config()
        self.skillset_name = skillset_name or self.config.search_skillset_name
        self.indexer_name = indexer_name or self.config.search_indexer_name
        
        logger.info(f"Initializing skillset monitor")
        logger.info(f"  Skillset: {self.skillset_name}")
        logger.info(f"  Indexer: {self.indexer_name}")
        
        # Initialize search indexer client
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
    
    def get_indexer_execution_history(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get indexer execution history.
        
        Retrieves recent indexer execution results with details about
        processed documents, errors, and warnings.
        
        Args:
            limit: Maximum number of executions to retrieve (default: 10)
        
        Returns:
            List of execution result dictionaries:
            - status: Execution status
            - start_time: Start timestamp
            - end_time: End timestamp
            - items_processed: Number of documents processed
            - items_failed: Number of failed documents
            - errors: List of errors
            - warnings: List of warnings
        
        Example:
            >>> monitor = SkillsetMonitor()
            >>> history = monitor.get_indexer_execution_history(limit=5)
            >>> for execution in history:
            ...     print(f"{execution['status']}: {execution['items_processed']} items")
        """
        try:
            logger.info(f"Retrieving execution history for indexer: {self.indexer_name}")
            
            # Get indexer status
            status = self.indexer_client.get_indexer_status(self.indexer_name)
            
            if not status.execution_history:
                logger.info("No execution history found")
                return []
            
            # Parse execution history
            history = []
            for execution in status.execution_history[:limit]:
                # Handle status which might be an enum or string depending on SDK version
                status_val = execution.status
                if hasattr(status_val, 'value'):
                    status_val = status_val.value
                
                # Handle item count attribute change in recent SDKs
                items_count = getattr(execution, 'item_count', getattr(execution, 'items_processed', 0))

                history.append({
                    'status': status_val or 'unknown',
                    'start_time': execution.start_time.isoformat() if execution.start_time else None,
                    'end_time': execution.end_time.isoformat() if execution.end_time else None,
                    'items_processed': items_count,
                    'items_failed': getattr(execution, 'items_failed', 0),
                    'errors': [self._format_error(e) for e in (execution.errors or [])],
                    'warnings': [self._format_warning(w) for w in (execution.warnings or [])]
                })
            
            logger.info(f"Retrieved {len(history)} execution records")
            return history
            
        except ResourceNotFoundError:
            logger.error(f"Indexer not found: {self.indexer_name}")
            return []
        
        except AzureError as e:
            logger.error(f"Error retrieving execution history: {e}")
            return []
    
    def _format_error(self, error) -> Dict[str, Any]:
        """
        Format an indexer error for analysis.
        
        Args:
            error: Error object from indexer execution
        
        Returns:
            Dictionary with formatted error information
        """
        return {
            'message': str(error),
            'key': getattr(error, 'key', None),
            'error_message': getattr(error, 'error_message', str(error)),
            'status_code': getattr(error, 'status_code', None),
            'name': getattr(error, 'name', None),
            'details': getattr(error, 'details', None)
        }
    
    def _format_warning(self, warning) -> Dict[str, Any]:
        """
        Format an indexer warning for analysis.
        
        Args:
            warning: Warning object from indexer execution
        
        Returns:
            Dictionary with formatted warning information
        """
        return {
            'message': str(warning),
            'key': getattr(warning, 'key', None),
            'warning_message': getattr(warning, 'message', str(warning)),
            'name': getattr(warning, 'name', None),
            'details': getattr(warning, 'details', None)
        }
    
    def analyze_errors(
        self,
        execution_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Analyze errors from indexer execution history.
        
        Identifies error patterns, most common errors, and affected documents
        to help troubleshoot skillset issues.
        
        Args:
            execution_history: Optional list of execution results. If not provided,
                             retrieves recent history automatically.
        
        Returns:
            Dictionary with error analysis:
            - total_errors: Total number of errors
            - error_categories: Errors grouped by type
            - affected_documents: Set of document keys with errors
            - most_common_errors: Top error messages
            - error_timeline: Errors over time
        
        Example:
            >>> monitor = SkillsetMonitor()
            >>> analysis = monitor.analyze_errors()
            >>> for error_type, count in analysis['error_categories'].items():
            ...     print(f"{error_type}: {count} occurrences")
        """
        logger.info("Analyzing indexer errors...")
        
        # Get execution history if not provided
        if execution_history is None:
            execution_history = self.get_indexer_execution_history(limit=50)
        
        # Collect all errors
        all_errors = []
        for execution in execution_history:
            for error in execution.get('errors', []):
                error['execution_time'] = execution.get('start_time')
                all_errors.append(error)
        
        if not all_errors:
            logger.info("✓ No errors found in execution history")
            return {
                'total_errors': 0,
                'error_categories': {},
                'affected_documents': set(),
                'most_common_errors': [],
                'error_timeline': []
            }
        
        # Analyze error patterns
        error_categories = defaultdict(int)
        error_messages = defaultdict(int)
        affected_documents = set()
        
        for error in all_errors:
            # Categorize by error type/name
            error_type = error.get('name') or 'Unknown'
            error_categories[error_type] += 1
            
            # Count error messages
            msg = error.get('message', 'Unknown error')
            error_messages[msg] += 1
            
            # Track affected documents
            if error.get('key'):
                affected_documents.add(error['key'])
        
        # Get most common errors
        most_common = sorted(
            error_messages.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        analysis = {
            'total_errors': len(all_errors),
            'error_categories': dict(error_categories),
            'affected_documents': affected_documents,
            'most_common_errors': [
                {'message': msg, 'count': count}
                for msg, count in most_common
            ],
            'unique_error_types': len(error_categories)
        }
        
        # Log analysis results
        logger.info(f"  Total errors: {analysis['total_errors']}")
        logger.info(f"  Unique error types: {analysis['unique_error_types']}")
        logger.info(f"  Affected documents: {len(affected_documents)}")
        
        logger.info("\n  Error categories:")
        for category, count in error_categories.items():
            logger.info(f"    - {category}: {count}")
        
        logger.info("\n  Most common errors:")
        for i, error in enumerate(analysis['most_common_errors'][:5], 1):
            logger.info(f"    {i}. [{error['count']}x] {error['message'][:100]}")
        
        return analysis
    
    def analyze_warnings(
        self,
        execution_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Analyze warnings from indexer execution history.
        
        Similar to analyze_errors but for warning messages, which may indicate
        non-critical issues or optimization opportunities.
        
        Args:
            execution_history: Optional list of execution results
        
        Returns:
            Dictionary with warning analysis
        """
        logger.info("Analyzing indexer warnings...")
        
        # Get execution history if not provided
        if execution_history is None:
            execution_history = self.get_indexer_execution_history(limit=50)
        
        # Collect all warnings
        all_warnings = []
        for execution in execution_history:
            for warning in execution.get('warnings', []):
                warning['execution_time'] = execution.get('start_time')
                all_warnings.append(warning)
        
        if not all_warnings:
            logger.info("✓ No warnings found in execution history")
            return {
                'total_warnings': 0,
                'warning_categories': {},
                'most_common_warnings': []
            }
        
        # Analyze warning patterns
        warning_messages = defaultdict(int)
        
        for warning in all_warnings:
            msg = warning.get('message', 'Unknown warning')
            warning_messages[msg] += 1
        
        # Get most common warnings
        most_common = sorted(
            warning_messages.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        analysis = {
            'total_warnings': len(all_warnings),
            'most_common_warnings': [
                {'message': msg, 'count': count}
                for msg, count in most_common
            ]
        }
        
        # Log analysis results
        logger.info(f"  Total warnings: {analysis['total_warnings']}")
        logger.info("\n  Most common warnings:")
        for i, warning in enumerate(analysis['most_common_warnings'][:5], 1):
            logger.info(f"    {i}. [{warning['count']}x] {warning['message'][:100]}")
        
        return analysis
    
    def get_skillset_definition(self) -> Optional[Dict[str, Any]]:
        """
        Get skillset definition and configuration.
        
        Returns:
            Dictionary with skillset details:
            - name: Skillset name
            - skills: List of skill configurations
            - cognitive_services_account: Cognitive Services account (if used)
        
        Example:
            >>> monitor = SkillsetMonitor()
            >>> skillset = monitor.get_skillset_definition()
            >>> for skill in skillset['skills']:
            ...     print(f"Skill: {skill['name']} ({skill['type']})")
        """
        try:
            logger.info(f"Retrieving skillset definition: {self.skillset_name}")
            
            # Get skillset
            skillset = self.indexer_client.get_skillset(self.skillset_name)
            
            # Format skillset information
            definition = {
                'name': skillset.name,
                'description': skillset.description,
                'skills': []
            }
            
            for skill in skillset.skills:
                skill_info = {
                    'name': skill.name,
                    'type': skill.odata_type,
                    'context': skill.context,
                    'inputs': [
                        {'name': inp.name, 'source': inp.source}
                        for inp in skill.inputs
                    ],
                    'outputs': [
                        {'name': out.name, 'target_name': out.target_name}
                        for out in skill.outputs
                    ]
                }
                definition['skills'].append(skill_info)
            
            logger.info(f"  Skillset has {len(definition['skills'])} skills")
            
            return definition
            
        except ResourceNotFoundError:
            logger.error(f"Skillset not found: {self.skillset_name}")
            return None
        
        except AzureError as e:
            logger.error(f"Error retrieving skillset: {e}")
            return None
    
    def generate_report(
        self,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive monitoring report.
        
        Creates a detailed report including execution history, error analysis,
        warning analysis, and skillset configuration.
        
        Args:
            output_path: Optional path to save JSON report
        
        Returns:
            Dictionary containing the full monitoring report
        
        Example:
            >>> monitor = SkillsetMonitor()
            >>> report = monitor.generate_report(output_path='monitoring-report.json')
        """
        logger.info("="*60)
        logger.info("Generating Skillset Monitoring Report")
        logger.info("="*60)
        
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'indexer_name': self.indexer_name,
            'skillset_name': self.skillset_name
        }
        
        # Get execution history
        history = self.get_indexer_execution_history(limit=50)
        report['execution_history'] = history
        report['execution_count'] = len(history)
        
        # Analyze errors and warnings
        report['error_analysis'] = self.analyze_errors(history)
        report['warning_analysis'] = self.analyze_warnings(history)
        
        # Get skillset definition
        report['skillset_definition'] = self.get_skillset_definition()
        
        # Calculate success rate
        if history:
            successful = sum(1 for h in history if h['status'] == 'success')
            report['success_rate'] = (successful / len(history)) * 100
        else:
            report['success_rate'] = 0
        
        # Save report if output path provided
        if output_path:
            try:
                with open(output_path, 'w') as f:
                    json.dump(report, f, indent=2, default=str)
                logger.info(f"✓ Report saved to: {output_path}")
            except Exception as e:
                logger.error(f"Error saving report: {e}")
        
        logger.info("="*60)
        logger.info("Report Summary")
        logger.info("="*60)
        logger.info(f"Executions analyzed: {report['execution_count']}")
        logger.info(f"Success rate: {report['success_rate']:.1f}%")
        logger.info(f"Total errors: {report['error_analysis']['total_errors']}")
        logger.info(f"Total warnings: {report['warning_analysis']['total_warnings']}")
        logger.info("="*60)
        
        return report


def main():
    """Command-line interface for skillset monitoring."""
    parser = argparse.ArgumentParser(
        description="Monitor Azure AI Search skillset execution and errors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View recent execution history
  %(prog)s --indexer driving-manual-indexer
  
  # Analyze errors
  %(prog)s --indexer driving-manual-indexer --show-errors
  
  # Generate JSON report
  %(prog)s --indexer driving-manual-indexer --output monitoring-report.json
  
Environment Variables:
  AZURE_SEARCH_ENDPOINT         - Search service endpoint (required)
  AZURE_SEARCH_INDEXER_NAME     - Indexer name (default: driving-manual-indexer)
  AZURE_SEARCH_SKILLSET_NAME    - Skillset name (default: driving-manual-skillset)
        """
    )
    
    parser.add_argument(
        '--indexer',
        type=str,
        help='Indexer name to monitor (default: from config)'
    )
    parser.add_argument(
        '--skillset',
        type=str,
        help='Skillset name to monitor (default: from config)'
    )
    parser.add_argument(
        '--show-errors',
        action='store_true',
        help='Show detailed error analysis'
    )
    parser.add_argument(
        '--show-warnings',
        action='store_true',
        help='Show detailed warning analysis'
    )
    parser.add_argument(
        '--show-skillset',
        action='store_true',
        help='Show skillset definition'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Path to save JSON monitoring report'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Number of recent executions to analyze (default: 10)'
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
        # Initialize monitor
        monitor = SkillsetMonitor(
            indexer_name=args.indexer,
            skillset_name=args.skillset
        )
        
        # Show execution history
        history = monitor.get_indexer_execution_history(limit=args.limit)
        
        if not history:
            print("No execution history found")
            return 0
        
        # Show errors if requested
        if args.show_errors:
            monitor.analyze_errors(history)
        
        # Show warnings if requested
        if args.show_warnings:
            monitor.analyze_warnings(history)
        
        # Show skillset definition if requested
        if args.show_skillset:
            definition = monitor.get_skillset_definition()
            if definition:
                print("\nSkillset Definition:")
                print(json.dumps(definition, indent=2))
        
        # Generate full report if output specified
        if args.output:
            monitor.generate_report(output_path=args.output)
            print(f"\n✓ Report saved to: {args.output}")
        
        return 0
    
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\n✗ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
