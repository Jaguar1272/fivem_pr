import discord
from discord.ext import commands
from datetime import timedelta

PUNISH_LOG_CHANNEL_ID = 1491268664564121773  # 처벌 로그 채널 ID
BAN_LOG_CHANNEL_ID = 1491268664564121773      # 차단 로그 채널 ID

# --- 제재 처리용 Modal 입력 폼 ---
class ModActionModal(discord.ui.Modal):
    def __init__(self, action_type: str):
        self.action_type = action_type
        titles = {
            "warn_add": "➕ 경고 추가",
            "warn_remove": "➖ 경고 삭제",
            "timeout_add": "⏳ 타임아웃 등록",
            "timeout_remove": "🕊️ 타임아웃 해제",
            "kick": "👟 추방 실행",
            "ban": "🚫 차단 등록",
            "unban": "🔓 차단 해제"
        }
        super().__init__(title=titles.get(action_type, "제재 실행"))

        self.user_input = discord.ui.TextInput(
            label="👤 대상 유저 ID 또는 멘션/이름",
            placeholder="유저 ID(숫자) 또는 이름을 입력하세요.",
            required=True
        )
        self.add_item(self.user_input)

        if action_type == "timeout_add":
            self.time_input = discord.ui.TextInput(
                label="⏱️ 타임아웃 시간 (분)",
                placeholder="예: 10 (10분 동안 타임아웃)",
                required=True
            )
            self.add_item(self.time_input)

        if action_type not in ["warn_remove", "timeout_remove"]:
            self.reason_input = discord.ui.TextInput(
                label="📝 사유",
                placeholder="제재 사유를 입력하세요.",
                required=False,
                default="운영 지침 위반"
            )
            self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user_raw = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        
        # 유저 찾기 (ID 우선, 없을 시 이름 검색)
        member = None
        if user_raw.isdigit():
            member = guild.get_member(int(user_raw)) or await self.fetch_user_safe(interaction.client, int(user_raw))
        else:
            member = discord.utils.get(guild.members, name=user_raw)

        if not member and self.action_type != "unban":
            return await interaction.response.send_message("❌ 대상 유저를 찾을 수 없습니다.", ephemeral=True)

        reason = getattr(self, "reason_input", None)
        reason_val = reason.value if reason else "스태프 수동 조치"

        # 1. 경고 추가
        if self.action_type == "warn_add":
            await self.send_log(guild, PUNISH_LOG_CHANNEL_ID, "⚠️ [경고 부여]", member, interaction.user, reason_val)
            await interaction.response.send_message(f"✅ {member.mention} 유저에게 경고를 부여했습니다.", ephemeral=True)

        # 2. 경고 삭제
        elif self.action_type == "warn_remove":
            await self.send_log(guild, PUNISH_LOG_CHANNEL_ID, "🟢 [경고 차감]", member, interaction.user, "경고 차감 조치")
            await interaction.response.send_message(f"✅ {member.mention} 유저의 경고를 1회 차감했습니다.", ephemeral=True)

        # 3. 타임아웃 등록
        elif self.action_type == "timeout_add":
            minutes = int(self.time_input.value) if self.time_input.value.isdigit() else 10
            await member.timeout(timedelta(minutes=minutes), reason=f"[{interaction.user.name}] {reason_val}")
            await self.send_log(guild, PUNISH_LOG_CHANNEL_ID, f"🔇 [타임아웃 {minutes}분]", member, interaction.user, reason_val)
            await interaction.response.send_message(f"✅ {member.mention} 유저를 {minutes}분간 타임아웃 처리했습니다.", ephemeral=True)

        # 4. 타임아웃 해제
        elif self.action_type == "timeout_remove":
            await member.timeout(None, reason=f"[{interaction.user.name}] 타임아웃 해제")
            await self.send_log(guild, PUNISH_LOG_CHANNEL_ID, "🔊 [타임아웃 해제]", member, interaction.user, "스태프 직권 해제")
            await interaction.response.send_message(f"✅ {member.mention} 유저의 타임아웃을 해제했습니다.", ephemeral=True)

        # 5. 추방 실행
        elif self.action_type == "kick":
            await member.kick(reason=f"[{interaction.user.name}] {reason_val}")
            await self.send_log(guild, PUNISH_LOG_CHANNEL_ID, "👟 [강제 추방]", member, interaction.user, reason_val)
            await interaction.response.send_message(f"✅ {member.mention} 유저를 추방했습니다.", ephemeral=True)

        # 6. 차단 등록
        elif self.action_type == "ban":
            await guild.ban(member, reason=f"[{interaction.user.name}] {reason_val}")
            await self.send_log(guild, BAN_LOG_CHANNEL_ID, "🚫 [서버 차단]", member, interaction.user, reason_val)
            await interaction.response.send_message(f"✅ {member.mention} 유저를 차단했습니다.", ephemeral=True)

        # 7. 차단 해제
        elif self.action_type == "unban":
            user_id = int(user_raw) if user_raw.isdigit() else None
            if not user_id:
                return await interaction.response.send_message("❌ 차단 해제 시에는 유저 ID(숫자)를 입력해주세요.", ephemeral=True)
            user = await interaction.client.fetch_user(user_id)
            await guild.unban(user, reason=f"[{interaction.user.name}] {reason_val}")
            await self.send_log(guild, BAN_LOG_CHANNEL_ID, "🔓 [차단 해제]", user, interaction.user, reason_val)
            await interaction.response.send_message(f"✅ {user.name} 유저의 차단을 해제했습니다.", ephemeral=True)

    async def fetch_user_safe(self, client, uid):
        try:
            return await client.fetch_user(uid)
        except Exception:
            return None

    async def send_log(self, guild, channel_id, action, target, admin, reason):
        channel = guild.get_channel(channel_id)
        if not channel:
            return
        embed = discord.Embed(
            title=f"⚖️ {action}",
            color=discord.Color.red() if "차단" in action or "추방" in action else discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 대상 유저", value=f"{target.mention} (`{target.name}` / ID: `{target.id}`)", inline=False)
        embed.add_field(name="🛡️ 처리 스태프", value=f"{admin.mention} (`{admin.name}`)", inline=False)
        embed.add_field(name="📝 사유", value=f"```\n{reason}\n```", inline=False)
        await channel.send(embed=embed)


# --- 서버 제재 컨트롤 패널 뷰 ---
class ModControlPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # 1행 (Row 0)
    @discord.ui.button(label="경고 추가", style=discord.ButtonStyle.danger, emoji="➕", custom_id="btn_warn_add", row=0)
    async def btn_warn_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModActionModal("warn_add"))

    @discord.ui.button(label="타임아웃 등록", style=discord.ButtonStyle.danger, emoji="⏳", custom_id="btn_timeout_add", row=0)
    async def btn_timeout_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModActionModal("timeout_add"))

    @discord.ui.button(label="추방 실행", style=discord.ButtonStyle.danger, emoji="👟", custom_id="btn_kick", row=0)
    async def btn_kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModActionModal("kick"))

    @discord.ui.button(label="차단 등록", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="btn_ban", row=0)
    async def btn_ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModActionModal("ban"))

    # 2행 (Row 1)
    @discord.ui.button(label="경고 삭제", style=discord.ButtonStyle.success, emoji="➖", custom_id="btn_warn_remove", row=1)
    async def btn_warn_remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModActionModal("warn_remove"))

    @discord.ui.button(label="타임아웃 해제", style=discord.ButtonStyle.success, emoji="🕊️", custom_id="btn_timeout_remove", row=1)
    async def btn_timeout_remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModActionModal("timeout_remove"))

    @discord.ui.button(label="차단 해제", style=discord.ButtonStyle.success, emoji="🔓", custom_id="btn_unban", row=1)
    async def btn_unban(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModActionModal("unban"))


class ModControlPanelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(ModControlPanelView())

    @commands.command(name="제재패널")
    @commands.has_permissions(administrator=True)
    async def setup_mod_panel(self, ctx):
        embed = discord.Embed(
            title="⚖️ 서버 제재 컨트롤 패널",
            description=(
                "관리자 전용 제재 도구입니다.\n\n"
                "**사용 방법:**\n"
                "1. 버튼 클릭 후 대상의 **사용자명 또는 ID**를 입력합니다.\n"
                "2. 사유와 수량을 입력하여 제재를 진행합니다.\n\n"
                "📌 로그는 각각 처벌로그/차단로그 채널에 기록됩니다."
            ),
            color=discord.Color.dark_embed()
        )
        await ctx.send(embed=embed, view=ModControlPanelView())

async def setup(bot):
    await bot.add_cog(ModControlPanelCog(bot))