"""
Role-Based Access Control (RBAC) Module
Provides comprehensive user permissions and role management
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Set
from enum import Enum
from functools import wraps
from flask import g, abort, current_app, request
from app import db, User, UserRoleAssignment

logger = logging.getLogger(__name__)

class Permission(Enum):
    """System permissions"""
    # User management
    USER_READ = "users.read"
    USER_CREATE = "users.create"
    USER_UPDATE = "users.update"
    USER_UPDATE_OWN = "users.update.own"
    USER_DELETE = "users.delete"
    
    # Customer management
    CUSTOMER_READ = "customers.read"
    CUSTOMER_CREATE = "customers.create"
    CUSTOMER_UPDATE = "customers.update"
    CUSTOMER_UPDATE_OWN = "customers.update.own"
    CUSTOMER_DELETE = "customers.delete"
    CUSTOMER_DELETE_OWN = "customers.delete.own"
    
    # Invoice management
    INVOICE_READ = "invoices.read"
    INVOICE_CREATE = "invoices.create"
    INVOICE_UPDATE = "invoices.update"
    INVOICE_UPDATE_OWN = "invoices.update.own"
    INVOICE_DELETE = "invoices.delete"
    INVOICE_DELETE_OWN = "invoices.delete.own"
    
    # Product management
    PRODUCT_READ = "products.read"
    PRODUCT_CREATE = "products.create"
    PRODUCT_UPDATE = "products.update"
    PRODUCT_DELETE = "products.delete"
    
    # Quote management
    QUOTE_READ = "quotes.read"
    QUOTE_CREATE = "quotes.create"
    QUOTE_UPDATE = "quotes.update"
    QUOTE_DELETE = "quotes.delete"
    
    # Report management
    REPORT_READ = "reports.read"
    REPORT_CREATE = "reports.create"
    REPORT_EXPORT = "reports.export"
    
    # System administration
    SYSTEM_BACKUP = "system.backup"
    SYSTEM_RESTORE = "system.restore"
    SYSTEM_CONFIG = "system.config"
    SYSTEM_MONITOR = "system.monitor"
    
    # Audit and security
    AUDIT_READ = "audit.read"
    AUDIT_EXPORT = "audit.export"
    SECURITY_2FA_MANAGE = "security.2fa.manage"
    SECURITY_RATE_LIMIT_MANAGE = "security.rate_limit.manage"
    
    # Role management
    ROLE_READ = "roles.read"
    ROLE_ASSIGN = "roles.assign"
    ROLE_MANAGE = "roles.manage"
    
    # Session management
    SESSION_READ = "sessions.read"
    SESSION_MANAGE = "sessions.manage"
    SESSION_MANAGE_OWN = "sessions.manage.own"
    
    # Notification management
    NOTIFICATION_READ = "notifications.read"
    NOTIFICATION_SEND = "notifications.send"
    NOTIFICATION_MANAGE_OWN = "notifications.manage.own"

class Role(Enum):
    """System roles"""
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    USER = "USER"
    VIEWER = "VIEWER"

class RoleDefinition:
    """Defines role permissions"""
    
    ROLES = {
        Role.ADMIN: {
            'name': 'Administrator',
            'description': 'Full system access with all permissions',
            'permissions': ['*'],  # Wildcard for all permissions
            'is_system': True
        },
        Role.MANAGER: {
            'name': 'Manager',
            'description': 'Can manage users, content, and view system information',
            'permissions': [
                Permission.USER_READ.value,
                Permission.USER_CREATE.value,
                Permission.USER_UPDATE.value,
                Permission.CUSTOMER_READ.value,
                Permission.CUSTOMER_CREATE.value,
                Permission.CUSTOMER_UPDATE.value,
                Permission.CUSTOMER_DELETE.value,
                Permission.INVOICE_READ.value,
                Permission.INVOICE_CREATE.value,
                Permission.INVOICE_UPDATE.value,
                Permission.INVOICE_DELETE.value,
                Permission.PRODUCT_READ.value,
                Permission.PRODUCT_CREATE.value,
                Permission.PRODUCT_UPDATE.value,
                Permission.PRODUCT_DELETE.value,
                Permission.QUOTE_READ.value,
                Permission.QUOTE_CREATE.value,
                Permission.QUOTE_UPDATE.value,
                Permission.QUOTE_DELETE.value,
                Permission.REPORT_READ.value,
                Permission.REPORT_CREATE.value,
                Permission.REPORT_EXPORT.value,
                Permission.SESSION_READ.value,
                Permission.SESSION_MANAGE.value,
                Permission.NOTIFICATION_READ.value,
                Permission.NOTIFICATION_SEND.value,
                Permission.SECURITY_2FA_MANAGE.value,
                Permission.SYSTEM_MONITOR.value,
                Permission.AUDIT_READ.value,
            ],
            'is_system': True
        },
        Role.USER: {
            'name': 'User',
            'description': 'Standard user with content creation and self-management',
            'permissions': [
                Permission.USER_READ.value,
                Permission.USER_UPDATE_OWN.value,
                Permission.CUSTOMER_READ.value,
                Permission.CUSTOMER_CREATE.value,
                Permission.CUSTOMER_UPDATE_OWN.value,
                Permission.CUSTOMER_DELETE_OWN.value,
                Permission.INVOICE_READ.value,
                Permission.INVOICE_CREATE.value,
                Permission.INVOICE_UPDATE_OWN.value,
                Permission.INVOICE_DELETE_OWN.value,
                Permission.PRODUCT_READ.value,
                Permission.PRODUCT_CREATE.value,
                Permission.PRODUCT_UPDATE.value,
                Permission.PRODUCT_DELETE.value,
                Permission.QUOTE_READ.value,
                Permission.QUOTE_CREATE.value,
                Permission.QUOTE_UPDATE.value,
                Permission.QUOTE_DELETE.value,
                Permission.REPORT_READ.value,
                Permission.REPORT_CREATE.value,
                Permission.SESSION_MANAGE_OWN.value,
                Permission.NOTIFICATION_READ.value,
                Permission.NOTIFICATION_MANAGE_OWN.value,
            ],
            'is_system': True
        },
        Role.VIEWER: {
            'name': 'Viewer',
            'description': 'Read-only access to public content',
            'permissions': [
                Permission.USER_READ.value,
                Permission.CUSTOMER_READ.value,
                Permission.INVOICE_READ.value,
                Permission.PRODUCT_READ.value,
                Permission.QUOTE_READ.value,
                Permission.REPORT_READ.value,
            ],
            'is_system': True
        }
    }

class RBACManager:
    """Manages role-based access control"""
    
    def __init__(self):
        self.role_definitions = RoleDefinition.ROLES
    
    def assign_role(self, user_id: int, role: Role, assigned_by: int, 
                   additional_permissions: List[str] = None,
                   expires_at: datetime = None) -> UserRoleAssignment:
        """
        Assign role to user
        
        Args:
            user_id: User ID to assign role to
            role: Role to assign
            assigned_by: User ID making the assignment
            additional_permissions: Additional permissions beyond role defaults
            expires_at: Optional expiration date for role assignment
        
        Returns:
            UserRoleAssignment object
        """
        # Validate role
        if role not in Role:
            raise ValueError(f"Invalid role: {role}")
        
        # Create role assignment
        assignment = UserRoleAssignment(
            user_id=user_id,
            role=role.value,
            permissions=json.dumps(additional_permissions or []),
            assigned_by=assigned_by,
            expires_at=expires_at
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        logger.info(f"Role {role.value} assigned to user {user_id} by user {assigned_by}")
        return assignment
    
    def remove_role(self, user_id: int, role: Role, removed_by: int) -> bool:
        """
        Remove role from user
        
        Args:
            user_id: User ID to remove role from
            role: Role to remove
            removed_by: User ID removing the role
        
        Returns:
            True if role removed successfully
        """
        assignment = UserRoleAssignment.query.filter_by(
            user_id=user_id,
            role=role.value
        ).first()
        
        if not assignment:
            return False
        
        db.session.delete(assignment)
        db.session.commit()
        
        logger.info(f"Role {role.value} removed from user {user_id} by user {removed_by}")
        return True
    
    def get_user_roles(self, user_id: int) -> List[UserRoleAssignment]:
        """Get all role assignments for user"""
        return UserRoleAssignment.query.filter_by(user_id=user_id).all()
    
    def get_user_permissions(self, user_id: int) -> Set[str]:
        """
        Get all effective permissions for user
        
        Args:
            user_id: User ID
        
        Returns:
            Set of permission strings
        """
        permissions = set()
        
        # Get user's role assignments
        assignments = self.get_user_roles(user_id)
        
        for assignment in assignments:
            # Skip expired assignments
            if assignment.expires_at and assignment.expires_at < datetime.utcnow():
                continue
            
            # Get role definition
            role = Role(assignment.role)
            role_def = self.role_definitions.get(role)
            
            if role_def:
                # Add role permissions
                role_permissions = role_def['permissions']
                
                # Handle wildcard permission
                if '*' in role_permissions:
                    # Add all available permissions
                    permissions.update(p.value for p in Permission)
                else:
                    permissions.update(role_permissions)
                
                # Add additional permissions from assignment
                if assignment.permissions:
                    try:
                        additional_perms = json.loads(assignment.permissions)
                        permissions.update(additional_perms)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid permissions JSON for user {user_id}")
        
        return permissions
    
    def has_permission(self, user_id: int, permission: str) -> bool:
        """
        Check if user has specific permission
        
        Args:
            user_id: User ID
            permission: Permission to check
        
        Returns:
            True if user has permission
        """
        user_permissions = self.get_user_permissions(user_id)
        
        # Check for wildcard permission
        if '*' in user_permissions:
            return True
        
        # Check for exact permission match
        if permission in user_permissions:
            return True
        
        # Check for wildcard resource permissions (e.g., 'users.*')
        resource = permission.split('.')[0]
        wildcard_permission = f"{resource}.*"
        if wildcard_permission in user_permissions:
            return True
        
        return False
    
    def has_any_permission(self, user_id: int, permissions: List[str]) -> bool:
        """Check if user has any of the specified permissions"""
        return any(self.has_permission(user_id, perm) for perm in permissions)
    
    def has_all_permissions(self, user_id: int, permissions: List[str]) -> bool:
        """Check if user has all specified permissions"""
        return all(self.has_permission(user_id, perm) for perm in permissions)
    
    def get_users_with_permission(self, permission: str) -> List[User]:
        """Get all users who have a specific permission"""
        users_with_permission = []
        
        users = User.query.filter_by(is_active=True).all()
        for user in users:
            if self.has_permission(user.id, permission):
                users_with_permission.append(user)
        
        return users_with_permission
    
    def get_role_definition(self, role: Role) -> Dict[str, Any]:
        """Get role definition"""
        return self.role_definitions.get(role, {})
    
    def get_all_roles(self) -> Dict[str, Dict[str, Any]]:
        """Get all available roles"""
        return {role.value: definition for role, definition in self.role_definitions.items()}
    
    def cleanup_expired_assignments(self) -> int:
        """Clean up expired role assignments"""
        expired_count = UserRoleAssignment.query.filter(
            UserRoleAssignment.expires_at < datetime.utcnow()
        ).delete()
        
        db.session.commit()
        logger.info(f"Cleaned up {expired_count} expired role assignments")
        return expired_count

# RBAC decorators
def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user') or not g.user:
                abort(401)
            
            if not rbac.has_permission(g.user.id, permission):
                abort(403, f"Permission required: {permission}")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_any_permission(permissions: List[str]):
    """Decorator to require any of the specified permissions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user') or not g.user:
                abort(401)
            
            if not rbac.has_any_permission(g.user.id, permissions):
                abort(403, f"One of these permissions required: {', '.join(permissions)}")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_all_permissions(permissions: List[str]):
    """Decorator to require all specified permissions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user') or not g.user:
                abort(401)
            
            if not rbac.has_all_permissions(g.user.id, permissions):
                abort(403, f"All these permissions required: {', '.join(permissions)}")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_role(role: Role):
    """Decorator to require specific role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user') or not g.user:
                abort(401)
            
            user_roles = rbac.get_user_roles(g.user.id)
            has_role = any(assignment.role == role.value for assignment in user_roles)
            
            if not has_role:
                abort(403, f"Role required: {role.value}")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_any_role(roles: List[Role]):
    """Decorator to require any of the specified roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user') or not g.user:
                abort(401)
            
            user_roles = rbac.get_user_roles(g.user.id)
            role_values = {assignment.role for assignment in user_roles}
            required_values = {role.value for role in roles}
            
            if not role_values.intersection(required_values):
                required_names = [role.value for role in roles]
                abort(403, f"One of these roles required: {', '.join(required_names)}")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Resource ownership checking
def check_ownership(resource_type: str, resource_id: int, user_id: int) -> bool:
    """
    Check if user owns the resource
    
    Args:
        resource_type: Type of resource (customer, invoice, etc.)
        resource_id: ID of the resource
        user_id: User ID to check ownership against
    
    Returns:
        True if user owns the resource
    """
    try:
        if resource_type == 'customer':
            from app import Customer
            resource = Customer.query.get(resource_id)
            return resource and resource.user_id == user_id
        
        elif resource_type == 'invoice':
            from app import Invoice
            resource = Invoice.query.get(resource_id)
            return resource and resource.user_id == user_id
        
        elif resource_type == 'quote':
            from app import Quote
            resource = Quote.query.get(resource_id)
            return resource and resource.user_id == user_id
        
        elif resource_type == 'product':
            from app import Product
            resource = Product.query.get(resource_id)
            return resource and resource.user_id == user_id
        
        return False
    except Exception as e:
        logger.error(f"Error checking ownership: {e}")
        return False

def require_ownership(resource_type: str, resource_id_param: str = 'id'):
    """Decorator to require resource ownership"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user') or not g.user:
                abort(401)
            
            # Get resource ID from request
            resource_id = request.view_args.get(resource_id_param) or request.args.get(resource_id_param)
            if not resource_id:
                abort(400, "Resource ID not provided")
            
            try:
                resource_id = int(resource_id)
            except ValueError:
                abort(400, "Invalid resource ID")
            
            # Check ownership
            if not check_ownership(resource_type, resource_id, g.user.id):
                abort(403, "You don't have permission to access this resource")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# RBAC utilities
