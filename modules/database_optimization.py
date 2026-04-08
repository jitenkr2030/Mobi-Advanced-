"""
Database Optimization Module
Provides indexing and query optimization utilities for the Mobi Invoice application
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from flask import current_app
from app import db

logger = logging.getLogger(__name__)

class DatabaseOptimizer:
    """Database optimization utilities for performance improvements"""
    
    def __init__(self):
        self.db_path = 'mobi_invoice.db'
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def analyze_query_performance(self, query: str, params: tuple = ()) -> Dict[str, Any]:
        """Analyze and optimize query performance"""
        with self.get_connection() as conn:
            # Enable query planning
            conn.execute("EXPLAIN QUERY PLAN " + query, params)
            plan = conn.fetchall()
            
            # Execute query with timing
            start_time = datetime.now()
            cursor = conn.execute(query, params)
            results = cursor.fetchall()
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                'query': query,
                'execution_time': execution_time,
                'result_count': len(results),
                'query_plan': [dict(row) for row in plan],
                'recommendations': self._analyze_query_plan(plan)
            }
    
    def _analyze_query_plan(self, plan: List[sqlite3.Row]) -> List[str]:
        """Analyze query plan and provide optimization recommendations"""
        recommendations = []
        
        for row in plan:
            detail = row['detail']
            
            if 'SCAN' in detail and 'TABLE' in detail:
                recommendations.append(f"Consider adding index on table mentioned in: {detail}")
            
            if 'TEMP B-TREE' in detail:
                recommendations.append("Query is using temporary B-tree - consider optimizing JOIN conditions")
            
            if 'SUBQUERY' in detail:
                recommendations.append("Consider rewriting subquery as JOIN if possible")
        
        return recommendations
    
    def create_performance_indexes(self):
        """Create indexes for performance optimization"""
        indexes = [
            # User-related indexes
            "CREATE INDEX IF NOT EXISTS idx_users_email_active ON users(email, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_users_role_created ON users(role, created_at)",
            
            # Customer-related indexes
            "CREATE INDEX IF NOT EXISTS idx_customers_user_name ON customers(user_id, name)",
            "CREATE INDEX IF NOT EXISTS idx_customers_email_active ON customers(email, user_id)",
            "CREATE INDEX IF NOT EXISTS idx_customers_group_created ON customers(group_id, created_at)",
            
            # Invoice-related indexes
            "CREATE INDEX IF NOT EXISTS idx_invoices_user_status ON invoices(user_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_customer_date ON invoices(customer_id, issue_date)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_number_user ON invoices(invoice_number, user_id)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_due_status ON invoices(due_date, status)",
            
            # Invoice items indexes
            "CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id)",
            "CREATE INDEX IF NOT EXISTS idx_invoice_items_product ON invoice_items(product_id)",
            
            # Payment indexes
            "CREATE INDEX IF NOT EXISTS idx_payments_invoice_date ON payments(invoice_id, payment_date)",
            
            # Quote indexes
            "CREATE INDEX IF NOT EXISTS idx_quotes_user_status ON quotes(user_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_quotes_customer_valid ON quotes(customer_id, valid_until)",
            
            # Recurring invoice indexes
            "CREATE INDEX IF NOT EXISTS idx_recurring_user_active ON recurring_invoices(user_id, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_recurring_next_gen ON recurring_invoices(next_generation, is_active)",
            
            # Session indexes
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_token ON user_sessions(user_id, token)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_expires_active ON user_sessions(expires_at, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_ip_address ON user_sessions(ip_address)",
            
            # Audit log indexes
            "CREATE INDEX IF NOT EXISTS idx_audit_user_timestamp ON audit_logs(user_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_audit_resource_timestamp ON audit_logs(resource, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_audit_action_timestamp ON audit_logs(action, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_audit_severity_timestamp ON audit_logs(severity, timestamp)",
            
            # Rate limiting indexes
            "CREATE INDEX IF NOT EXISTS idx_rate_limit_identifier_endpoint ON rate_limits(identifier, endpoint)",
            "CREATE INDEX IF NOT EXISTS idx_rate_limit_reset ON rate_limits(reset_at)",
            
            # Background job indexes
            "CREATE INDEX IF NOT EXISTS idx_jobs_status_priority ON background_jobs(status, priority)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_scheduled ON background_jobs(scheduled_at, status)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_type_status ON background_jobs(job_type, status)",
            
            # Notification indexes
            "CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_type_created ON notifications(notification_type, created_at)",
            
            # Login attempt indexes
            "CREATE INDEX IF NOT EXISTS idx_login_attempts_email_timestamp ON login_attempts(email, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_login_attempts_ip_timestamp ON login_attempts(ip_address, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_login_attempts_success_timestamp ON login_attempts(success, timestamp)",
            
            # Cache entry indexes
            "CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at)",
            
            # Backup indexes
            "CREATE INDEX IF NOT EXISTS idx_backups_type_status ON database_backups(backup_type, status)",
            "CREATE INDEX IF NOT EXISTS idx_backups_created ON database_backups(created_at)",
        ]
        
        with self.get_connection() as conn:
            for index_sql in indexes:
                try:
                    conn.execute(index_sql)
                    logger.info(f"Created index: {index_sql}")
                except sqlite3.Error as e:
                    logger.error(f"Failed to create index: {index_sql}. Error: {e}")
            
            conn.commit()
        
        logger.info("Database indexes creation completed")
    
    def analyze_table_statistics(self) -> Dict[str, Any]:
        """Analyze table statistics for optimization insights"""
        stats = {}
        
        tables = [
            'users', 'customers', 'products', 'invoices', 'invoice_items',
            'quotes', 'quote_items', 'recurring_invoices', 'recurring_invoice_items',
            'payments', 'user_sessions', 'audit_logs', 'background_jobs',
            'notifications', 'login_attempts', 'cache_entries'
        ]
        
        with self.get_connection() as conn:
            for table in tables:
                try:
                    # Get row count
                    cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
                    row_count = cursor.fetchone()['count']
                    
                    # Get table size (approximate)
                    cursor = conn.execute(f"SELECT COUNT(*) * AVG(LENGTH(CAST(* AS TEXT))) as size FROM {table}")
                    size_info = cursor.fetchone()
                    approx_size = size_info['size'] if size_info['size'] else 0
                    
                    # Get index information
                    cursor = conn.execute(f"PRAGMA index_list({table})")
                    indexes = cursor.fetchall()
                    
                    stats[table] = {
                        'row_count': row_count,
                        'approx_size_bytes': approx_size,
                        'index_count': len(indexes),
                        'indexes': [dict(idx) for idx in indexes]
                    }
                    
                except sqlite3.Error as e:
                    logger.error(f"Error analyzing table {table}: {e}")
                    stats[table] = {'error': str(e)}
        
        return stats
    
    def optimize_database(self):
        """Run database optimization commands"""
        with self.get_connection() as conn:
            try:
                # Analyze tables to update statistics
                tables = ['users', 'customers', 'products', 'invoices', 'invoice_items',
                         'quotes', 'quote_items', 'recurring_invoices', 'payments',
                         'user_sessions', 'audit_logs', 'background_jobs', 'notifications']
                
                for table in tables:
                    try:
                        conn.execute(f"ANALYZE {table}")
                        logger.info(f"Analyzed table: {table}")
                    except sqlite3.Error as e:
                        logger.error(f"Failed to analyze table {table}: {e}")
                
                # Vacuum the database to reclaim space
                conn.execute("VACUUM")
                logger.info("Database VACUUM completed")
                
                # Reindex the database
                conn.execute("REINDEX")
                logger.info("Database REINDEX completed")
                
                conn.commit()
                
            except sqlite3.Error as e:
                logger.error(f"Database optimization failed: {e}")
                conn.rollback()
                raise
    
    def get_slow_queries(self, min_execution_time: float = 1.0) -> List[Dict[str, Any]]:
        """Identify potentially slow queries based on execution time"""
        # This is a simplified version - in production, you'd use query logging
        common_slow_patterns = [
            "SELECT * FROM invoices WHERE",
            "SELECT * FROM customers WHERE",
            "SELECT * FROM audit_logs WHERE",
            "SELECT * FROM background_jobs WHERE"
        ]
        
        slow_queries = []
        
        with self.get_connection() as conn:
            for pattern in common_slow_patterns:
                try:
                    # Test common query patterns
                    test_query = pattern + " 1=1 LIMIT 10"
                    result = self.analyze_query_performance(test_query)
                    
                    if result['execution_time'] > min_execution_time:
                        result['pattern'] = pattern
                        slow_queries.append(result)
                        
                except sqlite3.Error as e:
                    logger.error(f"Error testing query pattern {pattern}: {e}")
        
        return slow_queries
    
    def create_partitioned_tables(self):
        """Create partitioned tables for large datasets (SQLite limited support)"""
        # SQLite has limited partitioning support, but we can create separate tables
        # for different time periods as a workaround
        
        with self.get_connection() as conn:
            # Create archive tables for old audit logs
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_logs_archive (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER,
                        action TEXT,
                        resource TEXT,
                        resource_id INTEGER,
                        old_values TEXT,
                        new_values TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        timestamp DATETIME,
                        severity TEXT
                    )
                """)
                
                # Create index on archive table
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_archive_timestamp 
                    ON audit_logs_archive(timestamp)
                """)
                
                conn.commit()
                logger.info("Archive tables created for partitioning")
                
            except sqlite3.Error as e:
                logger.error(f"Failed to create partitioned tables: {e}")
    
    def archive_old_data(self, days_to_keep: int = 90):
        """Archive old data to improve performance"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with self.get_connection() as conn:
            try:
                # Archive old audit logs
                cursor = conn.execute("""
                    INSERT INTO audit_logs_archive 
                    SELECT * FROM audit_logs 
                    WHERE timestamp < ?
                """, (cutoff_date,))
                
                archived_count = cursor.rowcount
                
                # Delete archived data from main table
                conn.execute("""
                    DELETE FROM audit_logs 
                    WHERE timestamp < ?
                """, (cutoff_date,))
                
                # Archive old login attempts
                conn.execute("""
                    DELETE FROM login_attempts 
                    WHERE timestamp < ?
                """, (cutoff_date,))
                
                # Clean up old cache entries
                conn.execute("""
                    DELETE FROM cache_entries 
                    WHERE expires_at < ?
                """, (datetime.now(),))
                
                # Clean up completed background jobs older than 30 days
                job_cutoff = datetime.now() - timedelta(days=30)
                conn.execute("""
                    DELETE FROM background_jobs 
                    WHERE status IN ('COMPLETED', 'FAILED') 
                    AND completed_at < ?
                """, (job_cutoff,))
                
                conn.commit()
                logger.info(f"Archived {archived_count} audit log entries")
                
                # Vacuum to reclaim space
                conn.execute("VACUUM")
                conn.commit()
                
            except sqlite3.Error as e:
                logger.error(f"Data archiving failed: {e}")
                conn.rollback()
                raise

