"""
Week 56 - Real-time Stream Processing
Stream processing with windowing, watermarks, and event handling.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
import time
import logging
import threading
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class ProcessingMode(Enum):
    """Processing modes for stream processing."""
    REAL_TIME = "real_time"
    MICRO_BATCH = "micro_batch"
    WINDOWED = "windowed"


class WindowType(Enum):
    """Types of windowing strategies."""
    TUMBLING = "tumbling"
    SLIDING = "sliding"
    SESSION = "session"


@dataclass
class StreamConfig:
    """Configuration for stream processing."""
    mode: ProcessingMode = ProcessingMode.REAL_TIME
    window_size: int = 60  # seconds
    window_slide: int = 30  # seconds for sliding windows
    watermark_delay: int = 5  # seconds
    buffer_size: int = 10000
    max_events_per_window: int = 100000
    session_timeout: int = 300  # seconds for session windows
    enable_late_events: bool = True
    late_event_tolerance: int = 60  # seconds
    parallelism: int = 1
    checkpoint_interval: int = 60  # seconds
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.mode, str):
            self.mode = ProcessingMode(self.mode)


@dataclass
class StreamEvent:
    """Represents an event in the stream."""
    event_id: str
    event_type: str
    data: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    partition_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other: 'StreamEvent') -> bool:
        return self.timestamp < other.timestamp


@dataclass
class WindowResult:
    """Result of window processing."""
    window_start: datetime
    window_end: datetime
    event_count: int
    events: List[StreamEvent] = field(default_factory=list)
    result: Any = None
    late_events: List[StreamEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """Result of stream processing operation."""
    success: bool
    mode: ProcessingMode
    events_processed: int = 0
    events_failed: int = 0
    windows_created: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class WatermarkManager:
    """Manages watermarks for event time processing."""
    
    def __init__(self, delay_seconds: int = 5):
        self.delay = timedelta(seconds=delay_seconds)
        self._current_watermark: Optional[datetime] = None
        self._lock = threading.Lock()
    
    def update(self, event_time: datetime) -> datetime:
        """Update watermark based on event time."""
        with self._lock:
            new_watermark = event_time - self.delay
            if self._current_watermark is None or new_watermark > self._current_watermark:
                self._current_watermark = new_watermark
            return self._current_watermark
    
    def get_current(self) -> Optional[datetime]:
        """Get current watermark."""
        with self._lock:
            return self._current_watermark
    
    def is_late(self, event_time: datetime) -> bool:
        """Check if an event is late based on watermark."""
        with self._lock:
            if self._current_watermark is None:
                return False
            return event_time < self._current_watermark


class WindowManager:
    """Manages window creation and eviction."""
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self._windows: Dict[Tuple[datetime, datetime], List[StreamEvent]] = {}
        self._window_type = WindowType.TUMBLING
        self._lock = threading.Lock()
    
    def set_window_type(self, window_type: WindowType) -> None:
        """Set the window type."""
        self._window_type = window_type
    
    def assign_window(self, event: StreamEvent) -> List[Tuple[datetime, datetime]]:
        """Assign event to appropriate window(s)."""
        event_time = event.timestamp
        
        if self._window_type == WindowType.TUMBLING:
            window_start = self._get_tumbling_window_start(event_time)
            window_end = window_start + timedelta(seconds=self.config.window_size)
            return [(window_start, window_end)]
        
        elif self._window_type == WindowType.SLIDING:
            windows = []
            window_start = self._get_tumbling_window_start(event_time)
            # Slide backwards to find all windows this event belongs to
            while window_start <= event_time:
                window_end = window_start + timedelta(seconds=self.config.window_size)
                if window_end > event_time:
                    windows.append((window_start, window_end))
                window_start = window_start + timedelta(seconds=self.config.window_slide)
            return windows
        
        elif self._window_type == WindowType.SESSION:
            # Session windows are dynamic
            return self._assign_session_window(event)
        
        return []
    
    def _get_tumbling_window_start(self, event_time: datetime) -> datetime:
        """Calculate window start for tumbling windows."""
        epoch = datetime(1970, 1, 1)
        seconds = (event_time - epoch).total_seconds()
        window_seconds = self.config.window_size
        window_start_seconds = (seconds // window_seconds) * window_seconds
        return epoch + timedelta(seconds=window_start_seconds)
    
    def _assign_session_window(self, event: StreamEvent) -> List[Tuple[datetime, datetime]]:
        """Assign event to session window."""
        event_time = event.timestamp
        
        # Find existing session or create new one
        for (start, end), events in list(self._windows.items()):
            if start <= event_time <= end:
                # Event fits in existing session
                return [(start, end)]
            elif event_time > end and (event_time - end).total_seconds() <= self.config.session_timeout:
                # Extend session
                new_end = event_time
                self._windows[(start, new_end)] = self._windows.pop((start, end))
                return [(start, new_end)]
        
        # Create new session
        window_end = event_time + timedelta(seconds=self.config.session_timeout)
        return [(event_time, window_end)]
    
    def add_event(self, event: StreamEvent, window: Tuple[datetime, datetime]) -> None:
        """Add event to a window."""
        with self._lock:
            if window not in self._windows:
                self._windows[window] = []
            self._windows[window].append(event)
    
    def get_window_events(self, window: Tuple[datetime, datetime]) -> List[StreamEvent]:
        """Get all events in a window."""
        with self._lock:
            return self._windows.get(window, []).copy()
    
    def evict_window(self, window: Tuple[datetime, datetime]) -> Optional[List[StreamEvent]]:
        """Evict a window and return its events."""
        with self._lock:
            return self._windows.pop(window, None)
    
    def get_ready_windows(self, watermark: datetime) -> List[Tuple[datetime, datetime]]:
        """Get windows ready for processing based on watermark."""
        with self._lock:
            ready = []
            for (start, end) in self._windows.keys():
                if end <= watermark:
                    ready.append((start, end))
            return ready


class StreamProcessor:
    """
    Real-time stream processor with windowing support.
    
    Features:
    - Multiple processing modes (real-time, micro-batch, windowed)
    - Event time processing with watermarks
    - Multiple window types (tumbling, sliding, session)
    - Late event handling
    - Checkpointing support
    """
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self._watermark_manager = WatermarkManager(config.watermark_delay)
        self._window_manager = WindowManager(config)
        self._event_handlers: Dict[str, Callable] = {}
        self._window_handlers: List[Callable] = []
        self._event_queue: Queue = Queue(maxsize=config.buffer_size)
        self._processing = False
        self._stats = {
            "events_processed": 0,
            "events_late": 0,
            "windows_processed": 0,
            "last_processed": None
        }
        self._late_events: List[StreamEvent] = []
    
    def register_event_handler(self, event_type: str, handler: Callable[[StreamEvent], Any]) -> None:
        """Register a handler for a specific event type."""
        self._event_handlers[event_type] = handler
    
    def register_window_handler(self, handler: Callable[[WindowResult], Any]) -> None:
        """Register a handler for window results."""
        self._window_handlers.append(handler)
    
    def emit(self, event: StreamEvent) -> bool:
        """
        Emit an event into the stream.
        
        Args:
            event: The event to emit
            
        Returns:
            True if event was accepted, False if buffer is full
        """
        try:
            self._event_queue.put_nowait(event)
            return True
        except:
            return False
    
    def emit_batch(self, events: List[StreamEvent]) -> int:
        """
        Emit multiple events into the stream.
        
        Returns:
            Number of events successfully emitted
        """
        count = 0
        for event in events:
            if self.emit(event):
                count += 1
        return count
    
    def process(self, events: Optional[List[StreamEvent]] = None) -> ProcessingResult:
        """
        Process events from the stream.
        
        Args:
            events: Optional list of events to process (bypasses queue)
            
        Returns:
            ProcessingResult with processing details
        """
        start_time = time.time()
        
        if events:
            # Direct processing of provided events
            return self._process_events_direct(events, start_time)
        
        # Process from queue based on mode
        if self.config.mode == ProcessingMode.REAL_TIME:
            return self._process_real_time(start_time)
        elif self.config.mode == ProcessingMode.MICRO_BATCH:
            return self._process_micro_batch(start_time)
        elif self.config.mode == ProcessingMode.WINDOWED:
            return self._process_windowed(start_time)
        
        return ProcessingResult(
            success=False,
            mode=self.config.mode,
            errors=["Unknown processing mode"]
        )
    
    def _process_events_direct(self, events: List[StreamEvent], start_time: float) -> ProcessingResult:
        """Process a list of events directly."""
        processed = 0
        failed = 0
        errors = []
        
        # Sort by timestamp for event time processing
        events.sort(key=lambda e: e.timestamp)
        
        for event in events:
            try:
                # Update watermark
                self._watermark_manager.update(event.timestamp)
                
                # Check if late
                if self._watermark_manager.is_late(event.timestamp):
                    self._stats["events_late"] += 1
                    if self.config.enable_late_events:
                        self._late_events.append(event)
                    continue
                
                # Process event
                self._process_single_event(event)
                processed += 1
                
            except Exception as e:
                failed += 1
                errors.append(f"Error processing event {event.event_id}: {str(e)}")
        
        self._stats["events_processed"] += processed
        self._stats["last_processed"] = datetime.utcnow()
        
        return ProcessingResult(
            success=failed == 0,
            mode=self.config.mode,
            events_processed=processed,
            events_failed=failed,
            errors=errors,
            duration_seconds=time.time() - start_time
        )
    
    def _process_real_time(self, start_time: float) -> ProcessingResult:
        """Process events in real-time mode."""
        processed = 0
        failed = 0
        errors = []
        
        try:
            while True:
                event = self._event_queue.get_nowait()
                try:
                    self._process_single_event(event)
                    processed += 1
                except Exception as e:
                    failed += 1
                    errors.append(str(e))
        except Empty:
            pass
        
        self._stats["events_processed"] += processed
        
        return ProcessingResult(
            success=failed == 0,
            mode=ProcessingMode.REAL_TIME,
            events_processed=processed,
            events_failed=failed,
            errors=errors,
            duration_seconds=time.time() - start_time
        )
    
    def _process_micro_batch(self, start_time: float) -> ProcessingResult:
        """Process events in micro-batch mode."""
        batch = []
        try:
            while len(batch) < self.config.max_events_per_window:
                event = self._event_queue.get_nowait()
                batch.append(event)
        except Empty:
            pass
        
        if not batch:
            return ProcessingResult(
                success=True,
                mode=ProcessingMode.MICRO_BATCH,
                events_processed=0,
                duration_seconds=time.time() - start_time
            )
        
        return self._process_events_direct(batch, start_time)
    
    def _process_windowed(self, start_time: float) -> ProcessingResult:
        """Process events in windowed mode."""
        # Collect events from queue
        events = []
        try:
            while True:
                event = self._event_queue.get_nowait()
                events.append(event)
        except Empty:
            pass
        
        if not events:
            return ProcessingResult(
                success=True,
                mode=ProcessingMode.WINDOWED,
                events_processed=0,
                duration_seconds=time.time() - start_time
            )
        
        # Assign events to windows
        windows_created = set()
        for event in events:
            assigned_windows = self._window_manager.assign_window(event)
            for window in assigned_windows:
                self._window_manager.add_event(event, window)
                windows_created.add(window)
        
        # Process ready windows
        watermark = self._watermark_manager.get_current()
        if watermark:
            ready_windows = self._window_manager.get_ready_windows(watermark)
            for window in ready_windows:
                window_events = self._window_manager.evict_window(window)
                if window_events:
                    result = WindowResult(
                        window_start=window[0],
                        window_end=window[1],
                        event_count=len(window_events),
                        events=window_events
                    )
                    self._trigger_window_handlers(result)
                    self._stats["windows_processed"] += 1
        
        return ProcessingResult(
            success=True,
            mode=ProcessingMode.WINDOWED,
            events_processed=len(events),
            windows_created=len(windows_created),
            duration_seconds=time.time() - start_time
        )
    
    def _process_single_event(self, event: StreamEvent) -> Any:
        """Process a single event."""
        handler = self._event_handlers.get(event.event_type)
        if handler:
            return handler(event)
        return None
    
    def _trigger_window_handlers(self, result: WindowResult) -> None:
        """Trigger all registered window handlers."""
        for handler in self._window_handlers:
            try:
                handler(result)
            except Exception as e:
                logger.error(f"Window handler error: {e}")
    
    async def process_async(self, events: Optional[List[StreamEvent]] = None) -> ProcessingResult:
        """Asynchronously process events."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.process(events))
    
    def start(self) -> None:
        """Start continuous processing."""
        self._processing = True
        logger.info(f"Stream processor started in {self.config.mode} mode")
    
    def stop(self) -> None:
        """Stop continuous processing."""
        self._processing = False
        logger.info("Stream processor stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return self._stats.copy()
    
    def reset_stats(self) -> None:
        """Reset processing statistics."""
        self._stats = {
            "events_processed": 0,
            "events_late": 0,
            "windows_processed": 0,
            "last_processed": None
        }
        self._late_events.clear()
    
    def get_late_events(self) -> List[StreamEvent]:
        """Get all late events collected."""
        return self._late_events.copy()
    
    def get_current_watermark(self) -> Optional[datetime]:
        """Get the current watermark."""
        return self._watermark_manager.get_current()
    
    def get_pending_events(self) -> int:
        """Get the number of pending events in the queue."""
        return self._event_queue.qsize()


class EventAggregator:
    """Aggregates events within windows."""
    
    def __init__(self):
        self._aggregations: Dict[str, Any] = defaultdict(list)
        self._counters: Dict[str, int] = defaultdict(int)
    
    def aggregate(self, events: List[StreamEvent], key_extractor: Callable[[StreamEvent], str]) -> Dict[str, List[StreamEvent]]:
        """Aggregate events by key."""
        result = defaultdict(list)
        for event in events:
            key = key_extractor(event)
            result[key].append(event)
        return dict(result)
    
    def count_by_type(self, events: List[StreamEvent]) -> Dict[str, int]:
        """Count events by type."""
        result = defaultdict(int)
        for event in events:
            result[event.event_type] += 1
        return dict(result)
    
    def sum_by_field(self, events: List[StreamEvent], field: str) -> float:
        """Sum a numeric field across events."""
        total = 0.0
        for event in events:
            if hasattr(event.data, 'get'):
                total += event.data.get(field, 0)
            elif isinstance(event.data, dict):
                total += event.data.get(field, 0)
        return total
