#!/bin/bash
#
# RBAC Deployment Automation Script
#
# This script automates the deployment of the RBAC system to staging or production
# environments, following the deployment runbook and best practices.
#
# Features:
# - Pre-deployment validation
# - Database backup
# - Migration execution
# - Canary deployment
# - Post-deployment validation
# - Rollback on failure
#
# Usage:
#   ./deploy_rbac.sh --environment staging
#   ./deploy_rbac.sh --environment production --confirm
#
# Options:
#   --environment <env>  Target environment (staging|production) [required]
#   --skip-backup        Skip database backup (not recommended)
#   --skip-tests         Skip pre-deployment tests
#   --confirm            Skip confirmation prompts
#   --canary-percent     Canary deployment percentage (default: 10)
#   --help               Show this help message

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$BACKEND_DIR/.." && pwd)"

# Default values
ENVIRONMENT=""
SKIP_BACKUP=false
SKIP_TESTS=false
CONFIRM=false
CANARY_PERCENT=10
BACKUP_DIR="/backups"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --skip-backup)
      SKIP_BACKUP=true
      shift
      ;;
    --skip-tests)
      SKIP_TESTS=true
      shift
      ;;
    --confirm)
      CONFIRM=true
      shift
      ;;
    --canary-percent)
      CANARY_PERCENT="$2"
      shift 2
      ;;
    --help)
      grep '^#' "$0" | tail -n +2 | sed 's/^# //g; s/^#//g'
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Validate required arguments
if [ -z "$ENVIRONMENT" ]; then
  echo -e "${RED}Error: --environment is required${NC}"
  echo "Use --help for usage information"
  exit 1
fi

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(staging|production)$ ]]; then
  echo -e "${RED}Error: Invalid environment '$ENVIRONMENT' (must be staging or production)${NC}"
  exit 1
fi

# Logging functions
log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
  echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
  echo ""
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}$1${NC}"
  echo -e "${GREEN}========================================${NC}"
}

# Confirmation function
confirm_action() {
  if [ "$CONFIRM" = true ]; then
    return 0
  fi
  
  echo -e "${YELLOW}$1${NC}"
  read -p "Continue? (yes/no): " response
  if [[ ! "$response" =~ ^(yes|y)$ ]]; then
    log_warning "Deployment cancelled by user"
    exit 0
  fi
}

