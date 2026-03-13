#!/usr/bin/env python3
"""
Conversation Trace Verification Script

This script verifies that the conversation tracing infrastructure is properly configured:
1. Checks if ENABLE_CONVERSATION_TRACING is set
2. Verifies book-conversation-traces-v1 exists in database
3. Verifies conversation-trace-item type exists in database
4. Tests trace cell creation and fragment recording
5. Displays sample trace data

Usage:
    python3 backend/scripts/verify_conversation_trace.py
"""

import sys
import os
import asyncio
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


async def verify_configuration():
    """Verify conversation trace configuration."""
    # Import configuration (done here to ensure backend app context is loaded)
    from app.config import ENABLE_CONVERSATION_TRACING
    
    logger.info("=" * 70)
    logger.info("CONVERSATION TRACE CONFIGURATION VERIFICATION")
    logger.info("=" * 70)
    
    logger.info(f"\n1. Configuration Check:")
    logger.info(f"   ENABLE_CONVERSATION_TRACING = {ENABLE_CONVERSATION_TRACING}")
    
    if not ENABLE_CONVERSATION_TRACING:
        logger.warning(
            "   ⚠️  WARNING: Tracing is DISABLED globally. "
            "Set ENABLE_CONVERSATION_TRACING=true in .env to enable."
        )
    else:
        logger.info("   ✓ Tracing is ENABLED globally")
    
    return ENABLE_CONVERSATION_TRACING


async def verify_database_objects():
    """Verify trace book and item type exist in database."""
    from app.database import db
    from app.models.content import Livro, NotebookItemType
    
    logger.info(f"\n2. Database Objects Check:")
    
    # Check trace book
    trace_book_id = "book-conversation-traces-v1"
    trace_book = db.find_one("books", trace_book_id, Livro, is_canonical=True)
    
    if trace_book:
        logger.info(f"   ✓ Trace book '{trace_book_id}' exists")
        logger.info(f"     - Name: {trace_book.name}")
        logger.info(f"     - Type: {trace_book.tipo}")
        # Check for system book flag - may not be defined in older versions
        is_system_book = hasattr(trace_book, 'is_canonical_system_book') and trace_book.is_canonical_system_book
        logger.info(f"     - Is system book: {is_system_book}")
    else:
        logger.error(f"   ✗ Trace book '{trace_book_id}' NOT FOUND in database!")
        logger.error("     Run: POST /api/system/seed-data to initialize system books")
        return False
    
    # Check trace item type
    trace_type_id = "conversation-trace-item"
    trace_type = db.find_one("notebook_item_types", trace_type_id, NotebookItemType, is_canonical=True)
    
    if trace_type:
        logger.info(f"   ✓ Trace item type '{trace_type_id}' exists")
        logger.info(f"     - Name: {trace_type.name}")
        logger.info(f"     - Description: {trace_type.description}")
    else:
        logger.error(f"   ✗ Trace item type '{trace_type_id}' NOT FOUND in database!")
        logger.error("     Run: POST /api/system/seed-data to initialize item types")
        return False
    
    return True


