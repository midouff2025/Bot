import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from datetime import datetime
import json
import os
import io
import uuid
import gc

CONFIG_FILE = "info_channels.json"
ALLOWED_CHANNEL_ID = 1403048599054454935  # القناة المسموح بها فقط

class InfoCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://profile-generator.up.railway.app/api/profile_info"
        self.generate_url = "https://profile-generator.up.railway.app/api/profile"
        self.session = aiohttp.ClientSession()
        self.config_data = self.load_config()
        self.cooldowns = {}

    def convert_unix_timestamp(self, timestamp: int) -> str:
        try:
            return datetime.utcfromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
        except:
            return "Not available"

    def load_config(self):
        default_config = {
            "servers": {},
            "global_settings": {
                "default_all_channels": False,
                "default_cooldown": 30,
                "default_daily_limit": 30
            }
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    loaded_config = json.load(f)
                    loaded_config.setdefault("global_settings", {})
                    loaded_config["global_settings"].setdefault("default_all_channels", False)
                    loaded_config["global_settings"].setdefault("default_cooldown", 30)
                    loaded_config["global_settings"].setdefault("default_daily_limit", 30)
                    loaded_config.setdefault("servers", {})
                    return loaded_config
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config: {e}")
                return default_config
        return default_config

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving config: {e}")

    async def is_channel_allowed(self, ctx):
        # السماح فقط للقناة المسموح بها
        return ctx.channel.id == ALLOWED_CHANNEL_ID

    @commands.hybrid_command(name="setinfochannel", description="Allow a channel for !info commands")
    @commands.has_permissions(administrator=True)
    async def set_info_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        self.config_data["servers"].setdefault(guild_id, {"info_channels": [], "config": {}})
        if str(channel.id) not in self.config_data["servers"][guild_id]["info_channels"]:
            self.config_data["servers"][guild_id]["info_channels"].append(str(channel.id))
            self.save_config()
            await ctx.send(f"✅ {channel.mention} is now allowed for !info commands")
        else:
            await ctx.send(f"ℹ️ {channel.mention} is already allowed for !info commands")

    @commands.hybrid_command(name="removeinfochannel", description="Remove a channel from !info commands")
    @commands.has_permissions(administrator=True)
    async def remove_info_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        if guild_id in self.config_data["servers"]:
            if str(channel.id) in self.config_data["servers"][guild_id]["info_channels"]:
                self.config_data["servers"][guild_id]["info_channels"].remove(str(channel.id))
                self.save_config()
                await ctx.send(f"✅ {channel.mention} has been removed from allowed channels")
            else:
                await ctx.send(f"❌ {channel.mention} is not in the list of allowed channels")
        else:
            await ctx.send("ℹ️ This server has no saved configuration")

    @commands.hybrid_command(name="infochannels", description="List allowed channels")
    async def list_info_channels(self, ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        if guild_id in self.config_data["servers"] and self.config_data["servers"][guild_id]["info_channels"]:
            channels = []
            for channel_id in self.config_data["servers"][guild_id]["info_channels"]:
                channel = ctx.guild.get_channel(int(channel_id))
                channels.append(f"• {channel.mention if channel else f'ID: {channel_id}'}")
            embed = discord.Embed(
                title="Allowed channels for !info",
                description="\n".join(channels),
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="Allowed channels for !info",
                description="All channels are allowed (no restriction configured)",
                color=discord.Color.green()
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="info", description="Displays information about a Free Fire player")
    @app_commands.describe(uid="FREE FIRE INFO")
    async def player_info(self, ctx: commands.Context, uid: str):
        # التحقق من القناة
        if not await self.is_channel_allowed(ctx):
            embed = discord.Embed(
                title="⚠️ Command Not Allowed",
                description=f"This command is only allowed in <#{ALLOWED_CHANNEL_ID}>",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            return  # توقف التنفيذ هنا

        if not uid.isdigit() or len(uid) < 6:
            return await ctx.reply("❌ Invalid UID! Must be numeric with at least 6 digits.", mention_author=False)

        cooldown = self.config_data["global_settings"]["default_cooldown"]
        guild_id = str(ctx.guild.id)
        if guild_id in self.config_data["servers"]:
            cooldown = self.config_data["servers"][guild_id]["config"].get("cooldown", cooldown)

        if ctx.author.id in self.cooldowns:
            last_used = self.cooldowns[ctx.author.id]
            if (datetime.now() - last_used).seconds < cooldown:
                remaining = cooldown - (datetime.now() - last_used).seconds
                return await ctx.send(f"⏱ Please wait {remaining}s before using this command again", ephemeral=True)

        self.cooldowns[ctx.author.id] = datetime.now()

        try:
            async with ctx.typing():
                async with self.session.get(f"{self.api_url}?uid={uid}") as response:
                    if response.status == 404:
                        return await ctx.send(f"❌ Player with UID {uid} not found.")
                    if response.status != 200:
                        return await ctx.send("⚠️ API error. Try again later.")
                    data = await response.json()

            profile_data = data.get('profile_info', {})
            basic_info = profile_data.get('basicInfo', {})
            captain_info = profile_data.get('captainBasicInfo', {})
            clan_info = profile_data.get('clanBasicInfo', {})
            credit_score_info = profile_data.get('creditScoreInfo', {})
            pet_info = profile_data.get('petInfo', {})
            profile_info = profile_data.get('profileInfo', {})
            social_info = profile_data.get('socialInfo', {})

            region = basic_info.get('region', 'Not found')

            embed = discord.Embed(
                title=f"🎮 Player Information",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=ctx.author.display_avatar.url)

            # ───────── ACCOUNT BASIC INFO ─────────
            embed.add_field(name="", value="\n".join([
                "**┌  ACCOUNT BASIC INFO**",
                f"**├─ Name**: {basic_info.get('nickname', 'Not found')}",
                f"**├─ UID**: {uid}",
                f"**├─ Level**: {basic_info.get('level', 'Not found')} (Exp: {basic_info.get('exp', '?')})",
                f"**├─ Region**: {region}",
                f"**├─ Likes**: {basic_info.get('liked', 'Not found')}",
                f"**├─ Honor Score**: {credit_score_info.get('creditScore', 'Not found')}",
                f"**└─ Signature**: {social_info.get('signature', 'None') or 'None'}"
            ]), inline=False)

            # ───────── ACCOUNT ACTIVITY ─────────
            embed.add_field(name="", value="\n".join([
                "**┌  ACCOUNT ACTIVITY**",
                f"**├─ Most Recent OB**: {basic_info.get('releaseVersion', '?')}",
                f"**├─ Current BP Badges**: {basic_info.get('badgeCnt', 'Not found')}",
                f"**├─ BR Rank**: {basic_info.get('rankingPoints', '?')}",
                f"**├─ CS Rank**: {basic_info.get('csRankingPoints', '?')}",
                f"**├─ Created At**: {self.convert_unix_timestamp(basic_info.get('createAt', 0))}",
                f"**└─ Last Login**: {self.convert_unix_timestamp(basic_info.get('lastLoginAt', 0))}"
            ]), inline=False)

            # ───────── ACCOUNT OVERVIEW ─────────
            embed.add_field(name="", value="\n".join([
                "**┌  ACCOUNT OVERVIEW**",
                f"**├─ Avatar ID**: {profile_info.get('avatarId', 'Not found')}",
                f"**├─ Banner ID**: {basic_info.get('bannerId', 'Not found')}",
                f"**├─ Pin ID**: {captain_info.get('pinId', 'Default') if captain_info else 'Default'}",
                f"**└─ Equipped Skills**: {profile_info.get('equipedSkills', 'Not found')}"
            ]), inline=False)

            # ───────── PET DETAILS ─────────
            embed.add_field(name="", value="\n".join([
                "**┌  PET DETAILS**",
                f"**├─ Equipped?**: {'Yes' if pet_info.get('isSelected') else 'Not Found'}",
                f"**├─ Pet Name**: {pet_info.get('name', 'Not Found')}",
                f"**├─ Pet Exp**: {pet_info.get('exp', 'Not Found')}",
                f"**└─ Pet Level**: {pet_info.get('level', 'Not Found')}"
            ]), inline=False)

            embed.set_footer(text="DEVELOPED BY MIDOU X CHEAT")

            await ctx.send(embed=embed)

            # ───────── IMAGE ─────────
            image_url = f"{self.generate_url}?uid={uid}"
            async with self.session.get(image_url) as img_file:
                if img_file.status == 200:
                    with io.BytesIO(await img_file.read()) as buf:
                        file = discord.File(buf, filename=f"outfit_{uuid.uuid4().hex[:8]}.png")
                        await ctx.send(file=file)

        except Exception as e:
            await ctx.send(f"⚠️ Unexpected error: {e}")
        finally:
            gc.collect()

    async def cog_unload(self):
        await self.session.close()


async def setup(bot):
    await bot.add_cog(InfoCommands(bot))

# --- Event Listener: حذف الرسائل في القناة المسموح بها فقط ---
@commands.Cog.listener()
async def on_message(message):
    if message.author.bot:
        return  # تجاهل رسائل البوت

    if message.channel.id == ALLOWED_CHANNEL_ID:
        if not message.content.startswith("!"):  # حذف الرسائل غير أوامر البوت
            try:
                await message.delete()
            except discord.Forbidden:
                print(f"⚠️ Missing permissions to delete message in {message.channel}")
            return
