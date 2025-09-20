import discord
from discord.ext import commands
import yt_dlp
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from collections import deque
import os
import traceback
import time
from concurrent.futures import ThreadPoolExecutor

def is_spotify_url(url):
    return 'open.spotify.com' in url

executor = ThreadPoolExecutor(max_workers=4)

def run_blocking_io(func, *args):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(executor, func, *args)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.currently_playing = {}
        self.spotify = self.setup_spotify()
        self.search_cache = {}
        self.CACHE_TTL = 3600
        self.ytdl_options = {
            'format': 'bestaudio[ext=webm]/bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'extractaudio': False,
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'logtostderr': False,
            'ignoreerrors': False,
            'default_search': 'ytsearch',
            'socket_timeout': 10,
            'retries': 2
        }
        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

    def setup_spotify(self):
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        if not client_id or not client_secret:
            print("Spotify credentials not found in environment variables.")
            return None
        auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        return spotipy.Spotify(auth_manager=auth_manager)

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = deque()
        return self.queues[guild_id]

    async def search_youtube(self, query):
        cache_key = f"yt_{query.lower()}"
        if cache_key in self.search_cache:
            cached_data, timestamp = self.search_cache[cache_key]
            if time.time() - timestamp < self.CACHE_TTL:
                return cached_data

        try:
            search_opts = self.ytdl_options.copy()
            search_opts.update({
                'extract_flat': False,
                'skip_download': True,
                'playlistend': 1
            })

            def extract_info():
                with yt_dlp.YoutubeDL(search_opts) as ytdl:
                    return ytdl.extract_info(f"ytsearch1:{query}", download=False)

            info = await asyncio.wait_for(run_blocking_io(extract_info), timeout=15.0)

            if 'entries' in info and info['entries']:
                video = info['entries'][0]
                result = {
                    'title': video.get('title', 'Unknown'),
                    'url': video.get('webpage_url', ''),
                    'stream_url': video.get('url', ''),
                    'duration': video.get('duration', 0),
                    'uploader': video.get('uploader', 'Unknown')
                }
                self.search_cache[cache_key] = (result, time.time())
                return result
        except asyncio.TimeoutError:
            print(f"Search timeout for: {query}")
        except Exception as e:
            print(f"Error searching YouTube: {e}")
        return None

    async def get_spotify_track_info(self, url):
        if not self.spotify:
            return None

        try:
            track_id = url.split('/')[-1].split('?')[0]
            track = self.spotify.track(track_id)
            return {
                'title': f"{track['artists'][0]['name']} - {track['name']}",
                'query': f"{track['artists'][0]['name']} {track['name']}"
            }
        except Exception as e:
            print(f"Error getting Spotify track: {e}")
        return None

    async def play_next(self, guild_id):
        queue = self.get_queue(guild_id)
        if not queue:
            self.currently_playing.pop(guild_id, None)
            return

        guild = self.bot.get_guild(guild_id)
        if not guild or not guild.voice_client:
            return

        next_song = queue.popleft()
        self.currently_playing[guild_id] = next_song

        try:
            if 'stream_url' in next_song and next_song['stream_url']:
                url = next_song['stream_url']
            else:
                def get_stream_url():
                    stream_opts = self.ytdl_options.copy()
                    stream_opts['format'] = 'bestaudio[ext=webm]/bestaudio'
                    with yt_dlp.YoutubeDL(stream_opts) as ytdl:
                        info = ytdl.extract_info(next_song['url'], download=False)
                        return info['url']

                url = await asyncio.wait_for(run_blocking_io(get_stream_url), timeout=10.0)

            source = discord.FFmpegPCMAudio(url, **self.ffmpeg_options)
            guild.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(guild_id), self.bot.loop))

        except asyncio.TimeoutError:
            print(f"Stream timeout for: {next_song['title']}")
            await self.play_next(guild_id)
        except Exception as e:
            print(f"Error playing audio: {e}")
            await self.play_next(guild_id)

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx, *, query):
        if not ctx.author.voice:
            await ctx.send("Você precisa estar em um canal de voz!")
            return

        channel = ctx.author.voice.channel

        search_msg = await ctx.send(f"🔍 Procurando: `{query}`")

        async with ctx.typing():
            song_info = None
            if is_spotify_url(query):
                spotify_info = await self.get_spotify_track_info(query)
                if spotify_info:
                    song_info = await self.search_youtube(spotify_info['query'])
            else:
                song_info = await self.search_youtube(query)

            if not song_info:
                await search_msg.edit(content="Não foi possível encontrar a música.")
                return

            if not ctx.voice_client:
                try:
                    await channel.connect()
                except Exception as e:
                    await search_msg.edit(content=f"Erro ao conectar no canal de voz: {e}")
                    return

        queue = self.get_queue(ctx.guild.id)
        queue.append(song_info)

        if not ctx.voice_client.is_playing():
            await self.play_next(ctx.guild.id)
            embed = discord.Embed(title="🎵 Tocando agora", description=song_info['title'], color=0x00ff00)
        else:
            embed = discord.Embed(title="➕ Adicionado à fila", description=song_info['title'], color=0x0099ff)
            embed.add_field(name="Posição na fila", value=len(queue), inline=True)

        await search_msg.edit(content="", embed=embed)

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await ctx.send("Nenhuma música está tocando.")
            return

        ctx.voice_client.stop()
        await ctx.send("⏭️ Música pulada!")

    @commands.command(name="stop")
    async def stop(self, ctx):
        if not ctx.voice_client:
            await ctx.send("❌ Não estou conectado a um canal de voz.")
            return

        queue = self.get_queue(ctx.guild.id)
        queue.clear()
        self.currently_playing.pop(ctx.guild.id, None)

        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        await ctx.send("⏹️ Música parada e desconectado!")

    @commands.command(name="pause")
    async def pause(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await ctx.send("Nenhuma música está tocando.")
            return

        ctx.voice_client.pause()
        await ctx.send("⏸️ Música pausada!")

    @commands.command(name="resume")
    async def resume(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_paused():
            await ctx.send("❌ Nenhuma música está pausada.")
            return

        ctx.voice_client.resume()
        await ctx.send("▶️ Música resumida!")

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx):
        queue = self.get_queue(ctx.guild.id)

        if not queue and ctx.guild.id not in self.currently_playing:
            await ctx.send("A fila está vazia.")
            return

        embed = discord.Embed(title="🎵 Fila de Músicas", color=0x0099ff)

        if ctx.guild.id in self.currently_playing:
            current = self.currently_playing[ctx.guild.id]
            embed.add_field(name="Tocando agora", value=current['title'], inline=False)

        if queue:
            queue_list = []
            for i, song in enumerate(list(queue)[:10], 1):
                queue_list.append(f"{i}. {song['title']}")

            embed.add_field(name="Próximas", value="\n".join(queue_list), inline=False)

            if len(queue) > 10:
                embed.add_field(name="", value=f"... e mais {len(queue) - 10} músicas", inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="clear_queue", aliases=["cq"])
    async def clear_queue(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        queue.clear()
        await ctx.send("🗑️ Fila limpa!")

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx):
        if ctx.guild.id not in self.currently_playing:
            await ctx.send("Nenhuma música está tocando.")
            return

        current = self.currently_playing[ctx.guild.id]
        embed = discord.Embed(title="Tocando agora", description=current['title'], color=0x00ff00)

        if 'uploader' in current:
            embed.add_field(name="Canal", value=current['uploader'], inline=True)

        if 'duration' in current and current['duration']:
            duration = str(current['duration'] // 60) + ":" + str(current['duration'] % 60).zfill(2)
            embed.add_field(name="Duração", value=duration, inline=True)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))

