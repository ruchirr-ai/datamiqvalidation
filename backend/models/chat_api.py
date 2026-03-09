"""
Chat API request/response models for ChatAgent feature.

This module defines Pydantic models for API requests and responses including:
- ChatMessageRequest: Request model for sending messages
- ChatMessageResponse: Response model for chat messages
- SuggestedQuestion: Model for suggested questions
- SuggestedQuestionsResponse: Response model for suggested questions
- ConversationSearchRequest: Request model for searching conversations
- ConversationSearchResult: Individual search result
- ConversationSearchResponse: Response model for search results
- PaginationMetadata: Pagination information
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from .message import Message


class ChatMessageRequest(BaseModel):
    """
    Request model for sending a chat message.
    
    Attributes:
        message: User's message text
        conversation_id: Optional existing conversation ID
        page_context: Current page context (dashboard, assessments, etc.)
        attachment_ids: Optional list of attachment IDs to include
    """
    
    message: str = Field(..., min_length=1, description="User's message text")
    conversation_id: Optional[int] = Field(None, description="Existing conversation ID (creates new if not provided)")
    page_context: str = Field(default="dashboard", description="Current page context")
    attachment_ids: Optional[List[int]] = Field(default_factory=list, description="List of attachment IDs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "How do I create a new assessment?",
                "conversation_id": 123,
                "page_context": "assessments",
                "attachment_ids": [456, 789]
            }
        }


class ChatMessageResponse(BaseModel):
    """
    Response model for chat messages.
    
    Attributes:
        response: AI-generated response text
        conversation_id: Conversation ID (new or existing)
        message_id: ID of the assistant's response message
        timestamp: Response timestamp
    """
    
    response: str = Field(..., description="AI-generated response text")
    conversation_id: int = Field(..., description="Conversation ID")
    message_id: int = Field(..., description="Message ID of the response")
    timestamp: datetime = Field(..., description="Response timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "response": "To create a new assessment, navigate to the Assessments page...",
                "conversation_id": 123,
                "message_id": 1002,
                "timestamp": "2026-03-02T10:30:05Z"
            }
        }


class SuggestedQuestion(BaseModel):
    """
    Model for a suggested question.
    
    Attributes:
        question_text: The suggested question text
        category: Question category (getting_started, troubleshooting, etc.)
        priority: Priority level (1 = highest)
    """
    
    question_text: str = Field(..., description="Suggested question text")
    category: str = Field(..., description="Question category")
    priority: int = Field(..., ge=1, description="Priority level (1 = highest)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question_text": "How do I troubleshoot my failed assessment?",
                "category": "troubleshooting",
                "priority": 1
            }
        }


class SuggestedQuestionsResponse(BaseModel):
    """
    Response model for suggested questions.
    
    Attributes:
        questions: List of suggested questions (exactly 4)
    """
    
    questions: List[SuggestedQuestion] = Field(..., min_length=4, max_length=4, description="List of 4 suggested questions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "questions": [
                    {
                        "question_text": "How do I troubleshoot my failed assessment?",
                        "category": "troubleshooting",
                        "priority": 1
                    },
                    {
                        "question_text": "How do I create a new assessment?",
                        "category": "getting_started",
                        "priority": 2
                    },
                    {
                        "question_text": "What does schema analysis check?",
                        "category": "features",
                        "priority": 3
                    },
                    {
                        "question_text": "How do I export assessment results?",
                        "category": "features",
                        "priority": 4
                    }
                ]
            }
        }


class ConversationSearchRequest(BaseModel):
    """
    Request model for searching conversation history.
    
    Attributes:
        query: Search query text
        page: Page number (1-indexed)
        page_size: Number of results per page
    """
    
    query: str = Field(..., min_length=1, description="Search query text")
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=50, ge=1, le=100, description="Results per page (max 100)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "schema compatibility",
                "page": 1,
                "page_size": 50
            }
        }


class ConversationSearchResult(BaseModel):
    """
    Individual search result with context.
    
    Attributes:
        message: The matching message
        previous_message: Previous message for context
        next_message: Next message for context
        relevance_score: Search relevance score (0-1)
    """
    
    message: Message = Field(..., description="The matching message")
    previous_message: Optional[Message] = Field(None, description="Previous message for context")
    next_message: Optional[Message] = Field(None, description="Next message for context")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score (0-1)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": {
                    "id": 1005,
                    "conversation_id": 123,
                    "role": "assistant",
                    "content": "Schema compatibility checks ensure...",
                    "page_context": "assessments",
                    "metadata": {},
                    "created_at": "2026-03-02T10:35:00Z"
                },
                "previous_message": {
                    "id": 1004,
                    "conversation_id": 123,
                    "role": "user",
                    "content": "What is schema compatibility?",
                    "page_context": "assessments",
                    "metadata": {},
                    "created_at": "2026-03-02T10:34:55Z"
                },
                "next_message": None,
                "relevance_score": 0.95
            }
        }


class PaginationMetadata(BaseModel):
    """
    Pagination metadata for list responses.
    
    Attributes:
        total_count: Total number of items
        page: Current page number
        page_size: Items per page
        has_next_page: Whether there are more pages
    """
    
    total_count: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    has_next_page: bool = Field(..., description="Whether there are more pages")


class ConversationSearchResponse(BaseModel):
    """
    Response model for conversation search.
    
    Attributes:
        results: List of search results
        total_count: Total number of matching results
        page: Current page number
        page_size: Results per page
        has_next_page: Whether there are more pages
    """
    
    results: List[ConversationSearchResult] = Field(..., description="List of search results")
    total_count: int = Field(..., ge=0, description="Total matching results")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Results per page")
    has_next_page: bool = Field(..., description="Whether there are more pages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "results": [
                    {
                        "message": {
                            "id": 1005,
                            "conversation_id": 123,
                            "role": "assistant",
                            "content": "Schema compatibility checks...",
                            "created_at": "2026-03-02T10:35:00Z"
                        },
                        "previous_message": None,
                        "next_message": None,
                        "relevance_score": 0.95
                    }
                ],
                "total_count": 3,
                "page": 1,
                "page_size": 50,
                "has_next_page": False
            }
        }
