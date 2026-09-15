import discord
from discord.ext import commands
import asyncio

# 📌 지정된 공식 문의처 링크 상수 정의
INQUIRY_URL = "https://discord.com/channels/1417202549295153305/1490073588655718541/1545055510590660739"


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 티켓 마감 (삭제)", style=discord.ButtonStyle.danger, custom_id="btn_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ 스태프(채널 관리 권한)만 티켓을 마감할 수 있습니다.", ephemeral=True)
        
        await interaction.response.send_message("🔒 잠시 후 티켓 채널이 삭제됩니다...", ephemeral=True)
        await asyncio.sleep(2)
        try:
            await interaction.channel.delete(reason=f"티켓 마감 by {interaction.user.name}")
        except Exception:
            pass


class TicketCreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 티켓 생성하기", style=discord.ButtonStyle.primary, emoji="📩", custom_id="btn_create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        # 중복 티켓 방지
        existing_channel = discord.utils.get(guild.text_channels, name=f"🎫ㆍ{user.name}")
        if existing_channel:
            return await interaction.response.send_message(f"⚠️ 이미 생성된 티켓 채널이 있습니다: {existing_channel.mention}", ephemeral=True)

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
                overwrites=overwrites,
                topic=f"ticket_owner:{user.id}"
            )

            embed = discord.Embed(
                title="🎫 [홍보나라] 고객센터 티켓이 생성되었습니다.",
                description=(
                    f"안녕하세요 {user.mention}님!\n"
                    f"스태프가 확인 후 답변을 도와드릴 테니 잠시만 기다려 주세요.\n\n"
                    f"🔗 **[공식 문의처 바로가기]({INQUIRY_URL})**"
                ),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text="티켓 마감을 원하시면 아래 마감 버튼을 눌러주세요.")

            # ✨ 티켓 생성 시 @everyone 멘션과 함께 안내 메시지 전송
            await channel.send(
                content=f"@everyone 🔔 {user.mention} 님의 새로운 티켓이 생성되었습니다!",
                embed=embed,
                view=TicketCloseView()
            )

            await interaction.response.send_message(f"✅ 티켓 채널이 생성되었습니다: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 티켓 생성 실패: `{e}`", ephemeral=True)


class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(TicketCreateView())
        self.bot.add_view(TicketCloseView())

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
            title="🎫 [홍보나라] 고객센터 티켓 문의 패널",
            description=(
                f"문의사항이나 도움이 필요하시다면 아래 버튼을 눌러 티켓을 생성해 주세요.\n\n"
                f"🔗 **[공식 문의처 바로가기]({INQUIRY_URL})**"
            ),
            color=discord.Color.dark_embed()
        )
        await ctx.send(embed=embed, view=TicketCreateView())

async def setup(bot):
    await bot.add_cog(Ticket(bot))
