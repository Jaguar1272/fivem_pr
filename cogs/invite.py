import os
import json
import discord
from discord.ext import commands

class InviteTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "invite_data.json"
        self.invites_cache = {}
        self.invite_counts = self.load_data()
        self.log_channel_id = 1491268664564121773  # 기존 로그 채널 ID 활용

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_data(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.invite_counts, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    async def cog_load(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                self.invites_cache[guild.id] = {invite.code: invite.uses for invite in invites}
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        if invite.guild.id not in self.invites_cache:
            self.invites_cache[invite.guild.id] = {}
        self.invites_cache[invite.guild.id][invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        if invite.guild.id in self.invites_cache:
            self.invites_cache[invite.guild.id].pop(invite.code, None)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        if guild.id not in self.invites_cache:
            return

        try:
            current_invites = await guild.invites()
        except Exception:
            return

        inviter = None
        old_invites = self.invites_cache[guild.id]
        
        for invite in current_invites:
            if invite.code in old_invites:
                if invite.uses > old_invites[invite.code]:
                    inviter = invite.inviter
                    break
            elif invite.uses > 0:
                inviter = invite.inviter
                break

        # 캐시 업데이트
        self.invites_cache[guild.id] = {invite.code: invite.uses for invite in current_invites}

        if inviter and not inviter.bot:
            if inviter.id == member.id:
                return  # 본인 초대 방지

            inviter_id_str = str(inviter.id)
            if inviter_id_str not in self.invite_counts:
                self.invite_counts[inviter_id_str] = {"count": 0, "rewarded": False}

            self.invite_counts[inviter_id_str]["count"] += 1
            self.save_data()

            current_count = self.invite_counts[inviter_id_str]["count"]
            log_channel = guild.get_channel(self.log_channel_id)

            # 15명 달성 시 스태프 로그 채널에 알림
            if current_count >= 15 and not self.invite_counts[inviter_id_str]["rewarded"]:
                self.invite_counts[inviter_id_str]["rewarded"] = True
                self.save_data()

                if log_channel:
                    reward_embed = discord.Embed(
                        title="🎉 [이벤트] 15명 초대 달성!",
                        description=f"**{inviter.mention}**님이 목표인 **15명 초대**를 달성하셨습니다! 확인 후 배너 채널을 지급해 주세요.",
                        color=discord.Color.gold(),
                        timestamp=discord.utils.utcnow()
                    )
                    await log_channel.send(content=f"@everyone 🚨 **{inviter.mention}**님께서 초대 이벤트 보상 조건을 달성하셨습니다!", embed=reward_embed)

    @commands.command(name="초대확인", aliases=["내초대", "초대수"])
    async def check_invites(self, ctx, user: discord.Member = None):
        target = user or ctx.author
        target_id_str = str(target.id)
        
        user_data = self.invite_counts.get(target_id_str, {"count": 0, "rewarded": False})
        count = user_data["count"]
        remain = max(0, 15 - count)

        embed = discord.Embed(
            title=f"📊 {target.display_name}님의 초대 현황",
            color=discord.Color.green() if count >= 15 else discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="현재 초대 인원", value=f"**{count}명** / 15명", inline=True)
        embed.add_field(name="목표까지 남은 인원", value=f"**{remain}명**", inline=True)
        
        await ctx.send(embed=embed)

    @commands.command(name="초대조정", aliases=["초대설정"])
    async def modify_invites(self, ctx, user: discord.Member, count: int):
        if not ctx.author.guild_permissions.administrator and not ctx.author.guild_permissions.manage_channels:
            return await ctx.send("❌ 관리자 권한이 필요합니다.", delete_after=5)

        target_id_str = str(user.id)
        if target_id_str not in self.invite_counts:
            self.invite_counts[target_id_str] = {"count": 0, "rewarded": False}

        self.invite_counts[target_id_str]["count"] = count
        if count >= 15:
            self.invite_counts[target_id_str] = {"count": count, "rewarded": True}
        self.save_data()

        await ctx.send(f"✅ {user.mention}님의 초대 인원이 **{count}명**으로 수정되었습니다.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(InviteTracker(bot))