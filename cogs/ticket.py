import discord
from discord.ext import commands
import os
import asyncio

# 고객센터 로그 채널 ID
LOG_CHANNEL_ID = 1491268664564121773

# 티켓 안에서 사용되는 '티켓 닫기' 버튼
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 티켓 닫기", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚠️ 티켓을 닫습니다. 5초 뒤 채널이 완전히 삭제됩니다.", ephemeral=False)
        
        # 로그 채널로 닫기 기록 전송
        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="🗑️ 고객센터 티켓 종료 로그",
                color=discord.Color.dark_gray(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="📄 삭제된 채널명", value=f"`{interaction.channel.name}`", inline=True)
            embed.add_field(name="🛡️ 종료 처리자", value=f"{interaction.user.mention} (`{interaction.user.name}`)", inline=True)
            await log_channel.send(embed=embed)

        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"티켓 종료 (요청자: {interaction.user.name})")

# 메인 채널에 띄워두는 '문의하기' 버튼
class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 고객센터 문의하기", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        
        # 설정된 티켓 카테고리 ID
        ticket_category_id = 1490073085016014848
        category = guild.get_channel(ticket_category_id)
        
        channel_name = f"문의-{interaction.user.name.lower()}"
        
        # 이미 진행 중인 티켓 채널이 있는지 확인
        existing_channel = discord.utils.get(guild.channels, name=channel_name)
        if existing_channel:
            return await interaction.response.send_message(f"⚠️ 이미 진행 중인 문의 내역이 있습니다: {existing_channel.mention}", ephemeral=True)

        # 권한 설정: 에브리원 차단, 요청 유저 및 봇 허용
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        # 관리자 역할도 볼 수 있도록 권한 부여
        admin_role_id = int(os.getenv("ADMIN_ROLE_ID", 0))
        admin_role = guild.get_role(admin_role_id)
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        # 채널 생성
        channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        
        # 생성된 채널 내부 메시지 전송
        embed = discord.Embed(
            title="🎫 1:1 고객센터", 
            description=f"{interaction.user.mention}님, 환영합니다!\n어떤 점이 궁금하신가요? 관리자가 확인 후 답변해 드립니다.\n\n문의가 종료되면 아래의 `🔒 티켓 닫기` 버튼을 눌러주세요.", 
            color=discord.Color.blue()
        )
        await channel.send(content=f"{interaction.user.mention}", embed=embed, view=TicketControlView())
        
        # 로그 채널로 생성 기록 전송
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🎫 고객센터 티켓 생성 로그",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            log_embed.add_field(name="👤 생성 유저", value=f"{interaction.user.mention} (`{interaction.user.name}`)", inline=True)
            log_embed.add_field(name="📄 생성된 채널", value=channel.mention, inline=True)
            await log_channel.send(embed=log_embed)

        await interaction.response.send_message(f"✅ 티켓이 생성되었습니다. 이동해주세요: {channel.mention}", ephemeral=True)


class TicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketControlView())

    @commands.command(name="티켓설정")
    @commands.has_permissions(administrator=True)
    async def setup_ticket(self, ctx):
        """지정한 채널에 고객센터 티켓 생성 패널을 띄웁니다."""
        embed = discord.Embed(
            title="📬 파이브엠 홍보나라 고객센터",
            description="배너 신청, 유저 신고 등 모든 문의 업무를 진행하는 곳입니다.\n\n아래의 **[🎫 고객센터 문의하기]** 버튼을 누르시면 1:1 대화가 가능한 채널이 생성됩니다.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed, view=TicketPanelView())


async def setup(bot):
    await bot.add_cog(TicketSystem(bot))