# Main deployment flow
main() {
  log_step "RBAC Deployment to $ENVIRONMENT"
  
  log_info "Deployment configuration:"
  log_info "  Environment: $ENVIRONMENT"
  log_info "  Skip backup: $SKIP_BACKUP"
  log_info "  Skip tests: $SKIP_TESTS"
  log_info "  Canary percent: $CANARY_PERCENT%"
  
  # Confirmation
  confirm_action "⚠️  You are about to deploy RBAC to $ENVIRONMENT"
  
  # Phase 1: Pre-deployment validation
  log_step "Phase 1: Pre-deployment Validation"
  
  if [ "$SKIP_TESTS" = false ]; then
    log_info "Running pre-deployment tests..."
    cd "$BACKEND_DIR"
    python -m pytest tests/ -k "rbac or permission" --tb=short || {
      log_error "Pre-deployment tests failed"
      exit 1
    }
    log_success "Pre-deployment tests passed"
  else
    log_warning "Skipping pre-deployment tests (--skip-tests)"
  fi
  
  # Phase 2: Database backup
  log_step "Phase 2: Database Backup"
  
  if [ "$SKIP_BACKUP" = false ]; then
    log_info "Creating database backup..."
    cd "$BACKEND_DIR"
    python -m scripts.backup_mongodb --backup-dir "$BACKUP_DIR" || {
      log_error "Database backup failed"
      exit 1
    }
    log_success "Database backup completed"
    
    # Save backup path for potential rollback
    BACKUP_PATH=$(ls -td "$BACKUP_DIR"/pre-rbac-migration-* | head -1)
    log_info "Backup saved to: $BACKUP_PATH"
  else
    log_warning "Skipping database backup (--skip-backup)"
  fi
  
  # Phase 3: Execute migrations
  log_step "Phase 3: Database Migrations"
  
  log_info "Seeding permissions and roles..."
  cd "$BACKEND_DIR"
  python -m scripts.seed_permissions || {
    log_error "Permission seeding failed"
    log_error "Consider restoring backup: python -m scripts.restore_mongodb --backup-path $BACKUP_PATH --drop --confirm"
    exit 1
  }
  log_success "Permissions and roles seeded"
  
  log_info "Migrating user roles..."
  python -m scripts.migrate_user_roles || {
    log_error "User role migration failed"
    log_error "Consider restoring backup: python -m scripts.restore_mongodb --backup-path $BACKUP_PATH --drop --confirm"
    exit 1
  }
  log_success "User roles migrated"
  
  # Phase 4: Deploy backend
  log_step "Phase 4: Backend Deployment"
  
  if [ "$ENVIRONMENT" = "production" ]; then
    log_info "Deploying backend with canary strategy ($CANARY_PERCENT%)..."
    
    # Apply canary deployment
    kubectl apply -f "$PROJECT_ROOT/infrastructure/local/kubernetes/deployments/backend-canary.yaml" -n production || {
      log_error "Canary deployment failed"
      exit 1
    }
    
    # Calculate canary replicas (assume 10 total pods)
    TOTAL_PODS=10
    CANARY_REPLICAS=$((TOTAL_PODS * CANARY_PERCENT / 100))
    if [ $CANARY_REPLICAS -lt 1 ]; then
      CANARY_REPLICAS=1
    fi
    
    log_info "Scaling canary deployment to $CANARY_REPLICAS replicas..."
    kubectl scale deployment/backend-canary --replicas=$CANARY_REPLICAS -n production
    
    log_info "Waiting for canary deployment to be ready..."
    kubectl rollout status deployment/backend-canary -n production --timeout=5m || {
      log_error "Canary deployment failed to become ready"
      exit 1
    }
    log_success "Canary deployment ready"
    
    log_info "Monitoring canary for 5 minutes..."
    log_info "Check Grafana dashboard: https://grafana.scareverse.com/d/rbac"
    sleep 300  # 5 minutes
    
    confirm_action "Canary deployment looks healthy. Proceed with full rollout?"
    
    log_info "Scaling canary to 100%..."
    kubectl scale deployment/backend-canary --replicas=$TOTAL_PODS -n production
    kubectl rollout status deployment/backend-canary -n production --timeout=10m
    
  else
    # Staging: Direct deployment
    log_info "Deploying backend to staging..."
    kubectl set image deployment/backend backend=scareverse/backend:rbac-v1 -n staging || {
      log_error "Backend deployment failed"
      exit 1
    }
    kubectl rollout status deployment/backend -n staging --timeout=5m
  fi
  
  log_success "Backend deployment completed"
  
  # Phase 5: Post-deployment validation
  log_step "Phase 5: Post-deployment Validation"
  
  log_info "Running validation tests..."
  cd "$BACKEND_DIR"
  python -m scripts.validate_rbac_deployment --environment "$ENVIRONMENT" || {
    log_error "Post-deployment validation failed"
    log_error "Consider rollback: See docs/permissions/rollback-plan.md"
    exit 1
  }
  log_success "Post-deployment validation passed"
  
  # Phase 6: Health checks
  log_step "Phase 6: Health Checks"
  
  if [ "$ENVIRONMENT" = "production" ]; then
    HEALTH_URL="https://api.scareverse.com/api/health/ready"
  else
    HEALTH_URL="http://staging.scareverse.com/api/health/ready"
  fi
  
  log_info "Checking backend health..."
  for i in {1..5}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
      log_success "Backend health check passed (HTTP $HTTP_CODE)"
      break
    else
      log_warning "Health check attempt $i/5 failed (HTTP $HTTP_CODE)"
      if [ $i -eq 5 ]; then
        log_error "Backend health checks failed after 5 attempts"
        exit 1
      fi
      sleep 10
    fi
  done
  
  # Final success message
  log_step "Deployment Complete"
  
  log_success "RBAC system successfully deployed to $ENVIRONMENT!"
  echo ""
  log_info "Next steps:"
  log_info "  1. Monitor Grafana dashboard for 2 hours"
  log_info "  2. Check error rates and latency"
  log_info "  3. Validate user access"
  log_info "  4. Keep backup available for 24 hours"
  echo ""
  log_info "Dashboard: https://grafana.scareverse.com/d/rbac"
  log_info "Rollback plan: $PROJECT_ROOT/docs/permissions/rollback-plan.md"
  
  if [ -n "${BACKUP_PATH:-}" ]; then
    log_info "Backup location: $BACKUP_PATH"
  fi
}

# Execute main function
main "$@"
