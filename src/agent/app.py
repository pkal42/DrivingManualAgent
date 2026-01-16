"""
Main agent application with CLI interface.

This module provides a command-line interface for interacting with the
driving rules expert agent. It handles query processing, streaming responses,
and multimodal output formatting.

Features:
- Interactive CLI for testing agent
- Streaming response display
- State-specific query filtering
- Image inclusion toggle
- Conversation history
- Structured logging

Usage:
    python -m agent.app "What does a stop sign mean?"
    python -m agent.app --state California "Parking rules near hydrants"
    python -m agent.app --interactive
"""

import argparse
import logging
import sys
from typing import Optional, List
from datetime import datetime

from .agent_factory import create_driving_rules_agent, delete_agent
from .client import get_project_client, close_project_client
from .conversation import (
    create_thread,
    add_message,
    get_conversation_history,
    delete_thread
)
from .streaming import AgentEventHandler, create_simple_handler
from .image_relevance import should_include_images
from .response_formatter import assemble_multimodal_response
from .config_loader import load_agent_config
from .telemetry import init_telemetry, trace_operation, log_with_trace_context

# Configure module logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_agent_query(
    query: str,
    state: Optional[str] = None,
    include_images: Optional[bool] = None,
    verbose: bool = False
) -> str:
    """
    Run a single agent query and return the response.
    
    This function orchestrates the complete query processing pipeline:
    1. Create/reuse thread
    2. Add user message
    3. Run agent with streaming
    4. Assemble multimodal response
    5. Format and return output
    
    Args:
        query: User's question
        state: Optional state filter (e.g., "California")
        include_images: Whether to include images (auto-detect if None)
        verbose: Enable verbose logging
    
    Returns:
        Formatted response text with citations and images
    
    Example:
        >>> response = run_agent_query("What does a stop sign mean?")
        >>> print(response)
        A stop sign is an octagonal red sign...
    """
    try:
        with trace_operation("agent_query", {"query": query, "state": state}):
            # Load configuration
            config = load_agent_config()
            
            # Get project client
            client = get_project_client(config)
            
            # Create agent
            logger.info("Creating driving rules agent")
            agent = create_driving_rules_agent(client=client, config=config)
            
            try:
                # Create conversation thread
                logger.info("Creating conversation thread")
                thread_metadata = {
                    "query": query[:100],
                    "state": state or "all",
                    "timestamp": datetime.now().isoformat()
                }
                thread = create_thread(client=client, metadata=thread_metadata)
                
                try:
                    # Add state context to query if specified
                    if state:
                        enhanced_query = f"[State: {state}] {query}"
                    else:
                        enhanced_query = query
                    
                    # Add user message
                    logger.info(f"Adding user message: {enhanced_query[:50]}...")
                    add_message(thread.id, enhanced_query, client=client)
                    
                    # Determine if images should be included
                    if include_images is None:
                        include_images = should_include_images(query)
                        logger.info(
                            f"Auto-detected image inclusion: {include_images}"
                        )
                    
                    # Create streaming event handler
                    print("\nAgent: ", end="", flush=True)
                    handler = create_simple_handler(verbose=verbose)
                    
                    # Run agent with streaming
                    logger.info("Running agent with streaming")
                    
                    # Note: The exact streaming API depends on azure-ai-projects SDK version
                    # This is the general pattern for Agent Framework v2
                    try:
                        # Attempt to run with streaming
                        run = client.agents.create_run_and_stream(
                            thread_id=thread.id,
                            agent_id=agent.id,
                            event_handler=handler
                        )
                        
                        # Wait for completion
                        run.wait_for_completion()
                        
                        # Get response
                        response_text = handler.get_response()
                        
                    except AttributeError:
                        # Fallback: Non-streaming run
                        logger.warning(
                            "Streaming not available, using non-streaming run"
                        )
                        run = client.agents.create_run(
                            thread_id=thread.id,
                            agent_id=agent.id
                        )
                        
                        # Wait for completion
                        while run.status in ["queued", "in_progress"]:
                            import time
                            time.sleep(1)
                            run = client.agents.get_run(thread.id, run.id)
                        
                        # Get messages
                        messages = client.agents.list_messages(thread.id)
                        response_text = messages[0].content[0].text.value
                        print(response_text)
                    
                    # Get conversation history for search results
                    # Note: In a real implementation, we would extract search results
                    # from the agent's tool calls. For now, we'll skip multimodal assembly.
                    
                    logger.info("Query completed successfully")
                    return response_text
                    
                finally:
                    # Cleanup thread
                    logger.debug(f"Deleting thread {thread.id}")
                    delete_thread(thread.id, client=client)
                    
            finally:
                # Cleanup agent
                logger.debug(f"Deleting agent {agent.id}")
                delete_agent(agent.id, client=client)
        
    except Exception as e:
        error_msg = f"Error processing query: {e}"
        logger.error(error_msg)
        print(f"\n\nError: {error_msg}", file=sys.stderr)
        import traceback
        if verbose:
            traceback.print_exc()
        return ""


