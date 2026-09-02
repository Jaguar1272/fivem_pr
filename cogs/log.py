import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta

class JoinLeaveLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.join_log_channel_id = 1417202550016311449
        self.leave_log_channel_id = 1456245094582849704

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel = self.bot.get_channel(self.join_log_channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(self.join_log_channel_id)
            except Exception:
                return

        kst = timezone(timedelta(hours=9))
        now_str = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")

        embed = discord.Embed(
            title="🟢 유저 입장",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="닉네임", value=member.display_name, inline=False)
        embed.add_field(name="아이디", value=f"`{member.id}`", inline=False)
        embed.add_field(name="시간", value=now_str, inline=False)

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        channel = self.bot.get_channel(self.leave_log_channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(self.leave_log_channel_id)
            except Exception:
                return

        kst = timezone(timedelta(hours=9))
        now_str = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")

        embed = discord.Embed(
            title="🔴 유저 퇴장",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="닉네임", value=member.display_name, inline=False)
        embed.add_field(name="아이디", value=f"`{member.id}`", inline=False)
        embed.add_field(name="시간", value=now_str, inline=False)

        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(JoinLeaveLog(bot))
