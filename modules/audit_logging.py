"""
Audit Logging Module
Provides comprehensive system change tracking and security auditing
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
from functools import wraps
from flask import g, request, current_app
from app import db, AuditLog, User

logger = logging.getLogger(__name__)

class AuditAction(Enum):
    """Audit action types"""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    PASSWORD_RESET = "PASSWORD_RESET"
    2FA_ENABLED = "2FA_ENABLED"
    2FA_DISABLED = "2FA_DISABLED"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    ROLE_REMOVED = "ROLE_REMOVED"
    PERMISSION_GRANTED = "PERMISSION_GRANTED"
    PERMISSION_REVOKED = "PERMISSION_REVOKED"
    BACKUP_CREATED = "BACKUP_CREATED"
    BACKUP_RESTORED = "BACKUP_RESTORED"
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    SYSTEM_CONFIG = "SYSTEM_CONFIG"
    SECURITY_EVENT = "SECURITY_EVENT"

class AuditResource(Enum):
    """Audit resource types"""
    USER = "USER"
    CUSTOMER = "CUSTOMER"
    INVOICE = "INVOICE"
    QUOTE = "QUOTE"
    PRODUCT = "PRODUCT"
    PAYMENT = "PAYMENT"
    ROLE = "ROLE"
    SESSION = "SESSION"
    BACKUP = "BACKUP"
    SYSTEM = "SYSTEM"
    AUTHENTICATION = "AUTHENTICATION"
    SECURITY = "SECURITY"

class AuditSeverity(Enum):
    """Audit log severity levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class AuditLogger:
    """Manages audit logging functionality"""
    
    def __init__(self):
        self.sensitive_fields = [
            'password', 'password_hash', 'two_factor_secret', 
            'token', 'secret', 'key', 'credit_card', 'ssn'
        ]
    
    def log(self, user_id: Optional[int], action: AuditAction, resource: AuditResource,
            resource_id: Optional[int] = None, old_values: Optional[Dict] = None,
            new_values: Optional[Dict] = None, severity: AuditSeverity = AuditSeverity.INFO,
            metadata: Optional[Dict] = None) -> AuditLog:
        """
        Create an audit log entry
        
        Args:
            user_id: User ID performing the action
            action: Action performed
            resource: Resource type
            resource_id: ID of the resource
            old_values: Previous values (for updates)
            new_values: New values
            severity: Log severity level
            metadata: Additional metadata
        
        Returns:
            AuditLog object
        """
        try:
            # Sanitize sensitive data
            safe_old_values = self._sanitize_data(old_values) if old_values else None
            safe_new_values = self._sanitize_data(new_values) if new_values else None
            
            # Get request context
            ip_address = self._get_client_ip()
            user_agent = request.headers.get('User-Agent') if request else None
            
            # Create audit log entry
            audit_log = AuditLog(
                user_id=user_id,
                action=action.value,
                resource=resource.value,
                resource_id=resource_id,
                old_values=json.dumps(safe_old_values) if safe_old_values else None,
                new_values=json.dumps(safe_new_values) if safe_new_values else None,
                ip_address=ip_address,
                user_agent=user_agent,
                severity=severity.value,
                timestamp=datetime.utcnow()
            )
            
            db.session.add(audit_log)
            db.session.commit()
            
            logger.debug(f"Audit log created: {action.value} on {resource.value}")
            return audit_log
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            db.session.rollback()
            raise
    
    def log_user_action(self, user_id: int, action: AuditAction, resource: AuditResource,
                       resource_id: Optional[int] = None, changes: Optional[Dict] = None) -> AuditLog:
        """Log user action with automatic severity determination"""
        severity = self._determine_severity(action, resource)
        return self.log(user_id, action, resource, resource_id, 
                      changes.get('old') if changes else None,
                      changes.get('new') if changes else None,
                      severity)
    
    def log_system_action(self, action: AuditAction, resource: AuditResource,
                         details: Optional[Dict] = None, severity: AuditSeverity = AuditSeverity.INFO) -> AuditLog:
        """Log system action (no user context)"""
        return self.log(None, action, resource, None, None, details, severity)
    
    def log_security_event(self, event_type: str, details: Dict[str, Any], 
                          user_id: Optional[int] = None, severity: AuditSeverity = AuditSeverity.WARNING) -> AuditLog:
        """Log security-related event"""
        metadata = {
            'event_type': event_type,
            'details': details
        }
        
        return self.log(user_id, AuditAction.SECURITY_EVENT, AuditResource.SECURITY,
                       None, None, None, severity, metadata)
    
    def log_authentication_event(self, action: AuditAction, user_id: Optional[int] = None,
                               email: Optional[str] = None, reason: Optional[str] = None) -> AuditLog:
        """Log authentication event"""
        metadata = {}
        if email:
            metadata['email'] = email
        if reason:
            metadata['reason'] = reason
        
        severity = AuditSeverity.WARNING if action == AuditAction.LOGIN_FAILED else AuditSeverity.INFO
        return self.log(user_id, action, AuditResource.AUTHENTICATION, None, None, None, severity, metadata)
    
    def log_data_access(self, user_id: int, resource: AuditResource, resource_id: int,
                       access_type: str = 'READ') -> AuditLog:
        """Log data access event"""
        metadata = {'access_type': access_type}
        severity = AuditSeverity.WARNING if access_type in ['EXPORT', 'DOWNLOAD'] else AuditSeverity.INFO
        
        return self.log(user_id, AuditAction(action=access_type), resource, resource_id,
                       None, None, severity, metadata)
    
    def _sanitize_data(self, data: Dict) -> Dict:
        """Remove sensitive data from audit logs"""
        if not data:
            return {}
        
        sanitized = {}
        for key, value in data.items():
            if any(field in key.lower() for field in self.sensitive_fields):
                sanitized[key] = '[REDACTED]'
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
            elif isinstance(value, list):
                sanitized[key] = [self._sanitize_data(item) if isinstance(item, dict) else item for item in value]
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _get_client_ip(self) -> Optional[str]:
        """Get client IP address"""
        if not request:
            return None
        
        # Check various headers for IP address
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.remote_addr
    
    def _determine_severity(self, action: AuditAction, resource: AuditResource) -> AuditSeverity:
        """Determine appropriate severity level"""
        critical_actions = {AuditAction.DELETE, AuditAction.LOGIN_FAILED, AuditAction.SECURITY_EVENT}
        critical_resources = {AuditResource.USER, AuditResource.ROLE, AuditResource.SYSTEM}
        
        if action in critical_actions or resource in critical_resources:
            if action == AuditAction.DELETE and resource in critical_resources:
                return AuditSeverity.CRITICAL
            return AuditSeverity.WARNING
        
        return AuditSeverity.INFO
    
    def get_audit_logs(self, user_id: Optional[int] = None, action: Optional[AuditAction] = None,
                      resource: Optional[AuditResource] = None, severity: Optional[AuditSeverity] = None,
                      start_date: Optional[datetime] = None, end_date: Optional[datetime] = None,
                      limit: int = 100, offset: int = 0) -> List[AuditLog]:
        """Get audit logs with filtering"""
        query = AuditLog.query
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        if action:
            query = query.filter_by(action=action.value)
        if resource:
            query = query.filter_by(resource=resource.value)
        if severity:
            query = query.filter_by(severity=severity.value)
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        return query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
    
    def get_audit_log_by_id(self, log_id: int) -> Optional[AuditLog]:
        """Get specific audit log by ID"""
        return AuditLog.query.get(log_id)
    
    def get_audit_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get audit log statistics"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Total logs
            total_logs = AuditLog.query.filter(AuditLog.timestamp >= start_date).count()
            
            # Logs by action
            action_stats = db.session.query(
                AuditLog.action,
                db.func.count(AuditLog.id)
            ).filter(AuditLog.timestamp >= start_date).group_by(AuditLog.action).all()
            
            logs_by_action = {action: count for action, count in action_stats}
            
            # Logs by resource
            resource_stats = db.session.query(
                AuditLog.resource,
                db.func.count(AuditLog.id)
            ).filter(AuditLog.timestamp >= start_date).group_by(AuditLog.resource).all()
            
            logs_by_resource = {resource: count for resource, count in resource_stats}
            
            # Logs by severity
            severity_stats = db.session.query(
                AuditLog.severity,
                db.func.count(AuditLog.id)
            ).filter(AuditLog.timestamp >= start_date).group_by(AuditLog.severity).all()
            
            logs_by_severity = {severity: count for severity, count in severity_stats}
            
            # Top users by activity
            user_stats = db.session.query(
                AuditLog.user_id,
                db.func.count(AuditLog.id)
            ).filter(
                AuditLog.timestamp >= start_date,
                AuditLog.user_id.isnot(None)
            ).group_by(AuditLog.user_id).order_by(db.func.count(AuditLog.id).desc()).limit(10).all()
            
            top_users = []
            for user_id, count in user_stats:
                user = User.query.get(user_id)
                top_users.append({
                    'user_id': user_id,
                    'user_email': user.email if user else 'Unknown',
                    'action_count': count
                })
            
            # Recent critical events
            critical_logs = AuditLog.query.filter(
                AuditLog.timestamp >= start_date,
                AuditLog.severity.in_(['WARNING', 'ERROR', 'CRITICAL'])
            ).order_by(AuditLog.timestamp.desc()).limit(10).all()
            
            recent_critical = []
            for log in critical_logs:
                recent_critical.append({
                    'id': log.id,
                    'action': log.action,
                    'resource': log.resource,
                    'severity': log.severity,
                    'timestamp': log.timestamp.isoformat(),
                    'user_id': log.user_id,
                    'ip_address': log.ip_address
                })
            
            return {
                'period_days': days,
                'total_logs': total_logs,
                'logs_by_action': logs_by_action,
                'logs_by_resource': logs_by_resource,
                'logs_by_severity': logs_by_severity,
                'top_active_users': top_users,
                'recent_critical_events': recent_critical,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating audit statistics: {e}")
            return {'error': str(e)}
    
    def export_audit_logs(self, start_date: datetime, end_date: datetime,
                         user_id: Optional[int] = None, format: str = 'json') -> str:
        """Export audit logs for specified period"""
        try:
            logs = self.get_audit_logs(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                limit=10000  # Limit export size
            )
            
            export_data = {
                'export_info': {
                    'generated_at': datetime.utcnow().isoformat(),
                    'period': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat()
                    },
                    'user_id': user_id,
                    'total_logs': len(logs),
                    'format': format
                },
                'logs': []
            }
            
            for log in logs:
                log_data = {
                    'id': log.id,
                    'user_id': log.user_id,
                    'action': log.action,
                    'resource': log.resource,
                    'resource_id': log.resource_id,
                    'old_values': json.loads(log.old_values) if log.old_values else None,
                    'new_values': json.loads(log.new_values) if log.new_values else None,
                    'ip_address': log.ip_address,
                    'user_agent': log.user_agent,
                    'severity': log.severity,
                    'timestamp': log.timestamp.isoformat()
                }
                export_data['logs'].append(log_data)
            
            if format == 'json':
                return json.dumps(export_data, indent=2)
            else:
                # Could add CSV, XML export formats
                return json.dumps(export_data, indent=2)
                
        except Exception as e:
            logger.error(f"Error exporting audit logs: {e}")
            raise
    
    def cleanup_old_logs(self, days_to_keep: int = 365) -> int:
        """Clean up old audit logs"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            deleted_count = AuditLog.query.filter(
                AuditLog.timestamp < cutoff_date
            ).delete()
            
            db.session.commit()
            logger.info(f"Cleaned up {deleted_count} old audit logs")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Audit log cleanup failed: {e}")
            db.session.rollback()
            return 0

# Global audit logger instance
audit_logger = AuditLogger()

# Audit decorators
def audit_action(action: AuditAction, resource: AuditResource, 
                get_resource_id: Optional[callable] = None):
    """Decorator to automatically audit function calls"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get user ID from context
            user_id = g.user.id if hasattr(g, 'user') and g.user else None
            
            # Get resource ID if function provided
            resource_id = None
            if get_resource_id:
                try:
                    resource_id = get_resource_id(*args, **kwargs)
                except Exception:
                    pass
            
            # For update operations, try to get old values
            old_values = None
            if action == AuditAction.UPDATE and resource_id:
                try:
                    old_values = _get_old_values(resource, resource_id)
                except Exception:
                    pass
            
            # Execute the function
            result = f(*args, **kwargs)
            
            # Get new values for create/update operations
            new_values = None
            if action in [AuditAction.CREATE, AuditAction.UPDATE]:
                try:
                    new_values = _get_new_values(result)
                except Exception:
                    pass
            
            # Log the action
            changes = None
            if old_values or new_values:
                changes = {'old': old_values, 'new': new_values}
            
            audit_logger.log_user_action(user_id, action, resource, resource_id, changes)
            
            return result
        return decorated_function
    return decorator

