import discord
import logging
import psutil
import os

logger = logging.getLogger(__name__)

async def info(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """System Info."""
    mem = psutil.virtual_memory()
    embed = discord.Embed(title="System Status", color=0x00ff00)
    embed.add_field(name="Memory", value=f"{mem.percent}% ({mem.used/1024**3:.1f}GB / {mem.total/1024**3:.1f}GB)")
    if bot:
        embed.add_field(name="Latency", value=f"{bot.latency*1000:.1f}ms")
        embed.add_field(name="Guilds", value=str(len(bot.guilds)))
    
    await message.reply(embed=embed)
    return "Status sent. [SILENT_COMPLETION]"

async def router_health(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """Displays Router Health Metrics (S7)."""
    try:
        from src.cogs.handlers.router_monitor import router_monitor
        metrics = router_monitor.get_metrics()
        
        status_emoji = "🟢" if "HEALTHY" in metrics["status"] else "🔴"
        if metrics["status"] == "DEGRADED": status_emoji = "🟡"
        
        embed = discord.Embed(
            title=f"{status_emoji} Router Health: {metrics['status']}",
            color=0x00ff00 if metrics["status"] == "HEALTHY" else (0xffff00 if metrics["status"] == "DEGRADED" else 0xff0000)
        )
        
        m = metrics["metrics"]
        embed.add_field(name="Fallback Rate", value=f"{m['fallback_rate_percent']}%", inline=True)
        embed.add_field(name="Retry Rate", value=f"{m['retry_rate_percent']}%", inline=True)
        embed.add_field(name="Latency (P95/Avg)", value=f"{m['latency_p95_ms']}ms / {m['latency_avg_ms']}ms", inline=True)
        embed.add_field(
            name="Cache Stability",
            value=f"Unstable Bundles: {m.get('unstable_bundles_count', 0)}\nBundle Versions: {m['unique_bundles']}",
            inline=False,
        )
        
        if metrics["alerts"]:
            embed.add_field(name="⚠️ Alerts", value="\n".join(metrics["alerts"]), inline=False)
            
        embed.set_footer(text=f"Window: {metrics['window_size']} requests | Last Event: {metrics['last_event_time']}")
        
        await message.reply(embed=embed)
        return "Health metrics sent. [SILENT_COMPLETION]"
    except Exception as e:
        return f"❌ Failed to get router health: {e}"

async def check_privilege(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    if bot and message.author.id == bot.config.admin_user_id:
        return "👑 Admin"
    return "User"
