import os
import json
import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timedelta

# --- 관리자 전용 반성문 심사 버튼 패널 ---
class ReflectionReviewView(discord.ui.View):
    def __init__(self, cog, target_member: discord.Member, reason: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.target_member = target_member
        self.reason = reason

    @discord.ui.button(label="✅ 승인 (차단 해제 & 일반 유저 부여)", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.ban_members and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 스태프(차단 권한자)만 심사할 수 있습니다.", ephemeral=True)

        guild = interaction.guild
        member = self.target_member

        # 1. 역할 교체
        banned_role = guild.get_role(self.cog.banned_role_id)
        user_role = guild.get_role(self.cog.user_role_id)

        if banned_role and banned_role in member.roles:
            try:
                await member.remove_roles(banned_role, reason="반성문 소명 승인")
            except discord.Forbidden:
                pass

        if user_role and user_role not in member.roles:
            try:
                await member.add_roles(user_role, reason="반성문 소명 승인 후 유저 역할 부여")
            except discord.Forbidden:
                pass

        # 2. 전과 기록 저장
        self.cog.add_history(member.id, "반성문 소명 승인 (차단 해제)", f"격리 사유: {self.reason}", interaction.user.name)

        # 3. DM 안내
        try:
            await member.send(f"🎉 **{guild.name}** 서버의 반성문 소명이 승인되었습니다! 차단자 역할이 해제되고 일반 유저 권한이 부여되었습니다.")
        except discord.Forbidden:
            pass

        # 4. 반성문 전용 로그 채널 전송
        reflect_log_channel = guild.get_channel(self.cog.reflection_log_channel_id)
        if reflect_log_channel:
            embed = discord.Embed(
                title="📝 [반성문 소명 완료] 차단 해제 기록",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="👤 대상자", value=f"{member.mention} (`{member.name}` / ID: `{member.id}`)", inline=False)
            embed.add_field(name="👮 승인 스태프", value=f"{interaction.user.mention} (`{interaction.user.name}`)", inline=False)
            embed.add_field(name="🚨 최초 격리 사유", value=f"```\n{self.reason}\n```", inline=False)
            embed.add_field(name="📋 누적 전과 건수", value=f"**{len(self.cog.get_user_history(member.id))}건** (`!전과` 명령어로 확인)", inline=False)
            await reflect_log_channel.send(embed=embed)

        await interaction.response.send_message("✅ 소명이 승인되었으며 로그 채널에 기록되었습니다. 3초 후 채널이 삭제됩니다.")
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete(reason="소명 승인 완료로 채널 정리")
        except discord.NotFound:
            pass

    @discord.ui.button(label="❌ 거절 (서버 영구 차단)", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.ban_members and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 스태프(차단 권한자)만 심사할 수 있습니다.", ephemeral=True)

        guild = interaction.guild
        member = self.target_member

        # 1. 전과 기록 저장
        self.cog.add_history(member.id, "반성문 소명 거절 (영구 차단)", f"격리 사유: {self.reason}", interaction.user.name)

        try:
            await member.send(f"🔨 **{guild.name}** 서버의 반성문 소명이 거절되어 서버에서 최종 영구 차단(BAN) 처리되었습니다.")
        except discord.Forbidden:
            pass

        try:
            await guild.ban(member, reason=f"[{interaction.user.name}] 반성문 소명 거절로 인한 서버 영구 차단")
        except discord.Forbidden:
            return await interaction.response.send_message("❌ 봇의 권한이 부족하여 유저를 서버 차단하지 못했습니다.", ephemeral=True)

        # 2. 반성문 전용 로그 채널 전송
        reflect_log_channel = guild.get_channel(self.cog.reflection_log_channel_id)
        if reflect_log_channel:
            embed = discord.Embed(
                title="🔨 [반성문 소명 거절] 서버 영구 차단 기록",
                color=discord.Color.dark_red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="👤 대상자", value=f"{member.mention} (`{member.name}` / ID: `{member.id}`)", inline=False)
            embed.add_field(name="👮 거절 스태프", value=f"{interaction.user.mention} (`{interaction.user.name}`)", inline=False)
            embed.add_field(name="🚨 최초 격리 사유", value=f"```\n{self.reason}\n```", inline=False)
            embed.add_field(name="📋 누적 전과 건수", value=f"**{len(self.cog.get_user_history(member.id))}건**", inline=False)
            await reflect_log_channel.send(embed=embed)

        try:
            await interaction.channel.delete(reason="소명 거절로 인한 영구 차단 후 채널 삭제")
        except discord.NotFound:
            pass


# --- 관리 및 제재 Cog ---
class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = 1417208003027009636            # 제재 일반 로그 채널 ID
        self.reflection_log_channel_id = 1417540438293872811 # 📝 반성문 결과 전용 로그 채널 ID
        self.reflection_category_id = 1417537474439151779    # 📝 반성문 카테고리 ID
        self.banned_role_id = 1417537287121670215            # 🚫 차단자 역할 ID
        self.user_role_id = 1417203420368081029              # ✅ 승인 시 부여할 유저 역할 ID
        
        self.warn_file = "warnings.json"
        self.history_file = "history.json"
        
        self.warnings = self.load_data(self.warn_file)
        self.history = self.load_data(self.history_file)

    def load_data(self, file_path):
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_data(self, data, file_path):
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[{file_path} 저장 오류] {e}")

    # 📜 전과(제재 이력) 추가 메서드
    def add_history(self, user_id: int, action_type: str, reason: str, moderator: str):
        uid = str(user_id)
        if uid not in self.history:
            self.history[uid] = []
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.history[uid].append({
            "type": action_type,
            "reason": reason,
            "moderator": moderator,
            "date": now
        })
        self.save_data(self.history, self.history_file)

    def get_user_history(self, user_id: int):
        return self.history.get(str(user_id), [])

    async def send_mod_log(self, guild: discord.Guild, action: str, target: discord.User, moderator: discord.Member, reason: str):
        log_channel = guild.get_channel(self.log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(
            title=f"🛡️ [관리 조치] {action}",
            color=discord.Color.dark_red() if "차단" in action else discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 대상자", value=f"{target.mention} (`{target.name}` / ID: `{target.id}`)", inline=False)
        embed.add_field(name="👮 처리 스태프", value=f"{moderator.mention} (`{moderator.name}`)", inline=False)
        embed.add_field(name="📝 조치 사유", value=f"```\n{reason}\n```", inline=False)
        
        user_records = self.get_user_history(target.id)
        embed.add_field(name="📋 누적 전과 이력", value=f"총 **{len(user_records)}회** (상세: `!전과 <@유저>`)", inline=False)
        await log_channel.send(embed=embed)

    # 🛑 반성문 채널 생성 및 격리 메서드
    async def isolate_user(self, guild: discord.Guild, member: discord.Member, reason: str, moderator: discord.Member = None):
        category = guild.get_channel(self.reflection_category_id)
        if not category:
            return None

        mod_name = moderator.name if moderator else guild.me.name
        self.add_history(member.id, "서버 격리 (반성문 채널 생성)", reason, mod_name)

        # 1. 역할 회수 (시스템/부스터 역할 제외)
        roles_to_remove = [
            r for r in member.roles 
            if r != guild.default_role 
            and r.id != self.banned_role_id 
            and r < guild.me.top_role 
            and not r.managed 
            and not r.is_premium_subscriber()
        ]
        
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason=f"격리 조치: 기존 역할 회수 ({reason})")
            except discord.Forbidden as e:
                print(f"⚠️ [권한 오류] {member.display_name} 유저 역할 제거 실패: {e}")

        # 2. 차단자 역할 부여
        banned_role = guild.get_role(self.banned_role_id)
        if banned_role and banned_role not in member.roles:
            try:
                await member.add_roles(banned_role, reason=f"격리 조치: {reason}")
            except discord.Forbidden:
                pass

        # 3. 채널 생성
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        for role in guild.roles:
            if role.permissions.administrator or role.permissions.manage_messages:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel_name = f"📝ㆍ반성문-{member.name}"
        reflect_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"banned_user_id:{member.id}"
        )

        # 4. 유저 및 스태프 패널 전송
        user_history = self.get_user_history(member.id)
        
        user_embed = discord.Embed(
            title="📝 서버 격리 및 반성문 제출 안내",
            description=f"{member.mention}님, 규정 위반으로 모든 역할이 회수되고 **소명 전용 채널**로 이동되었습니다.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        user_embed.add_field(name="🚨 격리 사유", value=f"```\n{reason}\n```", inline=False)
        user_embed.add_field(
            name="📋 반성문 작성 양식",
            value="1. 위반한 규정 내용:\n2. 차단/격리 사유 인정 여부:\n3. 재발 방지 약속 및 반성 내용:",
            inline=False
        )
        await reflect_channel.send(content=f"{member.mention}", embed=user_embed)

        admin_embed = discord.Embed(
            title="⚙️ 스태프 전용 반성문 심사 패널",
            description=f"대상 유저의 누적 전과 이력: **{len(user_history)}건**",
            color=discord.Color.gold()
        )
        admin_embed.add_field(name="👤 대상 유저", value=f"{member.mention} (`{member.id}`)", inline=True)
        view = ReflectionReviewView(self, member, reason)
        await reflect_channel.send(embed=admin_embed, view=view)

        # 5. DM 발송
        try:
            await member.send(f"🚨 **{guild.name}** 서버에서 활동이 제한되어 반성문 채널이 생성되었습니다. 사유: `{reason}`")
        except discord.Forbidden:
            pass

        mod_user = moderator or guild.me
        await self.send_mod_log(guild, "격리 차단 (반성문 채널 생성)", member, mod_user, reason)
        return reflect_channel

    # 🛑 경고 부여
    async def add_warning(self, guild: discord.Guild, user: discord.Member, reason: str, moderator: discord.Member = None):
        user_id = str(user.id)
        current_warns = self.warnings.get(user_id, 0) + 1
        self.warnings[user_id] = current_warns
        self.save_data(self.warnings, self.warn_file)

        mod_name = moderator.name if moderator else guild.me.name
        self.add_history(user.id, f"경고 부여 ({current_warns}/3회)", reason, mod_name)

        embed = discord.Embed(
            title="🚨 규정 위반 경고 부여",
            description=f"{user.mention}님에게 경고가 부여되었습니다. (누적: **{current_warns}/3**회)",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📝 사유", value=reason, inline=False)

        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass

        if current_warns >= 3:
            await self.isolate_user(guild, user, f"경고 3회 누적 (최종 사유: {reason})", moderator)

    # 🔍 전과 / 과거 제재 이력 조회 명령어
    @commands.command(name="전과", aliases=["전과조회", "기록", "제재기록"])
    @commands.has_permissions(manage_messages=True)
    async def show_user_history(self, ctx, user: discord.User = None):
        target = user or ctx.author
        records = self.get_user_history(target.id)

        embed = discord.Embed(
            title=f"📋 [{target.name}] 유저의 제재 및 전과 기록",
            description=f"총 **{len(records)}건**의 제재 내역이 조회되었습니다.",
            color=discord.Color.dark_orange() if records else discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        if not records:
            embed.add_field(name="✨ 깨끗한 상태", value="과거 조치 또는 차단/경고 내역이 존재하지 않습니다.", inline=False)
        else:
            for idx, item in enumerate(reversed(records[-10:]), 1):
                embed.add_field(
                    name=f"{idx}. {item['type']} ({item['date']})",
                    value=f"└ **사유:** {item['reason']}\n└ **처리자:** {item['moderator']}",
                    inline=False
                )

        await ctx.send(embed=embed)

    # 1. 경고 그룹
    @commands.group(name="경고", invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def warning_group(self, ctx):
        embed = discord.Embed(title="⚖️ 경고 관리 명령어", description="`!경고 부여 [@유저] [사유]`, `!경고 차감 [@유저]`, `!경고 조회 [@유저]`", color=discord.Color.blue())
        await ctx.send(embed=embed)

    @warning_group.command(name="부여")
    @commands.has_permissions(manage_messages=True)
    async def warning_add(self, ctx, user: discord.Member, *, reason: str = "운영 지침 위반"):
        await self.add_warning(ctx.guild, user, reason, ctx.author)
        await ctx.send(f"✅ {user.mention}님에게 경고를 부여했습니다. (현재: **{self.warnings.get(str(user.id), 0)}/3**회)")

    @warning_group.command(name="차감")
    @commands.has_permissions(manage_messages=True)
    async def warning_remove(self, ctx, user: discord.Member):
        user_id = str(user.id)
        if user_id in self.warnings and self.warnings[user_id] > 0:
            self.warnings[user_id] -= 1
            self.save_data(self.warnings, self.warn_file)
            self.add_history(user.id, "경고 1회 차감", "스태프 차감 조치", ctx.author.name)
            await ctx.send(f"✅ {user.mention}님의 경고를 1회 차감했습니다. (현재: **{self.warnings[user_id]}/3**회)")
        else:
            await ctx.send(f"ℹ️ {user.mention}님은 부여된 경고가 없습니다.")

    @warning_group.command(name="조회")
    async def warning_show(self, ctx, user: discord.Member = None):
        target = user or ctx.author
        count = self.warnings.get(str(target.id), 0)
        await ctx.send(f"📋 {target.mention}님의 누적 경고 횟수는 **{count}/3**회입니다.")

    @commands.command(name="역할정리", aliases=["차단정리"])
    @commands.has_permissions(ban_members=True)
    async def cleanup_banned_roles(self, ctx):
        banned_role = ctx.guild.get_role(self.banned_role_id)
        if not banned_role:
            return await ctx.send("⚠️ 차단자 역할을 찾을 수 없습니다.")

        count = 0
        for member in ctx.guild.members:
            if banned_role in member.roles:
                roles_to_remove = [
                    r for r in member.roles 
                    if r != ctx.guild.default_role 
                    and r.id != self.banned_role_id 
                    and r < ctx.guild.me.top_role
                    and not r.managed 
                    and not r.is_premium_subscriber()
                ]
                if roles_to_remove:
                    try:
                        await member.remove_roles(*roles_to_remove, reason="차단자 대상 잔여 역할 일괄 정리")
                        count += 1
                    except discord.Forbidden:
                        pass

        await ctx.send(f"🧹 총 **{count}명**의 차단자 유저에게 남아있던 불필요한 역할을 모두 제거했습니다.")

    @commands.command(name="청소", aliases=["삭제", "clear", "purge"])
    @commands.has_permissions(manage_messages=True)
    async def purge_messages(self, ctx, amount: int):
        if amount < 1 or amount > 100:
            return await ctx.send("⚠️ 1~100개의 메시지만 한 번에 삭제할 수 있습니다.", delete_after=5)
        deleted = await ctx.channel.purge(limit=amount + 1)
        count = len(deleted) - 1
        await ctx.send(f"🧹 메시지 **{count}개**를 성공적으로 청소했습니다.", delete_after=3)

    @commands.command(name="차단", aliases=["밴", "ban", "격리"])
    @commands.has_permissions(ban_members=True)
    async def ban_user(self, ctx, member: discord.Member, *, reason: str = "운영 지침 위반"):
        if member.guild_permissions.administrator:
            return await ctx.send("❌ 관리자는 차단할 수 없습니다.")
        reflect_channel = await self.isolate_user(ctx.guild, member, reason, ctx.author)
        if reflect_channel:
            await ctx.send(f"✅ {member.mention} 유저를 격리하고 반성문 채널({reflect_channel.mention})을 생성했습니다.")

    @commands.command(name="영구차단", aliases=["영밴", "hardban"])
    @commands.has_permissions(ban_members=True)
    async def hard_ban_user(self, ctx, user: discord.User, *, reason: str = "운영 지침 위반 (소명 불가)"):
        self.add_history(user.id, "서버 완전 영구 차단 (Hard Ban)", reason, ctx.author.name)
        try:
            await user.send(f"🔨 **{ctx.guild.name}** 서버에서 소명 불가 사유로 영구 차단되었습니다.\n사유: `{reason}`")
        except discord.Forbidden:
            pass
        await ctx.guild.ban(user, reason=f"[{ctx.author.name}] {reason}")
        await ctx.send(f"✅ {user.mention} (`{user.name}`) 유저를 완전 영구 차단(BAN)했습니다.")
        await self.send_mod_log(ctx.guild, "완전 영구 차단 (Direct BAN)", user, ctx.author, reason)

    @commands.command(name="차단해제", aliases=["언밴", "unban", "석방"])
    @commands.has_permissions(ban_members=True)
    async def unban_user(self, ctx, member: discord.Member, *, reason: str = "스태프 직권 차단 해제"):
        banned_role = ctx.guild.get_role(self.banned_role_id)
        user_role = ctx.guild.get_role(self.user_role_id)
        if banned_role and banned_role in member.roles:
            try:
                await member.remove_roles(banned_role, reason=f"차단 해제: {reason}")
            except discord.Forbidden:
                pass
        if user_role and user_role not in member.roles:
            try:
                await member.add_roles(user_role, reason=f"차단 해제 후 유저 역할 부여")
            except discord.Forbidden:
                pass

        self.add_history(member.id, "수동 차단 해제", reason, ctx.author.name)

        category = ctx.guild.get_channel(self.reflection_category_id)
        if category:
            for ch in category.text_channels:
                if ch.topic and f"banned_user_id:{member.id}" in ch.topic:
                    await ch.delete(reason="차단 해제로 인한 반성문 채널 정리")
                    break

        await ctx.send(f"✅ {member.mention} 유저의 차단을 해제하고 유저 역할을 다시 부여했습니다.")
        await self.send_mod_log(ctx.guild, "차단 해제 (수동 승인)", member, ctx.author, reason)

    @commands.command(name="추방", aliases=["강퇴", "kick"])
    @commands.has_permissions(kick_members=True)
    async def kick_user(self, ctx, member: discord.Member, *, reason: str = "운영 지침 위반"):
        if member.guild_permissions.administrator:
            return await ctx.send("❌ 관리자는 추방할 수 없습니다.")
        self.add_history(member.id, "강제 추방 (Kick)", reason, ctx.author.name)
        try:
            await member.send(f"⚠️ **{ctx.guild.name}** 서버에서 추방되었습니다.\n사유: `{reason}`")
        except discord.Forbidden:
            pass
        await member.kick(reason=f"[{ctx.author.name}] {reason}")
        await ctx.send(f"✅ {member.mention} 유저를 추방했습니다.")
        await self.send_mod_log(ctx.guild, "강제 추방 (Kick)", member, ctx.author, reason)

    @commands.command(name="뮤트", aliases=["타임아웃", "mute"])
    @commands.has_permissions(moderate_members=True)
    async def mute_user(self, ctx, member: discord.Member, minutes: int, *, reason: str = "언행 불량 및 채널 오용"):
        if member.guild_permissions.administrator:
            return await ctx.send("❌ 관리자에게는 뮤트를 적용할 수 없습니다.")
        self.add_history(member.id, f"뮤트/타임아웃 ({minutes}분)", reason, ctx.author.name)
        duration = timedelta(minutes=minutes)
        await member.timeout(duration, reason=f"[{ctx.author.name}] {reason}")
        await ctx.send(f"🔇 {member.mention} 유저를 **{minutes}분** 동안 뮤트 처리했습니다.")
        await self.send_mod_log(ctx.guild, f"뮤트/타임아웃 ({minutes}분)", member, ctx.author, reason)

    @commands.command(name="뮤트해제", aliases=["언뮤트", "unmute"])
    @commands.has_permissions(moderate_members=True)
    async def unmute_user(self, ctx, member: discord.Member):
        await member.timeout(None)
        self.add_history(member.id, "뮤트 해제", "스태프 직권 해제", ctx.author.name)
        await ctx.send(f"🔊 {member.mention} 유저의 뮤트를 해제했습니다.")
        await self.send_mod_log(ctx.guild, "뮤트 해제", member, ctx.author, "스태프 직권 해제")

async def setup(bot):
    await bot.add_cog(Moderation(bot))