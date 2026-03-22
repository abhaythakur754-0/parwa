"""
Storage utility for PARWA.
Provides an abstraction for local file storage (and future S3 integration).
"""
import os
import shutil
from typing import Optional
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)

class Storage:
    """
    Storage abstraction layer.
    Currently implements local filesystem storage.
    """
    def __init__(self, base_path: str = "/tmp/parwa_storage"):
        self.base_path = base_path
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path, exist_ok=True)

    def upload(self, source_path: str, destination_name: str) -> Optional[str]:
        """Upload (copy) a file to the storage area."""
        try:
            target_path = os.path.join(self.base_path, destination_name)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(source_path, target_path)
            logger.info("file_uploaded", extra={"context": {"path": target_path}})
            return target_path
        except Exception as e:
            logger.error("file_upload_failed", extra={"context": {"source": source_path, "error": str(e)}})
            return None

    def download(self, destination_name: str, target_local_path: str) -> bool:
        """Download (copy) a file from storage to a local path."""
        try:
            source_path = os.path.join(self.base_path, destination_name)
            if not os.path.exists(source_path):
                logger.warning("file_not_found", extra={"context": {"path": source_path}})
                return False
            shutil.copy2(source_path, target_local_path)
            return True
        except Exception as e:
            logger.error("file_download_failed", extra={"context": {"path": destination_name, "error": str(e)}})
            return False

    def delete(self, destination_name: str) -> bool:
        """Delete a file from storage."""
        try:
            path = os.path.join(self.base_path, destination_name)
            if os.path.exists(path):
                os.remove(path)
                logger.info("file_deleted", extra={"context": {"path": path}})
                return True
            return False
        except Exception as e:
            logger.error("file_delete_failed", extra={"context": {"path": destination_name, "error": str(e)}})
            return False
