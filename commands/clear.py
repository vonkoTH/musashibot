import discord
from discord.ext import commands

class Clear(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="clear", aliases=["efassador", "erradicador"])
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int = None):
        """Clear a specified number of messages from the channel."""
        if amount is None:
            deleted = await ctx.channel.purge(limit=10000)
            await ctx.send(f"Deleted {len(deleted)} messages.")            
            return

        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f"Deleted {len(deleted)} messages.")


async def setup(bot):
    await bot.add_cog(Clear(bot))
