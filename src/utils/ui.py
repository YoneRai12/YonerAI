import asyncio
import time
from typing import List, Optional

import discord


class StatusManager:
    """Manages the interactive 'Thinking' status message."""

    # Custom Emojis (User Uploaded)
    EMOJI_PROCESSING = "<a:rode:1449406298788597812>"
    EMOJI_DONE = "<a:conp:1449406158883389621>"
    EMOJI_PENDING = "▫️"
    EMOJI_FAILED = "❌"

    def __init__(self, channel: discord.abc.Messageable, existing_message: Optional[discord.Message] = None):
        self.channel = channel
        self.message: Optional[discord.Message] = existing_message
        self.steps: List[dict] = []  # List of {"label": str, "done": bool}
        self.file_buffer: List[dict] = [] # List of {"path": str, "filename": str, "content": str}
        self._lock = asyncio.Lock()
        self._last_update_time = 0.0
        self._update_task = None
        self.task_board: Optional[dict] = None

    def add_file(self, file_path: str, filename: str, content: str = ""):
        """Buffer a file to be sent later."""
        self.file_buffer.append({
            "path": file_path,
            "filename": filename,
            "content": content
        })

    async def flush_files(self, message: discord.Message = None):
        """Flush buffered files into combined messages."""
        if not self.file_buffer:
            return

        target_msg = message or self.message
        if not target_msg:
             return

        # Determine Limit
        limit_bytes = 10 * 1024 * 1024 # 10MB Default
        if target_msg.guild:
             limit_bytes = target_msg.guild.filesize_limit
        
        # Max files per message = 10
        import os
        
        current_batch_files = []
        current_batch_size = 0
        current_content_lines = []

        async def send_batch(files, content_lines):
             if not files: return
             
             # Construct content
             final_content = "\n".join(content_lines)
             if len(final_content) > 2000: final_content = final_content[:2000]
             
             try:
                 await target_msg.reply(content=final_content, files=files)
             except Exception as e:
                 # Fallback: Send individually
                 first_err = e
                 for f in files:
                      try:
                          f.fp.seek(0)
                          await target_msg.reply(file=f)
                      except Exception as inner_e:
                          await target_msg.channel.send(f"⚠️ ファイル送信失敗 ({f.filename}): {inner_e}")


        for item in self.file_buffer:
             try:
                 size = os.path.getsize(item["path"])
                 
                 # Check if adding this file exceeds limit or count
                 if (len(current_batch_files) >= 10) or (current_batch_size + size > limit_bytes):
                      # Flush current
                      await send_batch(current_batch_files, current_content_lines)
                      # Reset
                      current_batch_files = []
                      current_batch_size = 0
                      current_content_lines = []
                 
                 # Add to current
                 f_obj = discord.File(item["path"], filename=item["filename"])
                 current_batch_files.append(f_obj)
                 current_batch_size += size
                 if item["content"]:
                     current_content_lines.append(item["content"])
                     
             except Exception as e:
                 # If file error, skip
                 pass

        # Flush remaining
        if current_batch_files:
             await send_batch(current_batch_files, current_content_lines)
        
        # Cleanup: Delete all buffered files
        for item in self.file_buffer:
             try:
                 if os.path.exists(item["path"]):
                     os.remove(item["path"])
             except: pass
        
        # Clear buffer
        self.file_buffer = []

    async def start(self, label: str = "思考中", mode: str = "normal"):
        """
        Send the initial status message.
        mode: "normal" | "override"
        """
        self.steps = [{"label": label, "done": False}]
        self.mode = mode

        embed = self._build_embed()
        try:
            self.message = await self.channel.send(embed=embed)
        except Exception:
            pass  # Ignore if permission error etc.

    async def start_task_board(self, title: str, tasks: List[str], footer: str = "ORA Universal Brain"):
        """Start a numbered task board (1..N) with dynamic status updates."""
        self.task_board = {
            "title": title,
            "footer": footer,
            "tasks": [{"label": t, "state": "pending", "detail": ""} for t in tasks],
            "timeline": [],
        }
        embed = self._build_embed()
        try:
            self.message = await self.channel.send(embed=embed)
        except Exception:
            pass

    async def replace_tasks(
        self,
        tasks: List[str],
        *,
        title: str | None = None,
        footer: str | None = None,
        preserve_prefix_states: bool = True,
    ) -> None:
        """
        Replace the task list in the existing task board.

        Used to display "execution plan" as the first status card task list,
        instead of sending a separate plan message.
        """
        async with self._lock:
            if not self.message or not self.task_board:
                return

            old = self.task_board.get("tasks") or []
            new = [{"label": t, "state": "pending", "detail": ""} for t in tasks]

            if preserve_prefix_states:
                for i in range(min(len(old), len(new))):
                    try:
                        new[i]["state"] = old[i].get("state", "pending")
                        new[i]["detail"] = old[i].get("detail", "")
                    except Exception:
                        pass

            if title is not None:
                self.task_board["title"] = title
            if footer is not None:
                self.task_board["footer"] = footer
            self.task_board["tasks"] = new

            await self._update(force=True)

    async def set_task_state(self, index: int, state: str, detail: str = ""):
        """Set a task status. index is 1-based."""
        async with self._lock:
            if not self.message or not self.task_board:
                return
            i = index - 1
            if i < 0 or i >= len(self.task_board["tasks"]):
                return
            self.task_board["tasks"][i]["state"] = state
            if detail:
                self.task_board["tasks"][i]["detail"] = detail[:120]
            await self._update(force=True)

    async def add_timeline(self, text: str):
        """Append a short timeline line to the task board."""
        async with self._lock:
            if not self.message or not self.task_board:
                return
            line = text[:160]
            self.task_board["timeline"].append(line)
            self.task_board["timeline"] = self.task_board["timeline"][-6:]
            await self._update(force=False)

    async def next_step(self, label: str, force: bool = False):
        """Mark current step as done and add a new step. Set force=True for animations."""
        async with self._lock:
            if not self.message:
                return

            # Mark last step as done
            if self.steps:
                self.steps[-1]["done"] = True

            # Add new step
            self.steps.append({"label": label, "done": False})

            await self._update(force=force)

    async def update_current(self, label: str, force: bool = False):
        """Update the text of the *current* running step. Set force=True for animations."""
        async with self._lock:
            if not self.message or not self.steps:
                return

            self.steps[-1]["label"] = label
            await self._update(force=force)

    async def complete(self):
        """Mark the current step as done without adding a new one."""
        async with self._lock:
            if self.steps:
                self.steps[-1]["done"] = True
                await self._update(force=True)

    async def finish(self):
        """Mark all as done, flush any remaining files, and delete the message."""
        async with self._lock:
            if not self.message:
                return

            try:
                # Flush any remaining files before deleting status message
                if self.file_buffer:
                    await self.flush_files()
                
                await self.message.delete()
            except Exception:
                pass
            self.message = None

    async def _update(self, force: bool = False):
        """Edit the message with current steps (Debounced)."""
        if not self.message:
            return

        now = time.time()

        # Immediate update if Forced
        if force:
            await self._force_update()
            return

        # RATE LIMIT PREVENTER: Max 1 update per 2.0 seconds
        if now - self._last_update_time < 2.0:
            # If a task is already waiting to update, let it handle it.
            if self._update_task and not self._update_task.done():
                return

            # Create a delayed update task
            async def delayed():
                await asyncio.sleep(2.0 - (time.time() - self._last_update_time))
                await self._force_update()

            self._update_task = asyncio.create_task(delayed())
            return

        await self._force_update()

    async def _force_update(self):
        """Internal immediate update."""
        if not self.message:
            return

        # Guard for deleted message
        try:
            embed = self._build_embed()
            await self.message.edit(embed=embed)
            self._last_update_time = time.time()
        except discord.NotFound:
            # Message was deleted (e.g. by finish()), stop updating
            self.message = None
        except Exception:
            pass

    def _build_embed(self) -> discord.Embed:
        if self.task_board:
            title = self.task_board["title"]
            footer = self.task_board["footer"]
            task_lines = []
            for idx, task in enumerate(self.task_board["tasks"], start=1):
                state = task.get("state", "pending")
                if state == "done":
                    icon = self.EMOJI_DONE
                elif state == "running":
                    icon = self.EMOJI_PROCESSING
                elif state == "failed":
                    icon = self.EMOJI_FAILED
                else:
                    icon = self.EMOJI_PENDING
                line = f"{idx}. {icon} **{task.get('label', '')}**"
                detail = task.get("detail", "")
                if detail:
                    line += f"\n　└ {detail}"
                task_lines.append(line)

            timeline = self.task_board.get("timeline") or []
            if timeline:
                task_lines.append("\n**実行ログ**")
                for item in timeline:
                    task_lines.append(f"• {item}")

            desc = "\n".join(task_lines)[:3900]
            embed = discord.Embed(title=title[:250], description=desc, color=0x2ECC71)
            embed.set_footer(text=footer[:200])
            return embed

        # Build text description
        lines = []
        for step in self.steps:
            icon = self.EMOJI_DONE if step["done"] else self.EMOJI_PROCESSING
            # Format: icon **Label**
            lines.append(f"{icon} **{step['label']}**")

        desc = "\n".join(lines)

        # Style based on Mode
        if hasattr(self, "mode") and self.mode == "override":
            title = "🚨 SYSTEM OVERRIDE"
            color = 0xFF0000  # Red
            footer = "⚠️ 警告: セーフティ・リミッター解除中"
        else:
            title = "⚙️ System Processing"
            color = 0x2ECC71  # Green
            footer = "ORA Universal Brain"

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color,
        )
        embed.set_footer(text=footer)
        return embed


