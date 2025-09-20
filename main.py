import discord
from discord.ext import commands
import os
import asyncio
import sys
import traceback
from dotenv import load_dotenv

load_dotenv()

# TOKEN CONFIG
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("Error: DISCORD_TOKEN environment variable not set. The bot cannot start.", file=sys.stderr)
    sys.exit(1)

# INTENTS MAXIMUM PERMISSION
intents = discord.Intents.all()

# Setup Bot, with the prefix.
bot = commands.Bot(command_prefix="$", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is ready!")
    print("-------------")

# Cogs
async def load_cogs():
    print("Loading command cogs...")
    for filename in os.listdir('./commands'):
        if filename.endswith('.py'):
            cog_name = f'commands.{filename[:-3]}' # "admin.py" -> "admin"
            try:
                await bot.load_extension(cog_name)
                print(f"- Loaded cog: {cog_name}")
            except Exception as e:
                print(f"Failed to load cog {cog_name}: {e}", file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)


# Execution
async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (discord.LoginFailure, KeyboardInterrupt): # KeyboardInterrupt is the "Ctrl + C"
        print("Bot shutting down.")
    except Exception as e:
        print("An unexpected error occurred while running the bot:", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
