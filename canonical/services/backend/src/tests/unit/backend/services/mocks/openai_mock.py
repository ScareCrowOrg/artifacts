"""
OpenAI API Mock Utilities

Provides mock implementations for testing OpenAI API integrations
without making actual HTTP calls.

Usage:
    >>> from tests.unit.backend.services.mocks import MockHttpxAsyncClient
    >>> mock_client = MockHttpxAsyncClient()
    >>> mock_client.setup_post_response(
    ...     url="/assistants",
    ...     response_data={"id": "asst_123"},
    ...     status_code=200
    ... )
"""

from typing import Dict, Any, Optional, List
from unittest.mock import AsyncMock, MagicMock


class MockHttpxResponse:
    """
    Mock httpx.Response object for testing.
    
    Args:
        status_code: HTTP status code
        json_data: JSON response data
        text: Text response data (optional)
    """
    
    def __init__(
        self,
        status_code: int = 200,
        json_data: Optional[Dict[str, Any]] = None,
        text: Optional[str] = None
    ):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text or ""
        self.headers = {}
    
    def json(self) -> Dict[str, Any]:
        """Return JSON data."""
        return self._json_data
    
    def raise_for_status(self):
        """Simulate HTTP status validation."""
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=MagicMock(),
                response=self
            )


class MockHttpxAsyncClient:
    """
    Mock httpx.AsyncClient for testing async HTTP operations.
    
    This mock allows setting up predefined responses for different
    HTTP methods and URLs, making it ideal for testing API integrations.
    
    Example:
        >>> mock_client = MockHttpxAsyncClient()
        >>> mock_client.setup_post_response(
        ...     url="/threads",
        ...     response_data={"id": "thread_123"}
        ... )
        >>> response = await mock_client.post("/threads", json={})
        >>> assert response.json()["id"] == "thread_123"
    """
    
    def __init__(self):
        self.post_responses = {}
        self.get_responses = {}
        self.delete_responses = {}
        self.call_count = {}
        self.last_request = None
    
    def setup_post_response(
        self,
        url: str,
        response_data: Dict[str, Any],
        status_code: int = 200
    ):
        """Configure response for POST request."""
        self.post_responses[url] = MockHttpxResponse(
            status_code=status_code,
            json_data=response_data
        )
    
    def setup_get_response(
        self,
        url: str,
        response_data: Dict[str, Any],
        status_code: int = 200
    ):
        """Configure response for GET request."""
        self.get_responses[url] = MockHttpxResponse(
            status_code=status_code,
            json_data=response_data
        )
    
    def setup_delete_response(
        self,
        url: str,
        response_data: Dict[str, Any],
        status_code: int = 200
    ):
        """Configure response for DELETE request."""
        self.delete_responses[url] = MockHttpxResponse(
            status_code=status_code,
            json_data=response_data
        )
    
    async def post(
        self,
        url: str,
        **kwargs
    ) -> MockHttpxResponse:
        """Simulate POST request."""
        self.last_request = {'method': 'POST', 'url': url, 'kwargs': kwargs}
        self.call_count['POST'] = self.call_count.get('POST', 0) + 1
        
        # Match by URL pattern (extract path from full URL)
        for pattern, response in self.post_responses.items():
            if pattern in url:
                return response
        
        # Default success response
        return MockHttpxResponse(status_code=200, json_data={})
    
    async def get(
        self,
        url: str,
        **kwargs
    ) -> MockHttpxResponse:
        """Simulate GET request."""
        self.last_request = {'method': 'GET', 'url': url, 'kwargs': kwargs}
        self.call_count['GET'] = self.call_count.get('GET', 0) + 1
        
        # Match by URL pattern
        for pattern, response in self.get_responses.items():
            if pattern in url:
                return response
        
        # Default success response
        return MockHttpxResponse(status_code=200, json_data={})
    
    async def delete(
        self,
        url: str,
        **kwargs
    ) -> MockHttpxResponse:
        """Simulate DELETE request."""
        self.last_request = {'method': 'DELETE', 'url': url, 'kwargs': kwargs}
        self.call_count['DELETE'] = self.call_count.get('DELETE', 0) + 1
        
        # Match by URL pattern
        for pattern, response in self.delete_responses.items():
            if pattern in url:
                return response
        
        # Default success response
        return MockHttpxResponse(status_code=200, json_data={})
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, *args):
        """Async context manager exit."""
        pass


