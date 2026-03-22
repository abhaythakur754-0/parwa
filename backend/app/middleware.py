import uuid
import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from shared.core_functions.logger import get_logger

logger = get_logger("middleware")

class ContextMiddleware(BaseHTTPMiddleware):
    """
    Global middleware for:
    1. Injecting/Capturing X-Correlation-ID for distributed tracing.
    2. Extracting X-Company-ID for Row Level Security (RLS) context.
    3. Logging request/response lifecycle.
    """
    
    async def dispatch(self, request: Request, call_next):
        # 1. Handle Correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        
        # 2. Handle Multi-Tenancy (Company ID) for RLS
        # In a real scenario, this might come from a JWT, but for now we look at headers
        company_id = request.headers.get("X-Company-ID")
        request.state.company_id = company_id
        
        # 3. Request Logging
        start_time = time.time()
        logger.info(
            f"Incoming Request: {request.method} {request.url.path}",
            extra={
                "request_id": correlation_id,
                "context": {
                    "method": request.method,
                    "path": request.url.path,
                    "company_id": company_id
                }
            }
        )
        
        # Proceed with request
        response: Response = await call_next(request)
        
        # 4. Response Tracing & Logging
        process_time = time.time() - start_time
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        
        logger.info(
            f"Request Completed: {request.method} {request.url.path} - Status: {response.status_code}",
            extra={
                "request_id": correlation_id,
                "context": {
                    "status_code": response.status_code,
                    "process_time": process_time
                }
            }
        )
        
        return response
