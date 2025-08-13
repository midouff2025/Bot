import discord
from discord.ext import commands
from collections import defaultdict
from datetime import timedelta
from discord.utils import utcnow
import re
import threading
from aiohttp import web

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

warnings = defaultdict(lambda: {"mention": 0, "link": 0})
ADMIN_IDS = [1336374397723869245]
MUTE_DURATION = 60 * 60
URL_REGEX = re.compile(r'https?://\S+')

@bot.event
async def on_ready():
    print(f"✅ Bot is ready as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    member = message.guild.get_member(message.author.id)

    if member.id not in ADMIN_IDS:
        # ===== نظام المنشن =====
        if any(admin_id in [user.id for user in message.mentions] for admin_id in ADMIN_IDS):
            warnings[member.id]["mention"] += 1

            if warnings[member.id]["mention"] == 1:
                embed = discord.Embed(
                    description=f"**{member.mention} لقد قمت بمنشن المسؤول. المرة القادمة سيتم اسكاتك ⚠️**",
                    color=discord.Color.from_rgb(255, 255, 0)
                )
                await message.channel.send(embed=embed)

            elif warnings[member.id]["mention"] >= 2:
                try:
                    until_time = utcnow() + timedelta(seconds=MUTE_DURATION)
                    await member.timeout(until_time)
                    embed = discord.Embed(
                        description=f"**{member.mention} تم اسكاتك لمدة ساعة بسبب تكرارك للمنشن ⛔**",
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=embed)
                except Exception as e:
                    await message.channel.send(f"❌ لم أتمكن من اسكات العضو: {e}")
                warnings[member.id]["mention"] = 0

        # ===== نظام الروابط =====
        if URL_REGEX.search(message.content):
            warnings[member.id]["link"] += 1
            try:
                await message.delete()
            except:
                pass

            if warnings[member.id]["link"] == 1:
                embed = discord.Embed(
                    description=f"**{member.mention} لا يمكنك إرسال الروابط. المرة القادمة سيتم اسكاتك ⚠️**",
                    color=discord.Color.from_rgb(255, 255, 0)
                )
                await message.channel.send(embed=embed)

            elif warnings[member.id]["link"] >= 2:
                try:
                    until_time = utcnow() + timedelta(seconds=MUTE_DURATION)
                    await member.timeout(until_time)
                    embed = discord.Embed(
                        description=f"**{member.mention} تم اسكاتك لمدة ساعة بسبب تكرارك لنشر الروابط ⛔**",
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=embed)
                except Exception as e:
                    await message.channel.send(f"❌ لم أتمكن من اسكات العضو: {e}")
                warnings[member.id]["link"] = 0

    await bot.process_commands(message)


# ===== سيرفر الويب لمنع النوم =====
async def handle(request):
    return web.Response(text="I'm alive!")

def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    web.run_app(app, port=8080)

threading.Thread(target=start_webserver).start()









bot.run('MTQwNTI1NTgyNDIzMzk4ODE0Nw.GgJg-m.vrsTCPeFnlhjSu_ZDhDEt4axsRGzAFu7Go4xOQ')
