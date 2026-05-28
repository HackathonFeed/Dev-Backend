"""
Session-aware AI Copilot service.
Persists chat sessions and messages in Supabase.
Uses AWS Bedrock Nova with tool-use to fetch real projects from the DB.
"""
import asyncio
import json
import re
import uuid

from fastapi import HTTPException, status

from app.repositories.supabase_chat_repository import SupabaseChatRepository
from app.repositories.supabase_project_repository import SupabaseProjectRepository
from app.schemas.ai_schema import (
    ChatMessageOut,
    ChatSessionCreate,
    ChatSessionDetail,
    ChatSessionListItem,
    ChatSessionUpdate,
    HackathonContextForChat,
    ProjectSnippet,
    SessionChatRequest,
    SessionChatResponse,
)
from app.services.ai_validator_service import (
    call_bedrock_raw,
    call_bedrock_converse,
    build_copilot_system_prompt,
    get_bedrock_embedding,
)

# ── Tool definition ───────────────────────────────────────────────────────────

_SEARCH_PROJECTS_TOOL = {
    "toolSpec": {
        "name": "search_projects",
        "description": (
            "Search and retrieve REAL hackathon projects from the HackFeed database. "
            "ALWAYS call this tool when the user asks to see projects, examples, "
            "what others built, needs inspiration, wants the project gallery, or asks "
            "for project ideas (call it alongside your ideas to show real examples). "
            "To get top trending projects without a specific query, call with no 'search' "
            "parameter — this returns the most-liked projects. "
            "Only pass 'search' when the user explicitly names a topic or technology. "
            "IMPORTANT: After calling this tool, do NOT list each project's details in your "
            "text response. The UI automatically renders rich project cards with all details "
            "(thumbnail, title, tagline, tech stack, GitHub link, VIEW button). "
            "Just write a 1-sentence intro, then let the cards speak for themselves."
        ),
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": (
                            "Optional keywords to match project titles or taglines. "
                            "Leave empty/omit to get top projects by popularity."
                        ),
                    },
                    "technology": {
                        "type": "string",
                        "description": (
                            "Filter by a single technology "
                            "(e.g. 'React', 'Python', 'Blockchain', 'AI', 'ML', 'Web3')"
                        ),
                    },
                    "winner_only": {
                        "type": "boolean",
                        "description": "If true, only return winning / prize-winning projects",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of projects to return (1-8, default 5)",
                    },
                },
            }
        },
    }
}

_TOOL_CONFIG = {
    "tools": [_SEARCH_PROJECTS_TOOL],
    "toolChoice": {"auto": {}},
}

_MAX_TOOL_ITERATIONS = 3
_AUTO_TITLE_LEN = 65


def _strip_thinking(text: str) -> str:
    """Remove <thinking>...</thinking> blocks that Amazon Nova emits in its output."""
    return re.sub(r"<thinking>.*?</thinking>\s*", "", text, flags=re.DOTALL).strip()


# ── Row mapper ────────────────────────────────────────────────────────────────

