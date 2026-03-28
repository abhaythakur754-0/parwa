"""
Dashboard Storage
Enterprise Analytics & Reporting - Week 44 Builder 1
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
import os

logger = logging.getLogger(__name__)


@dataclass
class StorageConfig:
    """Configuration for dashboard storage"""
    storage_type: str = "file"  # file, database, memory
    storage_path: str = "data/dashboards"
    auto_save: bool = True
    backup_enabled: bool = True
    max_backups: int = 10


class DashboardStorage:
    """Handles dashboard persistence"""
    
    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self._cache: Dict[str, Any] = {}
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize storage"""
        if self._initialized:
            return True
        
        if self.config.storage_type == "file":
            try:
                os.makedirs(self.config.storage_path, exist_ok=True)
                self._initialized = True
                logger.info(f"Initialized file storage at {self.config.storage_path}")
                return True
            except Exception as e:
                logger.error(f"Storage initialization failed: {e}")
                return False
        
        self._initialized = True
        return True
    
    def save_dashboard(self, dashboard_id: str, data: Dict[str, Any]) -> bool:
        """Save a dashboard"""
        if not self._initialized:
            self.initialize()
        
        try:
            # Cache the data
            self._cache[dashboard_id] = data
            
            if self.config.storage_type == "file":
                return self._save_to_file(dashboard_id, data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving dashboard {dashboard_id}: {e}")
            return False
    
    def _save_to_file(self, dashboard_id: str, data: Dict[str, Any]) -> bool:
        """Save dashboard to file"""
        try:
            file_path = Path(self.config.storage_path) / f"{dashboard_id}.json"
            
            # Create backup if file exists
            if file_path.exists() and self.config.backup_enabled:
                self._create_backup(dashboard_id)
            
            # Write to file
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            return True
            
        except Exception as e:
            logger.error(f"File save error: {e}")
            return False
    
    def _create_backup(self, dashboard_id: str) -> bool:
        """Create a backup of the dashboard"""
        try:
            import shutil
            
            file_path = Path(self.config.storage_path) / f"{dashboard_id}.json"
            backup_dir = Path(self.config.storage_path) / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{dashboard_id}_{timestamp}.json"
            
            shutil.copy(file_path, backup_path)
            
            # Clean old backups
            self._clean_old_backups(dashboard_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Backup error: {e}")
            return False
    
    def _clean_old_backups(self, dashboard_id: str) -> None:
        """Remove old backups beyond max_backups"""
        try:
            backup_dir = Path(self.config.storage_path) / "backups"
            backups = sorted(backup_dir.glob(f"{dashboard_id}_*.json"))
            
            while len(backups) > self.config.max_backups:
                backups[0].unlink()
                backups = backups[1:]
                
        except Exception as e:
            logger.warning(f"Backup cleanup error: {e}")
    
    def load_dashboard(self, dashboard_id: str) -> Optional[Dict[str, Any]]:
        """Load a dashboard"""
        if not self._initialized:
            self.initialize()
        
        # Check cache first
        if dashboard_id in self._cache:
            return self._cache[dashboard_id]
        
        try:
            if self.config.storage_type == "file":
                return self._load_from_file(dashboard_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading dashboard {dashboard_id}: {e}")
            return None
    
    def _load_from_file(self, dashboard_id: str) -> Optional[Dict[str, Any]]:
        """Load dashboard from file"""
        try:
            file_path = Path(self.config.storage_path) / f"{dashboard_id}.json"
            
            if not file_path.exists():
                return None
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Cache the loaded data
            self._cache[dashboard_id] = data
            
            return data
            
        except Exception as e:
            logger.error(f"File load error: {e}")
            return None
    
    def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete a dashboard"""
        if not self._initialized:
            self.initialize()
        
        try:
            # Remove from cache
            self._cache.pop(dashboard_id, None)
            
            if self.config.storage_type == "file":
                file_path = Path(self.config.storage_path) / f"{dashboard_id}.json"
                if file_path.exists():
                    file_path.unlink()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting dashboard {dashboard_id}: {e}")
            return False
    
    def list_dashboards(self) -> List[str]:
        """List all stored dashboard IDs"""
        if not self._initialized:
            self.initialize()
        
        try:
            if self.config.storage_type == "file":
                return self._list_from_files()
            
            return list(self._cache.keys())
            
        except Exception as e:
            logger.error(f"Error listing dashboards: {e}")
            return []
    
    def _list_from_files(self) -> List[str]:
        """List dashboards from files"""
        try:
            storage_path = Path(self.config.storage_path)
            return [
                f.stem for f in storage_path.glob("*.json")
                if not f.name.endswith("_backup.json")
            ]
        except Exception as e:
            logger.error(f"File list error: {e}")
            return []
    
    def restore_backup(self, dashboard_id: str, backup_timestamp: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Restore dashboard from backup"""
        try:
            backup_dir = Path(self.config.storage_path) / "backups"
            
            if backup_timestamp:
                backup_file = backup_dir / f"{dashboard_id}_{backup_timestamp}.json"
            else:
                # Get latest backup
                backups = sorted(backup_dir.glob(f"{dashboard_id}_*.json"), reverse=True)
                if not backups:
                    return None
                backup_file = backups[0]
            
            if not backup_file.exists():
                return None
            
            with open(backup_file, 'r') as f:
                data = json.load(f)
            
            # Restore the dashboard
            self.save_dashboard(dashboard_id, data)
            
            return data
            
        except Exception as e:
            logger.error(f"Restore error: {e}")
            return None
    
    def list_backups(self, dashboard_id: str) -> List[Dict[str, Any]]:
        """List available backups for a dashboard"""
        try:
            backup_dir = Path(self.config.storage_path) / "backups"
            backups = []
            
            for backup_file in sorted(backup_dir.glob(f"{dashboard_id}_*.json"), reverse=True):
                stat = backup_file.stat()
                backups.append({
                    "dashboard_id": dashboard_id,
                    "timestamp": backup_file.stem.split("_")[-1] + "_" + backup_file.stem.split("_")[-1],
                    "file": str(backup_file),
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            
            return backups
            
        except Exception as e:
            logger.error(f"List backups error: {e}")
            return []
    
    def save_widget_data(
        self,
        dashboard_id: str,
        widget_id: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Cache widget data for faster loading"""
        cache_key = f"{dashboard_id}_{widget_id}"
        self._cache[cache_key] = {
            "data": data,
            "cached_at": datetime.utcnow().isoformat(),
            "ttl": ttl
        }
        return True
    
    def load_widget_data(
        self,
        dashboard_id: str,
        widget_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load cached widget data"""
        cache_key = f"{dashboard_id}_{widget_id}"
        cached = self._cache.get(cache_key)
        
        if not cached:
            return None
        
        # Check TTL
        if cached.get("ttl"):
            cached_at = datetime.fromisoformat(cached["cached_at"])
            age = (datetime.utcnow() - cached_at).total_seconds()
            if age > cached["ttl"]:
                return None
        
        return cached["data"]
    
    def clear_cache(self) -> None:
        """Clear the in-memory cache"""
        self._cache.clear()
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        stats = {
            "storage_type": self.config.storage_type,
            "initialized": self._initialized,
            "dashboards_count": len(self.list_dashboards()),
            "cache_size": len(self._cache)
        }
        
        if self.config.storage_type == "file":
            storage_path = Path(self.config.storage_path)
            if storage_path.exists():
                stats["storage_path"] = str(storage_path)
                stats["total_size_bytes"] = sum(
                    f.stat().st_size 
                    for f in storage_path.glob("**/*.json")
                )
        
        return stats
