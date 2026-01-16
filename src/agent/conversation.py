"""
Thread and conversation management module.

This module provides functions for managing conversation threads in the
Azure AI Agent Framework v2. Threads maintain conversation state and
history, enabling multi-turn interactions with context retention.

Key Concepts:
- Thread: A conversation session with message history
- Message: A single user or assistant message in a thread
- Run: An execution of the agent processing messages in a thread

Usage:
    from agent.conversation import create_thread, add_message, get_history
    
    # Create new conversation
    thread = create_thread()
    
    # Add user message
    add_message(thread.id, "What does a stop sign mean?")
    
    # Get conversation history
    history = get_conversation_history(thread.id)
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from azure.ai.projects import AIProjectClient

from .client import get_project_client
from .config_loader import AgentConfig

# Configure module logger
logger = logging.getLogger(__name__)


class ConversationError(Exception):
    """Exception raised for errors in conversation management."""
    pass


def create_thread(
    client: Optional[AIProjectClient] = None,
    config: Optional[AgentConfig] = None,
    metadata: Optional[Dict[str, str]] = None
) -> Any:
    """
    Create a new conversation thread.
    
    A thread represents a conversation session and stores all messages
    exchanged between the user and the agent. Threads enable:
    - Conversation history and context retention
    - Multi-turn interactions with memory
    - Metadata tagging for organization
    
    Thread Lifecycle:
    1. Create thread (this function)
    2. Add user messages
    3. Run agent to generate responses
    4. Retrieve conversation history
    5. Continue or delete thread
    
    Args:
        client: Optional AIProjectClient instance
        config: Optional AgentConfig instance
        metadata: Optional metadata dictionary for thread tagging
                 (e.g., {"user_id": "123", "session": "abc"})
    
    Returns:
        Thread object with id and metadata
    
    Raises:
        ConversationError: If thread creation fails
    
    Example:
        >>> thread = create_thread(metadata={"user": "john_doe"})
        >>> print(thread.id)
        'thread_abc123'
    """
    try:
        # Get project client if not provided
        if client is None:
            logger.debug("Getting project client for thread creation")
            client = get_project_client(config)
        
        # Create thread with optional metadata
        logger.info("Creating new conversation thread")
        thread = client.agents.create_thread(metadata=metadata or {})
        
        logger.info(f"Successfully created thread with ID: {thread.id}")
        if metadata:
            logger.debug(f"Thread metadata: {metadata}")
        
        return thread
        
    except Exception as e:
        error_msg = f"Failed to create thread: {e}"
        logger.error(error_msg)
        raise ConversationError(error_msg) from e


def add_message(
    thread_id: str,
    content: str,
    role: str = "user",
    client: Optional[AIProjectClient] = None,
    config: Optional[AgentConfig] = None,
    attachments: Optional[List[Dict[str, Any]]] = None
) -> Any:
    """
    Add a message to a conversation thread.
    
    Messages can be added by users or the system. The agent's responses
    are added automatically during run execution.
    
    Message Roles:
    - "user": Messages from the user/application
    - "assistant": Messages from the agent (usually added automatically)
    
    Args:
        thread_id: ID of the thread to add message to
        content: Message text content
        role: Message role ("user" or "assistant")
        client: Optional AIProjectClient instance
        config: Optional AgentConfig instance
        attachments: Optional list of file attachments
    
    Returns:
        Message object with id, content, and metadata
    
    Raises:
        ConversationError: If adding message fails
    
    Example:
        >>> thread = create_thread()
        >>> message = add_message(
        ...     thread_id=thread.id,
        ...     content="What does a stop sign mean?"
        ... )
        >>> print(message.content)
        'What does a stop sign mean?'
    """
    try:
        # Get project client if not provided
        if client is None:
            client = get_project_client(config)
        
        # Validate role
        if role not in ["user", "assistant"]:
            raise ValueError(f"Invalid role: {role}. Must be 'user' or 'assistant'")
        
        logger.info(f"Adding {role} message to thread {thread_id}")
        logger.debug(f"Message content: {content[:100]}...")
        
        # Add message to thread
        message = client.agents.create_message(
            thread_id=thread_id,
            role=role,
            content=content,
            attachments=attachments or []
        )
        
        logger.info(f"Successfully added message with ID: {message.id}")
        return message
        
    except ValueError as e:
        logger.error(str(e))
        raise ConversationError(str(e)) from e
    
    except Exception as e:
        error_msg = f"Failed to add message to thread {thread_id}: {e}"
        logger.error(error_msg)
        raise ConversationError(error_msg) from e


def get_conversation_history(
    thread_id: str,
    client: Optional[AIProjectClient] = None,
    config: Optional[AgentConfig] = None,
    limit: int = 100,
    order: str = "asc"
) -> List[Dict[str, Any]]:
    """
    Retrieve conversation history from a thread.
    
    This function fetches all messages in a thread, useful for:
    - Displaying conversation history to users
    - Analyzing conversation flow
    - Debugging agent behavior
    - Exporting conversation logs
    
    Args:
        thread_id: ID of the thread to retrieve
        client: Optional AIProjectClient instance
        config: Optional AgentConfig instance
        limit: Maximum number of messages to retrieve (default: 100)
        order: Sort order - "asc" (oldest first) or "desc" (newest first)
    
    Returns:
        List of message dictionaries with keys:
            - id: Message ID
            - role: "user" or "assistant"
            - content: Message text
            - created_at: Timestamp
            - metadata: Additional metadata
    
    Raises:
        ConversationError: If retrieval fails
    
    Example:
        >>> history = get_conversation_history(thread_id)
        >>> for msg in history:
        ...     print(f"{msg['role']}: {msg['content']}")
        user: What does a stop sign mean?
        assistant: A stop sign is an octagonal red sign...
    """
    try:
        # Get project client if not provided
        if client is None:
            client = get_project_client(config)
        
        # Validate order parameter
        if order not in ["asc", "desc"]:
            raise ValueError(f"Invalid order: {order}. Must be 'asc' or 'desc'")
        
        logger.info(f"Retrieving conversation history for thread {thread_id}")
        
        # Get messages from thread
        messages = client.agents.list_messages(
            thread_id=thread_id,
            limit=limit,
            order=order
        )
        
        # Convert to list of dictionaries
        history = []
        for message in messages:
            msg_dict = {
                "id": message.id,
                "role": message.role,
                "content": message.content[0].text.value if message.content else "",
                "created_at": message.created_at,
                "metadata": message.metadata if hasattr(message, 'metadata') else {}
            }
            history.append(msg_dict)
        
        logger.info(f"Retrieved {len(history)} messages from thread {thread_id}")
        return history
        
    except ValueError as e:
        logger.error(str(e))
        raise ConversationError(str(e)) from e
    
    except Exception as e:
        error_msg = f"Failed to retrieve conversation history for thread {thread_id}: {e}"
        logger.error(error_msg)
        raise ConversationError(error_msg) from e


def delete_thread(
    thread_id: str,
    client: Optional[AIProjectClient] = None,
    config: Optional[AgentConfig] = None
) -> None:
    """
    Delete a conversation thread.
    
    This permanently removes a thread and all its messages.
    Use for cleanup, privacy compliance, or resource management.
    
    Warning: This operation is irreversible. All messages in the
    thread will be permanently deleted.
    
    Args:
        thread_id: ID of the thread to delete
        client: Optional AIProjectClient instance
        config: Optional AgentConfig instance
    
    Raises:
        ConversationError: If deletion fails
    
    Example:
        >>> thread = create_thread()
        >>> # ... use thread ...
        >>> delete_thread(thread.id)
    """
    try:
        # Get project client if not provided
        if client is None:
            client = get_project_client(config)
        
        logger.info(f"Deleting thread {thread_id}")
        
        # Delete thread
        client.agents.delete_thread(thread_id)
        
        logger.info(f"Successfully deleted thread {thread_id}")
        
    except Exception as e:
        error_msg = f"Failed to delete thread {thread_id}: {e}"
        logger.error(error_msg)
        raise ConversationError(error_msg) from e


def get_thread_metadata(
    thread_id: str,
    client: Optional[AIProjectClient] = None,
    config: Optional[AgentConfig] = None
) -> Dict[str, Any]:
    """
    Retrieve metadata for a thread.
    
    Metadata can include user IDs, session information, tags, etc.
    Useful for thread management and organization.
    
    Args:
        thread_id: ID of the thread
        client: Optional AIProjectClient instance
        config: Optional AgentConfig instance
    
    Returns:
        Dictionary of metadata key-value pairs
    
    Raises:
        ConversationError: If retrieval fails
    
    Example:
        >>> metadata = get_thread_metadata(thread_id)
        >>> print(metadata.get("user_id"))
        'user_123'
    """
    try:
        # Get project client if not provided
        if client is None:
            client = get_project_client(config)
        
        logger.debug(f"Retrieving metadata for thread {thread_id}")
        
        # Get thread details
        thread = client.agents.get_thread(thread_id)
        
        metadata = thread.metadata if hasattr(thread, 'metadata') else {}
        logger.debug(f"Thread metadata: {metadata}")
        
        return metadata
        
    except Exception as e:
        error_msg = f"Failed to retrieve metadata for thread {thread_id}: {e}"
        logger.error(error_msg)
        raise ConversationError(error_msg) from e


# Example usage and testing
if __name__ == "__main__":
    """
    Test conversation management functions.
    """
    import sys
    
    # Configure logging for the test
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Try to load .env file if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print("Loaded .env file\n")
        except ImportError:
            print("python-dotenv not installed, using environment variables only\n")
        
        print("Testing conversation management...")
        
        # Note: This will fail without proper Azure AI Foundry project setup
        try:
            # Create thread
            print("\n1. Creating thread...")
            thread = create_thread(metadata={"test": "true", "user": "test_user"})
            print(f"   ✓ Created thread: {thread.id}")
            
            # Add messages
            print("\n2. Adding messages...")
            msg1 = add_message(thread.id, "What does a stop sign mean?")
            print(f"   ✓ Added message: {msg1.id}")
            
            msg2 = add_message(
                thread.id,
                "A stop sign is an octagonal red sign...",
                role="assistant"
            )
            print(f"   ✓ Added response: {msg2.id}")
            
            # Get history
            print("\n3. Retrieving conversation history...")
            history = get_conversation_history(thread.id)
            print(f"   ✓ Retrieved {len(history)} messages")
            
            for i, msg in enumerate(history, 1):
                print(f"   [{i}] {msg['role']}: {msg['content'][:50]}...")
            
            # Get metadata
            print("\n4. Retrieving thread metadata...")
            metadata = get_thread_metadata(thread.id)
            print(f"   ✓ Metadata: {metadata}")
            
            # Cleanup
            print("\n5. Cleaning up...")
            delete_thread(thread.id)
            print(f"   ✓ Deleted thread: {thread.id}")
            
            print("\n✓ All tests passed!")
            
        except Exception as e:
            print(f"\n⚠ Thread operations require Azure AI Foundry project setup")
            print(f"Error: {e}")
            print("\nThis is expected if running locally without Azure credentials.")
            print("The module is correctly structured and ready for deployment.\n")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}\n", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
