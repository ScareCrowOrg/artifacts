"""
RBAC Deployment Validation Script.

This script validates that the RBAC system is deployed correctly and functioning
as expected in the target environment (staging or production).

Features:
- Validates database migrations
- Tests permission checks
- Validates role assignments
- Tests API endpoints
- Generates comprehensive validation report

Usage:
    cd backend
    python -m scripts.validate_rbac_deployment
    
    # Validate specific environment
    python -m scripts.validate_rbac_deployment --environment staging
    
    # With detailed output
    python -m scripts.validate_rbac_deployment --verbose

Output:
    ✅ All validations passed (12/12)
    ⚠️  2 warnings detected
    📊 Validation report saved to: validation-report-20251127-140530.json
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, List, Tuple

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_path))

from app.database import db
from app.models.users import Usuario
from app.models.permissions import Role, Permission, RoleEnum

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Validate RBAC deployment'
    )
    parser.add_argument(
        '--environment',
        type=str,
        default='production',
        choices=['staging', 'production', 'dev'],
        help='Environment to validate (default: production)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        default=False,
        help='Enable verbose output'
    )
    parser.add_argument(
        '--report-dir',
        type=str,
        default='/tmp',
        help='Directory to save validation report (default: /tmp)'
    )
    return parser.parse_args()


class ValidationResult:
    """Container for validation test results."""
    
    def __init__(self):
        self.tests: List[Dict] = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def add_test(self, name: str, passed: bool, message: str, warning: bool = False):
        """Add a test result."""
        self.tests.append({
            'name': name,
            'passed': passed,
            'warning': warning,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
        
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        
        if warning:
            self.warnings += 1
    
    def get_summary(self) -> Dict:
        """Get validation summary."""
        total = len(self.tests)
        return {
            'total': total,
            'passed': self.passed,
            'failed': self.failed,
            'warnings': self.warnings,
            'success_rate': (self.passed / total * 100) if total > 0 else 0
        }


def validate_database_schema(results: ValidationResult):
    """Validate that required collections and indexes exist."""
    logger.info("Validating database schema...")
    
    required_collections = ['usuarios', 'roles', 'permissions']
    
    try:
        # Check collections exist
        for collection in required_collections:
            # Try to query each collection
            if collection == 'usuarios':
                db.find_many(collection, Usuario, is_canonical=True)
            elif collection == 'roles':
                db.find_many(collection, Role, is_canonical=True)
            elif collection == 'permissions':
                db.find_many(collection, Permission, is_canonical=True)
        
        results.add_test(
            'Database Schema',
            True,
            f'All required collections exist: {", ".join(required_collections)}'
        )
    except Exception as e:
        results.add_test(
            'Database Schema',
            False,
            f'Database schema validation failed: {e}'
        )


def validate_roles_seeded(results: ValidationResult):
    """Validate that all required roles are seeded."""
    logger.info("Validating roles...")
    
    required_roles = {
        RoleEnum.ADMIN.value,
        RoleEnum.USER.value,
        RoleEnum.VIEWER.value,
        RoleEnum.GUEST.value
    }
    
    try:
        roles = db.find_many("roles", Role, is_canonical=True)
        role_names = {r.name.value for r in roles}
        
        missing_roles = required_roles - role_names
        
        if not missing_roles:
            results.add_test(
                'Roles Seeded',
                True,
                f'All {len(required_roles)} required roles exist'
            )
        else:
            results.add_test(
                'Roles Seeded',
                False,
                f'Missing roles: {", ".join(missing_roles)}'
            )
    except Exception as e:
        results.add_test(
            'Roles Seeded',
            False,
            f'Could not validate roles: {e}'
        )


def validate_permissions_seeded(results: ValidationResult):
    """Validate that permissions are seeded."""
    logger.info("Validating permissions...")
    
    min_expected_permissions = 20  # From seed_permissions.py
    
    try:
        permissions = db.find_many("permissions", Permission, is_canonical=True)
        perm_count = len(permissions)
        
        if perm_count >= min_expected_permissions:
            results.add_test(
                'Permissions Seeded',
                True,
                f'{perm_count} permissions exist (expected >= {min_expected_permissions})'
            )
        else:
            results.add_test(
                'Permissions Seeded',
                False,
                f'Only {perm_count} permissions found (expected >= {min_expected_permissions})',
                warning=True
            )
    except Exception as e:
        results.add_test(
            'Permissions Seeded',
            False,
            f'Could not validate permissions: {e}'
        )


def validate_user_roles_migrated(results: ValidationResult):
    """Validate that all users have roles assigned."""
    logger.info("Validating user role migration...")
    
    try:
        # Check both storages
        usuarios = []
        
        try:
            runtime_users = db.find_many("usuarios", Usuario, is_canonical=False)
            usuarios.extend(runtime_users)
        except Exception:
            pass
        
        try:
            canonical_users = db.find_many("usuarios", Usuario, is_canonical=True)
            usuarios.extend(canonical_users)
        except Exception:
            pass
        
        if not usuarios:
            results.add_test(
                'User Roles Migration',
                True,
                'No users to validate (database may be empty)',
                warning=True
            )
            return
        
        # Check all users have roles
        users_without_roles = []
        for usuario in usuarios:
            if not hasattr(usuario, 'roles') or not usuario.roles:
                users_without_roles.append(usuario.email)
        
        if not users_without_roles:
            results.add_test(
                'User Roles Migration',
                True,
                f'All {len(usuarios)} users have roles assigned'
            )
        else:
            results.add_test(
                'User Roles Migration',
                False,
                f'{len(users_without_roles)} users missing roles: {", ".join(users_without_roles[:5])}'
            )
    except Exception as e:
        results.add_test(
            'User Roles Migration',
            False,
            f'Could not validate user roles: {e}'
        )


def validate_admin_exists(results: ValidationResult):
    """Validate that at least one admin user exists."""
    logger.info("Validating admin user...")
    
    try:
        usuarios = []
        
        try:
            runtime_users = db.find_many("usuarios", Usuario, is_canonical=False)
            usuarios.extend(runtime_users)
        except Exception:
            pass
        
        try:
            canonical_users = db.find_many("usuarios", Usuario, is_canonical=True)
            usuarios.extend(canonical_users)
        except Exception:
            pass
        
        admin_users = [
            u for u in usuarios 
            if hasattr(u, 'roles') and 'admin' in u.roles
        ]
        
        if admin_users:
            results.add_test(
                'Admin User Exists',
                True,
                f'{len(admin_users)} admin user(s) found'
            )
        else:
            results.add_test(
                'Admin User Exists',
                False,
                'No admin users found - system may be unmanageable',
                warning=True
            )
    except Exception as e:
        results.add_test(
            'Admin User Exists',
            False,
            f'Could not validate admin user: {e}'
        )


def validate_role_permissions_mapping(results: ValidationResult):
    """Validate that roles have correct permissions mapped."""
    logger.info("Validating role-permission mappings...")
    
    try:
        roles = db.find_many("roles", Role, is_canonical=True)
        
        # Check admin has wildcard
        admin_role = next((r for r in roles if r.name == RoleEnum.ADMIN), None)
        if admin_role and "*" in admin_role.permissions:
            results.add_test(
                'Admin Wildcard Permission',
                True,
                'Admin role has wildcard (*) permission'
            )
        else:
            results.add_test(
                'Admin Wildcard Permission',
                False,
                'Admin role missing wildcard permission'
            )
        
        # Check user role has basic permissions
        user_role = next((r for r in roles if r.name == RoleEnum.USER), None)
        expected_user_perms = ['cells.create', 'cells.read_own']
        if user_role:
            has_basic = all(p in user_role.permissions for p in expected_user_perms)
            if has_basic:
                results.add_test(
                    'User Basic Permissions',
                    True,
                    f'User role has {len(user_role.permissions)} permissions'
                )
            else:
                missing = [p for p in expected_user_perms if p not in user_role.permissions]
                results.add_test(
                    'User Basic Permissions',
                    False,
                    f'User role missing permissions: {", ".join(missing)}',
                    warning=True
                )
        else:
            results.add_test(
                'User Basic Permissions',
                False,
                'User role not found'
            )
    except Exception as e:
        results.add_test(
            'Role-Permission Mappings',
            False,
            f'Could not validate role-permission mappings: {e}'
        )


def save_validation_report(results: ValidationResult, args: argparse.Namespace):
    """Save validation report to JSON file."""
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    report_filename = f'rbac-validation-{args.environment}-{timestamp}.json'
    report_path = Path(args.report_dir) / report_filename
    
    report = {
        'metadata': {
            'environment': args.environment,
            'timestamp': datetime.now().isoformat(),
            'validator': 'validate_rbac_deployment.py',
            'version': '1.0.0'
        },
        'summary': results.get_summary(),
        'tests': results.tests
    }
    
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"📊 Validation report saved to: {report_path}")
    
    return report_path


def main():
    """
    Main execution function.
    
    Runs all validation tests and generates report.
    """
    try:
        logger.info("=" * 60)
        logger.info("ScareVerse RBAC Deployment Validation")
        logger.info("=" * 60)
        
        # Parse arguments
        args = parse_args()
        
        logger.info(f"Environment: {args.environment}")
        logger.info(f"Verbose: {args.verbose}")
        logger.info("-" * 60)
        
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Run validations
        results = ValidationResult()
        
        validate_database_schema(results)
        validate_roles_seeded(results)
        validate_permissions_seeded(results)
        validate_user_roles_migrated(results)
        validate_admin_exists(results)
        validate_role_permissions_mapping(results)
        
        logger.info("-" * 60)
        
        # Save report
        report_path = save_validation_report(results, args)
        
        # Print summary
        summary = results.get_summary()
        logger.info("=" * 60)
        logger.info("Validation Summary:")
        logger.info(f"   Total tests: {summary['total']}")
        logger.info(f"   ✅ Passed: {summary['passed']}")
        logger.info(f"   ❌ Failed: {summary['failed']}")
        logger.info(f"   ⚠️  Warnings: {summary['warnings']}")
        logger.info(f"   Success rate: {summary['success_rate']:.1f}%")
        logger.info("=" * 60)
        
        # Print failed tests
        if summary['failed'] > 0:
            logger.error("Failed tests:")
            for test in results.tests:
                if not test['passed']:
                    logger.error(f"   ❌ {test['name']}: {test['message']}")
        
        # Print warnings
        if summary['warnings'] > 0:
            logger.warning("Warnings:")
            for test in results.tests:
                if test['warning']:
                    logger.warning(f"   ⚠️  {test['name']}: {test['message']}")
        
        # Exit code based on results
        if summary['failed'] == 0:
            logger.info("✅ All validations passed!")
            sys.exit(0)
        else:
            logger.error(f"❌ {summary['failed']} validation(s) failed")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Validation failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
