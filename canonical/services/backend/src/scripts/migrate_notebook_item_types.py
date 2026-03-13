"""
Migration script to create NotebookItemType entries from existing TipoCelula entries.

This script:
1. Fetches all existing TipoCelula entries
2. Creates corresponding NotebookItemType entries
3. Ensures backward compatibility

Run this script once after deploying the NotebookItemType changes.
"""

import sys
import logging
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_path))

from app.models import TipoCelula, NotebookItemType
from app.database import db

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_tipos_celula_to_notebook_item_types():
    """
    Migrate existing TipoCelula entries to NotebookItemType.
    
    For each TipoCelula:
    - Create a corresponding NotebookItemType
    - Map python_refs, docs_refs, etc. to default_refs
    - Set allow_instance_override_refs to True (default behavior)
    """
    logger.info("Starting migration: TipoCelula -> NotebookItemType")
    
    try:
        # Fetch all existing TipoCelula entries
        tipos_celula = db.find_many("cell_types", TipoCelula, is_canonical=True)
        
        logger.info(f"Found {len(tipos_celula)} TipoCelula entries")
        
        if not tipos_celula:
            logger.warning("No TipoCelula entries found. Creating a default entry for testing.")
            # Create a default ingestion cell type
            default_tipo = TipoCelula(
                name="Ingestion Cell",
                descricao="Cell for document ingestion and processing",
                category="persistida",
                icon="file-document",
                python_refs=["app.workflows.ingestion_graph"],
                versao="1.0.0"
            )
            db.insert("cell_types", default_tipo, usuario_id="system", sessao_id="migration", is_canonical=True)
            tipos_celula = [default_tipo]
            logger.info("Created default TipoCelula")
        
        migrated_count = 0
        skipped_count = 0
        
        for tipo_celula in tipos_celula:
            try:
                # Check if NotebookItemType already exists with this ID
                existing_type = db.find_one(
                    "notebook_item_types",
                    tipo_celula.id,
                    NotebookItemType,
                    is_canonical=True
                )
                
                if existing_type:
                    logger.info(f"NotebookItemType already exists for {tipo_celula.name}, skipping")
                    skipped_count += 1
                    continue
                
                # Build default_refs from TipoCelula refs
                default_refs = {}
                
                if tipo_celula.python_refs:
                    # The first python_ref that ends with 'graph.py' is likely the workflow
                    workflow_refs = [ref for ref in tipo_celula.python_refs if ref.endswith('graph.py')]
                    if workflow_refs:
                        default_refs["workflow_graph"] = workflow_refs
                    
                    # Add all python refs
                    default_refs["python"] = tipo_celula.python_refs
                
                if tipo_celula.docs_refs:
                    default_refs["docs"] = tipo_celula.docs_refs
                
                if tipo_celula.javascript_refs:
                    default_refs["javascript"] = tipo_celula.javascript_refs
                
                if tipo_celula.yaml_refs:
                    default_refs["yaml"] = tipo_celula.yaml_refs
                
                if tipo_celula.attachment_refs:
                    default_refs["attachments"] = tipo_celula.attachment_refs
                
                # Create NotebookItemType
                notebook_item_type = NotebookItemType(
                    id=tipo_celula.id,  # Use same ID for backward compatibility
                    name=tipo_celula.name,
                    description=tipo_celula.descricao,
                    default_refs=default_refs,
                    default_initial_data={},  # No default initial data from TipoCelula
                    allow_instance_override_refs=True  # Allow overrides by default
                )
                
                # Insert into database
                db.insert(
                    "notebook_item_types",
                    notebook_item_type,
                    usuario_id="system",
                    sessao_id="migration",
                    is_canonical=True
                )
                
                logger.info(f"Migrated TipoCelula '{tipo_celula.name}' to NotebookItemType")
                migrated_count += 1
                
            except Exception as e:
                logger.error(f"Error migrating TipoCelula {tipo_celula.id}: {e}")
        
        logger.info(f"Migration complete: {migrated_count} migrated, {skipped_count} skipped")
        return migrated_count, skipped_count
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


def create_default_book_type():
    """Create a default NotebookItemType for books."""
    logger.info("Creating default NotebookItemType for books")
    
    try:
        # Check if default book type already exists
        existing = db.find_many("notebook_item_types", NotebookItemType, is_canonical=True)
        book_types = [t for t in existing if "book" in t.name.lower() or "livro" in t.name.lower()]
        
        if book_types:
            logger.info("Default book type already exists, skipping")
            return
        
        # Create default book type
        book_type = NotebookItemType(
            name="Standard Book",
            description="Standard book type for organizing cells",
            default_refs={},
            default_initial_data={},
            allow_instance_override_refs=True
        )
        
        db.insert(
            "notebook_item_types",
            book_type,
            usuario_id="system",
            sessao_id="migration",
            is_canonical=True
        )
        
        logger.info(f"Created default book type: {book_type.id}")
        
    except Exception as e:
        logger.error(f"Error creating default book type: {e}")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("NotebookItemType Migration Script")
    logger.info("=" * 60)
    
    try:
        # Migrate TipoCelula entries
        migrate_tipos_celula_to_notebook_item_types()
        
        # Create default book type
        create_default_book_type()
        
        logger.info("=" * 60)
        logger.info("Migration completed successfully!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error("Migration failed!")
        logger.error(str(e))
        sys.exit(1)