class RBACUtils:
    """Utility functions for RBAC management"""
    
    @staticmethod
    def get_user_effective_permissions(user_id: int) -> Dict[str, Any]:
        """Get comprehensive permission information for user"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'error': 'User not found'}
            
            # Get role assignments
            assignments = rbac.get_user_roles(user_id)
            
            # Get permissions
            permissions = rbac.get_user_permissions(user_id)
            
            # Get role details
            role_details = []
            for assignment in assignments:
                role = Role(assignment.role)
                role_def = rbac.get_role_definition(role)
                role_details.append({
                    'role': role.value,
                    'role_name': role_def.get('name', role.value),
                    'assigned_at': assignment.assigned_at.isoformat(),
                    'expires_at': assignment.expires_at.isoformat() if assignment.expires_at else None,
                    'additional_permissions': json.loads(assignment.permissions) if assignment.permissions else []
                })
            
            return {
                'user_id': user_id,
                'user_email': user.email,
                'user_role': user.role,
                'role_assignments': role_details,
                'permissions': list(permissions),
                'permission_count': len(permissions),
                'has_wildcard': '*' in permissions
            }
            
        except Exception as e:
            logger.error(f"Error getting user permissions: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def get_rbac_statistics() -> Dict[str, Any]:
        """Get RBAC system statistics"""
        try:
            total_users = User.query.count()
            active_users = User.query.filter_by(is_active=True).count()
            
            # Get role assignment statistics
            role_stats = {}
            for role in Role:
                count = UserRoleAssignment.query.filter_by(role=role.value).count()
                role_stats[role.value] = count
            
            # Get permission coverage
            total_assignments = UserRoleAssignment.query.count()
            expired_assignments = UserRoleAssignment.query.filter(
                UserRoleAssignment.expires_at < datetime.utcnow()
            ).count()
            active_assignments = total_assignments - expired_assignments
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'total_role_assignments': total_assignments,
                'active_role_assignments': active_assignments,
                'expired_role_assignments': expired_assignments,
                'role_distribution': role_stats,
                'available_roles': len(Role),
                'available_permissions': len(Permission)
            }
            
        except Exception as e:
            logger.error(f"Error getting RBAC statistics: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def validate_permission_hierarchy() -> Dict[str, Any]:
        """Validate permission hierarchy and consistency"""
        try:
            issues = []
            
            # Check for duplicate permissions in role definitions
            all_permissions = set()
            for role, definition in RoleDefinition.ROLES.items():
                perms = definition.get('permissions', [])
                if '*' in perms:
                    continue
                
                for perm in perms:
                    if perm in all_permissions:
                        issues.append(f"Duplicate permission '{perm}' found in role {role.value}")
                    all_permissions.add(perm)
            
            # Check for invalid permissions
            valid_permissions = {p.value for p in Permission}
            invalid_perms = all_permissions - valid_permissions
            for perm in invalid_perms:
                issues.append(f"Invalid permission '{perm}' found in role definitions")
            
            return {
                'valid': len(issues) == 0,
                'issues': issues,
                'total_permissions_checked': len(all_permissions),
                'valid_permissions': len(valid_permissions)
            }
            
        except Exception as e:
            logger.error(f"Error validating permission hierarchy: {e}")
            return {'valid': False, 'error': str(e)}

# Global RBAC manager instance
rbac = RBACManager()

# Initialize RBAC system
def initialize_rbac(app):
    """Initialize RBAC system"""
    logger.info("Initializing RBAC system...")
    
    # Schedule cleanup of expired assignments
    import threading
    import time
    
    def cleanup_task():
        while True:
            try:
                rbac.cleanup_expired_assignments()
            except Exception as e:
                logger.error(f"RBAC cleanup error: {e}")
            time.sleep(24 * 60 * 60)  # Run daily
    
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()
    
    logger.info("RBAC system initialized")

if __name__ == "__main__":
    # Test RBAC functionality
    print("Testing RBAC system...")
    
    try:
        # Test role definitions
        all_roles = rbac.get_all_roles()
        print(f"Available roles: {list(all_roles.keys())}")
        
        # Test permission checking
        test_user_id = 1
        
        # Check if user has permission (would depend on database state)
        has_perm = rbac.has_permission(test_user_id, Permission.USER_READ.value)
        print(f"User {test_user_id} has USER_READ permission: {has_perm}")
        
        # Test RBAC utilities
        stats = RBACUtils.get_rbac_statistics()
        print(f"RBAC statistics: {stats}")
        
        # Test permission validation
        validation = RBACUtils.validate_permission_hierarchy()
        print(f"Permission validation: {validation}")
        
    except Exception as e:
        print(f"RBAC test failed: {e}")
        import traceback
        traceback.print_exc()