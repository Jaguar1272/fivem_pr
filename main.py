import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.invites = True  # 📌 초대 추적(Invite Tracking)을 위한 필수 인텐트 추가

# help_command=None 설정으로 기본 디스코드 help 명령어와 cogs/help.py 충돌 방지
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"로그인 완료: {bot.user} (ID: {bot.user.id})")
    print("------")

# 🔄 Cog 실시간 리로드/신규 로드 명령어 (관리자 전용)
@bot.command(name="리로드", aliases=["reload", "리셋"])
@commands.has_permissions(administrator=True)
async def reload_cog(ctx, extension: str = None):
    # 1. 이름을 안 적었을 때 (예: !리로드) -> cogs 폴더 내 전체 새로고침 및 신규 로드
    if not extension:
        reloaded = []
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                cog_name = filename[:-3]
                try:
                    await bot.reload_extension(f"cogs.{cog_name}")
                    reloaded.append(cog_name)
                except commands.ExtensionNotLoaded:
                    await bot.load_extension(f"cogs.{cog_name}")
                    reloaded.append(f"{cog_name}(신규 로드)")
                except Exception as e:
                    await ctx.send(f"❌ `{cog_name}` 리로드 실패: `{e}`")
        return await ctx.send(f"🔄 전체 Cog 리로드 완료: `{', '.join(reloaded)}`")

    # 2. 특정 파일만 지정했을 때 (예: !리로드 invite) -> 해당 파일 리로드 또는 신규 로드
    try:
        await bot.reload_extension(f"cogs.{extension}")
        await ctx.send(f"✅ `cogs.{extension}` 리로드 완료!")
    except commands.ExtensionNotLoaded:
        await bot.load_extension(f"cogs.{extension}")
        await ctx.send(f"✅ `cogs.{extension}` 신규 로드 완료!")
    except Exception as e:
        await ctx.send(f"❌ `cogs.{extension}` 리로드/로드 실패:\n```py\n{e}\n```")

async def load_extensions():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")
            print(f"로드된 Cog: {filename[:-3]}")

async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())