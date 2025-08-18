import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from datetime import datetime
import json
import os
import asyncio
import gc

CONFIG_FILE = "info_channels.json"

class InfoCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://rawthug.onrender.com/info"
        self.card_url = "https://profile-generator.up.railway.app/api/profile_card"
        self.session = aiohttp.ClientSession()
        self.config_data = self.load_config()
        self.cooldowns = {}

    def convert_unix_timestamp(self, timestamp: int) -> str:
        return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

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
        try:
            guild_id = str(ctx.guild.id)
            allowed_channels = self.config_data["servers"].get(guild_id, {}).get("info_channels", [])
            if not allowed_channels:
                return True
            return str(ctx.channel.id) in allowed_channels
        except Exception as e:
            print(f"Error checking channel permission: {e}")
            return False

    @commands.hybrid_command(name="info", description="Displays information about a Free Fire player")
    @app_commands.describe(uid="FREE FIRE UID")
    async def player_info(self, ctx: commands.Context, uid: str):
        guild_id = str(ctx.guild.id)

        # UID validation
        if not uid.isdigit() or len(uid) < 6:
            return await ctx.reply("❌ Invalid UID! It must be numeric and at least 6 digits long.", mention_author=False)

        # Channel check
        if not await self.is_channel_allowed(ctx):
            return await ctx.send("🚫 This command is not allowed in this channel.", ephemeral=True)

        # Cooldown check
        cooldown = self.config_data["global_settings"]["default_cooldown"]
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
                        return await ctx.send(f"❌ Player with UID `{uid}` not found.")
                    if response.status != 200:
                        return await ctx.send("⚠️ API error. Try again later.")
                    data = await response.json()

            basic_info = data.get('basicInfo', {})
            captain_info = data.get('captainBasicInfo', {})
            clan_info = data.get('clanBasicInfo', {})
            credit_score_info = data.get('creditScoreInfo', {})
            pet_info = data.get('petInfo', {})
            profile_info = data.get('profileInfo', {})
            social_info = data.get('socialInfo', {})

            region = basic_info.get('region', 'Not found')

            # First send the card image
            card_image_url = f"{self.card_url}?uid={uid}"
            await ctx.send(card_image_url)

            # Then send the detailed embed
            embed = discord.Embed(
                title="Player Information",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=ctx.author.display_avatar.url)

            embed.add_field(name="ACCOUNT BASIC INFO", value="\n".join([
                f"Name: {basic_info.get('nickname', 'Not found')}",
                f"UID: `{uid}`",
                f"Level: {basic_info.get('level', 'Not found')} (Exp: {basic_info.get('exp', '?')})",
                f"Region: {region}",
                f"Likes: {basic_info.get('liked', 'Not found')}",
                f"Honor Score: {credit_score_info.get('creditScore', 'Not found')}",
                f"Signature: {social_info.get('signature', 'None') or 'None'}"
            ]), inline=False)

            embed.add_field(name="ACCOUNT ACTIVITY", value="\n".join([
                f"Most Recent OB: {basic_info.get('releaseVersion', '?')}",
                f"Current BP Badges: {basic_info.get('badgeCnt', 'Not found')}",
                f"BR Rank: {'' if basic_info.get('showBrRank') else 'Not found'} {basic_info.get('rankingPoints', '?')}",
                f"CS Rank: {'' if basic_info.get('showCsRank') else 'Not found'} {basic_info.get('csRankingPoints', '?')}",
                f"Created At: {self.convert_unix_timestamp(int(basic_info.get('createAt', 0)))}",
                f"Last Login: {self.convert_unix_timestamp(int(basic_info.get('lastLoginAt', 0)))}"
            ]), inline=False)

            embed.add_field(name="ACCOUNT OVERVIEW", value="\n".join([
                f"Avatar ID: {profile_info.get('avatarId', 'Not found')}",
                f"Banner ID: {basic_info.get('bannerId', 'Not found')}",
                f"Pin ID: {captain_info.get('pinId', 'Not found') if captain_info else 'Default'}",
                f"Equipped Skills: {profile_info.get('equipedSkills', 'Not found')}"
            ]), inline=False)

            embed.add_field(name="PET DETAILS", value="\n".join([
                f"Equipped?: {'Yes' if pet_info.get('isSelected') else 'Not Found'}",
                f"Pet Name: {pet_info.get('name', 'Not Found')}",
                f"Pet Exp: {pet_info.get('exp', 'Not Found')}",
                f"Pet Level: {pet_info.get('level', 'Not Found')}"
            ]), inline=False)

            if clan_info:
                guild_info = [
                    f"Guild Name: {clan_info.get('clanName', 'Not found')}",
                    f"Guild ID: `{clan_info.get('clanId', 'Not found')}`",
                    f"Guild Level: {clan_info.get('clanLevel', 'Not found')}",
                    f"Live Members: {clan_info.get('memberNum', 'Not found')}/{clan_info.get('capacity', '?')}"
                ]
                if captain_info:
                    guild_info.extend([
                        f"Leader Name: {captain_info.get('nickname', 'Not found')}",
                        f"Leader UID: `{captain_info.get('accountId', 'Not found')}`",
                        f"Leader Level: {captain_info.get('level', 'Not found')} (Exp: {captain_info.get('exp', '?')})",
                        f"Last Login: {self.convert_unix_timestamp(int(captain_info.get('lastLoginAt', 0)))}",
                        f"Title: {captain_info.get('title', 'Not found')}",
                        f"BP Badges: {captain_info.get('badgeCnt', '?')}",
                        f"BR Rank: {'' if captain_info.get('showBrRank') else 'Not found'} {captain_info.get('rankingPoints', 'Not found')}",
                        f"CS Rank: {'' if captain_info.get('showCsRank') else 'Not found'} {captain_info.get('csRankingPoints', 'Not found')}"
                    ])
                embed.add_field(name="GUILD INFO", value="\n".join(guild_info), inline=False)

            embed.set_footer(text="DEVELOPED BY MIDOU X CHEAT")
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"⚠️ Unexpected error: `{e}`")
        finally:
            gc.collect()

    async def cog_unload(self):
        await self.session.close()


async def setup(bot):
    await bot.add_cog(InfoCommands(bot))
