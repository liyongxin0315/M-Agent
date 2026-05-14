"""
Unit tests for memory module.

Tests cover:
- Memory fact management
- Confidence scoring
- Debounced persistence
- Search and filtering
"""

import asyncio
import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from memory import (
    MemoryManager,
    MemoryData,
    MemoryFact,
    UserContext,
    ContextSection,
    MemoryError,
    MemoryValidationError,
)


class TestMemoryFact:
    """Tests for MemoryFact."""
    
    def test_create_fact(self):
        """Test basic fact creation."""
        fact = MemoryFact(
            content="Test fact",
            category="test",
            confidence=0.8,
        )
        
        assert fact.content == "Test fact"
        assert fact.category == "test"
        assert fact.confidence == 0.8
        assert fact.id is not None
    
    def test_fact_validation_empty_content(self):
        """Test validation rejects empty content."""
        with pytest.raises(MemoryValidationError, match="empty"):
            MemoryFact(content="", category="test")
    
    def test_fact_validation_confidence_range(self):
        """Test validation rejects invalid confidence."""
        with pytest.raises(MemoryValidationError, match="between 0.0 and 1.0"):
            MemoryFact(content="Test", confidence=1.5)
        
        with pytest.raises(MemoryValidationError, match="between 0.0 and 1.0"):
            MemoryFact(content="Test", confidence=-0.1)
    
    def test_fact_to_dict(self):
        """Test fact serialization."""
        fact = MemoryFact(
            id="fact-123",
            content="Test",
            category="work",
            confidence=0.9,
            source="thread-abc",
        )
        
        data = fact.to_dict()
        
        assert data["id"] == "fact-123"
        assert data["content"] == "Test"
        assert data["category"] == "work"
        assert data["confidence"] == 0.9
        assert data["source"] == "thread-abc"
    
    def test_fact_from_dict(self):
        """Test fact deserialization."""
        data = {
            "id": "fact-456",
            "content": "From dict",
            "category": "personal",
            "confidence": 0.7,
        }
        
        fact = MemoryFact.from_dict(data)
        
        assert fact.id == "fact-456"
        assert fact.content == "From dict"
        assert fact.category == "personal"
    
    def test_fact_update(self):
        """Test fact update."""
        fact = MemoryFact(
            content="Original",
            confidence=0.5,
        )
        
        fact.update(
            content="Updated",
            confidence=0.9,
        )
        
        assert fact.content == "Updated"
        assert fact.confidence == 0.9
        assert fact.updated_at is not None
    
    def test_fact_touch(self):
        """Test fact access tracking."""
        fact = MemoryFact(content="Test")
        
        assert fact.access_count == 0
        assert fact.last_accessed is None
        
        fact.touch()
        
        assert fact.access_count == 1
        assert fact.last_accessed is not None


