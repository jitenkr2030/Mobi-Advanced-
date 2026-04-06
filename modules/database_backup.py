"""
Database Backup System
Provides automated backup functionality for the Mobi Invoice application
"""

import os
import shutil
import hashlib
import sqlite3
import zipfile
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
from flask import current_app
from app import db, DatabaseBackup

logger = logging.getLogger(__name__)

class BackupManager:
    """Manages database backup operations"""
    
    def __init__(self):
        self.backup_dir = Path('backups')
        self.db_path = Path('mobi_invoice.db')
        self.backup_dir.mkdir(exist_ok=True)
    
    def create_backup(self, backup_type: str = 'FULL', user_id: int = None, 
                     compression: bool = True, description: str = None) -> DatabaseBackup:
        """
        Create a database backup
        
        Args:
            backup_type: Type of backup (FULL, INCREMENTAL, DIFFERENTIAL)
            user_id: User ID creating the backup
            compression: Whether to compress the backup
            description: Backup description
        
        Returns:
            DatabaseBackup object
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"backup_{backup_type.lower()}_{timestamp}.db"
        if compression:
            filename += '.zip'
        
        backup_path = self.backup_dir / filename
        
        # Create backup record
        backup = DatabaseBackup(
            filename=filename,
            path=str(backup_path),
            backup_type=backup_type,
            status='PENDING',
            created_by=user_id
        )
        
        db.session.add(backup)
        db.session.commit()
        
        try:
            # Update status to in progress
            backup.status = 'IN_PROGRESS'
            db.session.commit()
            
            if backup_type == 'FULL':
                self._create_full_backup(backup_path, compression)
            elif backup_type == 'INCREMENTAL':
                self._create_incremental_backup(backup_path, compression)
            elif backup_type == 'DIFFERENTIAL':
                self._create_differential_backup(backup_path, compression)
            else:
                raise ValueError(f"Unknown backup type: {backup_type}")
            
            # Calculate checksum and size
            checksum = self._calculate_checksum(backup_path)
            size = backup_path.stat().st_size
            
            # Update backup record
            backup.status = 'COMPLETED'
            backup.size = size
            backup.checksum = checksum
            backup.completed_at = datetime.now()
            db.session.commit()
            
            logger.info(f"Backup created successfully: {filename}")
            return backup
            
        except Exception as e:
            # Update backup record with failure
            backup.status = 'FAILED'
            backup.completed_at = datetime.now()
            db.session.commit()
            
            # Clean up partial file
            if backup_path.exists():
                backup_path.unlink()
            
            logger.error(f"Backup creation failed: {e}")
            raise
    
    def _create_full_backup(self, backup_path: Path, compression: bool = True):
        """Create a full database backup"""
        if compression:
            # Create compressed backup
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(self.db_path, 'mobi_invoice.db')
                
                # Also backup schema if available
                schema_path = Path('schema.sql')
                if schema_path.exists():
                    zipf.write(schema_path, 'schema.sql')
        else:
            # Create uncompressed backup
            shutil.copy2(self.db_path, backup_path)
    
    def _create_incremental_backup(self, backup_path: Path, compression: bool = True):
        """Create an incremental backup (simplified for SQLite)"""
        # For SQLite, incremental backups are complex
        # This is a simplified implementation that copies the WAL file if available
        wal_path = self.db_path.with_suffix('.db-wal')
        
        if wal_path.exists():
            if compression:
                with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(wal_path, 'mobi_invoice.db-wal')
            else:
                shutil.copy2(wal_path, backup_path)
        else:
            # Fall back to full backup if no WAL file
            self._create_full_backup(backup_path, compression)
    
    def _create_differential_backup(self, backup_path: Path, compression: bool = True):
        """Create a differential backup (simplified for SQLite)"""
        # For SQLite, differential backups are similar to incremental
        # This implementation creates a backup of changes since last full backup
        last_full_backup = DatabaseBackup.query.filter_by(
            backup_type='FULL',
            status='COMPLETED'
        ).order_by(DatabaseBackup.created_at.desc()).first()
        
        if not last_full_backup:
            # No full backup exists, create full backup
            self._create_full_backup(backup_path, compression)
        else:
            # For demo purposes, create full backup
            # In production, you'd implement proper change tracking
            self._create_full_backup(backup_path, compression)
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def restore_backup(self, backup_id: int, user_id: int = None) -> bool:
        """
        Restore database from backup
        
        Args:
            backup_id: ID of backup to restore
            user_id: User ID performing the restore
        
        Returns:
            True if restore successful
        """
        backup = DatabaseBackup.query.get(backup_id)
        if not backup:
            raise ValueError("Backup not found")
        
        if backup.status != 'COMPLETED':
            raise ValueError("Backup is not completed and cannot be restored")
        
        backup_path = Path(backup.path)
        if not backup_path.exists():
            raise ValueError("Backup file not found")
        
        try:
            # Create a pre-restore backup
            pre_restore = self.create_backup(
                backup_type='FULL',
                user_id=user_id,
                description=f'Pre-restore backup before restoring {backup.filename}'
            )
            
            # Close database connections
            db.engine.dispose()
            
            # Restore the backup
            if backup.filename.endswith('.zip'):
                # Extract from zip
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extractall('.')
            else:
                # Copy directly
                shutil.copy2(backup_path, self.db_path)
            
            logger.info(f"Database restored from backup: {backup.filename}")
            return True
            
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            raise
    
    def verify_backup(self, backup_id: int) -> Dict[str, Any]:
        """
        Verify backup integrity
        
        Args:
            backup_id: ID of backup to verify
        
        Returns:
            Verification results
        """
        backup = DatabaseBackup.query.get(backup_id)
        if not backup:
            return {'valid': False, 'error': 'Backup not found'}
        
        backup_path = Path(backup.path)
        if not backup_path.exists():
            return {'valid': False, 'error': 'Backup file not found'}
        
        try:
            # Calculate current checksum
            current_checksum = self._calculate_checksum(backup_path)
            checksum_match = current_checksum == backup.checksum
            
            # Check file size
            current_size = backup_path.stat().st_size
            size_match = current_size == backup.size
            
            # Try to open database if it's a DB file
            db_valid = True
            if not backup.filename.endswith('.zip'):
                try:
                    conn = sqlite3.connect(str(backup_path))
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = cursor.fetchall()
                    conn.close()
                    
                    if len(tables) == 0:
                        db_valid = False
                except sqlite3.Error:
                    db_valid = False
            
            return {
                'valid': backup.status == 'COMPLETED' and checksum_match and size_match and db_valid,
                'checksum_match': checksum_match,
                'size_match': size_match,
                'database_valid': db_valid,
                'current_checksum': current_checksum,
                'stored_checksum': backup.checksum,
                'current_size': current_size,
                'stored_size': backup.size
            }
            
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    def delete_backup(self, backup_id: int) -> bool:
        """
        Delete a backup
        
        Args:
            backup_id: ID of backup to delete
        
        Returns:
            True if deletion successful
        """
        backup = DatabaseBackup.query.get(backup_id)
        if not backup:
            return False
        
        try:
            # Delete file
            backup_path = Path(backup.path)
            if backup_path.exists():
                backup_path.unlink()
            
            # Delete database record
            db.session.delete(backup)
            db.session.commit()
            
            logger.info(f"Backup deleted: {backup.filename}")
            return True
            
        except Exception as e:
            logger.error(f"Backup deletion failed: {e}")
            db.session.rollback()
            return False
    
    def list_backups(self, backup_type: str = None, status: str = None, 
                    limit: int = 50) -> List[DatabaseBackup]:
        """
        List backups with optional filtering
        
        Args:
            backup_type: Filter by backup type
            status: Filter by status
            limit: Maximum number of backups to return
        
        Returns:
            List of backups
        """
        query = DatabaseBackup.query
        
        if backup_type:
            query = query.filter_by(backup_type=backup_type)
        if status:
            query = query.filter_by(status=status)
        
        return query.order_by(DatabaseBackup.created_at.desc()).limit(limit).all()
    
    def get_backup_stats(self) -> Dict[str, Any]:
        """Get backup statistics"""
        try:
            total_backups = DatabaseBackup.query.count()
            completed_backups = DatabaseBackup.query.filter_by(status='COMPLETED').count()
            failed_backups = DatabaseBackup.query.filter_by(status='FAILED').count()
            
            # Calculate total size
            total_size = db.session.query(db.func.sum(DatabaseBackup.size)).filter(
                DatabaseBackup.status == 'COMPLETED'
            ).scalar() or 0
            
            # Count by type
            backup_types = db.session.query(
                DatabaseBackup.backup_type,
                db.func.count(DatabaseBackup.id)
            ).group_by(DatabaseBackup.backup_type).all()
            
            type_counts = {backup_type: count for backup_type, count in backup_types}
            
            # Get recent backups
            recent_backups = DatabaseBackup.query.filter_by(status='COMPLETED').order_by(
                DatabaseBackup.created_at.desc()
            ).limit(5).all()
            
            return {
                'total_backups': total_backups,
                'completed_backups': completed_backups,
                'failed_backups': failed_backups,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'backup_types': type_counts,
                'recent_backups': [
                    {
                        'id': backup.id,
                        'filename': backup.filename,
                        'type': backup.backup_type,
                        'size': backup.size,
                        'created_at': backup.created_at.isoformat()
                    }
                    for backup in recent_backups
                ],
                'backup_directory': str(self.backup_dir),
                'directory_exists': self.backup_dir.exists(),
                'directory_size': sum(f.stat().st_size for f in self.backup_dir.rglob('*') if f.is_file())
            }
            
        except Exception as e:
            logger.error(f"Error getting backup stats: {e}")
            return {'error': str(e)}
    
    def cleanup_old_backups(self, days_to_keep: int = 30, keep_min: int = 5) -> int:
        """
        Clean up old backups
        
        Args:
            days_to_keep: Number of days to keep backups
            keep_min: Minimum number of backups to keep
        
        Returns:
            Number of backups deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Get old backups, but always keep the most recent 'keep_min' backups
            old_backups = DatabaseBackup.query.filter(
                DatabaseBackup.created_at < cutoff_date
            ).order_by(DatabaseBackup.created_at.desc()).offset(keep_min).all()
            
            deleted_count = 0
            for backup in old_backups:
                if self.delete_backup(backup.id):
                    deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old backups")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
            return 0
    
    def schedule_automatic_backups(self):
        """Schedule automatic backups (would be integrated with task scheduler)"""
        # This would be integrated with the background job system
        # For now, it's a placeholder for the concept
        pass

