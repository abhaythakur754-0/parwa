# Edge Functions - Week 51 Builder 3
# Edge function execution

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import uuid


class FunctionStatus(Enum):
    CREATED = "created"
    DEPLOYED = "deployed"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class Runtime(Enum):
    PYTHON = "python"
    NODEJS = "nodejs"
    GO = "go"
    RUST = "rust"


@dataclass
class EdgeFunction:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    runtime: Runtime = Runtime.PYTHON
    code: str = ""
    handler: str = "handler"
    memory_mb: int = 128
    timeout_seconds: int = 30
    status: FunctionStatus = FunctionStatus.CREATED
    deployed_nodes: List[str] = field(default_factory=list)
    invocation_count: int = 0
    error_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FunctionInvocation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    function_id: str = ""
    node_id: str = ""
    trigger: str = "http"
    payload: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    status: str = "pending"
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0
    logs: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class EdgeFunctions:
    """Edge function management and execution"""

    def __init__(self):
        self._functions: Dict[str, EdgeFunction] = {}
        self._invocations: List[FunctionInvocation] = []
        self._metrics = {
            "total_functions": 0,
            "total_invocations": 0,
            "successful": 0,
            "failed": 0,
            "by_runtime": {}
        }

    def create_function(
        self,
        name: str,
        runtime: Runtime,
        code: str,
        handler: str = "handler",
        memory_mb: int = 128,
        timeout_seconds: int = 30
    ) -> EdgeFunction:
        """Create a new edge function"""
        func = EdgeFunction(
            name=name,
            runtime=runtime,
            code=code,
            handler=handler,
            memory_mb=memory_mb,
            timeout_seconds=timeout_seconds
        )
        self._functions[func.id] = func
        self._metrics["total_functions"] += 1

        runtime_key = runtime.value
        self._metrics["by_runtime"][runtime_key] = \
            self._metrics["by_runtime"].get(runtime_key, 0) + 1

        return func

    def update_function(
        self,
        function_id: str,
        **kwargs
    ) -> bool:
        """Update function configuration"""
        func = self._functions.get(function_id)
        if not func:
            return False

        for key, value in kwargs.items():
            if hasattr(func, key):
                setattr(func, key, value)
        return True

    def delete_function(self, function_id: str) -> bool:
        """Delete a function"""
        if function_id in self._functions:
            del self._functions[function_id]
            return True
        return False

    def deploy_function(
        self,
        function_id: str,
        node_ids: List[str]
    ) -> bool:
        """Deploy function to nodes"""
        func = self._functions.get(function_id)
        if not func:
            return False

        func.deployed_nodes = node_ids
        func.status = FunctionStatus.DEPLOYED
        return True

    def undeploy_function(self, function_id: str) -> bool:
        """Undeploy function from all nodes"""
        func = self._functions.get(function_id)
        if not func:
            return False

        func.deployed_nodes = []
        func.status = FunctionStatus.STOPPED
        return True

    def invoke_function(
        self,
        function_id: str,
        payload: Dict[str, Any],
        node_id: str = "",
        trigger: str = "http"
    ) -> Optional[FunctionInvocation]:
        """Invoke an edge function"""
        func = self._functions.get(function_id)
        if not func or func.status != FunctionStatus.DEPLOYED:
            return None

        if node_id and node_id not in func.deployed_nodes:
            return None

        invocation = FunctionInvocation(
            function_id=function_id,
            node_id=node_id or (func.deployed_nodes[0] if func.deployed_nodes else ""),
            trigger=trigger,
            payload=payload,
            status="pending"
        )

        self._invocations.append(invocation)
        self._metrics["total_invocations"] += 1
        func.invocation_count += 1

        return invocation

    def start_invocation(self, invocation_id: str) -> bool:
        """Start an invocation"""
        for inv in self._invocations:
            if inv.id == invocation_id and inv.status == "pending":
                inv.status = "running"
                inv.started_at = datetime.utcnow()
                return True
        return False

    def complete_invocation(
        self,
        invocation_id: str,
        result: Any,
        execution_time_ms: float,
        memory_used_mb: float = 0
    ) -> bool:
        """Complete an invocation"""
        for inv in self._invocations:
            if inv.id == invocation_id and inv.status in ["pending", "running"]:
                inv.status = "completed"
                inv.result = result
                inv.execution_time_ms = execution_time_ms
                inv.memory_used_mb = memory_used_mb
                inv.started_at = inv.started_at or datetime.utcnow()
                inv.completed_at = datetime.utcnow()
                self._metrics["successful"] += 1
                return True
        return False

    def fail_invocation(
        self,
        invocation_id: str,
        error: str = ""
    ) -> bool:
        """Mark invocation as failed"""
        for inv in self._invocations:
            if inv.id == invocation_id and inv.status in ["pending", "running"]:
                inv.status = "failed"
                inv.result = {"error": error}
                inv.completed_at = datetime.utcnow()

                func = self._functions.get(inv.function_id)
                if func:
                    func.error_count += 1

                self._metrics["failed"] += 1
                return True
        return False

    def add_log(self, invocation_id: str, log: str) -> bool:
        """Add log entry to invocation"""
        for inv in self._invocations:
            if inv.id == invocation_id:
                inv.logs.append(log)
                return True
        return False

    def get_function(self, function_id: str) -> Optional[EdgeFunction]:
        """Get function by ID"""
        return self._functions.get(function_id)

    def get_function_by_name(self, name: str) -> Optional[EdgeFunction]:
        """Get function by name"""
        for func in self._functions.values():
            if func.name == name:
                return func
        return None

    def get_functions_by_runtime(self, runtime: Runtime) -> List[EdgeFunction]:
        """Get all functions of a runtime"""
        return [f for f in self._functions.values() if f.runtime == runtime]

    def get_deployed_functions(self) -> List[EdgeFunction]:
        """Get all deployed functions"""
        return [f for f in self._functions.values() if f.status == FunctionStatus.DEPLOYED]

    def get_invocation(self, invocation_id: str) -> Optional[FunctionInvocation]:
        """Get invocation by ID"""
        for inv in self._invocations:
            if inv.id == invocation_id:
                return inv
        return None

    def get_invocations_by_function(
        self,
        function_id: str,
        limit: int = 100
    ) -> List[FunctionInvocation]:
        """Get invocations for a function"""
        invocations = [i for i in self._invocations if i.function_id == function_id]
        return invocations[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        """Get function metrics"""
        return self._metrics.copy()
