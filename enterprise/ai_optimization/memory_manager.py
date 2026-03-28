"""Memory Manager Module - Week 55, Builder 4"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging
import threading

logger = logging.getLogger(__name__)


class MemoryPriority(Enum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class MemoryBlock:
    id: str
    size: int
    usage: str
    priority: MemoryPriority = MemoryPriority.MEDIUM
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    data: Any = None

    def touch(self) -> None:
        self.last_accessed = datetime.utcnow()


@dataclass
class MemoryPool:
    name: str
    max_size: int = 1024 * 1024  # 1MB default
    used_size: int = 0
    blocks: Dict[str, MemoryBlock] = field(default_factory=dict)

    @property
    def available_size(self) -> int:
        return self.max_size - self.used_size

    @property
    def utilization(self) -> float:
        return self.used_size / self.max_size if self.max_size > 0 else 0


class AIMemoryManager:
    def __init__(self, default_pool_size: int = 1024 * 1024):
        self.pools: Dict[str, MemoryPool] = {}
        self._lock = threading.Lock()
        self._create_default_pool(default_pool_size)

    def _create_default_pool(self, size: int) -> None:
        self.pools["default"] = MemoryPool(name="default", max_size=size)

    def allocate(self, block_id: str, size: int, usage: str = "", pool_name: str = "default",
                 priority: MemoryPriority = MemoryPriority.MEDIUM, data: Any = None) -> Optional[MemoryBlock]:
        with self._lock:
            pool = self.pools.get(pool_name)
            if not pool:
                return None

            if pool.available_size < size:
                self._evict_low_priority(pool, size)

            if pool.available_size < size:
                return None

            block = MemoryBlock(
                id=block_id,
                size=size,
                usage=usage,
                priority=priority,
                data=data,
            )
            pool.blocks[block_id] = block
            pool.used_size += size
            return block

    def deallocate(self, block_id: str, pool_name: str = "default") -> bool:
        with self._lock:
            pool = self.pools.get(pool_name)
            if not pool:
                return False

            block = pool.blocks.get(block_id)
            if not block:
                return False

            pool.used_size -= block.size
            del pool.blocks[block_id]
            return True

    def get(self, block_id: str, pool_name: str = "default") -> Optional[MemoryBlock]:
        with self._lock:
            pool = self.pools.get(pool_name)
            if not pool:
                return None
            block = pool.blocks.get(block_id)
            if block:
                block.touch()
            return block

    def _evict_low_priority(self, pool: MemoryPool, required_size: int) -> int:
        evicted = 0
        blocks_by_priority = sorted(
            pool.blocks.values(),
            key=lambda b: (b.priority.value, b.last_accessed)
        )

        for block in blocks_by_priority:
            if evicted >= required_size:
                break
            if block.priority == MemoryPriority.LOW:
                self.deallocate(block.id, pool.name)
                evicted += block.size

        return evicted

    def create_pool(self, name: str, max_size: int) -> None:
        with self._lock:
            self.pools[name] = MemoryPool(name=name, max_size=max_size)

    def remove_pool(self, name: str) -> bool:
        with self._lock:
            if name == "default":
                return False
            if name in self.pools:
                del self.pools[name]
                return True
            return False

    def gc(self) -> int:
        """Garbage collect low priority blocks across all pools"""
        total_freed = 0
        for pool in self.pools.values():
            freed = self._evict_low_priority(pool, float('inf'))
            total_freed += freed
        return total_freed
