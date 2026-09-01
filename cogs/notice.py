import discord
from discord.ext import commands

# --- 공지 작성/수정/삭제 Modal (입력 폼) ---
class NoticeModal(discord.ui.Modal):
    def __init__(self, action_type: str):
        self.action_type = action_type
        titles = {
            "normal": "➕ 일반 공지 작성",
            "embed": "🟦 임베드 공지 작성",
            "edit": "✏️ 공지 수정",
            "delete": "🗑️ 공지 삭제"
        }
        super().__init__(title=titles.get(action_type, "공지 관리"))

        # 채널 ID 입력
        self.channel_id_input = discord.ui.TextInput(
            label="📢 공지할 채널 ID",
            placeholder="예: 123456789012345678 (비워두면 현재 채널)",
            required=False
        )
        self.add_item(self.channel_id_input)

        if action_type == "normal":
            self.content_input = discord.ui.TextInput(
                label="📝 공지 내용",
                style=discord.TextStyle.paragraph,
                placeholder="공지할 내용을 입력하세요.",
                required=True
            )
            self.add_item(self.content_input)

        elif action_type == "embed":
            self.title_input = discord.ui.TextInput(
                label="📌 임베드 제목",
                placeholder="공지 제목을 입력하세요.",
                required=True
            )
            self.content_input = discord.ui.TextInput(
                label="📝 임베드 내용",
                style=discord.TextStyle.paragraph,
                placeholder="공지 내용을 입력하세요.",
                required=True
            )
            self.add_item(self.title_input)
            self.add_item(self.content_input)

        elif action_type in ["edit", "delete"]:
            self.message_id_input = discord.ui.TextInput(
                label="🆔 대상 메시지 ID",
                placeholder="수정/삭제할 공지 메시지의 ID를 입력하세요.",
                required=True
            )
            self.add_item(self.message_id_input)

            if action_type == "edit":
                self.content_input = discord.ui.TextInput(
                    label="✏️ 수정할 내용",
                    style=discord.TextStyle.paragraph,
                    placeholder="새로운 공지 내용을 입력하세요.",
                    required=True
                )
                self.add_item(self.content_input)

    async def on_submit(self, interaction: discord.Interaction):
        ch_id = self.channel_id_input.value.strip()
        channel = interaction.guild.get_channel(int(ch_id)) if ch_id and ch_id.isdigit() else interaction.channel

        if not channel:
            return await interaction.response.send_message("❌ 올바른 채널 ID를 입력해 주세요.", ephemeral=True)

        if self.action_type == "normal":
            await channel.send(self.content_input.value)
            await interaction.response.send_message(f"✅ {channel.mention} 채널에 일반 공지를 전송했습니다.", ephemeral=True)

        elif self.action_type == "embed":
            embed = discord.Embed(
                title=self.title_input.value,
                description=self.content_input.value,
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text=f"작성자: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
            await channel.send(embed=embed)
            await interaction.response.send_message(f"✅ {channel.mention} 채널에 임베드 공지를 전송했습니다.", ephemeral=True)

        elif self.action_type in ["edit", "delete"]:
            msg_id = int(self.message_id_input.value.strip())
            try:
                target_msg = await channel.fetch_message(msg_id)
            except Exception:
                return await interaction.response.send_message("❌ 해당 메시지를 찾을 수 없습니다.", ephemeral=True)

            if self.action_type == "edit":
                if target_msg.embeds:
                    embed = target_msg.embeds[0]
                    embed.description = self.content_input.value
                    await target_msg.edit(embed=embed)
                else:
                    await target_msg.edit(content=self.content_input.value)
                await interaction.response.send_message("✅ 공지 메시지를 수정했습니다.", ephemeral=True)

            elif self.action_type == "delete":
                await target_msg.delete()
                await interaction.response.send_message("🗑️ 공지 메시지를 삭제했습니다.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"[NoticeModal Error] {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ 처리 중 오류가 발생했습니다.", ephemeral=True)


# --- 공지사항 관리 패널 버튼 ---
class NoticePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # 지속적 버튼 유지

    @discord.ui.button(label="일반 공지", style=discord.ButtonStyle.primary, emoji="➕", custom_id="btn_notice_normal")
    async def btn_normal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NoticeModal("normal"))

    @discord.ui.button(label="임베드 공지", style=discord.ButtonStyle.primary, emoji="🟦", custom_id="btn_notice_embed")
    async def btn_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NoticeModal("embed"))

    @discord.ui.button(label="공지 수정", style=discord.ButtonStyle.secondary, emoji="✏️", custom_id="btn_notice_edit")
    async def btn_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NoticeModal("edit"))

    @discord.ui.button(label="공지 삭제", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="btn_notice_delete")
    async def btn_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NoticeModal("delete"))


class NoticeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """코그 로드/리로드 시 봇에 패널 뷰를 등록하여 기존 메시지 버튼도 유지"""
        self.bot.add_view(NoticePanelView())

    @commands.command(name="공지패널", aliases=["공지관리"])
    async def setup_notice_panel(self, ctx):
        # 데코레이터 대신 함수 내부에서 권한 확인 (권한 부족 시 조용한 무반응 현상 방지)
        if not ctx.author.guild_permissions.administrator and not ctx.author.guild_permissions.manage_messages:
            return await ctx.send("❌ 이 명령어를 실행하려면 디스코드 **'관리자'** 또는 **'메시지 관리'** 권한이 필요합니다.")

        embed = discord.Embed(
            title="📢 공지사항 관리 패널",
            description="관리자 전용 도구입니다.",
            color=discord.Color.dark_theme_gray()
        )
        # 매번 완전히 새로운 NoticePanelView 객체를 생성하여 전송
        await ctx.send(embed=embed, view=NoticePanelView())

    async def cog_command_error(self, ctx, error):
        await ctx.send(f"⚠️ 명령어 처리 중 예외 발생: `{error}`")
        print(f"[NoticeCog Error] {error}")

async def setup(bot):
    await bot.add_cog(NoticeCog(bot))