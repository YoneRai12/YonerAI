import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.utils.agent_trace import trace_event
from src.utils.core_client import core_client
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class SwarmOrchestrator:
    """
    Lightweight Agent Swarm for high-complexity tasks.
    Guarantees five essentials:
    1) task decomposition
    2) parallel execution
    3) result merge
    4) retry
    5) observability (trace_event)
    """

    DANGEROUS_PATTERNS = [
        r"format\s+c:",
        r"rm\s+-rf\s+/",
        r"delete\s+all\s+files",
        r"credential\s+dump",
        r"exfiltrat(e|ion)",
    ]

    def __init__(self, bot, llm_client: LLMClient):
        self.bot = bot
        self.llm_client = llm_client

    @property
    def enabled(self) -> bool:
        return bool(getattr(self.bot.config, "swarm_enabled", False))

    def should_run(self, route_meta: Dict[str, Any], prompt: str) -> bool:
        if not self.enabled:
            return False
        complexity = (route_meta or {}).get("complexity")
        if complexity == "high":
            return True
        # Allow explicit user trigger
        p = (prompt or "").lower()
        return "swarm" in p or "サブエージェント" in p or "並列" in p

    def _guardrails(self, prompt: str) -> tuple[bool, str]:
        text = (prompt or "").strip()
        if len(text) < 8:
            return False, "Prompt too short"
        if len(text) > 8000:
            return False, "Prompt too long"
        low = text.lower()
        for pat in self.DANGEROUS_PATTERNS:
            if re.search(pat, low):
                return False, f"Blocked by guardrail: {pat}"
        return True, "ok"

    async def _decompose(self, prompt: str, rag_context: str, correlation_id: str) -> List[Dict[str, Any]]:
        max_tasks = int(getattr(self.bot.config, "swarm_max_tasks", 3))
        decompose_prompt = f"""
You are a task decomposition planner.
Split the user request into {max_tasks} or fewer independent subtasks for parallel execution.
Return ONLY the tasks that are actually needed; do NOT pad the list to reach the maximum.
It is valid to return 1-2 tasks for simple requests.
Subtasks must be analysis/research/planning oriented (not direct destructive operations).
Return STRICT JSON:
{{
  "tasks": [
    {{"id":"T1","role":"researcher","goal":"...","success_criteria":"..."}},
    {{"id":"T2","role":"planner","goal":"...","success_criteria":"..."}}
  ]
}}

[RAG CONTEXT]
{rag_context[:1200]}

[USER REQUEST]
{prompt}
"""
        try:
            resp, _, _ = await self.llm_client.chat(
                [{"role": "user", "content": decompose_prompt}],
                temperature=0.0,
                model=getattr(self.bot.config, "swarm_merge_model", "gpt-5-mini"),
            )
            raw = (resp or "").replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)
            tasks = data.get("tasks") if isinstance(data, dict) else None
            if isinstance(tasks, list):
                normalized = []
                for i, t in enumerate(tasks[:max_tasks], start=1):
                    if not isinstance(t, dict):
                        continue
                    normalized.append(
                        {
                            "id": str(t.get("id") or f"T{i}"),
                            "role": str(t.get("role") or "worker"),
                            "goal": str(t.get("goal") or "").strip(),
                            "success_criteria": str(t.get("success_criteria") or "").strip(),
                        }
                    )
                if normalized:
                    trace_event("swarm.decomposed", correlation_id=correlation_id, tasks=normalized)
                    return normalized
        except Exception as e:
            logger.warning(f"Swarm decomposition failed, using fallback: {e}")
            trace_event("swarm.decompose_error", correlation_id=correlation_id, error=str(e))

        # Fallback deterministic split
        fallback = [
            {"id": "T1", "role": "researcher", "goal": "Collect facts and constraints", "success_criteria": "facts listed"},
            {"id": "T2", "role": "planner", "goal": "Create executable plan", "success_criteria": "step-by-step plan"},
            {"id": "T3", "role": "reviewer", "goal": "Risk and permission review", "success_criteria": "risks and mitigations"},
            {"id": "T4", "role": "implementer", "goal": "Draft minimal patch outline", "success_criteria": "patch points identified"},
            {"id": "T5", "role": "tester", "goal": "Define verification steps", "success_criteria": "tests/commands listed"},
        ][:max_tasks]
        trace_event("swarm.decomposed_fallback", correlation_id=correlation_id, tasks=fallback)
        return fallback

    async def _execute_one(
        self,
        task: Dict[str, Any],
        prompt: str,
        provider_id: str,
        display_name: str,
        context_binding: Dict[str, Any],
        client_context: Dict[str, Any],
        correlation_id: str,
    ) -> Dict[str, Any]:
        retries = int(getattr(self.bot.config, "swarm_max_retries", 1))
        timeout = int(getattr(self.bot.config, "swarm_subtask_timeout_sec", 90))

        for attempt in range(retries + 1):
            try:
                trace_event(
                    "swarm.task_start",
                    correlation_id=correlation_id,
                    task_id=task.get("id"),
                    role=task.get("role"),
                    attempt=attempt,
                )
                sub_prompt = (
                    f"[SWARM SUBTASK {task.get('id')} | ROLE={task.get('role')}]\n"
                    f"Goal: {task.get('goal')}\n"
                    f"Success Criteria: {task.get('success_criteria')}\n\n"
                    "Rules:\n"
                    "- Output concise Japanese bullets.\n"
                    "- Do not execute external tools.\n"
                    "- Focus only on this subtask.\n\n"
                    f"Original request:\n{prompt}"
                )

                response = await core_client.send_message(
                    content=sub_prompt,
                    provider_id=provider_id,
                    display_name=display_name,
                    conversation_id=None,
                    idempotency_key=f"swarm:{correlation_id}:{task.get('id')}:{attempt}",
                    context_binding=context_binding,
                    attachments=[],
                    stream=False,
                    client_context=client_context,
                    available_tools=[],
                    source="discord",
                    llm_preference=getattr(self.bot.config, "swarm_merge_model", "gpt-5-mini"),
                    correlation_id=correlation_id,
                    origin_context={"admin_verified": bool((client_context or {}).get("is_admin"))},
                )
                if "error" in response:
                    raise RuntimeError(response.get("error", "unknown send error"))

                run_id = response.get("run_id")
                if not run_id:
                    raise RuntimeError("missing run_id")

                final_text = await asyncio.wait_for(core_client.get_final_response(run_id, timeout=timeout), timeout=timeout + 10)
                if not final_text:
                    raise RuntimeError("empty subtask response")

                out = {
                    "task_id": task.get("id"),
                    "role": task.get("role"),
                    "status": "ok",
                    "attempt": attempt,
                    "result": final_text.strip(),
                }
                trace_event("swarm.task_done", correlation_id=correlation_id, **out)
                return out
            except Exception as e:
                trace_event(
                    "swarm.task_retry",
                    correlation_id=correlation_id,
                    task_id=task.get("id"),
                    attempt=attempt,
                    error=str(e),
                )
                if attempt >= retries:
                    return {
                        "task_id": task.get("id"),
                        "role": task.get("role"),
                        "status": "failed",
                        "attempt": attempt,
                        "error": str(e),
                        "result": "",
                    }
                await asyncio.sleep(0.6 * (attempt + 1))

        return {
            "task_id": task.get("id"),
            "role": task.get("role"),
            "status": "failed",
            "attempt": retries,
            "error": "unreachable",
            "result": "",
        }

    async def _merge(self, prompt: str, task_results: List[Dict[str, Any]], correlation_id: str) -> str:
        ok_results = [r for r in task_results if r.get("status") == "ok" and r.get("result")]
        if not ok_results:
            return ""
        blocks = []
        for r in ok_results:
            blocks.append(f"[{r.get('task_id')}:{r.get('role')}]\n{r.get('result')}")
        merge_prompt = f"""
You are a synthesis agent.
Merge the parallel subtask outputs into one compact execution brief for the main agent.
Output Japanese, concise, with:
1) 要点
2) 推奨手順
3) リスク/権限注意

[ORIGINAL REQUEST]
{prompt}

[SUBTASK OUTPUTS]
{chr(10).join(blocks)}
"""
        try:
            merged, _, _ = await self.llm_client.chat(
                [{"role": "user", "content": merge_prompt}],
                temperature=0.0,
                model=getattr(self.bot.config, "swarm_merge_model", "gpt-5-mini"),
            )
            text = (merged or "").strip()
            trace_event("swarm.merged", correlation_id=correlation_id, merged_preview=text[:300])
            return text
        except Exception as e:
            trace_event("swarm.merge_error", correlation_id=correlation_id, error=str(e))
            return "\n\n".join(blocks)[:4000]

    async def run(
        self,
        prompt: str,
        rag_context: str,
        provider_id: str,
        display_name: str,
        context_binding: Dict[str, Any],
        client_context: Dict[str, Any],
        correlation_id: str,
    ) -> Dict[str, Any]:
        ok, reason = self._guardrails(prompt)
        if not ok:
            trace_event("swarm.guardrail_block", correlation_id=correlation_id, reason=reason)
            return {"ok": False, "reason": reason, "tasks": [], "results": [], "summary": ""}

        tasks = await self._decompose(prompt, rag_context, correlation_id)
        max_workers = int(getattr(self.bot.config, "swarm_max_workers", 3))
        sem = asyncio.Semaphore(max_workers)

        async def run_with_sem(task: Dict[str, Any]):
            async with sem:
                return await self._execute_one(
                    task=task,
                    prompt=prompt,
                    provider_id=provider_id,
                    display_name=display_name,
                    context_binding=context_binding,
                    client_context=client_context,
                    correlation_id=correlation_id,
                )

        results = await asyncio.gather(*[run_with_sem(t) for t in tasks], return_exceptions=False)
        summary = await self._merge(prompt, results, correlation_id)
        failed = len([r for r in results if r.get("status") != "ok"])
        trace_event(
            "swarm.completed",
            correlation_id=correlation_id,
            task_count=len(tasks),
            failed=failed,
            summary_preview=summary[:300],
        )
        return {
            "ok": True,
            "tasks": tasks,
            "results": results,
            "failed": failed,
            "summary": summary,
        }
