"""
Cell Generation Service for AI-driven code generation.

This service implements the Cell Factory MVP 1 generation workflow:
1. Accept generation requests from API endpoints
2. Integrate with LLM providers for code generation
3. Stream markdown responses with code fence tokens
4. Publish progress events to Event Bus
5. Coordinate with Validation Service for quality checks
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..database import db
from ..models import (
    ActionPlan,
    ActionStep,
    Cell,
    CellGenerationRequest,
    ConversationMessage,
    DynamicRef,
    EnrichedPrompt,
    GenerationMetadata,
    RAGContext,
    generate_uuid,
)
from ..models.event_bus import EventTopic, MessageEnvelope
from ..services.cell_validation_service import CellValidationService
from ..services.llm_service import LLMService
from ..services.redis_pubsub_service import RedisPubSubService

logger = logging.getLogger(__name__)

# Database constants for cell retrieval
# These are used when retrieving cells for generation across all users
DEFAULT_USER_ID = None  # None means all users (admin/system access)
DEFAULT_SESSION_ID = "default"  # Default session for system operations


class CellGenerationService:
    """
    Service for AI-driven cell code generation.

    Implements token-driven generation where LLM streams markdown
    and code fence blocks are extracted as dynamic refs.
    """

    def __init__(
        self,
        redis_service: Optional[RedisPubSubService] = None,
        llm_service: Optional[LLMService] = None,
        validation_service: Optional[CellValidationService] = None,
        use_real_llm: bool = False,
    ):
        """
        Initialize Cell Generation Service.

        Args:
            redis_service: Redis pub/sub service for event publishing
            llm_service: LLM service for real API integration (MVP 2)
            validation_service: Validation service for Hypnosis Loop
            use_real_llm: Whether to use real LLM API (True) or mock (False)
        """
        self.redis_service = redis_service
        self.llm_service = llm_service or LLMService()
        self.validation_service = validation_service or CellValidationService(
            redis_service
        )
        self.use_real_llm = use_real_llm
        self.logger = logger
        self._hypnosis_subscription_started = False

    async def start_hypnosis_loop_listener(self) -> None:
        """
        Start listening for Hypnosis Loop auto-correction events.

        Subscribes to validation/auto_correct topic and handles re-generation
        requests with error context.

        Should be called once during service initialization (e.g., in main.py startup).
        """
        if self._hypnosis_subscription_started:
            self.logger.info("Hypnosis Loop listener already started")
            return

        if not self.redis_service:
            self.logger.warning(
                "Redis service not configured, cannot start Hypnosis Loop listener"
            )
            return

        try:
            self.logger.info(
                "Starting Hypnosis Loop listener for validation/auto_correct"
            )

            # Subscribe to auto-correction topic
            await self.redis_service.subscribe(
                EventTopic.CELL_VALIDATE_AUTO_CORRECT.value,
                self._handle_auto_correct_request,
            )

            self._hypnosis_subscription_started = True
            self.logger.info("✅ Hypnosis Loop listener started successfully")

        except Exception as e:
            self.logger.error("Failed to start Hypnosis Loop listener: %s", e)
            raise

    async def generate_cell_code(
        self, request: CellGenerationRequest, cell: Cell
    ) -> Dict[str, Any]:
        """
        Generate code for a cell using AI with history orchestration and enriched prompts.

        This method implements the MVP 1 architecture:
        1. Retrieve conversation history from cell metadata
        2. Apply RAG context enrichment (mock for MVP 1)
        3. Format enriched prompt with all context
        4. Publish enriched prompt to Event Bus (WITHOUT user token)
        5. Wait for Wasm Orchestrator to handle LLM call with token handshake

        Args:
            request: Generation request parameters
            cell: Target cell to generate code for

        Returns:
            Dictionary with generation metadata

        Raises:
            ValueError: If generation fails
        """
        self.logger.info("=" * 80)
        self.logger.info("[GENERATION SERVICE] 🚀 generate_cell_code CALLED")
        self.logger.info("📍 Cell ID: %s", request.cell_id)
        self.logger.info(
            f"📝 Content: {request.content[:100]}..."
            if len(request.content) > 100
            else f"📝 Content: {request.content}"
        )
        self.logger.info("🎨 Format: %s", request.format)
        self.logger.info("🤖 Model: %s", request.model)
        self.logger.info("🔄 Use RAG: %s", request.use_rag)
        self.logger.info("💬 Conversation ID: %s", request.conversation_id)
        self.logger.info("🏭 Use real LLM: %s", self.use_real_llm)
        self.logger.info("=" * 80)

        try:
            # Generate unique request ID for correlation
            request_id = generate_uuid()
            self.logger.info("[GENERATION SERVICE] 🆔 Generated request ID: %s", request_id)

            # Step 1: Retrieve conversation history
            self.logger.info(
                "[GENERATION SERVICE] 📚 Retrieving conversation history..."
            )
            conversation_history = await self._retrieve_conversation_history(
                cell, request.conversation_id
            )
            self.logger.info("[GENERATION SERVICE] ✅ Retrieved %s messages from history", len(conversation_history))

            # Step 2: Apply RAG context enrichment (mock for MVP 1)
            rag_context = None
            if request.use_rag:
                self.logger.info(
                    "[GENERATION SERVICE] 🔍 Applying RAG context enrichment..."
                )
                rag_context = await self._enrich_with_rag(request.content)
                self.logger.info(
                    "[GENERATION SERVICE] ✅ Applied RAG context enrichment"
                )

            # Step 3: Evaluate task complexity for recursive transmutation
            self.logger.info("[GENERATION SERVICE] 📊 Evaluating task complexity...")
            complexity_score = self._evaluate_complexity(
                request.content, conversation_history, rag_context
            )
            self.logger.info("[GENERATION SERVICE] 📊 Complexity score: %s", complexity_score)

            # Step 4: Check if task should be decomposed into action plan
            should_decompose = self._should_decompose(complexity_score)
            self.logger.info("[GENERATION SERVICE] 🔀 Should decompose: %s (threshold: 7.0)", should_decompose)

            if should_decompose:
                self.logger.info(
                    "[GENERATION SERVICE] 🏗️ Task is complex, entering Architect Mode..."
                )
                # Enter Architect Mode: Generate action plan
                action_plan = await self._generate_action_plan(
                    prompt=request.content,
                    complexity_score=complexity_score,
                    conversation_history=conversation_history,
                    rag_context=rag_context,
                    cell_id=request.cell_id,
                    model=request.model,
                )

                self.logger.info("[GENERATION SERVICE] ✅ Action plan generated: %s", action_plan.plan_id)
                self.logger.info("[GENERATION SERVICE] 📋 Steps count: %s", len(action_plan.steps))

                # Publish action plan to Event Bus for WASM Orchestrator
                self.logger.info(
                    "[GENERATION SERVICE] 📤 Publishing action plan to Event Bus..."
                )
                await self._publish_event(
                    EventTopic.CELL_TRANSMUTE_PLAN,
                    {
                        "request_id": request_id,
                        "cell_id": request.cell_id,
                        "user_id": cell.assignee_id,
                        "action_plan": action_plan.model_dump(),
                        "complexity_score": complexity_score,
                    },
                )

                self.logger.info(
                    "[GENERATION SERVICE] ✅ Published action plan to Event Bus. Plan ID: %s, Steps: %s",
                    action_plan.plan_id, len(action_plan.steps)
                )

                # Return early - WASM Orchestrator will handle recursive execution
                result = {
                    "success": True,
                    "request_id": request_id,
                    "action_plan_id": action_plan.plan_id,
                    "decomposed": True,
                    "complexity_score": complexity_score,
                    "steps_count": len(action_plan.steps),
                }
                self.logger.info("[GENERATION SERVICE] 📤 Returning decomposed result")
                self.logger.info("=" * 80)
                return result

            # Step 5: Format enriched prompt for direct generation (non-decomposed)
            self.logger.info("[GENERATION SERVICE] 📝 Formatting enriched prompt...")
            enriched_prompt = await self._format_enriched_prompt(
                user_prompt=request.content,
                conversation_history=conversation_history,
                rag_context=rag_context,
                format_constraint=request.format,
                model=request.model,
            )
            self.logger.info("[GENERATION SERVICE] ✅ Formatted enriched prompt")

            # Initialize generation metadata
            metadata = GenerationMetadata(
                prompt=request.content,
                model=request.model,
                attempts=1,
                generated_at=datetime.utcnow(),
            )
            self.logger.info("[GENERATION SERVICE] 📊 Initialized generation metadata")

            # Step 6: Publish generation start event with enriched prompt
            # NOTE: NO USER TOKEN is included - Wasm Orchestrator will handle token handshake
            self.logger.info(
                "[GENERATION SERVICE] 📤 Publishing generation request to Event Bus..."
            )
            await self._publish_event(
                EventTopic.CELL_GENERATE_REQUEST,
                {
                    "request_id": request_id,
                    "cell_id": request.cell_id,
                    "user_id": cell.assignee_id,
                    "enriched_prompt": enriched_prompt.model_dump(),
                    "format": request.format,
                    "model": request.model,
                    "conversation_id": request.conversation_id,
                    "complexity_score": complexity_score,
                },
            )
            self.logger.info("[GENERATION SERVICE] ✅ Published enriched prompt to Event Bus. Request ID: %s. Awaiting Wasm Orchestrator...", request_id)

            # For MVP 1, we'll use a mock LLM response
            # In MVP 2, this is replaced with real LLM streaming
            self.logger.info("[GENERATION SERVICE] 🤖 Generating code (use_real_llm=%s)...", self.use_real_llm)

            if self.use_real_llm:
                self.logger.info("[GENERATION SERVICE] 🌐 Using REAL LLM streaming")
                generated_code = await self._generate_code_real_streaming(
                    enriched_prompt, request.model, request_id
                )
            else:
                self.logger.info("[GENERATION SERVICE] 🎭 Using MOCK generation")
                generated_code = await self._generate_code_mock(
                    request.content, request.format
                )

            self.logger.info(
                "[GENERATION SERVICE] ✅ Code generated, extracting dynamic refs..."
            )

            # Extract dynamic refs from generated code
            dynamic_refs = await self._extract_dynamic_refs(
                generated_code, request.format
            )

            # Update cell with dynamic refs and metadata
            await self._update_cell_with_refs(cell, dynamic_refs, metadata)

            # Publish generation complete event
            await self._publish_event(
                EventTopic.CELL_GENERATE_COMPLETE,
                {
                    "request_id": request_id,
                    "cell_id": request.cell_id,
                    "refs": [ref.model_dump() for ref in dynamic_refs],
                    "promotion_ready": False,  # Will be True after validation
                },
            )

            self.logger.info(
                "Code generation completed for cell %s. Generated %s refs.",
                request.cell_id, len(dynamic_refs)
            )

            return {
                "success": True,
                "request_id": request_id,
                "refs_count": len(dynamic_refs),
                "metadata": metadata.model_dump(),
            }

        except Exception as e:
            self.logger.error("Error generating code for cell %s: %s", request.cell_id, e)

            # Publish error event
            await self._publish_event(
                EventTopic.CELL_GENERATE_ERROR,
                {"cell_id": request.cell_id, "error": str(e)},
            )

            raise ValueError(f"Code generation failed: {str(e)}") from e

    async def _generate_code_mock(self, _prompt: str, format: str) -> str:
        """
        Mock LLM code generation.

        In production, this would call OpenAI/Anthropic streaming API.
        For MVP 1, we return mock code based on the requested format.

        Args:
            prompt: User prompt
            format: Desired output format (svg, vue, js, python, auto)

        Returns:
            Generated code string
        """
        # Mock responses based on format
        mock_responses = {
            "svg": '<svg width="200" height="200"><circle cx="100" cy="100" r="50" fill="blue"/></svg>',
            "vue": '<template><div class="component">{{ message }}</div></template>\n<script>export default { data() { return { message: "Hello" } } }</script>',
            "js": 'function greet(name) {\n  return `Hello, ${name}!`;\n}\n\nconsole.log(greet("World"));',
            "python": 'def greet(name: str) -> str:\n    return f"Hello, {name}!"\n\nif __name__ == "__main__":\n    print(greet("World"))',
            "auto": '<svg width="200" height="200"><rect x="50" y="50" width="100" height="100" fill="green"/></svg>',
        }

        return mock_responses.get(format, mock_responses["auto"])

    async def _generate_code_real_streaming(
        self, enriched_prompt: EnrichedPrompt, model: str, request_id: str
    ) -> str:
        """
        Real LLM code generation with streaming (MVP 2).

        Uses real OpenAI/Anthropic API with streaming response.
        Publishes progress events as chunks arrive.

        Args:
            enriched_prompt: Enriched prompt with history and context
            model: Model name to use
            request_id: Request ID for correlation

        Returns:
            Generated code string
        """
        self.logger.info("Starting real LLM streaming for request %s", request_id)

        generated_code = ""

        try:
            # Stream response from LLM
            async for chunk in self.llm_service.generate_code_streaming(
                enriched_prompt, model=model, temperature=0.7, max_tokens=2000
            ):
                # Publish progress event
                await self._publish_event(
                    EventTopic.CELL_GENERATE_PROGRESS,
                    {"request_id": request_id, "chunk": chunk},
                )

                # Accumulate code blocks
                if chunk["type"] == "code":
                    generated_code += (
                        f"\n```{chunk['fence']}\n{chunk['content']}\n```\n"
                    )

            self.logger.info("Real LLM streaming complete for request %s", request_id)

        except Exception as e:
            self.logger.error("Error during real LLM streaming: %s", e)
            raise

        return generated_code

    async def _retrieve_conversation_history(
        self, cell: Cell, _conversation_id: Optional[str] = None
    ) -> List[ConversationMessage]:
        """
        Retrieve conversation history from cell metadata or conversation store.

        Args:
            cell: Cell containing conversation context
            conversation_id: Optional conversation ID to retrieve specific history

        Returns:
            List of conversation messages
        """
        history = []

        # Try to retrieve from initial_data
        if cell.initial_data and "history" in cell.initial_data:
            for msg in cell.initial_data.get("history", []):
                if isinstance(msg, dict):
                    # Create timestamp if not provided
                    timestamp = msg.get("timestamp")
                    if timestamp is None:
                        timestamp = datetime.utcnow()
                    elif isinstance(timestamp, str):
                        timestamp = (
                            datetime.fromisoformat(timestamp)
                            if timestamp
                            else datetime.utcnow()
                        )

                    history.append(
                        ConversationMessage(
                            role=msg.get("role", "user"),
                            content=msg.get("content", ""),
                            timestamp=timestamp,
                        )
                    )

        # If conversation_id provided, we could fetch from a conversation store
        # For MVP 1, we'll just use what's in the cell

        self.logger.debug("Retrieved %s messages from cell history", len(history))
        return history

    async def _enrich_with_rag(self, _prompt: str) -> RAGContext:
        """
        Enrich prompt with RAG (Retrieval-Augmented Generation) context.

        For MVP 1, this is a mock implementation. In production, this would:
        1. Query vector database for relevant documents
        2. Retrieve and rank relevant context
        3. Format context for injection into prompt

        Args:
            prompt: User prompt to enrich

        Returns:
            RAG context with relevant documents
        """
        # Mock RAG context for MVP 1
        mock_docs = [
            "Cell Factory allows AI-driven code generation for cells.",
            "Supported formats: SVG, Vue, JavaScript, Python.",
            "Code is validated through the Hypnosis Loop with up to 3 auto-correction attempts.",
        ]

        return RAGContext(
            relevant_docs=mock_docs,
            metadata={
                "retrieval_method": "mock",
                "num_docs": len(mock_docs),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def _format_enriched_prompt(
        self,
        user_prompt: str,
        conversation_history: List[ConversationMessage],
        rag_context: Optional[RAGContext],
        format_constraint: str,
        model: str,
    ) -> EnrichedPrompt:
        """
        Format enriched prompt with all context for LLM generation.

        Args:
            user_prompt: Original user request
            conversation_history: Previous conversation messages
            rag_context: RAG context if available
            format_constraint: Desired output format
            model: Target AI model

        Returns:
            EnrichedPrompt ready for LLM consumption
        """
        # Build system instructions based on format
        system_instructions = self._build_system_instructions(format_constraint)

        # Build constraints
        constraints = {
            "format": format_constraint,
            "model": model,
            "max_tokens": 2000,
            "temperature": 0.7,
        }

        enriched = EnrichedPrompt(
            user_prompt=user_prompt,
            conversation_history=conversation_history,
            rag_context=rag_context,
            system_instructions=system_instructions,
            constraints=constraints,
        )

        self.logger.debug(
            "Formatted enriched prompt: %s history messages, RAG: %s",
            len(conversation_history), 'enabled' if rag_context else 'disabled'
        )

        return enriched

    def _build_system_instructions(self, format_constraint: str) -> str:
        """
        Build system instructions based on format constraint.

        Args:
            format_constraint: Desired output format

        Returns:
            System instructions string
        """
        base_instructions = (
            "You are an expert code generator for the ScareVerse Cell Factory. "
            "Generate clean, validated code based on the user's request. "
        )

        format_specific = {
            "svg": "Generate valid SVG markup with proper syntax. Ensure the SVG is well-formed.",
            "vue": "Generate a valid Vue 3 component with <template>, <script>, and optional <style> sections.",
            "js": "Generate clean JavaScript code with proper syntax and best practices.",
            "python": "Generate Python code following PEP 8 style guidelines.",
            "auto": "Analyze the request and choose the most appropriate format (SVG, Vue, JS, or Python).",
        }

        return base_instructions + format_specific.get(
            format_constraint, format_specific["auto"]
        )

    async def _extract_dynamic_refs(self, code: str, format: str) -> List[DynamicRef]:
        """
        Extract dynamic refs from generated code.

        In production, this would parse markdown fence blocks.
        For MVP 1, we create a single ref from the generated code.

        Args:
            code: Generated code
            format: Code format

        Returns:
            List of DynamicRef objects
        """
        # Map format to ref type and language
        format_mapping = {
            "svg": ("visual", "svg"),
            "vue": ("component", "vue"),
            "js": ("logic", "js"),
            "python": ("logic", "python"),
            "auto": ("visual", "svg"),
        }

        ref_type, lang = format_mapping.get(format, ("logic", "js"))

        # Create dynamic ref
        ref = DynamicRef(
            type=ref_type,
            lang=lang,
            path=f"sandbox/assets/{ref_type}_{generate_uuid()}.{lang}",
            filename=f"{ref_type}_{generate_uuid()}.{lang}",
            size_bytes=len(code.encode("utf-8")),
            validated=False,  # Will be validated by Validation Service
            created_at=datetime.utcnow(),
        )

        return [ref]

    async def _update_cell_with_refs(
        self, cell: Cell, refs: List[DynamicRef], metadata: GenerationMetadata
    ) -> None:
        """
        Update cell with generated refs and metadata.

        Args:
            cell: Target cell
            refs: Generated dynamic refs
            metadata: Generation metadata
        """
        # Update cell's initial_data with dynamic refs and metadata
        if not cell.initial_data:
            cell.initial_data = {}

        cell.initial_data["dynamic_refs"] = [ref.model_dump() for ref in refs]
        cell.initial_data["generation_metadata"] = metadata.model_dump()

        # Persist updated cell
        db.update(
            "cells",
            cell.id,
            cell,
            user_id=cell.assignee_id,
            session_id="default",
            is_canonical=False,
        )

    async def _publish_event(self, topic: EventTopic, payload: Dict[str, Any]) -> None:
        """
        Publish event to Event Bus.

        Args:
            topic: Event topic
            payload: Event payload
        """
        if not self.redis_service:
            self.logger.warning("Redis service not configured, skipping event publish for %s", topic)
            return

        try:
            envelope = MessageEnvelope(
                topic=topic.value,  # Use string value for topic
                payload=payload,
                timestamp=datetime.utcnow(),
            )

            # Publish envelope to Redis (RedisPubSubService.publish expects MessageEnvelope)
            await self.redis_service.publish(envelope)

            self.logger.debug("Published event %s with payload: %s", topic.value, payload)

        except Exception as e:
            self.logger.error("Error publishing event %s: %s", topic.value, e)

    def _evaluate_complexity(
        self,
        prompt: str,
        conversation_history: List[ConversationMessage],
        rag_context: Optional[RAGContext],
    ) -> float:
        """
        Evaluate task complexity on a 0-10 scale.

        Analyzes the prompt and context to determine if the task requires
        recursive decomposition. Complex tasks with multiple dependencies,
        multiple components, or unclear requirements score higher.

        Scoring factors:
        - Prompt length and detail level
        - Number of distinct components/features requested
        - Presence of conditional logic or data dependencies
        - Ambiguity and lack of specificity
        - Conversation history complexity

        Args:
            prompt: User prompt to evaluate
            conversation_history: Previous conversation messages
            rag_context: RAG context if available

        Returns:
            Complexity score from 0.0 (simple) to 10.0 (highly complex)
        """
        score = 0.0

        # Factor 1: Prompt length (longer = potentially more complex)
        # 0-100 chars = +0, 100-300 = +1, 300-500 = +2, 500+ = +3
        prompt_length = len(prompt)
        if prompt_length > 500:
            score += 3.0
        elif prompt_length > 300:
            score += 2.0
        elif prompt_length > 100:
            score += 1.0

        # Factor 2: Multiple components indicator
        # Look for keywords suggesting multiple components
        multi_component_keywords = [
            "and",
            "also",
            "plus",
            "with",
            "including",
            "multiple",
            "several",
            "various",
            "different",
            "both",
            "each",
            "all",
        ]
        keyword_count = sum(
            1 for kw in multi_component_keywords if kw in prompt.lower()
        )
        score += min(keyword_count * 0.5, 2.0)  # Max +2 points

        # Factor 3: Conditional logic indicators
        conditional_keywords = [
            "if",
            "when",
            "unless",
            "depending",
            "condition",
            "based on",
        ]
        conditional_count = sum(
            1 for kw in conditional_keywords if kw in prompt.lower()
        )
        score += min(conditional_count * 0.7, 2.0)  # Max +2 points

        # Factor 4: Data dependency indicators
        data_keywords = ["fetch", "load", "retrieve", "api", "database", "data", "from"]
        data_count = sum(1 for kw in data_keywords if kw in prompt.lower())
        score += min(data_count * 0.5, 1.5)  # Max +1.5 points

        # Factor 5: Conversation history depth (longer history = potentially more complex)
        if len(conversation_history) > 5:
            score += 1.0
        elif len(conversation_history) > 2:
            score += 0.5

        # Factor 6: RAG context complexity
        if rag_context and rag_context.relevant_docs:
            # More retrieved docs = more complex domain
            doc_count = len(rag_context.relevant_docs)
            score += min(doc_count * 0.2, 1.0)  # Max +1 point

        # Factor 7: Technical complexity indicators
        tech_keywords = [
            "integrate",
            "orchestrate",
            "coordinate",
            "synchronize",
            "architecture",
            "system",
            "pipeline",
            "workflow",
        ]
        tech_count = sum(1 for kw in tech_keywords if kw in prompt.lower())
        score += min(tech_count * 0.8, 2.0)  # Max +2 points

        # Cap at 10.0
        final_score = min(score, 10.0)

        self.logger.info("Complexity evaluation: %s/10.0 (length=%s, multi=%s, conditional=%s, data=%s, history=%s, tech=%s)", final_score, prompt_length, keyword_count, conditional_count, data_count, len(conversation_history), tech_count)

        return final_score

    def _should_decompose(
        self, complexity_score: float, threshold: float = 7.0
    ) -> bool:
        """
        Determine if task should be decomposed into action plan.

        Tasks with complexity score above threshold trigger "Architect Mode"
        which generates a structured action:plan for recursive transmutation.

        Args:
            complexity_score: Complexity score from _evaluate_complexity()
            threshold: Complexity threshold for decomposition (default: 7.0)

        Returns:
            True if task should be decomposed, False otherwise
        """
        should_decompose = complexity_score > threshold

        if should_decompose:
            self.logger.info(
                "Task complexity (%s) exceeds threshold (%s). Triggering Architect Mode for action plan generation.",
                complexity_score, threshold
            )
        else:
            self.logger.info(
                "Task complexity (%s) below threshold (%s). Proceeding with direct generation.",
                complexity_score, threshold
            )

        return should_decompose

    async def _generate_action_plan(
        self,
        prompt: str,
        complexity_score: float,
        conversation_history: List[ConversationMessage],
        rag_context: Optional[RAGContext],
        cell_id: str,
        model: str = "gpt-4",
    ) -> ActionPlan:
        """
        Generate structured action plan using LLM in "Architect Mode".

        Prompts the LLM to analyze the task and generate a hierarchical
        action plan with atomic steps and dependencies. The plan is returned
        as structured JSON conforming to ActionPlan schema.

        Args:
            prompt: Original user prompt
            complexity_score: Complexity score that triggered decomposition
            conversation_history: Previous conversation messages
            rag_context: RAG context if available
            cell_id: ID of the cell triggering this plan
            model: AI model to use for plan generation

        Returns:
            ActionPlan with hierarchical steps

        Raises:
            ValueError: If plan generation fails
        """
        self.logger.info("Generating action plan for cell %s using Architect Mode", cell_id)

        try:
            # Build Architect Mode system instructions
            architect_instructions = """You are an expert task architect for the ScareVerse Cell Factory.