class BackupScheduler:
    """Schedules automatic backups"""
    
    def __init__(self, backup_manager: BackupManager):
        self.backup_manager = backup_manager
        self.is_running = False
    
    def start(self):
        """Start the backup scheduler"""
        self.is_running = True
        # In a real implementation, this would use a proper scheduler
        logger.info("Backup scheduler started")
    
    def stop(self):
        """Stop the backup scheduler"""
        self.is_running = False
        logger.info("Backup scheduler stopped")
    
    def schedule_daily_backup(self):
        """Schedule daily backup at 2 AM"""
        # This would be implemented with a proper scheduling library
        pass

# Global backup manager instance
backup_manager = BackupManager()

# Backup utilities
class BackupUtils:
    """Utility functions for backup management"""
    
    @staticmethod
    def export_backup_metadata(backup_id: int) -> Dict[str, Any]:
        """Export backup metadata"""
        backup = DatabaseBackup.query.get(backup_id)
        if not backup:
            return {'error': 'Backup not found'}
        
        verification = backup_manager.verify_backup(backup_id)
        
        return {
            'backup': {
                'id': backup.id,
                'filename': backup.filename,
                'path': backup.path,
                'type': backup.backup_type,
                'status': backup.status,
                'size': backup.size,
                'checksum': backup.checksum,
                'created_at': backup.created_at.isoformat(),
                'completed_at': backup.completed_at.isoformat() if backup.completed_at else None,
                'created_by': backup.created_by
            },
            'verification': verification,
            'exported_at': datetime.now().isoformat()
        }
    
    @staticmethod
    def get_backup_health_report() -> Dict[str, Any]:
        """Get comprehensive backup health report"""
        try:
            stats = backup_manager.get_backup_stats()
            
            # Get recent backup verification results
            recent_backups = DatabaseBackup.query.filter_by(status='COMPLETED').order_by(
                DatabaseBackup.created_at.desc()
            ).limit(10).all()
            
            verification_results = []
            for backup in recent_backups:
                verification = backup_manager.verify_backup(backup.id)
                verification_results.append({
                    'backup_id': backup.id,
                    'filename': backup.filename,
                    'valid': verification.get('valid', False),
                    'verified_at': datetime.now().isoformat()
                })
            
            # Calculate health metrics
            total_completed = stats.get('completed_backups', 0)
            valid_backups = sum(1 for v in verification_results if v['valid'])
            health_score = (valid_backups / total_completed * 100) if total_completed > 0 else 0
            
            return {
                'health_score': round(health_score, 2),
                'total_backups': stats.get('total_backups', 0),
                'completed_backups': total_completed,
                'valid_backups': valid_backups,
                'failed_backups': stats.get('failed_backups', 0),
                'total_size_mb': stats.get('total_size_mb', 0),
                'backup_types': stats.get('backup_types', {}),
                'recent_verifications': verification_results,
                'recommendations': BackupUtils._generate_recommendations(stats, verification_results),
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating backup health report: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def _generate_recommendations(stats: Dict[str, Any], verifications: List[Dict]) -> List[str]:
        """Generate backup recommendations"""
        recommendations = []
        
        # Check backup count
        if stats.get('total_backups', 0) < 5:
            recommendations.append("Consider creating more backups for better data protection")
        
        # Check failure rate
        total_backups = stats.get('total_backups', 0)
        failed_backups = stats.get('failed_backups', 0)
        if total_backups > 0 and (failed_backups / total_backups) > 0.1:
            recommendations.append("High backup failure rate detected - check storage space and permissions")
        
        # Check backup size
        if stats.get('total_size_mb', 0) > 1000:
            recommendations.append("Consider implementing backup rotation to manage storage usage")
        
        # Check verification results
        invalid_backups = sum(1 for v in verifications if not v['valid'])
        if invalid_backups > 0:
            recommendations.append(f"{invalid_backups} recent backups failed verification - check backup integrity")
        
        # Check backup types
        backup_types = stats.get('backup_types', {})
        if backup_types.get('FULL', 0) == 0:
            recommendations.append("No full backups found - create a full backup for complete data protection")
        
        return recommendations

# Initialize backup system
def initialize_backup_system():
    """Initialize backup system"""
    logger.info("Initializing backup system...")
    
    # Ensure backup directory exists
    backup_manager.backup_dir.mkdir(exist_ok=True)
    
    # Start backup scheduler
    scheduler = BackupScheduler(backup_manager)
    scheduler.start()
    
    logger.info("Backup system initialized")

if __name__ == "__main__":
    # Test backup system
    initialize_backup_system()
    
    # Test creating a backup
    try:
        backup = backup_manager.create_backup(
            backup_type='FULL',
            compression=True,
            description='Test backup'
        )
        print(f"Created backup: {backup.filename}")
        
        # Test verification
        verification = backup_manager.verify_backup(backup.id)
        print(f"Backup verification: {verification}")
        
        # Test stats
        stats = backup_manager.get_backup_stats()
        print(f"Backup stats: {stats}")
        
        # Test health report
        health = BackupUtils.get_backup_health_report()
        print(f"Backup health: {health}")
        
    except Exception as e:
        print(f"Backup test failed: {e}")