async def test_trace_creation():
    """Test creating a trace cell and recording fragments."""
    from app.services.conversation_trace_service import get_conversation_trace_service
    
    logger.info(f"\n3. Trace Creation Test:")
    
    trace_service = get_conversation_trace_service()
    
    if not trace_service.is_tracing_enabled():
        logger.warning("   ⚠️  SKIP: Tracing is disabled, cannot test trace creation")
        return False
    
    # Generate test conversation ID
    test_conv_id = trace_service.generate_conversation_id(session_id="test_session")
    logger.info(f"   Generated conversation ID: {test_conv_id}")
    
    # Create trace cell
    logger.info(f"   Creating trace cell...")
    trace_cell = await trace_service.create_trace_cell(
        conversation_id=test_conv_id,
        assignee_id="system",
        session_id="test_session",
        user_message="Test message for trace verification",
        target_llm="ollama"
    )
    
    if not trace_cell:
        logger.error("   ✗ FAILED: Could not create trace cell")
        return False
    
    logger.info(f"   ✓ Created trace cell: {trace_cell.id}")
    
    # Record test fragment
    logger.info(f"   Recording test fragment...")
    success = await trace_service.record_fragment(
        trace_cell_id=trace_cell.id,
        stage="test_stage",
        data={
            "test": True,
            "message": "This is a test fragment",
            "timestamp_check": "verify_script"
        },
        conversation_id=test_conv_id
    )
    
    if not success:
        logger.error("   ✗ FAILED: Could not record fragment")
        return False
    
    logger.info(f"   ✓ Recorded test fragment")
    
    # Verify fragment was stored
    from app.database import db
    from app.models.content import Celula
    
    logger.info(f"   Verifying fragment persistence...")
    updated_cell = db.find_one("celulas", trace_cell.id, Celula, is_canonical=False)
    
    if updated_cell and len(updated_cell.fragments) > 0:
        logger.info(f"   ✓ Fragment verified in database")
        logger.info(f"     - Total fragments: {len(updated_cell.fragments)}")
        logger.info(f"     - Last fragment stage: {updated_cell.fragments[-1]['stage']}")
        logger.info(f"     - Fragment data: {updated_cell.fragments[-1]['data']}")
    else:
        logger.error("   ✗ FAILED: Fragment not found in database after recording")
        return False
    
    # Cleanup: Delete test trace cell
    logger.info(f"   Cleaning up test data...")
    db.delete("celulas", trace_cell.id, is_canonical=False)
    logger.info(f"   ✓ Test trace cell deleted")
    
    return True


async def display_existing_traces():
    """Display any existing trace cells."""
    from app.database import db
    from app.models.content import Celula
    
    logger.info(f"\n4. Existing Trace Cells:")
    
    try:
        # Query all cells of type conversation-trace-item
        all_cells = db.find("celulas", Celula, is_canonical=False)
        trace_cells = [
            cell for cell in all_cells 
            if cell.notebook_item_type_id == "conversation-trace-item"
        ]
        
        if not trace_cells:
            logger.info("   No existing trace cells found")
        else:
            logger.info(f"   Found {len(trace_cells)} trace cell(s):")
            for cell in trace_cells[:5]:  # Show first 5
                conv_id = cell.initial_data.get('conversation_id', 'N/A')
                fragments_count = len(cell.fragments) if cell.fragments else 0
                logger.info(f"   - Cell ID: {cell.id}")
                logger.info(f"     Conversation: {conv_id}")
                logger.info(f"     Fragments: {fragments_count}")
                if fragments_count > 0:
                    stages = [f['stage'] for f in cell.fragments]
                    logger.info(f"     Stages: {', '.join(stages)}")
    
    except Exception as e:
        logger.error(f"   ✗ Error querying existing trace cells from database: {e}")


async def main():
    """Main verification routine."""
    try:
        # Step 1: Verify configuration
        config_ok = await verify_configuration()
        
        # Step 2: Verify database objects
        db_ok = await verify_database_objects()
        
        if not db_ok:
            logger.error("\n❌ FAILED: Database objects not found. Run system seed data first.")
            return 1
        
        # Step 3: Test trace creation (if enabled)
        if config_ok:
            test_ok = await test_trace_creation()
            if not test_ok:
                logger.error("\n❌ FAILED: Trace creation test failed.")
                return 1
        
        # Step 4: Display existing traces
        await display_existing_traces()
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        if config_ok and db_ok:
            logger.info("✓ Conversation tracing is FULLY OPERATIONAL")
            logger.info("\nTo use tracing in API requests, set:")
            logger.info("  {")
            logger.info('    "enable_tracing": true,')
            logger.info('    "message": "your message"')
            logger.info("  }")
        elif db_ok:
            logger.info("⚠️  Database objects exist, but tracing is DISABLED")
            logger.info("\nTo enable tracing, set in .env:")
            logger.info("  ENABLE_CONVERSATION_TRACING=true")
        else:
            logger.info("❌ Conversation tracing is NOT operational")
            logger.info("\nRun: POST /api/system/seed-data")
        
        logger.info("=" * 70)
        
        return 0
    
    except Exception as e:
        logger.error(f"\n❌ Verification failed with error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