def audit_login_success(user_id: int):
    """Audit successful login"""
    audit_logger.log_authentication_event(AuditAction.LOGIN, user_id)

def audit_login_failure(email: str, reason: str = None):
    """Audit failed login"""
    audit_logger.log_authentication_event(AuditAction.LOGIN_FAILED, email=email, reason=reason)

def audit_logout(user_id: int):
    """Audit logout"""
    audit_logger.log_authentication_event(AuditAction.LOGOUT, user_id)

def audit_password_change(user_id: int):
    """Audit password change"""
    audit_logger.log_authentication_event(AuditAction.PASSWORD_CHANGE, user_id)

def audit_2fa_change(user_id: int, enabled: bool):
    """Audit 2FA enable/disable"""
    action = AuditAction.2FA_ENABLED if enabled else AuditAction.2FA_DISABLED
    audit_logger.log_authentication_event(action, user_id)

# Helper functions for audit decorators
def _get_old_values(resource: AuditResource, resource_id: int) -> Optional[Dict]:
    """Get old values before update"""
    try:
        if resource == AuditResource.USER:
            from app import User
            obj = User.query.get(resource_id)
            if obj:
                return {
                    'email': obj.email,
                    'name': obj.name,
                    'role': obj.role,
                    'is_active': obj.is_active
                }
        
        elif resource == AuditResource.CUSTOMER:
            from app import Customer
            obj = Customer.query.get(resource_id)
            if obj:
                return {
                    'name': obj.name,
                    'email': obj.email,
                    'phone': obj.phone
                }
        
        # Add more resource types as needed
        return None
    except Exception as e:
        logger.error(f"Error getting old values: {e}")
        return None