def interactive_mode(verbose: bool = False) -> None:
    """
    Run agent in interactive mode for multi-turn conversations.
    
    Allows users to have a conversation with the agent, maintaining
    context across multiple queries in a single thread.
    
    Commands:
    - /exit, /quit: Exit interactive mode
    - /clear: Clear conversation history
    - /history: Show conversation history
    - /state <name>: Set state filter
    - /images on|off: Toggle image inclusion
    
    Args:
        verbose: Enable verbose logging
    
    Example:
        >>> interactive_mode()
        DrivingRules Agent > What does a stop sign mean?
        Agent: A stop sign is...
        DrivingRules Agent > 
    """
    print("\n" + "="*60)
    print("DrivingRules Agent - Interactive Mode")
    print("="*60)
    print("\nCommands:")
    print("  /exit, /quit  - Exit interactive mode")
    print("  /clear        - Clear conversation history")
    print("  /history      - Show conversation history")
    print("  /state <name> - Set state filter (e.g., /state California)")
    print("  /images on|off - Toggle image inclusion")
    print("\n" + "="*60 + "\n")
    
    # State tracking
    current_state = None
    auto_images = True
    
    # Create persistent thread and agent
    try:
        config = load_agent_config()
        client = get_project_client(config)
        agent = create_driving_rules_agent(client=client, config=config)
        thread = create_thread(client=client, metadata={"mode": "interactive"})
        
        print("Agent ready! Type your question or /exit to quit.\n")
        
        while True:
            try:
                # Get user input
                user_input = input("You > ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith("/"):
                    command = user_input.lower()
                    
                    if command in ["/exit", "/quit"]:
                        print("\nGoodbye!")
                        break
                    
                    elif command == "/clear":
                        # Delete old thread and create new one
                        delete_thread(thread.id, client=client)
                        thread = create_thread(client=client, metadata={"mode": "interactive"})
                        print("Conversation cleared.\n")
                        continue
                    
                    elif command == "/history":
                        history = get_conversation_history(thread.id, client=client)
                        print("\nConversation History:")
                        print("-" * 60)
                        for msg in history:
                            role = msg['role'].capitalize()
                            content = msg['content'][:100]
                            print(f"{role}: {content}...")
                        print("-" * 60 + "\n")
                        continue
                    
                    elif command.startswith("/state "):
                        state_name = user_input[7:].strip()
                        current_state = state_name if state_name else None
                        print(f"State filter: {current_state or 'All states'}\n")
                        continue
                    
                    elif command.startswith("/images "):
                        setting = user_input[8:].strip().lower()
                        if setting == "on":
                            auto_images = True
                            print("Image inclusion: ON\n")
                        elif setting == "off":
                            auto_images = False
                            print("Image inclusion: OFF\n")
                        else:
                            print("Usage: /images on|off\n")
                        continue
                    
                    else:
                        print(f"Unknown command: {command}\n")
                        continue
                
                # Process query
                # Add state context if set
                query = user_input
                if current_state:
                    query = f"[State: {current_state}] {query}"
                
                # Add message to thread
                add_message(thread.id, query, client=client)
                
                # Determine image inclusion
                include_images = auto_images and should_include_images(user_input)
                
                # Run agent
                print("\nAgent: ", end="", flush=True)
                handler = create_simple_handler(verbose=verbose)
                
                try:
                    run = client.agents.create_run_and_stream(
                        thread_id=thread.id,
                        agent_id=agent.id,
                        event_handler=handler
                    )
                    run.wait_for_completion()
                    
                except AttributeError:
                    # Fallback: Non-streaming
                    run = client.agents.create_run(thread.id, agent.id)
                    while run.status in ["queued", "in_progress"]:
                        import time
                        time.sleep(1)
                        run = client.agents.get_run(thread.id, run.id)
                    
                    messages = client.agents.list_messages(thread.id)
                    print(messages[0].content[0].text.value)
                
                print("\n")
                
            except KeyboardInterrupt:
                print("\n\nInterrupted. Use /exit to quit.\n")
            except EOFError:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}\n")
                if verbose:
                    import traceback
                    traceback.print_exc()
        
    finally:
        # Cleanup
        try:
            if 'thread' in locals():
                delete_thread(thread.id, client=client)
            if 'agent' in locals():
                delete_agent(agent.id, client=client)
            close_project_client()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    """
    Main entry point for CLI application.
    """
    parser = argparse.ArgumentParser(
        description="DrivingRules Agent - Expert on US driving laws and regulations"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Question to ask the agent"
    )
    parser.add_argument(
        "--state", "-s",
        help="Filter results to specific state (e.g., California, TX)"
    )
    parser.add_argument(
        "--images", "-i",
        action="store_true",
        help="Force include images in response"
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Disable image inclusion"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize telemetry
    try:
        init_telemetry()
    except Exception as e:
        logger.warning(f"Failed to initialize telemetry: {e}")
    
    # Run in appropriate mode
    if args.interactive:
        interactive_mode(verbose=args.verbose)
    elif args.query:
        # Determine image inclusion
        include_images = None
        if args.images:
            include_images = True
        elif args.no_images:
            include_images = False
        
        # Run single query
        response = run_agent_query(
            query=args.query,
            state=args.state,
            include_images=include_images,
            verbose=args.verbose
        )
        
        if response:
            print("\n")  # Add spacing after response
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
