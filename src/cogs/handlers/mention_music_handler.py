from __future__ import annotations

import logging
import os
import re
from typing import Any

import discord

logger = logging.getLogger(__name__)


async def handle_mention_music(cog: Any, message: discord.Message, clean_content: str) -> bool:
    """
    Handle mention-based music requests.

    Returns:
        True if handled and caller should return early, False otherwise.
    """
    try:
        music_enabled = str(os.getenv("ORA_MUSIC_MENTION_TRIGGERS") or "1").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not music_enabled:
            return False

        legacy_allow_all = str(os.getenv("ORA_MUSIC_MENTION_ALLOW_NON_ADMIN") or "0").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        # Default policy:
        # - private: owner-only (safe)
        # - shared: allow everyone by default (friend-friendly)
        prof = (getattr(cog.bot.config, "profile", None) or "private").strip().lower()
        default_att = "user" if prof == "shared" else "owner"
        default_yt = "user" if prof == "shared" else "vc_admin"

        level_att = (os.getenv("ORA_MUSIC_MENTION_LEVEL") or "").strip().lower() or (
            "user" if legacy_allow_all else default_att
        )
        level_yt = (os.getenv("ORA_MUSIC_MENTION_YOUTUBE_LEVEL") or "").strip().lower() or (
            "user" if legacy_allow_all else default_yt
        )

        async def _allow(level: str) -> bool:
            lv = (level or "owner").strip().lower()
            if lv == "user":
                return True
            if lv == "vc_admin":
                return await cog._check_permission(message.author.id, "vc_admin")
            # default: owner
            return message.author.id == cog.bot.config.admin_user_id

        if not (await _allow(level_att)):
            return False

        kw_trigger = any(k in clean_content.lower() for k in ["play", "music", "song", "流して", "再生", "かけて", "聴かせ"])

        # Attachment audio (mp3/wav/ogg/m4a)
        att = None
        for a in (getattr(message, "attachments", []) or []):
            fn = (getattr(a, "filename", "") or "").lower()
            ct = (getattr(a, "content_type", "") or "").lower()
            if fn.endswith((".mp3", ".wav", ".ogg", ".m4a")) or ct.startswith("audio/"):
                att = a
                break

        # YouTube/Spotify URL in message content
        yt_url = None
        sp_url = None
        for tok in clean_content.split():
            t = tok.strip().strip("<>").strip()
            if ("youtube.com" in t) or ("youtu.be" in t):
                if t.startswith("http://") or t.startswith("https://"):
                    yt_url = t
                    break
            if (
                ("open.spotify.com" in t)
                or ("spotify.com" in t)
                or ("spotify.link" in t)
                or ("spoti.fi" in t)
                or t.startswith("spotify:")
            ):
                if t.startswith("spotify:") or t.startswith("http://") or t.startswith("https://"):
                    sp_url = t

        want_music = kw_trigger or bool(att) or bool(yt_url or sp_url)
        if not want_music:
            return False

        media_cog = cog.bot.get_cog("MediaCog")
        if not media_cog:
            return False

        # Mention UX default: @Bot + playlist URL should immediately queue all.
        # Set ORA_MUSIC_MENTION_PLAYLIST_MODE=ui to force action buttons first.
        playlist_mode = (os.getenv("ORA_MUSIC_MENTION_PLAYLIST_MODE") or "queue_all").strip().lower()
        prefer_queue_all = playlist_mode not in {"ui", "picker"}

        # 1) Attachment audio
        if att and hasattr(media_cog, "play_attachment_from_ai"):
            ctx = await cog.bot.get_context(message)
            await media_cog.play_attachment_from_ai(ctx, att)
            try:
                await message.add_reaction("🎵")
            except Exception:
                pass
            return True

        # URL playback permission can be stricter than attachments.
        if (yt_url or sp_url) and not (await _allow(level_yt)):
            logger.info(
                "Mention music denied (url): user_id=%s guild_id=%s required=%s",
                message.author.id,
                getattr(message.guild, "id", None),
                level_yt,
            )
            return False

        # 2) Spotify URL
        if sp_url and (not yt_url):
            ctx = await cog.bot.get_context(message)
            try:
                if prefer_queue_all and hasattr(media_cog, "enqueue_playlist_url_from_ai"):
                    await media_cog.enqueue_playlist_url_from_ai(ctx, sp_url, force_queue_all=True)
                elif hasattr(media_cog, "playlist_actions_ui_from_ai"):
                    await media_cog.playlist_actions_ui_from_ai(ctx, sp_url)
                elif hasattr(media_cog, "enqueue_playlist_url_from_ai"):
                    await media_cog.enqueue_playlist_url_from_ai(ctx, sp_url, force_queue_all=True)
                else:
                    await media_cog.play_from_ai(ctx, sp_url)
            except Exception:
                await media_cog.play_from_ai(ctx, sp_url)
            try:
                await message.add_reaction("🎵")
            except Exception:
                pass
            return True

        # 3) YouTube URL
        if yt_url:
            ctx = await cog.bot.get_context(message)
            try:
                is_playlist = False
                try:
                    from ...utils.youtube import is_youtube_playlist_url

                    is_playlist = is_youtube_playlist_url(yt_url)
                except Exception:
                    is_playlist = ("list=" in yt_url) or ("/playlist" in yt_url)

                if prefer_queue_all and is_playlist and hasattr(media_cog, "enqueue_playlist_url_from_ai"):
                    await media_cog.enqueue_playlist_url_from_ai(ctx, yt_url, force_queue_all=True)
                elif hasattr(media_cog, "playlist_actions_ui_from_ai"):
                    await media_cog.playlist_actions_ui_from_ai(ctx, yt_url)
                elif hasattr(media_cog, "enqueue_playlist_url_from_ai"):
                    await media_cog.enqueue_playlist_url_from_ai(ctx, yt_url, force_queue_all=True)
                else:
                    await media_cog.play_from_ai(ctx, yt_url)
            except Exception:
                await media_cog.play_from_ai(ctx, yt_url)
            try:
                await message.add_reaction("🎵")
            except Exception:
                pass
            return True

        # 4) YouTube search by query (no URL provided)
        # Example: "@YonerAI YOASOBI 流して" -> search YouTube and play top result.
        if kw_trigger:
            q = clean_content.strip()
            try:
                bot_name = ""
                if getattr(cog.bot, "user", None):
                    bot_name = (
                        getattr(cog.bot.user, "display_name", None) or getattr(cog.bot.user, "name", None) or ""
                    )
                if bot_name:
                    q = re.sub(rf"^@?{re.escape(str(bot_name))}\s*", "", q, flags=re.IGNORECASE)
            except Exception:
                pass

            for kw in ["play", "music", "song", "流して", "再生", "かけて", "聴かせ", "流せ", "かけろ"]:
                try:
                    q = q.replace(kw, " ")
                    q = q.replace(kw.upper(), " ")
                except Exception:
                    pass
            q = re.sub(r"\s+", " ", q).strip(" \t:：-")

            if q:
                ctx = await cog.bot.get_context(message)
                await media_cog.play_from_ai(ctx, q)
                try:
                    await message.add_reaction("🎵")
                except Exception:
                    pass
                return True

    except Exception:
        logger.exception("Mention music handler failed unexpectedly")

    return False

