import discord
from discord.ext import commands

class Announce(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="announce")
    @commands.has_permissions(manage_messages=True)
    async def announce(self, ctx, mention_everyone: bool = False, *, message=""):
        """Sends a formatted announcement to the current channel.
        
        Usage: !announce [True/False] <message> + attach image
        Example: !announce False Hello everyone!
        Example: !announce True Important update! + image attachment
        """
        # Handle empty message with attachment
        if not message and not ctx.message.attachments:
            await ctx.send("Please provide a message or attach an image.", delete_after=5)
            return
        
        embed = discord.Embed(
            description=message if message else "",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Announcement by {ctx.author.display_name}")
        
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        
        # Add image if attachment exists
        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]
            # Check if it's an image
            if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                embed.set_image(url=attachment.url)
        
        mention = "@everyone" if mention_everyone else ""
        
        try:
            await ctx.message.delete()  # Delete the command message
            await ctx.send(content=mention, embed=embed)
        except discord.Forbidden:
            await ctx.send("I don't have permission to send messages or delete in this channel.", delete_after=5)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}", delete_after=5)

async def setup(bot):
    await bot.add_cog(Announce(bot))
