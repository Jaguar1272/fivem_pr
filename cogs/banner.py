import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timezone, timedelta

# 📌 KST (한국 표준시, UTC+9) 설정
KST = timezone(timedelta(hours=9))

# 📌 지정된 공식 문의처 링크 상수 정의
INQUIRY_URL = "https://discord.com/channels/1417202549295153305/1490073588655718541/1545055510590660739"


# --- 📝 배너 신청서 작성 Modal (유저 입력 폼) ---
class BannerApplyModal(discord.ui.Modal, title="⚡ 파이브엠 홍보나라 배너 신청서"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    server_name = discord.ui.TextInput(
        label="1. 서버 이름 (서버명)",
        placeholder="서버 이름을 입력하세요.",
        required=True,
        max_length=100
    )
    category_type = discord.ui.TextInput(
        label="2. 서버 장르 및 카테고리",
        placeholder="1: 맞디스코드 / 2: 커뮤니티 / 3: 롤플레이 / 4: 팩션",
        required=True,
        max_length=100
    )
    server_link = discord.ui.TextInput(
        label="3. 디스코드 영구 초대 링크",
        placeholder="https://discord.gg/...",
        required=True,
        max_length=200
    )
    server_desc = discord.ui.TextInput(
        label="4. 서버 핵심 특징 및 소개 (3~4줄)",
        placeholder="서버의 특징과 매력을 간략히 적어주세요.",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    extra_check = discord.ui.TextInput(
        label="5. 이미지 첨부(O/X) 및 6. 규칙 동의(동의/비동의)",
        placeholder="예: 이미지 O / 규칙 동의",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        review_channel = interaction.guild.get_channel(self.cog.review_channel_id)
        
        embed = discord.Embed(
            title="📥 [신규] 배너 채널 개설 신청 접수",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="신청자", value=f"{user.mention} (`{user.id}`)", inline=False)
        embed.add_field(name="1. 서버 이름", value=self.server_name.value, inline=True)
        embed.add_field(name="2. 카테고리", value=self.category_type.value, inline=True)
        embed.add_field(name="3. 서버 링크", value=self.server_link.value, inline=False)
        embed.add_field(name="4. 서버 소개", value=self.server_desc.value, inline=False)
        embed.add_field(name="5 & 6. 이미지 / 규칙 동의", value=self.extra_check.value, inline=False)
        embed.set_footer(text="스태프 검토 채널로 접수되었습니다.")

        if review_channel:
            await review_channel.send(embed=embed)

        await interaction.response.send_message(
            "✅ 배너 신청서가 성공적으로 접수되었습니다! 스태프 확인 후 안내해 드리겠습니다.", 
            ephemeral=True
        )


# --- 🔘 신청 패널 뷰 ---
class BannerApplyView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="📝 배너 신청서 작성하기", style=discord.ButtonStyle.success, emoji="📋", custom_id="btn_open_banner_apply_modal")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BannerApplyModal(self.cog))


# --- 📢 배너 채널 전체 공지 전송 Modal ---
class BannerAnnouncementModal(discord.ui.Modal, title="📢 배너 채널 전체 공지 전송"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    notice_title = discord.ui.TextInput(
        label="공지 제목",
        placeholder="공지 제목을 입력하세요",
        required=True,
        max_length=100
    )
    notice_content = discord.ui.TextInput(
        label="공지 내용 (장문 지원)",
        placeholder="공지 내용을 입력하세요",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=3000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        title = self.notice_title.value.strip()
        content = self.notice_content.value.strip()

        success, fail = 0, 0
        for channel in guild.text_channels:
            if channel.name.startswith("⚡"):
                try:
                    embed = discord.Embed(
                        title=f"📢 {title}",
                        description=content,
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed.add_field(name="🔗 공식 문의처", value=f"[바로가기]({INQUIRY_URL})", inline=False)
                    embed.set_footer(text=f"발송 관리자: {interaction.user.display_name}")
                    
                    await channel.send(embed=embed)
                    success += 1
                    await asyncio.sleep(0.4)
                except Exception:
                    fail += 1

        await interaction.followup.send(f"✅ 배너 전체 공지 전송 완료! (성공: {success}, 실패: {fail})", ephemeral=True)


# --- 🛠️ 배너 관리 패널 뷰 ---
class BannerPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="⚡ 배너 전체 공지", style=discord.ButtonStyle.primary, emoji="📢", custom_id="btn_banner_notice")
    async def send_notice(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ 관리자 권한이 필요합니다.", ephemeral=True)
        await interaction.response.send_modal(BannerAnnouncementModal(self.cog))


# --- ⚡ Banner Cog 본체 ---
class Banner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.review_channel_id = 1491268664564121773  # 스태프 검토 및 로그 채널 ID

    async def cog_load(self):
        self.bot.add_view(BannerApplyView(self))
        self.bot.add_view(BannerPanelView(self))

    @commands.command(name="배너신청서", aliases=["신청서발행"])
    async def banner_apply_panel(self, ctx):
        if not ctx.author.guild_permissions.administrator and not ctx.author.guild_permissions.manage_channels:
            return await ctx.send("❌ 관리자 권한이 필요합니다.", delete_after=5)

        try:
            await ctx.message.delete()
        except Exception:
            pass

        embed = discord.Embed(
            title="> **[ ⚡ 파이브엠 홍보나라 배너 채널 개설 신청서 ]**",
            description=(
                "파이브엠 홍보나라 배너 채널 개설을 원하시는 서버장님께서는\n"
                "아래 배너 규칙을 반드시 확인하신 후 **[배너 신청서 작성하기]** 버튼을 눌러주세요!\n\n"
                "📜 **[ 파이브엠 홍보나라 배너 이용 규칙 ]**\n"
                "1. 본인 배너 채널 외 타인 채널에 무단 홍보 글 작성 금지\n"
                "2. 홍보글 작성 시 자동 잠금되며, 일일 작성 횟수 준수 (일반 1회, 부스터 3회)\n"
                "3. 답장(끌올) 기능을 이용한 글 끌어올리기 절대 금지\n"
                "4. 스태프 개인 DM 문의 금지 (반드시 고객센터 티켓 이용)\n"
                "5. 허위 정보 기재 및 불건전 서버 적발 시 채널 즉시 회수 및 차단\n\n"
                f"🔗 **[공식 문의처 바로가기]({INQUIRY_URL})**"
            ),
            color=discord.Color.dark_embed()
        )
        await ctx.send(embed=embed, view=BannerApplyView(self))

    @commands.command(name="배너패널", aliases=["배너관리"])
    async def banner_control_panel(self, ctx):
        if not ctx.author.guild_permissions.administrator and not ctx.author.guild_permissions.manage_channels:
            return await ctx.send("❌ 관리자 권한이 필요합니다.", delete_after=5)

        try:
            await ctx.message.delete()
        except Exception:
            pass

        embed = discord.Embed(
            title="⚡ 파이브엠 홍보나라 배너 관리 패널",
            description=f"아래 버튼을 통해 배너 채널들에 공지를 일괄 발송할 수 있습니다.\n\n🔗 **[공식 문의처 바로가기]({INQUIRY_URL})**",
            color=discord.Color.dark_embed()
        )
        await ctx.send(embed=embed, view=BannerPanelView(self))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # 배너 채널 감지 (⚡ 기호로 시작하는 채널)
        if message.channel.name.startswith("⚡"):
            # 1. 답장(끌올) 방지
            if message.reference:
                try:
                    await message.delete()
                    await message.channel.send(f"{message.author.mention}, 배너 채널에서는 답장(끌올) 기능이 금지되어 있습니다!", delete_after=5)
                except Exception:
                    pass
                return

            # 2. 활동 금지 시간 체크 (새벽 00:31 ~ 아침 08:29) - 부스터 유저 예외 처리
            now_kst = datetime.now(KST)
            current_time_val = now_kst.hour * 60 + now_kst.minute
            
            is_booster = any(role.name.startswith("부스터") or role.id == message.guild.premium_subscriber_role_id for role in message.author.roles) if hasattr(message.author, "roles") else False

            if 31 <= current_time_val <= 509 and not is_booster:
                try:
                    await message.delete()
                    await message.channel.send(f"{message.author.mention}, 현재는 활동 금지 시간(00:31 ~ 08:29)입니다. 글 작성이 제한됩니다.", delete_after=6)
                except Exception:
                    pass
                return

            # 3. 홍보글 조건 검사 (사진 첨부 또는 링크 포함 + 10자 이상)
            has_media = len(message.attachments) > 0 or "http://" in message.content or "https://" in message.content or "discord.gg" in message.content
            if has_media and len(message.content.strip()) >= 10:
                try:
                    overwrite = message.channel.overwrites_for(message.guild.default_role)
                    overwrite.send_messages = False
                    await message.channel.set_permissions(message.guild.default_role, overwrite=overwrite)
                    
                    embed = discord.Embed(
                        title="🔒 배너 채널 자동 잠금 완료",
                        description="정상적으로 홍보글이 등록되어 채널이 잠금 처리되었습니다. 다음 이용 가능 시간에 뵙겠습니다!",
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed.add_field(name="🔗 공식 문의처", value=f"[바로가기]({INQUIRY_URL})", inline=False)
                    await message.channel.send(embed=embed)
                except Exception as e:
                    print(f"[Banner Auto-Lock Error] {e}")


async def setup(bot):
    await bot.add_cog(Banner(bot))