Your role is to analyze complex user requests and decompose them into structured action plans.

For the given task, generate a JSON action plan with the following structure:
{
  "steps": [
    {
      "is_atomic": true/false,
      "action": "action_type",
      "tool": "tool_name",
      "parameters": {...},
      "description": "what this step does",
      "cell_type": "target_cell_type",
      "context_inheritance": {...},
      "substeps": [...]
    }
  ]
}

Guidelines:
- Break complex tasks into logical steps
- Mark steps as atomic (directly executable) or composite (needs further decomposition)
- For non-atomic steps, include substeps
- Specify tool/service for each atomic step (e.g., "llm_service", "rag_service", "data_service")
- Include context_inheritance for nested steps (what context to pass from parent to child)
- Be specific about parameters needed for each step
- Use clear, action-oriented descriptions

Example actions: "generate_svg", "create_vue_component", "fetch_api_data", "transform_data", "validate_output"
"""

            # Format prompt for Architect Mode
            architect_prompt = f"""Analyze this complex task and generate a structured action plan:

USER REQUEST:
{prompt}

COMPLEXITY SCORE: {complexity_score:.1f}/10.0

CONTEXT:
- Conversation history: {len(conversation_history)} messages
- RAG context: {"enabled" if rag_context else "disabled"}

Generate a detailed action plan that breaks this task into manageable steps."""

            # Build enriched prompt for Architect Mode
            enriched_prompt = EnrichedPrompt(
                user_prompt=architect_prompt,
                conversation_history=conversation_history,
                rag_context=rag_context,
                system_instructions=architect_instructions,
                constraints={
                    "format": "json",
                    "model": model,
                    "temperature": 0.3,  # Lower temperature for structured output
                    "max_tokens": 3000,
                },
            )

            # Generate action plan using LLM
            if self.use_real_llm:
                # Use real LLM API
                plan_json = await self._generate_plan_with_llm(enriched_prompt, model)
            else:
                # Use mock for testing
                plan_json = self._generate_mock_action_plan(prompt)

            # Parse and validate action plan
            action_plan = ActionPlan(
                original_cell_id=cell_id,
                original_prompt=prompt,
                complexity_score=complexity_score,
                steps=[ActionStep(**step) for step in plan_json.get("steps", [])],
                metadata={
                    "model": model,
                    "architect_mode": True,
                    "generation_timestamp": datetime.utcnow().isoformat(),
                },
                status="pending",
            )

            self.logger.info(
                "Action plan generated: %s top-level steps, plan_id=%s",
                len(action_plan.steps), action_plan.plan_id
            )

            return action_plan

        except Exception as e:
            self.logger.error("Failed to generate action plan: %s", e)
            raise ValueError(f"Action plan generation failed: {str(e)}") from e

    def _generate_mock_action_plan(self, _prompt: str) -> Dict[str, Any]:
        """
        Generate mock action plan for testing.

        In production, this is replaced by real LLM-generated plans.

        Args:
            prompt: User prompt

        Returns:
            Mock action plan as dictionary
        """
        return {
            "steps": [
                {
                    "is_atomic": False,
                    "action": "create_dashboard",
                    "tool": None,
                    "parameters": {},
                    "description": "Create interactive dashboard with charts",
                    "cell_type": "dashboard-cell",
                    "context_inheritance": {"theme": "dark", "layout": "grid"},
                    "substeps": [
                        {
                            "is_atomic": True,
                            "action": "generate_chart",
                            "tool": "llm_service",
                            "parameters": {"chart_type": "bar", "data_source": "api"},
                            "description": "Generate bar chart component",
                            "cell_type": "chart-cell",
                            "context_inheritance": {},
                            "substeps": [],
                        },
                        {
                            "is_atomic": True,
                            "action": "generate_table",
                            "tool": "llm_service",
                            "parameters": {
                                "columns": ["name", "value"],
                                "sortable": True,
                            },
                            "description": "Generate data table component",
                            "cell_type": "table-cell",
                            "context_inheritance": {},
                            "substeps": [],
                        },
                    ],
                }
            ]
        }

    async def _generate_plan_with_llm(
        self, enriched_prompt: EnrichedPrompt, model: str
    ) -> Dict[str, Any]:
        """
        Generate action plan using real LLM API.

        Calls LLM with structured output request to generate JSON action plan.

        Args:
            enriched_prompt: Enriched prompt for Architect Mode
            model: Model to use

        Returns:
            Action plan as dictionary
        """
        # This would call the real LLM service with JSON mode
        # For now, delegate to LLMService
        response = await self.llm_service.generate_structured_output(
            enriched_prompt,
            model=model,
            output_schema={
                "type": "object",
                "properties": {"steps": {"type": "array", "items": {"type": "object"}}},
            },
        )

        return response

    def _inject_parent_context(
        self, child_prompt: str, parent_context: Dict[str, Any]
    ) -> str:
        """
        Inject parent context into child prompt for "Inheritance Mode".

        When executing substeps in a hierarchical plan, this method extracts
        relevant context fragments from the parent step and injects them into
        the child prompt to maintain coherence.

        Args:
            child_prompt: Original child step prompt
            parent_context: Context inherited from parent step

        Returns:
            Enhanced child prompt with parent context injected
        """
        if not parent_context:
            return child_prompt

        # Build context injection prefix
        context_parts = []

        for key, value in parent_context.items():
            if value:  # Only include non-empty values
                context_parts.append(f"- {key}: {value}")

        if not context_parts:
            return child_prompt

        # Inject context at the beginning of the prompt
        context_injection = "INHERITED CONTEXT:\n" + "\n".join(context_parts) + "\n\n"

        enhanced_prompt = context_injection + child_prompt

        self.logger.debug("Injected parent context into child prompt: %s fields", len(parent_context))

        return enhanced_prompt

    async def _handle_auto_correct_request(self, message: MessageEnvelope) -> None:
        """
        Handle auto-correction request from Hypnosis Loop.

        Receives validation errors and re-generates code with error context
        appended to the system instructions for LLM auto-correction.

        Args:
            message: Event Bus message containing error context and cell_id
        """
        payload = message.payload
        cell_id = payload.get("cell_id")
        error_context = payload.get("error_context", "")
        attempt = payload.get("attempt", 1)

        self.logger.info("Received auto-correction request for cell %s, attempt %s", cell_id, attempt)

        try:
            # Retrieve cell from database
            cell = await db.get(
                "cells",
                cell_id,
                user_id=DEFAULT_USER_ID,
                session_id=DEFAULT_SESSION_ID,
                is_canonical=False,
            )

            if not cell:
                self.logger.error("Cell %s not found for auto-correction", cell_id)
                return

            # Get original generation request from metadata
            metadata_dict = cell.initial_data.get("generation_metadata", {})
            original_prompt = metadata_dict.get("prompt", "")
            original_format = metadata_dict.get("format", "auto")
            original_model = metadata_dict.get("model", "gpt-4")

            if not original_prompt:
                self.logger.error("No original prompt found in cell %s metadata", cell_id)
                return

            # Build enriched prompt with error context appended
            system_instructions = await self._build_system_instructions(original_format)
            system_instructions += f"\n\n{error_context}"

            enriched_prompt = EnrichedPrompt(
                user_prompt=original_prompt,
                system_instructions=system_instructions,
                conversation_history=[],
                rag_context=None,
            )

            # Re-generate code with error corrections
            self.logger.info("Re-generating code for cell %s with error corrections", cell_id)

            request_id = generate_uuid()

            if self.use_real_llm:
                # Use real LLM with streaming
                generated_markdown = await self._generate_code_real_streaming(
                    enriched_prompt, original_model, request_id
                )
            else:
                # Use mock for testing
                generated_markdown = await self._generate_code_mock(
                    original_prompt, original_format
                )

            # Extract dynamic refs from generated code
            refs = await self._extract_dynamic_refs(generated_markdown, original_format)

            # Update generation metadata with new attempt count
            new_metadata = GenerationMetadata(
                prompt=original_prompt,
                format=original_format,
                model=original_model,
                attempts=attempt,
                promotion_ready=False,  # Will be set by validation service
                created_at=datetime.utcnow(),
            )

            # Update cell with new refs and metadata
            await self._update_cell_with_refs(cell, refs, new_metadata)

            # Publish generation complete event for validation service to re-validate
            await self._publish_event(
                EventTopic.CELL_GENERATE_COMPLETE,
                {
                    "cell_id": cell_id,
                    "refs": [ref.model_dump() for ref in refs],
                    "attempt": attempt,
                    "auto_corrected": True,
                },
            )

            self.logger.info("Auto-correction complete for cell %s, attempt %s", cell_id, attempt)

        except Exception as e:
            self.logger.error("Error handling auto-correction for cell %s: %s", cell_id, e)

            # Publish error event
            await self._publish_event(
                EventTopic.CELL_GENERATE_ERROR,
                {"cell_id": cell_id, "error": str(e), "attempt": attempt},
            )
