import discord
from discord.ext import commands

class Avatar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="avatar", aliases=["av", "pfp"])
    async def avatar(self, ctx, *, member: discord.Member = None):
        """Display a user's avatar."""
        
        if member is None:
            member = ctx.author

        embed = discord.Embed(
            title=f"{member.display_name}'s Avatar",
            color=discord.Color.blue()
        )

        embed.set_image(url=member.avatar.url)

        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Avatar(bot))