def _get_new_values(result) -> Optional[Dict]:
    """Get new values from function result"""
    try:
        if hasattr(result, '__dict__'):
            # For SQLAlchemy objects
            obj_dict = result.__dict__.copy()
            obj_dict.pop('_sa_instance_state', None)
            return obj_dict
        elif isinstance(result, dict):
            return result
        return None
    except Exception as e:
        logger.error(f"Error getting new values: {e}")
        return None

# Audit utilities
class AuditUtils:
    """Utility functions for audit management"""
    
    @staticmethod
    def get_security_report(days: int = 7) -> Dict[str, Any]:
        """Generate security-focused audit report"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Security events
            security_logs = AuditLog.query.filter(
                AuditLog.timestamp >= start_date,
                AuditLog.resource == AuditResource.SECURITY.value
            ).all()
            
            # Failed logins
            failed_logins = AuditLog.query.filter(
                AuditLog.timestamp >= start_date,
                AuditLog.action == AuditAction.LOGIN_FAILED.value
            ).all()
            
            # Password changes
            password_changes = AuditLog.query.filter(
                AuditLog.timestamp >= start_date,
                AuditLog.action == AuditAction.PASSWORD_CHANGE.value
            ).all()
            
            # 2FA changes
            two_fa_changes = AuditLog.query.filter(
                AuditLog.timestamp >= start_date,
                AuditLog.action.in_([AuditAction.2FA_ENABLED.value, AuditAction.2FA_DISABLED.value])
            ).all()
            
            # Role changes
            role_changes = AuditLog.query.filter(
                AuditLog.timestamp >= start_date,
                AuditLog.action.in_([AuditAction.ROLE_ASSIGNED.value, AuditAction.ROLE_REMOVED.value])
            ).all()
            
            # Suspicious IP addresses (multiple failed logins)
            failed_by_ip = {}
            for log in failed_logins:
                ip = log.ip_address
                if ip:
                    failed_by_ip[ip] = failed_by_ip.get(ip, 0) + 1
            
            suspicious_ips = {ip: count for ip, count in failed_by_ip.items() if count > 5}
            
            return {
                'period_days': days,
                'security_events': len(security_logs),
                'failed_logins': len(failed_logins),
                'password_changes': len(password_changes),
                'two_fa_changes': len(two_fa_changes),
                'role_changes': len(role_changes),
                'suspicious_ips': suspicious_ips,
                'security_score': max(0, 100 - len(failed_logins) - len(suspicious_ips) * 2),
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating security report: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def get_compliance_report(days: int = 30) -> Dict[str, Any]:
        """Generate compliance-focused audit report"""
        try:
            stats = audit_logger.get_audit_statistics(days)
            
            # Compliance checks
            compliance_issues = []
            
            # Check for critical events
            critical_events = stats.get('logs_by_severity', {}).get('CRITICAL', 0)
            if critical_events > 0:
                compliance_issues.append(f"{critical_events} critical events detected")
            
            # Check for excessive failed logins
            failed_logins = stats.get('logs_by_action', {}).get('LOGIN_FAILED', 0)
            if failed_logins > 100:
                compliance_issues.append(f"High number of failed logins: {failed_logins}")
            
            # Check for user management without audit
            user_actions = stats.get('logs_by_action', {}).get('CREATE', 0) + \
                          stats.get('logs_by_action', {}).get('DELETE', 0)
            if user_actions == 0:
                compliance_issues.append("No user management activities detected")
            
            return {
                'period_days': days,
                'compliance_score': max(0, 100 - len(compliance_issues) * 10),
                'compliance_issues': compliance_issues,
                'total_audit_events': stats.get('total_logs', 0),
                'critical_events': critical_events,
                'failed_login_attempts': failed_logins,
                'data_access_events': stats.get('logs_by_action', {}).get('READ', 0),
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating compliance report: {e}")
            return {'error': str(e)}

# Initialize audit system
def initialize_audit_system(app):
    """Initialize audit system"""
    logger.info("Initializing audit system...")
    
    # Schedule cleanup of old logs
    import threading
    import time
    
    def cleanup_task():
        while True:
            try:
                audit_logger.cleanup_old_logs()
            except Exception as e:
                logger.error(f"Audit cleanup error: {e}")
            time.sleep(24 * 60 * 60)  # Run daily
    
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()
    
    logger.info("Audit system initialized")

if __name__ == "__main__":
    # Test audit functionality
    print("Testing audit system...")
    
    try:
        # Test basic logging
        log = audit_logger.log(
            user_id=1,
            action=AuditAction.CREATE,
            resource=AuditResource.USER,
            resource_id=1,
            new_values={'email': 'test@example.com', 'name': 'Test User'},
            severity=AuditSeverity.INFO
        )
        print(f"Created audit log: {log.id}")
        
        # Test security event logging
        security_log = audit_logger.log_security_event(
            'SUSPICIOUS_LOGIN',
            {'ip': '192.168.1.1', 'user_agent': 'Test Agent'},
            user_id=1,
            severity=AuditSeverity.WARNING
        )
        print(f"Created security log: {security_log.id}")
        
        # Test authentication logging
        audit_login_success(1)
        audit_login_failure('test@example.com', 'Invalid password')
        print("Authentication events logged")
        
        # Test statistics
        stats = audit_logger.get_audit_statistics(days=7)
        print(f"Audit statistics: {stats}")
        
        # Test security report
        security_report = AuditUtils.get_security_report(days=7)
        print(f"Security report: {security_report}")
        
        # Test compliance report
        compliance_report = AuditUtils.get_compliance_report(days=30)
        print(f"Compliance report: {compliance_report}")
        
    except Exception as e:
        print(f"Audit test failed: {e}")
        import traceback
        traceback.print_exc()