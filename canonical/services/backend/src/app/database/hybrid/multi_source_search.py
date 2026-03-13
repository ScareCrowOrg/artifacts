"""
Multi-Source Search for HybridDatabase.

Provides multi-tier search functionality across Sandbox, Canonical, and Runtime
data sources with precedence-based result merging.
"""

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from ...models.users import User
    from ..centralhub_client import CentralHubClient
    from ..mongodb.operations import MongoDBOperations
    from ..query_engine.canonical_engine import CanonicalQueryEngine
    from ..query_engine.rbac import RBACValidator
    from ..query_engine.sandbox_engine import SandboxQueryEngine

logger = logging.getLogger(__name__)


class MultiSourceSearch:
    """
    Multi-source search handler for HybridDatabase.

    Searches across 3 tiers with precedence rules:
    1. Sandbox (user-private data)
    2. Canonical (blueprint/schema data)
    3. Runtime (operational data - MongoDB/CentralHub)

    Features:
    - RBAC-aware searching (checks access before querying)
    - Graceful error handling (continues on engine failures)
    - Result de-duplication by _id
    - Precedence-based merging (Sandbox > Canonical > Runtime)
    """

    def __init__(
        self,
        rbac: "RBACValidator",
        sandbox_engine: Optional["SandboxQueryEngine"],
        canonical_engine: Optional["CanonicalQueryEngine"],
        mongo_ops: Optional["MongoDBOperations"],
        centralhub_client: Optional["CentralHubClient"],
        mongodb_enabled: bool,
    ):
        """
        Initialize multi-source search handler.

        Args:
            rbac: RBAC validator for access control
            sandbox_engine: Sandbox query engine (can be None)
            canonical_engine: Canonical query engine (can be None)
            mongo_ops: MongoDB operations (can be None)
            centralhub_client: CentralHub HTTP client (can be None)
            mongodb_enabled: Whether MongoDB is enabled
        """
        self._rbac = rbac
        self._sandbox_engine = sandbox_engine
        self._canonical_engine = canonical_engine
        self._mongo_ops = mongo_ops
        self._centralhub_client = centralhub_client
        self._mongodb_enabled = mongodb_enabled

    async def find(
        self,
        collection: str,
        query: Dict,
        current_user: "User",
        resource_owner_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """
        Search all 3 sources and merge results with precedence.

        Precedence: Sandbox > Canonical > Runtime

        Args:
            collection: Collection name
            query: Query filter
            current_user: User making request
            resource_owner_id: Resource owner ID (for sandbox)
            limit: Maximum results

        Returns:
            Merged results (de-duplicated by _id)
        """
        results_sandbox = []
        results_canonical = []
        results_runtime = []

        # 1. Check sandbox (if user has access and resource_owner_id provided)
        if resource_owner_id and self._sandbox_engine:
            if self._rbac.check_sandbox_access(resource_owner_id, current_user):
                try:
                    results_sandbox = await self._sandbox_engine.find(
                        user_id=resource_owner_id,
                        collection=collection,
                        query=query,
                        limit=limit,
                    )
                    logger.info(
                        "[MultiSourceSearch] Sandbox search: %s results from %s",
                        len(results_sandbox), collection
                    )
                except Exception as e:
                    logger.warning("[MultiSourceSearch] Sandbox search error: %s", e)
        elif resource_owner_id:
            logger.debug("[MultiSourceSearch] Sandbox engine not available for %s", collection)

        # 2. Check canonical (if user has access)
        if self._rbac.check_canonical_access(collection, current_user):
            if self._canonical_engine:
                try:
                    results_canonical = await self._canonical_engine.find(
                        collection=collection,
                        query=query,
                        limit=limit,
                    )
                    logger.info(
                        "[MultiSourceSearch] Canonical search: %s results from %s",
                        len(results_canonical), collection
                    )
                except Exception as e:
                    logger.error("[MultiSourceSearch] Canonical search error: %s", e, exc_info=True)
            else:
                logger.error("[MultiSourceSearch] RBAC allows canonical access but engine is None for %s", collection)
        else:
            logger.debug("[MultiSourceSearch] RBAC denies canonical access for %s", collection)

        # 3. Check runtime/MongoDB via CentralHub
        # Note: "users" collection requires special handling - it's needed for authentication
        # so we must allow access even if user doesn't have explicit "users.read" permission
        logger.info("[MultiSourceSearch] Checking runtime access for collection: %s", collection)
        if collection == "users":
            logger.info(
                "[MultiSourceSearch] 'users' collection - skipping RBAC, going to CentralHub"
            )
        elif self._rbac.check_runtime_access(collection, current_user):
            logger.info("[MultiSourceSearch] RBAC check passed for %s", collection)
        else:
            logger.warning("[MultiSourceSearch] RBAC check FAILED for %s - user %s", collection, current_user.id)
            return results_runtime

        if collection == "users" or self._rbac.check_runtime_access(
            collection, current_user
        ):
            # Always use CentralHub to access MongoDB (backend never connects directly)
            logger.info("[MultiSourceSearch] Calling CentralHub.find_many for %s", collection)
            try:
                results_runtime = await self._centralhub_client.find_many(
                    collection=collection,
                    query=query,
                    user_id=current_user.id,
                    limit=limit,
                )
                logger.info(
                    "[MultiSourceSearch] CentralHub success: %s results from %s",
                    len(results_runtime), collection
                )
            except Exception as e:
                logger.warning("[MultiSourceSearch] CentralHub unavailable for %s: %s", collection, e)

        # 4. Merge with precedence (Sandbox > Canonical > Runtime)
        logger.info(
            "[MultiSourceSearch] Before merge: sandbox=%s, canonical=%s, runtime=%s",
            len(results_sandbox), len(results_canonical), len(results_runtime)
        )
        merged = self.merge_results(results_sandbox, results_canonical, results_runtime)
        logger.info("[MultiSourceSearch] After merge: %s total results from %s", len(merged), collection)

        return merged

    @staticmethod
    def merge_results(
        sandbox_results: List[Dict],
        canonical_results: List[Dict],
        runtime_results: List[Dict],
    ) -> List[Dict]:
        """
        Merge results from 3 sources with precedence rules.

        Precedence: Sandbox > Canonical > Runtime
        De-duplicates by _id field.

        Args:
            sandbox_results: Results from sandbox
            canonical_results: Results from canonical
            runtime_results: Results from runtime

        Returns:
            Merged and de-duplicated results
        """
        # Track seen IDs to avoid duplicates
        seen_ids = set()
        merged = []

        # Priority 1: Sandbox results
        for result in sandbox_results:
            doc_id = result.get("_id") or result.get("id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                merged.append(result)

        # Priority 2: Canonical results
        for i, result in enumerate(canonical_results):
            result_id_field = result.get("_id") if isinstance(result, dict) else None
            result_id_fallback = result.get("id") if isinstance(result, dict) else None
            doc_id = result_id_field or result_id_fallback
            if not doc_id:
                logger.warning("[Merge] Canonical result #%s: _id=%s, id=%s, result type=%s, keys=%s", i, repr(result_id_field), repr(result_id_fallback), type(result), list(result.keys()) if isinstance(result, dict) else 'N/A')
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                merged.append(result)

        # Priority 3: Runtime results
        for result in runtime_results:
            doc_id = result.get("_id") or result.get("id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                merged.append(result)

        logger.info(
            "[Merge] Merged results: %s total (sandbox=%s, canonical=%s, runtime=%s)",
            len(merged), len(sandbox_results), len(canonical_results), len(runtime_results)
        )

        return merged