# Factory functions for creating mock responses

def create_mock_assistant_response(
    assistant_id: str = "asst_123",
    name: str = "Test Assistant",
    model: str = "gpt-4o-mini"
) -> Dict[str, Any]:
    """
    Create a mock assistant creation response.
    
    Args:
        assistant_id: Assistant ID
        name: Assistant name
        model: Model name
    
    Returns:
        Mock assistant response dict
    """
    return {
        "id": assistant_id,
        "object": "assistant",
        "created_at": 1699009709,
        "name": name,
        "model": model,
        "instructions": "You are a helpful assistant",
        "tools": [],
        "metadata": {}
    }


def create_mock_thread_response(
    thread_id: str = "thread_123"
) -> Dict[str, Any]:
    """
    Create a mock thread creation response.
    
    Args:
        thread_id: Thread ID
    
    Returns:
        Mock thread response dict
    """
    return {
        "id": thread_id,
        "object": "thread",
        "created_at": 1699009709,
        "metadata": {}
    }


def create_mock_message_response(
    message_id: str = "msg_123",
    thread_id: str = "thread_123",
    role: str = "user",
    content: str = "Hello"
) -> Dict[str, Any]:
    """
    Create a mock message response.
    
    Args:
        message_id: Message ID
        thread_id: Thread ID
        role: Message role
        content: Message content
    
    Returns:
        Mock message response dict
    """
    return {
        "id": message_id,
        "object": "thread.message",
        "created_at": 1699009709,
        "thread_id": thread_id,
        "role": role,
        "content": [
            {
                "type": "text",
                "text": {
                    "value": content,
                    "annotations": []
                }
            }
        ],
        "attachments": [],
        "metadata": {}
    }


def create_mock_run_response(
    run_id: str = "run_123",
    thread_id: str = "thread_123",
    assistant_id: str = "asst_123",
    status: str = "completed"
) -> Dict[str, Any]:
    """
    Create a mock run response.
    
    Args:
        run_id: Run ID
        thread_id: Thread ID
        assistant_id: Assistant ID
        status: Run status
    
    Returns:
        Mock run response dict
    """
    return {
        "id": run_id,
        "object": "thread.run",
        "created_at": 1699009709,
        "thread_id": thread_id,
        "assistant_id": assistant_id,
        "status": status,
        "required_action": None,
        "last_error": None,
        "model": "gpt-4o-mini",
        "instructions": "You are a helpful assistant",
        "tools": [],
        "metadata": {}
    }


def create_mock_file_response(
    file_id: str = "file-123",
    filename: str = "test.txt",
    purpose: str = "assistants"
) -> Dict[str, Any]:
    """
    Create a mock file upload response.
    
    Args:
        file_id: File ID
        filename: File name
        purpose: Upload purpose
    
    Returns:
        Mock file response dict
    """
    return {
        "id": file_id,
        "object": "file",
        "bytes": 1024,
        "created_at": 1699009709,
        "filename": filename,
        "purpose": purpose
    }


def create_mock_file_list_response(
    files: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Create a mock file list response.
    
    Args:
        files: List of file objects
    
    Returns:
        Mock file list response dict
    """
    if files is None:
        files = [
            create_mock_file_response("file-1", "file1.txt"),
            create_mock_file_response("file-2", "file2.txt")
        ]
    
    return {
        "object": "list",
        "data": files
    }


def create_mock_delete_response(
    file_id: str = "file-123",
    deleted: bool = True
) -> Dict[str, Any]:
    """
    Create a mock file deletion response.
    
    Args:
        file_id: File ID
        deleted: Whether deletion was successful
    
    Returns:
        Mock delete response dict
    """
    return {
        "id": file_id,
        "object": "file",
        "deleted": deleted
    }
