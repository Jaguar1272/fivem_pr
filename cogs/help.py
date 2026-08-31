import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="도움말", aliases=["도움", "help"])
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="🤖 파이브엠 홍보나라 명령어 안내",
            description="서버 관리에 사용되는 전체 명령어 목록입니다.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        # 1. 배너 관리 명령어
        embed.add_field(
            name="⚡ 배너 관리 (`!배너`)",
            value=(
                "**`!배너 생성 [@유저] [카테고리] [채널이름]`** - 배너 채널 생성 (1:맞, 2:커뮤, 3:RP, 4:팩션)\n"
                "**`!배너 삭제 [@유저] [#채널] [삭제사유]`** - 배너 채널 즉시 삭제 및 DM 안내\n"
                "**`!배너 초기화 [@유저]`** - 대상 유저의 오늘 작성 제한/검토 대기 해제"
            ),
            inline=False
        )

        # 2. 티켓 및 관리 명령어
        embed.add_field(
            name="🎫 티켓 & 처벌 관리",
            value=(
                "**`!티켓`** - 티켓 생성 및 처리 관련 기능\n"
                "**`!경고` / `!차단`** - 유저 제재 관련 기능"
            ),
            inline=False
        )

        # 3. 시스템 명령어
        embed.add_field(
            name="⚙️ 시스템 (관리자)",
            value=(
                "**`!리로드 [파일명]`** - 특정 Cog 실시간 새로고침 (예: `!리로드 banner`)\n"
                "**`!리로드`** - 전체 Cog 모듈 일괄 새로고침"
            ),
            inline=False
        )

        embed.set_footer(text=f"요청자: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))