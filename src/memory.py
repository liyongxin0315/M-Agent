"""
Memory System for AgentM.

This module provides a structured memory system for storing and retrieving
user context, facts, and conversation history across sessions. The system
supports confidence scoring, automatic pruning, and debounced persistence.

Design Philosophy:
- Structured storage: JSON-based with Pydantic validation
- Confidence scoring: Facts have reliability scores (0.0-1.0)
- Debounced writes: Batch updates to reduce I/O
- Automatic pruning: Limit storage size with intelligent eviction

Architecture:
    MemoryManager
    ├── MemoryData (root structure)
    │   ├── UserContext (user-specific data)
    │   │   ├── work_context
    │   │   ├── personal_context
    │   │   └── top_of_mind
    │   └── facts (list of MemoryFact)
    └── Storage (JSON file persistence)

Data Model:
    MemoryFact:
        - id: Unique identifier
        - content: Fact text
        - category: Classification (work/personal/preference/etc)
        - confidence: Reliability score (0.0-1.0)
        - created_at: Creation timestamp
        - source: Origin thread/conversation

Example Usage:
    >>> manager = MemoryManager("/path/to/memory.json")
    >>> manager.load()
    >>> 
    >>> # Add a fact
    >>> fact = MemoryFact(
    ...     content="User prefers TypeScript over JavaScript",
    ...     category="preference",
    ...     confidence=0.9,
    ... )
    >>> manager.add_fact(fact)
    >>> 
    >>> # Get top facts
    >>> facts = manager.get_top_facts(limit=10, min_confidence=0.7)
    >>> 
    >>> # Flush to disk (or wait for auto-flush)
    >>> manager.flush()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class MemoryError(Exception):
    """Base exception for memory system errors."""
    pass


class MemoryValidationError(MemoryError):
    """Raised when memory data fails validation."""
    pass


@dataclass
class MemoryFact:
    """A single memory fact.
    
    Attributes:
        id: Unique identifier (auto-generated if not provided)
        content: The fact content/text
        category: Classification category
        confidence: Reliability score (0.0-1.0)
        created_at: ISO format timestamp
        updated_at: Last update timestamp (optional)
        source: Source thread/conversation ID
        access_count: Number of times accessed (for usage tracking)
        last_accessed: Last access timestamp
    """
    content: str
    category: str = "context"
    confidence: float = 0.5
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: Optional[str] = None
    source: str = "unknown"
    access_count: int = 0
    last_accessed: Optional[str] = None
    
    def __post_init__(self):
        """Validate fact after initialization."""
        if not self.content or not self.content.strip():
            raise MemoryValidationError("Fact content cannot be empty")
        
        if not 0.0 <= self.confidence <= 1.0:
            raise MemoryValidationError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        
        # Validate category
        valid_categories = {
            "context", "work", "personal", "preference",
            "skill", "project", "contact", "note", "other"
        }
        if self.category not in valid_categories:
            logger.warning(f"Unknown category: {self.category}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryFact:
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            content=data.get("content", ""),
            category=data.get("category", "context"),
            confidence=data.get("confidence", 0.5),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at"),
            source=data.get("source", "unknown"),
            access_count=data.get("access_count", 0),
            last_accessed=data.get("last_accessed"),
        )
    
    def update(self, **kwargs) -> None:
        """Update fact fields.
        
        Args:
            **kwargs: Fields to update (content, category, confidence)
        """
        for key, value in kwargs.items():
            if hasattr(self, key) and key not in {"id", "created_at"}:
                setattr(self, key, value)
        
        self.updated_at = datetime.now().isoformat()
    
    def touch(self) -> None:
        """Record access for usage tracking."""
        self.access_count += 1
        self.last_accessed = datetime.now().isoformat()


@dataclass
class ContextSection:
    """A section of user context.
    
    Attributes:
        summary: Context summary text
        updated_at: Last update timestamp
        version: Schema version for migration
    """
    summary: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.0"
    
    def update(self, summary: str) -> None:
        """Update context summary."""
        self.summary = summary
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary": self.summary,
            "updated_at": self.updated_at,
            "version": self.version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ContextSection:
        """Create from dictionary."""
        return cls(
            summary=data.get("summary", ""),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            version=data.get("version", "1.0"),
        )


@dataclass
class UserContext:
    """User-specific context data.
    
    Attributes:
        work_context: Work-related context
        personal_context: Personal context
        top_of_mind: Current focus/priority items
    """
    work_context: ContextSection = field(default_factory=ContextSection)
    personal_context: ContextSection = field(default_factory=ContextSection)
    top_of_mind: ContextSection = field(default_factory=ContextSection)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "work_context": self.work_context.to_dict(),
            "personal_context": self.personal_context.to_dict(),
            "top_of_mind": self.top_of_mind.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UserContext:
        """Create from dictionary."""
        return cls(
            work_context=ContextSection.from_dict(data.get("work_context", {})),
            personal_context=ContextSection.from_dict(data.get("personal_context", {})),
            top_of_mind=ContextSection.from_dict(data.get("top_of_mind", {})),
        )


@dataclass
class MemoryData:
    """Root memory data structure.
    
    Attributes:
        version: Schema version
        last_updated: Last update timestamp
        user: User context
        facts: List of memory facts
        metadata: Additional metadata
    """
    version: str = "1.0"
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    user: UserContext = field(default_factory=UserContext)
    facts: List[MemoryFact] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "last_updated": self.last_updated,
            "user": self.user.to_dict(),
            "facts": [f.to_dict() for f in self.facts],
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryData:
        """Create from dictionary."""
        return cls(
            version=data.get("version", "1.0"),
            last_updated=data.get("last_updated", datetime.now().isoformat()),
            user=UserContext.from_dict(data.get("user", {})),
            facts=[MemoryFact.from_dict(f) for f in data.get("facts", [])],
            metadata=data.get("metadata", {}),
        )


class MemoryManager:
    """Memory system manager.
    
    The memory manager handles:
    - Loading/saving memory data
    - Adding/updating/deleting facts
    - Confidence-based filtering
    - Debounced persistence
    - Automatic pruning
    
    Attributes:
        storage_path: Path to storage file
        debounce_seconds: Time to wait before flushing
        max_facts: Maximum facts to store
        confidence_threshold: Minimum confidence for retention
    
    Example:
        >>> manager = MemoryManager(
        ...     storage_path="/tmp/memory.json",
        ...     debounce_seconds=60,
        ...     max_facts=100,
        ... )
        >>> manager.load()
        >>> 
        >>> # Add fact (auto-flushes after debounce)
        >>> manager.add_fact(MemoryFact(
        ...     content="User prefers dark mode",
        ...     category="preference",
        ...     confidence=0.8,
        ... ))
        >>> 
        >>> # Get high-confidence facts
        >>> facts = manager.get_top_facts(limit=10, min_confidence=0.7)
    """
    
    def __init__(
        self,
        storage_path: str = "/tmp/agentm/memory.json",
        debounce_seconds: int = 60,
        max_facts: int = 100,
        confidence_threshold: float = 0.5,
    ):
        """Initialize memory manager.
        
        Args:
            storage_path: Path to JSON storage file
            debounce_seconds: Seconds to wait before auto-flush
            max_facts: Maximum facts to retain
            confidence_threshold: Default minimum confidence
        """
        self._storage_path = Path(storage_path)
        self._debounce_seconds = debounce_seconds
        self._max_facts = max_facts
        self._confidence_threshold = confidence_threshold
        
        self._memory: Optional[MemoryData] = None
        self._pending_updates: List[MemoryFact] = []
        self._pending_deletes: Set[str] = set()
        self._debounce_timer: Optional[asyncio.Task] = None
        self._lock = threading.Lock()
        self._flush_lock = asyncio.Lock()
        
        logger.info(f"MemoryManager initialized: {storage_path}")
    
    @property
    def storage_path(self) -> Path:
        """Get storage file path."""
        return self._storage_path
    
    @property
    def memory(self) -> Optional[MemoryData]:
        """Get current memory data."""
        return self._memory
    
    @property
    def fact_count(self) -> int:
        """Get number of stored facts."""
        return len(self._memory.facts) if self._memory else 0
    
    def load(self) -> MemoryData:
        """Load memory from storage.
        
        Returns:
            Loaded memory data
            
        Raises:
            MemoryError: If loading fails
        """
        with self._lock:
            if self._storage_path.exists():
                try:
                    with open(self._storage_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._memory = MemoryData.from_dict(data)
                    logger.info(f"Loaded memory from {self._storage_path}")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in memory file: {e}")
                    self._memory = MemoryData()
                except Exception as e:
                    logger.error(f"Failed to load memory: {e}")
                    self._memory = MemoryData()
            else:
                self._memory = MemoryData()
                logger.info("Created new memory (file didn't exist)")
            
            return self._memory
    
    def save(self) -> None:
        """Save memory to storage immediately.
        
        Raises:
            MemoryError: If saving fails
        """
        if not self._memory:
            return
        
        with self._lock:
            try:
                # Ensure directory exists
                self._storage_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write atomically (write to temp, then rename)
                temp_path = self._storage_path.with_suffix(".tmp")
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(self._memory.to_dict(), f, indent=2, ensure_ascii=False)
                
                temp_path.rename(self._storage_path)
                logger.debug(f"Saved memory to {self._storage_path}")
                
            except Exception as e:
                logger.error(f"Failed to save memory: {e}")
                raise MemoryError(f"Failed to save memory: {e}") from e
    
    def add_fact(self, fact: MemoryFact) -> None:
        """Add a memory fact.
        
        Schedules the fact for insertion and triggers debounced flush.
        
        Args:
            fact: Fact to add
            
        Raises:
            MemoryValidationError: If fact is invalid
        """
        if not self._memory:
            self.load()
        
        # Validate fact
        if not fact.content or not fact.content.strip():
            raise MemoryValidationError("Fact content cannot be empty")
        
        if not 0.0 <= fact.confidence <= 1.0:
            raise MemoryValidationError("Confidence must be between 0.0 and 1.0")
        
        with self._lock:
            # Remove from pending deletes if present
            self._pending_deletes.discard(fact.id)
            
            # Check for existing fact with same ID
            existing = self.get_fact_by_id(fact.id)
            if existing:
                # Update existing
                existing.update(
                    content=fact.content,
                    category=fact.category,
                    confidence=fact.confidence,
                )
            else:
                # Add new fact
                self._memory.facts.append(fact)
            
            # Add to pending updates
            self._pending_updates.append(fact)
            
            # Schedule flush
            self._schedule_flush()
            
            logger.debug(f"Added fact: {fact.id}")
    
    def update_fact(
        self,
        fact_id: str,
        content: Optional[str] = None,
        category: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> Optional[MemoryFact]:
        """Update an existing fact.
        
        Args:
            fact_id: ID of fact to update
            content: New content (optional)
            category: New category (optional)
            confidence: New confidence (optional)
            
        Returns:
            Updated fact, or None if not found
        """
        if not self._memory:
            self.load()
        
        fact = self.get_fact_by_id(fact_id)
        if not fact:
            return None
        
        update_kwargs = {}
        if content is not None:
            update_kwargs["content"] = content
        if category is not None:
            update_kwargs["category"] = category
        if confidence is not None:
            update_kwargs["confidence"] = confidence
        
        fact.update(**update_kwargs)
        self._pending_updates.append(fact)
        self._schedule_flush()
        
        return fact
    
    def delete_fact(self, fact_id: str) -> bool:
        """Delete a fact by ID.
        
        Args:
            fact_id: ID of fact to delete
            
        Returns:
            True if deleted, False if not found
        """
        if not self._memory:
            self.load()
        
        # Find and remove
        for i, fact in enumerate(self._memory.facts):
            if fact.id == fact_id:
                self._memory.facts.pop(i)
                self._pending_deletes.add(fact_id)
                self._schedule_flush()
                logger.debug(f"Deleted fact: {fact_id}")
                return True
        
        return False
    
    def get_fact_by_id(self, fact_id: str) -> Optional[MemoryFact]:
        """Get fact by ID.
        
        Args:
            fact_id: Fact ID
            
        Returns:
            Fact if found, None otherwise
        """
        if not self._memory:
            self.load()
        
        for fact in self._memory.facts:
            if fact.id == fact_id:
                fact.touch()
                return fact
        
        return None
    
    def get_top_facts(
        self,
        limit: int = 10,
        min_confidence: Optional[float] = None,
        category: Optional[str] = None,
    ) -> List[MemoryFact]:
        """Get top facts by confidence.
        
        Args:
            limit: Maximum facts to return
            min_confidence: Minimum confidence threshold
            category: Filter by category
            
        Returns:
            List of facts sorted by confidence (descending)
        """
        if not self._memory:
            self.load()
        
        threshold = min_confidence or self._confidence_threshold
        
        # Filter facts
        filtered = [
            f for f in self._memory.facts
            if f.confidence >= threshold
            and (category is None or f.category == category)
        ]
        
        # Sort by confidence (descending), then by recency
        sorted_facts = sorted(
            filtered,
            key=lambda f: (f.confidence, f.created_at),
            reverse=True,
        )
        
        # Touch accessed facts
        for fact in sorted_facts[:limit]:
            fact.touch()
        
        return sorted_facts[:limit]
    
    def get_facts_by_category(self, category: str) -> List[MemoryFact]:
        """Get all facts in a category.
        
        Args:
            category: Category name
            
        Returns:
            List of facts in category
        """
        if not self._memory:
            self.load()
        
        return [f for f in self._memory.facts if f.category == category]
    
    def search_facts(self, query: str, limit: int = 10) -> List[MemoryFact]:
        """Search facts by content.
        
        Simple substring search. For production, use vector search.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            Matching facts
        """
        if not self._memory:
            self.load()
        
        query_lower = query.lower()
        matches = [
            f for f in self._memory.facts
            if query_lower in f.content.lower()
        ]
        
        # Sort by confidence
        matches.sort(key=lambda f: f.confidence, reverse=True)
        
        return matches[:limit]
    
    def flush(self) -> None:
        """Flush pending updates to storage.
        
        Applies all pending updates and deletes, then saves.
        """
        if not self._memory:
            return
        
        async def _flush_async():
            async with self._flush_lock:
                if not self._pending_updates and not self._pending_deletes:
                    return
                
                # Apply pending deletes
                if self._pending_deletes:
                    self._memory.facts = [
                        f for f in self._memory.facts
                        if f.id not in self._pending_deletes
                    ]
                    self._pending_deletes.clear()
                
                # Enforce max facts limit
                if len(self._memory.facts) > self._max_facts:
                    # Sort by confidence and keep top
                    self._memory.facts.sort(
                        key=lambda f: f.confidence,
                        reverse=True,
                    )
                    removed = self._memory.facts[self._max_facts:]
                    self._memory.facts = self._memory.facts[:self._max_facts]
                    logger.info(f"Pruned {len(removed)} facts (exceeded max)")
                
                # Update timestamp
                self._memory.last_updated = datetime.now().isoformat()
                
                # Save
                self.save()
                
                # Clear pending
                self._pending_updates.clear()
                
                if self._debounce_timer:
                    self._debounce_timer.cancel()
                    self._debounce_timer = None
        
        # Run in event loop if available
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_flush_async())
            else:
                loop.run_until_complete(_flush_async())
        except RuntimeError:
            # No event loop, create one
            asyncio.run(_flush_async())
    
    def _schedule_flush(self) -> None:
        """Schedule a debounced flush."""
        if self._debounce_timer:
            self._debounce_timer.cancel()
        
        async def _delayed_flush():
            await asyncio.sleep(self._debounce_seconds)
            self.flush()
        
        try:
            loop = asyncio.get_event_loop()
            self._debounce_timer = loop.create_task(_delayed_flush())
        except RuntimeError:
            pass  # No event loop, will flush on next save
    
    def clear(self) -> None:
        """Clear all memory data."""
        self._memory = MemoryData()
        self._pending_updates.clear()
        self._pending_deletes.clear()
        
        if self._storage_path.exists():
            self._storage_path.unlink()
        
        logger.info("Cleared all memory data")
    
    def export_data(self) -> Dict[str, Any]:
        """Export memory data as dictionary.
        
        Returns:
            Memory data dictionary
        """
        if not self._memory:
            self.load()
        
        return self._memory.to_dict()
    
    def import_data(self, data: Dict[str, Any]) -> None:
        """Import memory data from dictionary.
        
        Args:
            data: Memory data dictionary
        """
        self._memory = MemoryData.from_dict(data)
        self._pending_updates.clear()
        self._pending_deletes.clear()
        self.save()
        logger.info("Imported memory data")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics.
        
        Returns:
            Statistics dictionary
        """
        if not self._memory:
            self.load()
        
        facts = self._memory.facts
        
        # Category distribution
        categories: Dict[str, int] = {}
        for fact in facts:
            categories[fact.category] = categories.get(fact.category, 0) + 1
        
        # Confidence distribution
        high_confidence = sum(1 for f in facts if f.confidence >= 0.8)
        medium_confidence = sum(1 for f in facts if 0.5 <= f.confidence < 0.8)
        low_confidence = sum(1 for f in facts if f.confidence < 0.5)
        
        return {
            "total_facts": len(facts),
            "max_facts": self._max_facts,
            "pending_updates": len(self._pending_updates),
            "categories": categories,
            "confidence_distribution": {
                "high": high_confidence,
                "medium": medium_confidence,
                "low": low_confidence,
            },
            "storage_path": str(self._storage_path),
            "last_updated": self._memory.last_updated,
        }


__all__ = [
    "MemoryManager",
    "MemoryData",
    "MemoryFact",
    "UserContext",
    "ContextSection",
    "MemoryError",
    "MemoryValidationError",
]