class TestMemoryManager:
    """Tests for MemoryManager."""
    
    @pytest.fixture
    def manager(self):
        """Create test memory manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "memory.json"
            manager = MemoryManager(
                storage_path=str(storage_path),
                debounce_seconds=1,  # Short for testing
                max_facts=10,
            )
            yield manager
    
    def test_load_new_memory(self, manager):
        """Test loading non-existent memory creates new."""
        memory = manager.load()
        
        assert memory.version == "1.0"
        assert memory.facts == []
        assert manager.fact_count == 0
    
    def test_save_and_load(self, manager):
        """Test saving and loading memory."""
        manager.load()
        manager.add_fact(MemoryFact(
            content="Test fact",
            confidence=0.8,
        ))
        manager.flush()
        
        # Create new manager and load
        manager2 = MemoryManager(storage_path=str(manager.storage_path))
        manager2.load()
        
        assert manager2.fact_count == 1
        assert manager2.get_fact_by_id(manager.get_top_facts()[0].id) is not None
    
    def test_add_fact(self, manager):
        """Test adding facts."""
        manager.load()
        
        fact = MemoryFact(
            content="New fact",
            category="work",
            confidence=0.9,
        )
        
        manager.add_fact(fact)
        
        assert manager.fact_count == 1
        
        # Get fact
        retrieved = manager.get_fact_by_id(fact.id)
        assert retrieved is not None
        assert retrieved.content == "New fact"
    
    def test_update_fact(self, manager):
        """Test updating facts."""
        manager.load()
        
        fact = MemoryFact(content="Original", confidence=0.5)
        manager.add_fact(fact)
        
        # Update
        updated = manager.update_fact(
            fact.id,
            content="Updated",
            confidence=0.9,
        )
        
        assert updated is not None
        assert updated.content == "Updated"
        assert updated.confidence == 0.9
    
    def test_delete_fact(self, manager):
        """Test deleting facts."""
        manager.load()
        
        fact = MemoryFact(content="To delete")
        manager.add_fact(fact)
        
        assert manager.fact_count == 1
        
        # Delete
        deleted = manager.delete_fact(fact.id)
        assert deleted is True
        assert manager.fact_count == 0
        
        # Delete non-existent
        deleted = manager.delete_fact("nonexistent")
        assert deleted is False
    
    def test_get_top_facts(self, manager):
        """Test getting top facts by confidence."""
        manager.load()
        
        # Add facts with different confidences
        manager.add_fact(MemoryFact(content="Low", confidence=0.3))
        manager.add_fact(MemoryFact(content="High", confidence=0.9))
        manager.add_fact(MemoryFact(content="Medium", confidence=0.6))
        manager.flush()
        
        # Get top 2
        top = manager.get_top_facts(limit=2)
        
        assert len(top) == 2
        assert top[0].content == "High"
        assert top[1].content == "Medium"
    
    def test_get_top_facts_with_threshold(self, manager):
        """Test getting facts with confidence threshold."""
        manager.load()
        
        manager.add_fact(MemoryFact(content="Low", confidence=0.3))
        manager.add_fact(MemoryFact(content="High", confidence=0.9))
        manager.flush()
        
        # Get only high confidence
        top = manager.get_top_facts(min_confidence=0.7)
        
        assert len(top) == 1
        assert top[0].content == "High"
    
    def test_get_facts_by_category(self, manager):
        """Test filtering facts by category."""
        manager.load()
        
        manager.add_fact(MemoryFact(content="Work 1", category="work"))
        manager.add_fact(MemoryFact(content="Work 2", category="work"))
        manager.add_fact(MemoryFact(content="Personal", category="personal"))
        manager.flush()
        
        work_facts = manager.get_facts_by_category("work")
        
        assert len(work_facts) == 2
        assert all(f.category == "work" for f in work_facts)
    
    def test_search_facts(self, manager):
        """Test searching facts."""
        manager.load()
        
        manager.add_fact(MemoryFact(content="Python is great"))
        manager.add_fact(MemoryFact(content="JavaScript is popular"))
        manager.add_fact(MemoryFact(content="TypeScript is typed JavaScript"))
        manager.flush()
        
        # Search for "JavaScript"
        results = manager.search_facts("JavaScript")
        
        assert len(results) == 2
        assert all("JavaScript" in f.content for f in results)
    
    def test_max_facts_limit(self, manager):
        """Test that max facts limit is enforced."""
        manager.load()
        
        # Add more facts than max
        for i in range(15):
            manager.add_fact(MemoryFact(
                content=f"Fact {i}",
                confidence=0.5 + (i * 0.01),  # Varying confidence
            ))
        
        manager.flush()
        
        # Should be limited to max_facts
        assert manager.fact_count <= 10
        
        # Should keep highest confidence
        facts = manager.get_top_facts(limit=10)
        assert all(f.confidence >= 0.5 for f in facts)
    
    def test_clear_memory(self, manager):
        """Test clearing all memory."""
        manager.load()
        
        manager.add_fact(MemoryFact(content="Fact 1"))
        manager.add_fact(MemoryFact(content="Fact 2"))
        manager.flush()
        
        assert manager.fact_count == 2
        
        manager.clear()
        
        assert manager.fact_count == 0
        assert not manager.storage_path.exists()
    
    def test_export_import(self, manager):
        """Test export and import."""
        manager.load()
        manager.add_fact(MemoryFact(content="Export test"))
        manager.flush()
        
        # Export
        data = manager.export_data()
        
        assert "version" in data
        assert "facts" in data
        assert len(data["facts"]) == 1
        
        # Import to new manager
        manager2 = MemoryManager(storage_path=str(manager.storage_path))
        manager2.import_data(data)
        
        assert manager2.fact_count == 1
    
    def test_get_statistics(self, manager):
        """Test getting statistics."""
        manager.load()
        
        manager.add_fact(MemoryFact(content="High", confidence=0.9, category="work"))
        manager.add_fact(MemoryFact(content="Low", confidence=0.3, category="personal"))
        manager.flush()
        
        stats = manager.get_statistics()
        
        assert stats["total_facts"] == 2
        assert stats["max_facts"] == 10
        assert "high" in stats["confidence_distribution"]
        assert "categories" in stats
    
    def test_concurrent_access(self, manager):
        """Test thread-safe concurrent access."""
        manager.load()
        
        async def add_fact(i):
            manager.add_fact(MemoryFact(content=f"Concurrent {i}"))
        
        # Add facts concurrently
        asyncio.run(asyncio.gather(*[add_fact(i) for i in range(5)]))
        
        # Flush and verify
        manager.flush()
        assert manager.fact_count == 5


class TestContextSection:
    """Tests for ContextSection."""
    
    def test_create_section(self):
        """Test creating context section."""
        section = ContextSection(summary="Test summary")
        
        assert section.summary == "Test summary"
        assert section.updated_at is not None
    
    def test_update_section(self):
        """Test updating section."""
        section = ContextSection(summary="Original")
        
        section.update("Updated summary")
        
        assert section.summary == "Updated summary"
        assert section.updated_at is not None


class TestUserContext:
    """Tests for UserContext."""
    
    def test_create_user_context(self):
        """Test creating user context."""
        ctx = UserContext()
        
        assert ctx.work_context is not None
        assert ctx.personal_context is not None
        assert ctx.top_of_mind is not None
    
    def test_user_context_serialization(self):
        """Test user context serialization."""
        ctx = UserContext()
        ctx.work_context.update("Work summary")
        
        data = ctx.to_dict()
        
        assert "work_context" in data
        assert data["work_context"]["summary"] == "Work summary"
        
        # Deserialize
        ctx2 = UserContext.from_dict(data)
        assert ctx2.work_context.summary == "Work summary"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
