import os
import discord
from discord.ext import commands

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.admin_role_id = int(os.getenv("ADMIN_ROLE_ID", 0))
        self.warnings = {}
        self.general_log_channel_id = 1417208003027009636  # 일반 처벌 로그 채널 ID
        self.ban_log_channel_id = 1417208140746854471      # 차단 전용 로그 채널 ID

    async def cog_check(self, ctx):
        """관리자 권한 또는 지정된 관리자 역할 보유자만 명령어 사용 가능"""
        if ctx.author.guild_permissions.administrator:
            return True
        if self.admin_role_id and any(role.id == self.admin_role_id for role in ctx.author.roles):
            return True
        await ctx.send("이 명령어를 사용할 권한이 없습니다.", delete_after=5)
        return False

    async def send_general_log(self, ctx, action: str, member: discord.Member, reason: str = None, extra_info: tuple = None, color: discord.Color = discord.Color.default()):
        """일반 처벌 로그(경고, 뮤트, 킥, 청소 등)를 일반 로그 채널로 전송"""
        log_channel = self.bot.get_channel(self.general_log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(
            title=f"🚨 처벌 로그 | {action}",
            timestamp=discord.utils.utcnow(),
            color=color
        )
        embed.add_field(name="👤 대상 유저", value=f"{member.mention} (`{member.name}`)", inline=True)
        embed.add_field(name="🛡️ 처리자", value=f"{ctx.author.mention}", inline=True)
        
        if extra_info:
            embed.add_field(name=extra_info[0], value=extra_info[1], inline=False)
            
        if reason:
            embed.add_field(name="📝 사유", value=reason, inline=False)
            
        embed.set_footer(text=f"User ID: {member.id}", icon_url=member.display_avatar.url)
        await log_channel.send(embed=embed)

    async def send_ban_log(self, user: discord.User, reason: str, warn_count: int):
        """차단 전용 텍스트 포맷 로그를 차단 로그 채널로 전송"""
        log_channel = self.bot.get_channel(self.ban_log_channel_id)
        if not log_channel:
            return

        log_text = (
            f"디스코드 아이디: {user.name} ({user.mention})\n"
            f"디스코드 닉네임: {user.mention}\n"
            f"처벌 내용: {reason}\n"
            f"누적 경고: {warn_count}회 + 영구 차단"
        )
        await log_channel.send(log_text)

    @commands.command(name="경고")
    async def warn(self, ctx, member: discord.Member, *, reason="사유 없음"):
        """유저에게 경고를 부여합니다. (3회 초과 시 자동 차단)"""
        self.warnings[member.id] = self.warnings.get(member.id, 0) + 1
        count = self.warnings[member.id]
        
        # 1. 일반 로그 채널로 경고 로그 전송
        await self.send_general_log(ctx, "경고 부여", member, reason, ("⚠️ 누적 경고", f"**{count}회**"), discord.Color.orange())

        # 2. 경고 3회 초과(4회 이상) 시 자동 차단 (3회 달성 시 차단으로 바꾸려면 count >= 3 로 수정)
        if count > 3:
            ban_reason = f"경고 3회 초과 자동 차단 (마지막 사유: {reason})"
            try:
                await ctx.guild.ban(member, reason=ban_reason)
                # 차단 로그 채널로 텍스트 포맷 로그 전송
                await self.send_ban_log(member, ban_reason, count)
                await ctx.send(f"🚨 **{member.name}**님이 경고 **{count}회**를 기록하여 자동으로 서버에서 **영구 차단**되었습니다.")
            except discord.HTTPException as e:
                await ctx.send(f"⚠️ 경고는 부여되었으나 자동 차단 처리 실패: `{e}`")
        else:
            await ctx.send(f"⚠️ **{member.name}**님에게 경고가 부여되었습니다. (현재 경고: {count}회) | 사유: {reason}")

    @commands.command(name="경고확인")
    async def warn_check(self, ctx, member: discord.Member):
        """유저의 경고 횟수를 확인합니다."""
        count = self.warnings.get(member.id, 0)
        await ctx.send(f"🔍 **{member.name}**님의 현재 경고 횟수는 **{count}회**입니다.")

    @commands.command(name="뮤트")
    async def mute(self, ctx, member: discord.Member, minutes: int = 60, *, reason="사유 없음"):
        """유저의 채팅을 지정된 시간(분) 동안 제한합니다."""
        duration = discord.utils.utcnow() + discord.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await ctx.send(f"🔇 **{member.name}**님의 채팅이 {minutes}분 동안 제한되었습니다. | 사유: {reason}")
        await self.send_general_log(ctx, "채팅 제한 (타임아웃)", member, reason, ("⏳ 제한 시간", f"**{minutes}분**"), discord.Color.gold())

    @commands.command(name="언뮤트")
    async def unmute(self, ctx, member: discord.Member):
        """유저의 채팅 제한을 해제합니다."""
        await member.timeout(None)
        await ctx.send(f"🔊 **{member.name}**님의 채팅 제한이 해제되었습니다.")
        await self.send_general_log(ctx, "제한 해제 (언뮤트)", member, None, None, discord.Color.green())

    @commands.command(name="킥")
    async def kick(self, ctx, member: discord.Member, *, reason="사유 없음"):
        """유저를 서버에서 추방합니다."""
        await member.kick(reason=reason)
        await ctx.send(f"👢 **{member.name}**님을 서버에서 추방했습니다. | 사유: {reason}")
        await self.send_general_log(ctx, "서버 추방 (킥)", member, reason, None, discord.Color.red())

    @commands.command(name="차단")
    async def ban(self, ctx, user: discord.User, *, reason="서버 박제자 등록"):
        """유저를 서버에서 영구 차단하고 차단 전용 로그를 남깁니다."""
        try:
            await ctx.guild.ban(user, reason=reason)
        except discord.HTTPException as e:
            return await ctx.send(f"❌ 유저 차단 실패: `{e}`")

        warn_count = self.warnings.get(user.id, 0)
        await self.send_ban_log(user, reason, warn_count)
        await ctx.send(f"🔨 **{user.name}**님을 서버에서 차단하고 차단 로그를 전송했습니다. | 사유: {reason}")

    @commands.command(name="청소")
    async def clear_messages(self, ctx, amount: int):
        """지정한 개수만큼 채팅창의 메시지를 삭제합니다."""
        if amount <= 0:
            return await ctx.send("⚠️ 1 이상의 숫자를 입력해주세요.", delete_after=5)

        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"🧹 **{len(deleted)-1}**개의 메시지를 삭제했습니다.", delete_after=5)

        log_channel = self.bot.get_channel(self.general_log_channel_id)
        if log_channel:
            embed = discord.Embed(
                title="🚨 처벌 로그 | 채팅 청소",
                timestamp=discord.utils.utcnow(),
                color=discord.Color.blue()
            )
            embed.add_field(name="📄 채널", value=ctx.channel.mention, inline=True)
            embed.add_field(name="🛡️ 처리자", value=ctx.author.mention, inline=True)
            embed.add_field(name="🧹 삭제된 메시지 수", value=f"**{len(deleted)-1}개**", inline=False)
            await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))