# Global instance
db_optimizer = DatabaseOptimizer()

def initialize_database_optimization():
    """Initialize database optimization features"""
    logger.info("Initializing database optimization...")
    
    # Create performance indexes
    db_optimizer.create_performance_indexes()
    
    # Create archive tables for partitioning
    db_optimizer.create_partitioned_tables()
    
    # Optimize database
    try:
        db_optimizer.optimize_database()
    except Exception as e:
        logger.error(f"Database optimization failed: {e}")
    
    logger.info("Database optimization initialized")

def get_database_performance_report() -> Dict[str, Any]:
    """Generate comprehensive database performance report"""
    return {
        'table_statistics': db_optimizer.analyze_table_statistics(),
        'slow_queries': db_optimizer.get_slow_queries(),
        'timestamp': datetime.now().isoformat()
    }

# Schedule regular optimization tasks
def schedule_optimization_tasks():
    """Schedule regular database optimization tasks"""
    # This would be integrated with a task scheduler like Celery
    # For now, it's a placeholder for the concept
    pass

if __name__ == "__main__":
    # Test database optimization
    initialize_database_optimization()
    report = get_database_performance_report()
    print("Database Performance Report:")
    print(f"Generated at: {report['timestamp']}")
    for table, stats in report['table_statistics'].items():
        print(f"{table}: {stats.get('row_count', 0)} rows")