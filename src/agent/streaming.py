"""
Streaming response handler for Agent Framework v2.

This module provides a custom event handler for streaming agent responses,
enabling real-time display of generated text and tracking of tool calls.

Streaming Benefits:
- Immediate feedback to users (better UX)
- Lower perceived latency
- Progress indication for long responses
- Ability to cancel long-running operations

Usage:
    from agent.streaming import AgentEventHandler
    
    handler = AgentEventHandler()
    # Use with agent.run_stream() or similar
"""

import logging
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime

# Configure module logger
logger = logging.getLogger(__name__)


class AgentEventHandler:
    """
    Custom event handler for streaming agent responses.
    
    This handler processes events emitted during agent execution,
    including message deltas (text chunks), tool calls, and run status.
    
    Events:
    - on_message_delta: Partial text chunks as they're generated
    - on_thread_run: Run status updates (queued, in_progress, completed)
    - on_tool_call: Tool invocations (e.g., search queries)
    - on_error: Error handling and formatting
    
    Usage:
        handler = AgentEventHandler(
            on_text=lambda text: print(text, end="", flush=True)
        )
    """
    
    def __init__(
        self,
        on_text: Optional[Callable[[str], None]] = None,
        on_tool: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_complete: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        verbose: bool = False
    ):
        """
        Initialize the event handler with callback functions.
        
        Args:
            on_text: Callback for text chunks (receives string)
            on_tool: Callback for tool calls (receives dict with tool info)
            on_complete: Callback when run completes (receives full response)
            on_error: Callback for errors (receives exception)
            verbose: If True, log detailed event information
        """
        self.on_text = on_text
        self.on_tool = on_tool
        self.on_complete = on_complete
        self.on_error = on_error
        self.verbose = verbose
        
        # State tracking
        self.full_response = ""
        self.tool_calls: List[Dict[str, Any]] = []
        self.run_status = "unknown"
        self.start_time = datetime.now()
        
        logger.debug("Initialized AgentEventHandler")
    
    def handle_message_delta(self, delta: Any) -> None:
        """
        Handle streaming text delta events.
        
        This method is called for each chunk of text as the agent generates
        the response. It allows for real-time display of the response.
        
        Args:
            delta: Delta object containing text chunk and metadata
        """
        try:
            # Extract text from delta (format depends on SDK version)
            text = ""
            if hasattr(delta, 'content'):
                for content in delta.content:
                    if hasattr(content, 'text') and hasattr(content.text, 'value'):
                        text = content.text.value
            elif hasattr(delta, 'text'):
                text = delta.text
            
            if text:
                # Append to full response
                self.full_response += text
                
                # Call callback if provided
                if self.on_text:
                    self.on_text(text)
                
                if self.verbose:
                    logger.debug(f"Received text delta: {text[:50]}...")
        
        except Exception as e:
            logger.error(f"Error handling message delta: {e}")
            if self.on_error:
                self.on_error(e)
    
    def handle_thread_run(self, run: Any) -> None:
        """
        Handle thread run status updates.
        
        Run Status Lifecycle:
        1. queued: Run is waiting to start
        2. in_progress: Run is actively executing
        3. requires_action: Waiting for tool approval or input
        4. completed: Run finished successfully
        5. failed: Run encountered an error
        6. cancelled: Run was cancelled
        
        Args:
            run: Run object with status and metadata
        """
        try:
            status = getattr(run, 'status', 'unknown')
            self.run_status = status
            
            if self.verbose:
                logger.info(f"Run status: {status}")
            
            # Log status changes
            if status == "queued":
                logger.debug("Run queued, waiting to start")
            elif status == "in_progress":
                logger.debug("Run in progress, generating response")
            elif status == "completed":
                duration = (datetime.now() - self.start_time).total_seconds()
                logger.info(f"Run completed in {duration:.2f}s")
                
                if self.on_complete:
                    self.on_complete(self.full_response)
            elif status == "failed":
                error_msg = getattr(run, 'last_error', 'Unknown error')
                logger.error(f"Run failed: {error_msg}")
                
                if self.on_error:
                    self.on_error(Exception(f"Run failed: {error_msg}"))
            elif status == "cancelled":
                logger.warning("Run was cancelled")
        
        except Exception as e:
            logger.error(f"Error handling thread run: {e}")
            if self.on_error:
                self.on_error(e)
    
    def handle_tool_call(self, tool_call: Any) -> None:
        """
        Handle tool call events.
        
        Tool calls occur when the agent uses integrated tools like
        Azure AI Search. This handler logs the tool invocations.
        
        Tool Call Information:
        - type: Type of tool (e.g., "azure_ai_search")
        - function: Function being called
        - arguments: Tool arguments (e.g., search query)
        - result: Tool execution result (if available)
        
        Args:
            tool_call: Tool call object with type, function, and arguments
        """
        try:
            # Extract tool call information
            tool_type = getattr(tool_call, 'type', 'unknown')
            tool_id = getattr(tool_call, 'id', 'unknown')
            
            # Extract function and arguments
            if hasattr(tool_call, 'function'):
                function_name = tool_call.function.name
                arguments = tool_call.function.arguments
            else:
                function_name = 'unknown'
                arguments = {}
            
            # Store tool call info
            tool_info = {
                "type": tool_type,
                "id": tool_id,
                "function": function_name,
                "arguments": arguments,
                "timestamp": datetime.now().isoformat()
            }
            self.tool_calls.append(tool_info)
            
            # Log tool call
            if tool_type == "azure_ai_search":
                query = arguments.get("query", "N/A") if isinstance(arguments, dict) else "N/A"
                logger.info(f"Search tool called with query: {query}")
            else:
                logger.info(f"Tool called: {tool_type} - {function_name}")
            
            # Call callback if provided
            if self.on_tool:
                self.on_tool(tool_info)
        
        except Exception as e:
            logger.error(f"Error handling tool call: {e}")
            if self.on_error:
                self.on_error(e)
    
    def handle_error(self, error: Exception) -> None:
        """
        Handle error events.
        
        Errors can occur during:
        - Agent execution
        - Tool calls
        - Response generation
        - Network communication
        
        Args:
            error: Exception object
        """
        logger.error(f"Agent error: {error}")
        
        # Format error message for user
        error_msg = self._format_error_message(error)
        logger.error(error_msg)
        
        # Call callback if provided
        if self.on_error:
            self.on_error(error)
    
    def _format_error_message(self, error: Exception) -> str:
        """
        Format error message for display.
        
        Provides user-friendly error messages with actionable guidance.
        
        Args:
            error: Exception object
        
        Returns:
            Formatted error message string
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        # Common error patterns and user-friendly messages
        if "authentication" in error_msg.lower():
            return (
                "Authentication error: Unable to authenticate with Azure services. "
                "Please check your credentials and permissions."
            )
        elif "not found" in error_msg.lower():
            return (
                "Resource not found: The requested resource does not exist. "
                "Please verify the configuration and resource names."
            )
        elif "timeout" in error_msg.lower():
            return (
                "Timeout error: The operation took too long to complete. "
                "Please try again or contact support if the issue persists."
            )
        elif "rate limit" in error_msg.lower():
            return (
                "Rate limit exceeded: Too many requests in a short time. "
                "Please wait a moment and try again."
            )
        else:
            return f"{error_type}: {error_msg}"
    
    def get_response(self) -> str:
        """
        Get the full accumulated response.
        
        Returns:
            Complete response text
        """
        return self.full_response
    
    def get_tool_calls(self) -> List[Dict[str, Any]]:
        """
        Get all tool calls that occurred during execution.
        
        Returns:
            List of tool call information dictionaries
        """
        return self.tool_calls
    
    def get_status(self) -> str:
        """
        Get the current run status.
        
        Returns:
            Run status string
        """
        return self.run_status
    
    def reset(self) -> None:
        """
        Reset handler state for reuse.
        
        Clears accumulated response, tool calls, and status.
        Useful when reusing the same handler for multiple runs.
        """
        self.full_response = ""
        self.tool_calls = []
        self.run_status = "unknown"
        self.start_time = datetime.now()
        logger.debug("Event handler state reset")


def create_simple_handler(
    verbose: bool = False
) -> AgentEventHandler:
    """
    Create a simple event handler with console output.
    
    This is a convenience function for quick testing and demos.
    The handler prints text to console and logs tool calls.
    
    Args:
        verbose: If True, enable verbose logging
    
    Returns:
        AgentEventHandler configured for console output
    
    Example:
        >>> handler = create_simple_handler()
        >>> # Use with agent streaming
    """
    def print_text(text: str) -> None:
        """Print text chunk to console."""
        print(text, end="", flush=True)
    
    def log_tool(tool_info: Dict[str, Any]) -> None:
        """Log tool call information."""
        print(f"\n[Tool: {tool_info['type']}]", flush=True)
    
    def on_complete(response: str) -> None:
        """Print completion message."""
        print("\n\n[Response complete]", flush=True)
    
    def on_error(error: Exception) -> None:
        """Print error message."""
        print(f"\n\n[Error: {error}]", flush=True)
    
    return AgentEventHandler(
        on_text=print_text,
        on_tool=log_tool,
        on_complete=on_complete,
        on_error=on_error,
        verbose=verbose
    )


# Example usage and testing
if __name__ == "__main__":
    """
    Test event handler with simulated events.
    """
    import sys
    import time
    
    # Configure logging for the test
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    
    print("\n" + "="*60)
    print("Event Handler Test")
    print("="*60 + "\n")
    
    # Create handler
    handler = create_simple_handler(verbose=True)
    
    # Simulate streaming response
    print("Simulating streaming response...\n")
    response_chunks = [
        "A stop sign ",
        "is an octagonal ",
        "red sign ",
        "with white letters ",
        "that means you must ",
        "come to a complete stop."
    ]
    
    for chunk in response_chunks:
        handler.handle_message_delta(type('Delta', (), {'text': chunk}))
        time.sleep(0.1)
    
    # Simulate tool call
    print("\n\nSimulating tool call...")
    tool_call = type('ToolCall', (), {
        'type': 'azure_ai_search',
        'id': 'call_123',
        'function': type('Function', (), {
            'name': 'search',
            'arguments': {'query': 'stop sign'}
        })
    })
    handler.handle_tool_call(tool_call)
    
    # Complete
    handler.handle_thread_run(type('Run', (), {'status': 'completed'}))
    
    print("\n" + "="*60)
    print(f"Final response length: {len(handler.get_response())} characters")
    print(f"Tool calls: {len(handler.get_tool_calls())}")
    print(f"Status: {handler.get_status()}")
    print("="*60 + "\n")
    
    print("✓ Event handler test completed!")
    sys.exit(0)