class EmbedFactory:
    """Factory for creating consistent Discord Embeds."""

    @staticmethod
    def create_search_embed(query: str, results: List[dict]) -> discord.Embed:
        """
        Create a card for search results.
        results: List of {"title": str, "link": str, "snippet": str}
        """
        embed = discord.Embed(
            title=f"🔍 検索結果: {query}",
            color=0x4285F4,  # Google Blue
            timestamp=discord.utils.utcnow(),
        )

        # Set Thumbnail from First Result if available
        if results and "thumbnail" in results[0] and results[0]["thumbnail"]:
            embed.set_thumbnail(url=results[0]["thumbnail"])

        # Add Top 3-5 Results
        for i, res in enumerate(results[:5]):
            title = res.get("title", "No Title")
            link = res.get("link", "")
            snippet = res.get("snippet", "")

            # Format: Snippet...
            #         [🔗 サイトを見る](Link)
            field_val = f"{snippet[:150]}..." if len(snippet) > 150 else snippet
            if link:
                field_val += f"\n[🔗 サイトを見る]({link})"

            embed.add_field(name=f"{i + 1}. {title}", value=field_val, inline=False)

        embed.set_footer(text="Powered by Google Search")
        return embed

    @staticmethod
    def create_info_embed(
        title: str, description: str, fields: Optional[dict] = None, color: int = 0x95A5A6
    ) -> discord.Embed:
        """Create a generic info card."""
        embed = discord.Embed(
            title=f"ℹ️ {title}", description=description, color=color, timestamp=discord.utils.utcnow()
        )

        if fields:
            for k, v in fields.items():
                val_str = str(v)
                if len(val_str) > 1000:
                    val_str = val_str[:1000] + "..."
                embed.add_field(name=k, value=val_str, inline=True)

        return embed

    @staticmethod
    def create_news_embed(source_name: str, articles: List[dict]) -> discord.Embed:
        """
        Create a card for news.
        articles: List of {"title": str, "url": str, "image_url": str (opt)}
        """
        embed = discord.Embed(
            title=f"📰 今日のニュース ({source_name})",
            color=0xE74C3C,  # News Red
            timestamp=discord.utils.utcnow(),
        )

        for i, art in enumerate(articles[:5]):
            embed.add_field(name=f"{i + 1}. {art['title']}", value=f"[記事を読む]({art['url']})", inline=False)

        # Set image from first article if available
        if articles and "image_url" in articles[0] and articles[0]["image_url"]:
            embed.set_image(url=articles[0]["image_url"])

        return embed

    @staticmethod
    def create_chat_embed(content: str, model_name: str = "ORA Universal Brain", footer_text: str = "Sanitized & Powered by ORA Universal Brain") -> discord.Embed:
        """
        Create a card for normal chat responses.
        """
        # Truncate if too long (Embed limit is 4096)
        if len(content) > 4000:
            content = content[:4000] + "..."

        embed = discord.Embed(
            description=content,
            color=0x7289DA,  # Blurple or Brand Color
            timestamp=discord.utils.utcnow(),
        )
        
        # Header: Model Name
        embed.set_author(name=f"⚡ {model_name}", icon_url="https://cdn.discordapp.com/emojis/1326002165039206461.webp?size=96&quality=lossless")

        # Footer
        if footer_text:
            embed.set_footer(text=footer_text)

        return embed
