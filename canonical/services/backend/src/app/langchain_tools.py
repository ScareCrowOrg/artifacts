"""
LangChain Tools for ScareVerse

Defines LangChain tools for interacting with cells and books:
- criar_celula: Creates a new cell
- executar_celula: Executes an existing cell
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.tools import Tool

from .database import db
from .models import (
    Cell,
    CellStatus,
    NotebookItemType,
)

logger = logging.getLogger(__name__)


class CellTools:
    """LangChain tools for cell operations."""

    @staticmethod
    async def criar_celula_impl(
        responsavel_id: str,
        tipo_celula_id: Optional[str] = None,
        dados_iniciais: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Internal implementation to create a new cell.

        Args:
            responsavel_id: User ID responsible for the cell
            tipo_celula_id: Optional cell type ID. If not provided, uses first available.
            dados_iniciais: Optional initial data for the cell

        Returns:
            Dictionary with cell creation result
        """
        try:
            # Get available cell types if not specified
            if not tipo_celula_id:
                notebook_item_types = db.find_many(
                    "notebook_item_types", NotebookItemType, is_canonical=True
                )
                if not notebook_item_types:
                    return {
                        "success": False,
                        "error": "Nenhum notebook item type disponível",
                    }
                tipo_celula_id = notebook_item_types[0].id

            # Verify that the cell type exists
            notebook_item_type = db.find_one(
                "notebook_item_types",
                tipo_celula_id,
                NotebookItemType,
                is_canonical=True,
            )

            if not notebook_item_type:
                return {
                    "success": False,
                    "error": f"NotebookItemType {tipo_celula_id} não encontrado",
                }

            # Create new cell (using notebook_item_type_id, not tipoCelulaId)
            celula = Cell(
                assignee_id=responsavel_id, notebook_item_type_id=tipo_celula_id
            )

            # Add initial data as a memory fragment if provided
            if dados_iniciais:
                # Create fragment as a dict (supports Union[str, Dict])
                fragmento = {"tipo": "memoria", "conteudo": str(dados_iniciais)}
                celula.fragments.append(fragmento)

            # Store cell
            db.insert("cells", celula, current_user=SYSTEM_USER)

            logger.info("Célula %s criada com sucesso pelo LangChain", celula.id)

            return {
                "success": True,
                "celula_id": celula.id,
                "tipo_celula_id": tipo_celula_id,
                "estado": celula.status.value,
                "message": f"Célula criada com sucesso: {celula.id}",
            }

        except Exception as e:
            logger.error("Erro ao criar célula via LangChain: %s", e)
            return {"success": False, "error": f"Erro ao criar célula: {str(e)}"}

    @staticmethod
    async def executar_celula_impl(
        celula_id: str, dados_execucao: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Internal implementation to execute a cell.

        Args:
            celula_id: ID of the cell to execute
            dados_execucao: Optional execution data/parameters

        Returns:
            Dictionary with execution result
        """
        try:
            # Find the cell
            celula = db.find_one("cells", celula_id, Cell, is_canonical=False)

            if not celula:
                return {"success": False, "error": f"Célula {celula_id} não encontrada"}

            # Get the cell type
            notebook_item_type = db.find_one(
                "notebook_item_types",
                celula.notebook_item_type_id,
                NotebookItemType,
                is_canonical=True,
            )

            if not notebook_item_type:
                return {
                    "success": False,
                    "error": f"NotebookItemType {celula.notebook_item_type_id} não encontrado",
                }

            # Update cell state to executing
            celula.status = CellStatus.RUNNING
            db.update(
                "cells", celula_id, {"estado": celula.status.value}, is_canonical=False
            )

            # Simulate execution - in a real implementation, this would
            # run the actual scripts from the cell type
            resultado = {
                "output": f"Célula {celula_id} executada com sucesso",
                "tipo": notebook_item_type.descricao,
                "dados_execucao": dados_execucao,
            }

            # Create execution fragment
            # Create fragment as a dict (supports Union[str, Dict])
            fragmento = {"tipo": "execucao", "resultado": resultado}
            celula.fragments.append(fragmento)

            # Update cell state to finished
            celula.status = CellStatus.COMPLETED

            # Prepare fragmentos for database - handle Union[str, Dict] types
            fragmentos_for_db = []
            for frag in celula.fragments:
                if isinstance(frag, str):
                    fragmentos_for_db.append(frag)
                elif isinstance(frag, dict):
                    fragmentos_for_db.append(frag)
                else:
                    # Handle unexpected types
                    fragmentos_for_db.append(str(frag))

            db.update(
                "cells",
                celula_id,
                {"estado": celula.status.value, "fragmentos": fragmentos_for_db},
                is_canonical=False,
            )

            logger.info("Célula %s executada com sucesso pelo LangChain", celula_id)

            return {
                "success": True,
                "celula_id": celula_id,
                "estado": celula.status.value,
                "resultado": resultado,
                "message": f"Célula executada com sucesso: {celula_id}",
            }

        except Exception as e:
            logger.error("Erro ao executar célula via LangChain: %s", e)

            # Update cell state to error if it exists
            try:
                db.update(
                    "cells",
                    celula_id,
                    {"estado": CellStatus.ERROR.value},
                    is_canonical=False,
                )
            except Exception:
                # Ignore errors when updating error state
                pass

            return {"success": False, "error": f"Erro ao executar célula: {str(e)}"}

    @staticmethod
    def criar_celula_tool() -> Tool:
        """
        Create a LangChain Tool for creating cells.

        Returns:
            LangChain Tool instance
        """

        async def _criar_celula_async(input_str: str) -> str:
            """
            Async tool function to create a cell.
            Input should be in format: "responsavel_id,tipo_celula_id,dados_iniciais"
            """
            parts = input_str.split(",", 2)
            responsavel_id = parts[0].strip() if len(parts) > 0 else None
            tipo_celula_id = parts[1].strip() if len(parts) > 1 else None
            dados_iniciais = parts[2].strip() if len(parts) > 2 else None

            if not responsavel_id:
                return "Erro: responsavel_id é obrigatório"

            # Call async implementation directly (no asyncio.run needed)
            result = await CellTools.criar_celula_impl(
                responsavel_id=responsavel_id,
                tipo_celula_id=tipo_celula_id if tipo_celula_id else None,
                dados_iniciais={"input": dados_iniciais} if dados_iniciais else None,
            )

            if result["success"]:
                return f"Célula criada: {result['celula_id']}"
            else:
                return f"Erro: {result['error']}"

        return Tool(
            name="criar_celula",
            description="Cria uma nova célula no sistema. Input: responsavel_id,tipo_celula_id,dados_iniciais",
            func=lambda x: "Use coroutine instead",  # Placeholder for sync, not used
            coroutine=_criar_celula_async,
        )

    @staticmethod
    def executar_celula_tool() -> Tool:
        """
        Create a LangChain Tool for executing cells.

        Returns:
            LangChain Tool instance
        """

        async def _executar_celula_async(input_str: str) -> str:
            """
            Async tool function to execute a cell.
            Input should be in format: "celula_id,dados_execucao"
            """
            parts = input_str.split(",", 1)
            celula_id = parts[0].strip() if len(parts) > 0 else None
            dados_execucao = parts[1].strip() if len(parts) > 1 else None

            if not celula_id:
                return "Erro: celula_id é obrigatório"

            # Call async implementation directly (no asyncio.run needed)
            result = await CellTools.executar_celula_impl(
                celula_id=celula_id,
                dados_execucao={"input": dados_execucao} if dados_execucao else None,
            )

            if result["success"]:
                return f"Célula executada: {result['celula_id']}, Resultado: {result['resultado']['output']}"
            else:
                return f"Erro: {result['error']}"

        return Tool(
            name="executar_celula",
            description="Executa uma célula existente. Input: celula_id,dados_execucao",
            func=lambda x: "Use coroutine instead",  # Placeholder for sync, not used
            coroutine=_executar_celula_async,
        )


def get_cell_tools() -> list[Tool]:
    """
    Get all available cell tools.

    Returns:
        List of LangChain Tool instances
    """
    return [CellTools.criar_celula_tool(), CellTools.executar_celula_tool()]
