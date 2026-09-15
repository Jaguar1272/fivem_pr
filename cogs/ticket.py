import discord
from discord.ext import commands
import asyncio

# 📌 지정된 공식 문의처 링크 상수 정의
INQUIRY_URL = "https://discord.com/channels/1417202549295153305/1490073588655718541/1545055510590660739"


class TicketCloseView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="🔒 티켓 마감 (삭제)", style=discord.ButtonStyle.danger, custom_id="btn_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ 스태프(채널 관리 권한)만 티켓을 마감할 수 있습니다.", ephemeral=True)
        
        await interaction.response.send_message("🔒 잠시 후 티켓 채널이 삭제됩니다...", ephemeral=True)
        
        # 📋 로그 채널에 티켓 마감 기록 전송
        await self.cog.send_ticket_log("티켓 마감", interaction.channel, interaction.user)

        await asyncio.sleep(2)
        try:
            await interaction.channel.delete(reason=f"티켓 마감 by {interaction.user.name}")
        except Exception:
            pass


class TicketCreateView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="🎫 티켓 생성하기", style=discord.ButtonStyle.primary, emoji="📩", custom_id="btn_create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        # 중복 티켓 방지
        existing_channel = discord.utils.get(guild.text_channels, name=f"🎫ㆍ{user.name}")
        if existing_channel:
            return await interaction.response.send_message(f"⚠️ 이미 생성된 티켓 채널이 있습니다: {existing_channel.mention}", ephemeral=True)

        # 티켓 카테고리 가져오기 (정확한 ID 반영)
        category = guild.get_channel(self.cog.ticket_category_id) if self.cog.ticket_category_id else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }

        # 관리자 및 메시지 관리 권한이 있는 스태프 역할 자동 허용
        for role in guild.roles:
            if role.permissions.manage_messages or role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            channel = await guild.create_text_channel(
                name=f"🎫ㆍ{user.name}",
                category=category,
                overwrites=overwrites,
                topic=f"ticket_owner:{user.id}"
            )

            embed = discord.Embed(
                title="🎫 [홍보나라] 고객센터 티켓이 생성되었습니다.",
                description=(
                    f"안녕하세요 {user.mention}님!\n\n"
                    f"• 문의하실 내용을 상세히 남겨주시면 스태프가 확인 후 신속하게 도와드리겠습니다.\n"
                    f"• 원활한 상담을 위해 스태프 개인 DM 문의는 지양해 주시기 바랍니다.\n\n"
                    f"🔗 **[공식 문의처 바로가기]({INQUIRY_URL})**"
                ),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text="상담 종료 후 마감을 원하시면 아래 버튼을 눌러주세요.")

            # ✨ @everyone 멘션과 함께 안내 전송
            await channel.send(
                content=f"@everyone 🔔 {user.mention} 님의 새로운 티켓이 생성되었습니다!",
                embed=embed,
                view=TicketCloseView(self.cog)
            )

            # 📋 로그 채널에 티켓 생성 기록 전송
            await self.cog.send_ticket_log("생성", channel, user)

            await interaction.response.send_message(f"✅ 티켓 채널이 생성되었습니다: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 티켓 생성 실패: `{e}`", ephemeral=True)


class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # ⚙️ 사용자가 제공한 정확한 ID 적용
        self.ticket_category_id = 1490073085016014848  # 카테고리 ID
        self.log_channel_id = 1491268664564121773       # 문의로그 채널 ID

    async def cog_load(self):
        self.bot.add_view(TicketCreateView(self))
        self.bot.add_view(TicketCloseView(self))

    async def send_ticket_log(self, action_name: str, channel: discord.TextChannel, user: discord.abc.User):
        log_channel = self.bot.get_channel(self.log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(
            title=f"📋 고객센터 티켓 {action_name}",
            color=discord.Color.green() if "생성" in action_name else discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="관련 유저", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="채널 명", value=f"#{channel.name}", inline=True)
        await log_channel.send(embed=embed)

    @commands.command(name="티켓패널", aliases=["고객센터", "티켓"])
    async def ticket_panel(self, ctx):
        if not ctx.author.guild_permissions.administrator and not ctx.author.guild_permissions.manage_channels:
            return await ctx.send("❌ 관리자 권한이 필요합니다.", delete_after=5)

        # 🧹 명령어 입력 메시지 자동 삭제
        try:
            await ctx.message.delete()
        except Exception:
            pass

        embed = discord.Embed(
            title="🎫 [홍보나라] 고객센터 및 1:1 문의 패널",
            description=(
                f"서버 이용 중 불편한 점, 제휴 문의, 건의사항 등이 있으신가요?\n\n"
                f"• 아래 **[티켓 생성하기]** 버튼을 누르시면 전용 상담 채널이 생성됩니다.\n"
                f"• 생성된 채널은 오직 회원님과 서버 스태프만 열람할 수 있어 프라이빗하게 소통하실 수 있습니다.\n\n"
                f"🔗 **[공식 문의처 바로가기]({INQUIRY_URL})**"
            ),
            color=discord.Color.dark_embed()
        )
        embed.set_footer(text="허위 티켓 생성 및 도용 시 제재를 받을 수 있습니다.")
        
        await ctx.send(embed=embed, view=TicketCreateView(self))

async def setup(bot):
    await bot.add_cog(Ticket(bot))