def _row_to_detail(row: dict, messages: list[dict]) -> ChatSessionDetail:
    return ChatSessionDetail(
        id=row["id"],
        title=row["title"],
        hackathon_context=row.get("hackathon_context"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        messages=[
            ChatMessageOut(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                created_at=m["created_at"],
            )
            for m in messages
        ],
    )


# ── Service ───────────────────────────────────────────────────────────────────

class AIChatSessionService:
    def __init__(self):
        self.repo = SupabaseChatRepository()

    # ── Session CRUD ──────────────────────────────────────────────────────────

    async def create_session(
        self, user_id: uuid.UUID, payload: ChatSessionCreate
    ) -> ChatSessionDetail:
        ctx_dict = (
            payload.hackathon_context.model_dump() if payload.hackathon_context else None
        )
        row = await self.repo.create_session(
            user_id=user_id,
            title="New Chat",
            hackathon_context=ctx_dict,
        )
        return _row_to_detail(row, [])

    async def list_sessions(self, user_id: uuid.UUID) -> list[ChatSessionListItem]:
        rows = await self.repo.list_sessions(user_id)
        items: list[ChatSessionListItem] = []
        for row in rows:
            ctx = row.get("hackathon_context")
            hackathon_title = ctx.get("title") if isinstance(ctx, dict) else None
            items.append(
                ChatSessionListItem(
                    id=row["id"],
                    title=row["title"],
                    hackathon_title=hackathon_title,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
        return items

    async def get_session(
        self, session_id: str, user_id: uuid.UUID
    ) -> ChatSessionDetail:
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        messages = await self.repo.get_messages(session_id)
        return _row_to_detail(session, messages)

    async def update_session(
        self, session_id: str, user_id: uuid.UUID, payload: ChatSessionUpdate
    ) -> ChatSessionDetail:
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

        updates: dict = {}
        if "title" in payload.model_fields_set and payload.title is not None:
            updates["title"] = payload.title.strip() or "New Chat"
        if "hackathon_context" in payload.model_fields_set:
            updates["hackathon_context"] = (
                payload.hackathon_context.model_dump()
                if payload.hackathon_context
                else None
            )

        if updates:
            session = await self.repo.update_session(session_id, user_id, updates) or session

        messages = await self.repo.get_messages(session_id)
        return _row_to_detail(session, messages)

    async def delete_session(self, session_id: str, user_id: uuid.UUID) -> None:
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        await self.repo.delete_session(session_id, user_id)

    # ── Chat with tool use ────────────────────────────────────────────────────

    async def send_message(
        self, session_id: str, user_id: uuid.UUID, payload: SessionChatRequest
    ) -> SessionChatResponse:
        # 1. Verify session ownership
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

        # 2. Load message history
        existing_messages = await self.repo.get_messages(session_id)

        # 3. Save user message
        await self.repo.add_message(session_id, "user", payload.message)

        # 4. Track whether this is the first message (title generated after reply)
        is_first_message = not existing_messages and session["title"] == "New Chat"

        # 5. Build messages for Bedrock (history + new message)
        bedrock_messages = [
            {"role": m["role"], "content": [{"text": m["content"]}]}
            for m in existing_messages
        ]
        bedrock_messages.append({"role": "user", "content": [{"text": payload.message}]})

        # 6. Resolve hackathon context → system prompt
        ctx_data = session.get("hackathon_context")
        ctx: HackathonContextForChat | None = None
        if ctx_data and isinstance(ctx_data, dict):
            try:
                ctx = HackathonContextForChat.model_validate(ctx_data)
            except Exception:
                ctx = None

        # 6b. Pre-fetch DB context so the LLM already knows what's in the database
        tech_summary = ""
        top_projects_preview = ""
        hackathon_projects_preview = ""
        try:
            proj_repo = SupabaseProjectRepository()

            # Top technologies — LLM uses exact names as technology filter
            tech_stats = await proj_repo.get_technology_stats(limit=20)
            if tech_stats:
                tech_summary = ", ".join(
                    f'"{t}" ({c})' for t, c in tech_stats[:20]
                )

            # If a hackathon is selected, fetch projects relevant to its themes
            if ctx and (ctx.themes or ctx.tags or ctx.title):
                # Build a search query from hackathon themes + tags
                theme_query = " ".join(
                    (ctx.themes[:3] if ctx.themes else [])
                    + (ctx.tags[:2] if ctx.tags else [])
                ) or ctx.title

                # Try semantic search first, fall back to keyword search
                hack_projs: list = []
                embedding = await get_bedrock_embedding(theme_query)
                if embedding:
                    hack_projs = await proj_repo.semantic_search(
                        embedding=embedding, limit=5
                    )
                if not hack_projs:
                    # Keyword fallback: search titles/taglines for theme words
                    for term in (ctx.themes or [ctx.title])[:3]:
                        hack_projs, _ = await proj_repo.list_projects(
                            page=1, page_size=5, search=term, sort="likes"
                        )
                        if hack_projs:
                            break
                if hack_projs:
                    rows = []
                    for p in hack_projs:
                        tech = ", ".join(p.technologies[:4]) if p.technologies else "N/A"
                        win = " [WINNER]" if p.is_winner else ""
                        rows.append(
                            f'• "{p.title}"{win} — {p.tagline or "no tagline"} | {tech}'
                        )
                    hackathon_projects_preview = "\n".join(rows)

            # Top 5 projects by likes — general inspiration fallback
            top_projects, _ = await proj_repo.list_projects(
                page=1, page_size=5, sort="likes"
            )
            if top_projects:
                rows = []
                for p in top_projects:
                    tech = ", ".join(p.technologies[:4]) if p.technologies else "N/A"
                    win = " [WINNER]" if p.is_winner else ""
                    rows.append(
                        f'• "{p.title}"{win} — {p.tagline or "no tagline"} | {tech}'
                    )
                top_projects_preview = "\n".join(rows)
        except Exception:
            pass  # non-critical — copilot still works without this

        system_prompt = build_copilot_system_prompt(
            ctx,
            tech_summary=tech_summary,
            top_projects_preview=top_projects_preview,
            hackathon_projects_preview=hackathon_projects_preview,
        )

        # 7. Call Bedrock with tool use loop
        reply_text, projects = await self._call_with_tools(system_prompt, bedrock_messages)

        # 8. Save assistant reply + generate smart title concurrently on first message
        if is_first_message:
            assistant_msg, smart_title = await asyncio.gather(
                self.repo.add_message(session_id, "assistant", reply_text),
                self._generate_session_title(payload.message, ctx),
            )
            await self.repo.update_session(session_id, user_id, {"title": smart_title})
        else:
            assistant_msg = await self.repo.add_message(session_id, "assistant", reply_text)
            # 9. Bump session updated_at so it floats to top of list
            await self.repo.update_session(session_id, user_id, {})

        return SessionChatResponse(
            reply=reply_text,
            session_id=session_id,
            message_id=assistant_msg["id"],
            projects=projects,
        )

    # ── Smart session title ───────────────────────────────────────────────────

    async def _generate_session_title(
        self,
        user_message: str,
        ctx: HackathonContextForChat | None,
    ) -> str:
        """
        Use a quick LLM call (max 20 tokens) to generate a unique 4-6 word
        session title from the user's first message and hackathon context.
        Runs concurrently with saving the assistant reply — zero extra latency.
        """
        hackathon_hint = f"\nHackathon: {ctx.title}" if ctx else ""
        prompt = (
            f"User message: {user_message[:300]}{hackathon_hint}\n\n"
            "Write a 4-6 word session title that captures the specific topic. "
            "Output ONLY the title — no quotes, no period at the end."
        )
        try:
            raw = await call_bedrock_converse(
                system=(
                    "You generate short, specific chat session titles. "
                    "4 to 6 words only. No quotes. No trailing punctuation. "
                    "Make each title unique and descriptive of the actual topic."
                ),
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                max_tokens=20,
                temperature=0.5,
            )
            title = _strip_thinking(raw).strip().strip('"\'').rstrip(".").strip()
            # Sanity-check: must be non-empty and reasonably short
            if title and len(title) <= 120:
                return title
        except Exception:
            pass
        # Fallback: first 6 words of the user message
        words = user_message.split()
        return " ".join(words[:6]) + ("…" if len(words) > 6 else "")

    # ── Tool use loop ─────────────────────────────────────────────────────────

    async def _call_with_tools(
        self,
        system_prompt: str,
        messages: list[dict],
    ) -> tuple[str, list[ProjectSnippet] | None]:
        """
        Agentic tool-use loop with Bedrock.
        Returns (reply_text, project_cards_or_None).
        """
        body: dict = {
            "system": [{"text": system_prompt}],
            "messages": list(messages),  # local copy — we append to it during the loop
            "inferenceConfig": {"maxTokens": 2048, "temperature": 0.75},
            "toolConfig": _TOOL_CONFIG,
        }

        all_projects: list[ProjectSnippet] = []

        for _ in range(_MAX_TOOL_ITERATIONS):
            response = await call_bedrock_raw(body)
            stop_reason = response.get("stopReason", "end_turn")
            output_content: list[dict] = response.get("output", {}).get("message", {}).get("content", [])

            if stop_reason == "end_turn":
                text_parts = [b["text"] for b in output_content if "text" in b]
                reply = _strip_thinking("\n".join(text_parts)) or "(no response)"
                return reply, all_projects if all_projects else None

            if stop_reason == "tool_use":
                # Add assistant's tool-use turn to the conversation
                body["messages"].append({"role": "assistant", "content": output_content})

                # Execute each tool call
                tool_result_content: list[dict] = []
                for block in output_content:
                    if "toolUse" not in block:
                        continue
                    tool = block["toolUse"]
                    result_text, snippets = await self._execute_tool(tool["name"], tool.get("input", {}))
                    all_projects.extend(snippets)
                    tool_result_content.append({
                        "toolResult": {
                            "toolUseId": tool["toolUseId"],
                            "content": [{"text": result_text}],
                            "status": "success",
                        }
                    })

                # Return tool results to Bedrock
                body["messages"].append({"role": "user", "content": tool_result_content})
                continue

            # Any other stop reason — grab whatever text is there
            text_parts = [b["text"] for b in output_content if "text" in b]
            return _strip_thinking("\n".join(text_parts)) or "(no response)", all_projects if all_projects else None

        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI tool-use loop exceeded max iterations.")

    async def _execute_tool(
        self, tool_name: str, tool_input: dict
    ) -> tuple[str, list[ProjectSnippet]]:
        """Execute a tool call and return (result_text_for_model, project_snippets_for_ui)."""
        if tool_name == "search_projects":
            return await self._search_projects(tool_input)
        return f"Unknown tool: {tool_name}", []

    async def _search_projects(
        self, tool_input: dict
    ) -> tuple[str, list[ProjectSnippet]]:
        """
        Query the projects DB using semantic search (pgvector) when a natural
        language query is provided, falling back to filter-based search.
        """
        try:
            repo = SupabaseProjectRepository()
            search = tool_input.get("search") or None
            technology = tool_input.get("technology") or None
            winner_only = bool(tool_input.get("winner_only", False))
            limit = min(int(tool_input.get("limit", 5)), 8)

            projects: list = []

            # ── Semantic search (primary path when query text is given) ───────
            if search:
                embedding = await get_bedrock_embedding(search)
                if embedding:
                    projects = await repo.semantic_search(
                        embedding=embedding,
                        limit=limit,
                        technology=technology,
                        is_winner=winner_only,
                    )

            # ── Technology-only filter (no text query) ────────────────────────
            if not projects and technology:
                projects, _ = await repo.list_projects(
                    page=1,
                    page_size=limit,
                    technology=technology,
                    is_winner=True if winner_only else None,
                    sort="likes",
                )

            # ── Keyword fallback: search titles/taglines by the technology term ─
            # e.g. technology="AI" has no exact tag, but many projects say "AI"
            # in their title or tagline — catch those here
            if not projects and technology:
                projects, _ = await repo.list_projects(
                    page=1,
                    page_size=limit,
                    search=technology,          # ilike on title + tagline
                    is_winner=True if winner_only else None,
                    sort="likes",
                )

            # ── Winner-only filter ────────────────────────────────────────────
            if not projects and winner_only:
                projects, _ = await repo.list_projects(
                    page=1,
                    page_size=limit,
                    is_winner=True,
                    sort="likes",
                )

            # ── Final fallback: top-N by likes — always returns something ─────
            if not projects:
                projects, _ = await repo.list_projects(
                    page=1,
                    page_size=limit,
                    sort="likes",
                )

            if not projects:
                return "The HackFeed database has no projects yet.", []

            # Build snippets for UI cards
            snippets = [
                ProjectSnippet(
                    id=p.id,
                    title=p.title,
                    tagline=p.tagline,
                    url=p.url,
                    thumbnail=p.thumbnail,
                    technologies=p.technologies[:6],
                    hackathon_name=p.hackathon_name,
                    likes_count=p.likes_count,
                    views=p.views,
                    team_members_count=len(p.team_members) if p.team_members else 0,
                    is_winner=p.is_winner,
                    github_url=p.github_url,
                    demo_url=p.demo_url,
                )
                for p in projects
            ]

            # Compact summary text for the model to reason about
            summary_rows = []
            for p in projects:
                tech = ", ".join(p.technologies[:4]) if p.technologies else "N/A"
                winner = " 🏆 WINNER" if p.is_winner else ""
                likes = f" ({p.likes_count} likes)" if p.likes_count else ""
                summary_rows.append(
                    f'- **{p.title}**{winner}{likes}: {p.tagline or "No tagline"} | Tech: {tech}'
                )

            result_text = f"Found {len(projects)} projects:\n" + "\n".join(summary_rows)
            return result_text, snippets

        except Exception as exc:
            return f"Project search failed: {exc}", []
