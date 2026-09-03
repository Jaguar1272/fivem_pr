import asyncio
import discord
from discord.ext import commands

# --- 1. 티켓 내부 제어 버튼 (티켓 닫기) ---
class TicketControlView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="🔒 티켓 닫기", style=discord.ButtonStyle.danger, custom_id="btn_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels and not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ 티켓은 스태프 또는 관리자만 닫을 수 있습니다.", ephemeral=True)

        await interaction.response.send_message("🔒 5초 후 문의 티켓 채널이 삭제됩니다...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"티켓 종료 (종료 스태프: {interaction.user.name})")
        except Exception as e:
            print(f"[티켓] 채널 삭제 에러: {e}")


# --- 2. 고객센터 메인 패널 버튼 (티켓 생성) ---
class TicketCreateView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="📩 문의 티켓 열기", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="btn_open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        ticket_channel_name = f"ticket-{user.name.lower().replace(' ', '-')}"
        existing_channel = discord.utils.get(guild.text_channels, name=ticket_channel_name)
        if existing_channel:
            return await interaction.response.send_message(f"⚠️ 이미 생성된 문의 티켓이 있습니다: {existing_channel.mention}", ephemeral=True)

        category = guild.get_channel(self.cog.ticket_category_id)
        staff_role = guild.get_role(self.cog.staff_role_id)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            ticket_channel = await guild.create_text_channel(
                name=ticket_channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"ticket_owner_id:{user.id}"
            )

            embed = discord.Embed(
                title="🎫 고객센터 1:1 문의 채널",
                description=(
                    f"안녕하세요 {user.mention}님! 문의사항을 아래에 작성해 두시면 담당 스태프가 확인 후 답변드립니다.\n\n"
                    f"🚫 **[경고] 스태프 개인 DM 문의 절대 금지**\n"
                    f"• 스태프/관리자에게 개인 DM 문의 시 **사전 통보 없이 경고 조치**됩니다.\n"
                    f"• 모든 문의는 본 티켓 채널을 통해서만 진행해 주세요.\n"
                    f"• 문의가 완결되면 아래 **'🔒 티켓 닫기'** 버튼을 눌러주세요."
                ),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text=f"신청자 ID: {user.id}")

            # 📢 티켓 오픈 시 @everyone 전체 멘션 발송 (알림 보장)
            await ticket_channel.send(
                content="@everyone 📩 새로운 문의 티켓이 개설되었습니다!",
                embed=embed,
                view=TicketControlView(self.cog),
                allowed_mentions=discord.AllowedMentions(everyone=True)
            )
            await interaction.response.send_message(f"✅ 문의 티켓이 성공적으로 생성되었습니다: {ticket_channel.mention}", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ 티켓 생성 중 오류가 발생했습니다: `{e}`", ephemeral=True)


# --- 3. 메인 Cog 클래스 ---
class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_category_id = 1541419838977745037  # 티켓 카테고리 ID
        self.staff_role_id = 1417209680559603953       # 스태프 역할 ID

    async def cog_load(self):
        self.bot.add_view(TicketCreateView(self))
        self.bot.add_view(TicketControlView(self))

    @commands.command(name="티켓패널", aliases=["티켓"])
    async def setup_ticket_panel(self, ctx):
        if not ctx.author.guild_permissions.administrator and not ctx.author.guild_permissions.manage_channels:
            return await ctx.send("❌ 명령어를 실행하려면 관리자 권한이 필요합니다.")

        embed = discord.Embed(
            title="🎧 파이브엠 홍보나라 고객센터 문의",
            description=(
                "서버 이용, 배너 신청, 제재 문의, 기타 알림 관련 문의사항은 아래 버튼을 눌러 1:1 티켓을 생성해 주세요.\n\n"
                "🚨 **[스태프 개인 DM 문의 금지 지침]**\n"
                "• **스태프/관리자 개인 DM으로 문의하는 행위는 엄격히 금지**됩니다.\n"
                "• DM 문의 적발 시 **경고 조치**가 부여되오니 반드시 본 공식 티켓 창구를 통해 문의해 주시기 바랍니다."
            ),
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="파이브엠 홍보나라 고객센터")
        await ctx.send(embed=embed, view=TicketCreateView(self))

async def setup(bot):
    await bot.add_cog(Ticket(bot))