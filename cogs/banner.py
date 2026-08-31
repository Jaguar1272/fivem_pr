import os
import json
import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta

class PromoReviewView(discord.ui.View):
    def __init__(self, cog, target_message: discord.Message, owner: discord.Member, today_date: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.target_message = target_message
        self.owner = owner
        self.today_date = today_date

    @discord.ui.button(label="✅ 승인 (유지)", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ 스태프(메시지 관리 권한)만 처리할 수 있습니다.", ephemeral=True)

        self.cog.daily_activity[str(self.owner.id)] = self.today_date
        self.cog.save_daily_activity()
        self.cog.pending_review.pop(self.owner.id, None)

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "✅ 배너 홍보글 승인 완료"
        embed.set_footer(text=f"처리 스태프: {interaction.user.display_name} | 승인 일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ {self.owner.mention}님의 배너 홍보글이 승인되었습니다.", ephemeral=True)

        try:
            await self.owner.send(f"🎉 **#{self.target_message.channel.name}** 채널의 배너 홍보글이 스태프 검토를 통해 정상 승인되었습니다!")
        except discord.Forbidden:
            pass

    @discord.ui.button(label="❌ 거절 (삭제)", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ 스태프(메시지 관리 권한)만 처리할 수 있습니다.", ephemeral=True)

        self.cog.pending_review.pop(self.owner.id, None)

        try:
            await self.target_message.delete()
        except discord.NotFound:
            pass

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.dark_grey()
        embed.title = "❌ 배너 홍보글 거절 및 삭제"
        embed.set_footer(text=f"처리 스태프: {interaction.user.display_name} | 거절 일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"❌ {self.owner.mention}님의 홍보글이 삭제 처리되었습니다.", ephemeral=True)

        try:
            await self.owner.send(f"⚠️ **#{self.target_message.channel.name}** 채널의 홍보글이 스태프 검토 결과 규정 미달로 삭제되었습니다.")
        except discord.Forbidden:
            pass


class Banner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = 1417208003027009636       # 위반 감지 로그 채널 ID
        self.review_channel_id = 1500079277977112606    # 🔍 짧은 홍보글 검토 채널 ID
        self.exempt_channel_ids = [1520094510464499887]  # 예외 채널 ID
        self.category_ids = {
            1: 1541419838977745037, 
            2: 1493997022108319827, 
            3: 1528717688887840898,
            4: 1537118596814217296
        }
        self.data_file = "daily_activity.json"
        self.daily_activity = self.load_daily_activity()
        self.pending_review = {}  # owner_id: message_id

    def load_daily_activity(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[배너] 데이터 로드 실패: {e}")
                return {}
        return {}

    def save_daily_activity(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.daily_activity, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[배너] 데이터 저장 실패: {e}")

    def get_channel_owner(self, channel: discord.TextChannel) -> discord.Member:
        if channel.topic and "owner_id:" in channel.topic:
            try:
                owner_id = int(channel.topic.split("owner_id:")[1].split()[0])
                member = channel.guild.get_member(owner_id)
                if member:
                    return member
            except (ValueError, IndexError):
                pass

        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Member) and not target.bot:
                if not target.guild_permissions.administrator and not target.guild_permissions.manage_messages:
                    if overwrite.send_messages is True:
                        return target
        return None

    async def send_user_dm(self, member: discord.Member, reason: str, channel_name: str, original_content: str = ""):
        try:
            embed = discord.Embed(
                title="🚨 배너 홍보 규정 위반 안내",
                description=f"**#{channel_name}** 채널에 작성된 메시지가 규정 위반으로 삭제되었습니다.",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="📝 위반 사유", value=f"**{reason}**", inline=False)
            if original_content:
                display_content = original_content[:500] + ("..." if len(original_content) > 500 else "")
                embed.add_field(name="💬 작성하셨던 내용", value=f"```\n{display_content}\n```", inline=False)
            embed.set_footer(text="잘못 처리되었거나 수정이 필요한 경우 스태프에게 문의해 주세요.")
            await member.send(embed=embed)
        except discord.Forbidden:
            pass

    async def send_penalty_log(self, reason: str, message: discord.Message, owner: discord.Member = None):
        log_channel = self.bot.get_channel(self.log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(
            title="🚨 배너 홍보 규정 위반 감지 (스태프 참고용)",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        if owner:
            embed.add_field(name="👑 채널 소유자", value=f"{owner.mention} (`{owner.name}`)", inline=True)
        embed.add_field(name="👤 실제 작성자", value=f"{message.author.mention} (`{message.author.name}`)", inline=True)
        embed.add_field(name="📄 발생 채널", value=message.channel.mention, inline=True)
        embed.add_field(name="📝 위반 사유", value=f"**{reason}**", inline=False)

        content = message.content if message.content else "(텍스트 내용 없음)"
        if len(content) > 1000:
            content = content[:1000] + "... (생략)"
        embed.add_field(name="💬 작성 내용", value=f"```\n{content}\n```", inline=False)

        if message.attachments:
            file_names = ", ".join([att.filename for att in message.attachments])
            embed.add_field(name="📁 첨부파일 목록", value=f"`{file_names}`", inline=False)

        await log_channel.send(embed=embed)

    async def send_to_review_channel(self, message: discord.Message, owner: discord.Member, today_date: str):
        review_channel = self.bot.get_channel(self.review_channel_id)
        if not review_channel:
            return

        embed = discord.Embed(
            title="🔍 짧은 홍보글 승인 검토 요청",
            description=f"유저가 작성한 짧은 홍보글이 감지되었습니다. 아래 버튼으로 승인 여부를 결정해 주세요.",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👑 채널 소유자", value=f"{owner.mention} (`{owner.name}`)", inline=True)
        embed.add_field(name="👤 실제 작성자", value=f"{message.author.mention} (`{message.author.name}`)", inline=True)
        embed.add_field(name="📄 작성 채널", value=message.channel.mention, inline=True)
        embed.add_field(name="🔗 메시지 바로가기", value=f"[작성된 글 이동]({message.jump_url})", inline=False)

        content = message.content if message.content else "(텍스트 내용 없음)"
        if len(content) > 1000:
            content = content[:1000] + "... (생략)"
        embed.add_field(name="💬 작성된 내용", value=f"```\n{content}\n```", inline=False)

        if message.attachments:
            file_names = ", ".join([att.filename for att in message.attachments])
            embed.add_field(name="📁 첨부파일 목록", value=f"`{file_names}`", inline=False)

        view = PromoReviewView(self, message, owner, today_date)
        await review_channel.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not getattr(message.channel, "category_id", None):
            return

        if message.author.guild_permissions.administrator:
            return

        if message.channel.category_id not in self.category_ids.values() or not message.channel.name.startswith("⚡ㆍ"):
            return

        owner = self.get_channel_owner(message.channel) or message.author

        if owner.id in self.pending_review and self.pending_review[owner.id] == message.id:
            del self.pending_review[owner.id]
            await self.send_penalty_log("⚠️ 검토 대기 중 홍보글 유저 직접 삭제 감지 (검토 취소됨)", message, owner)
        else:
            await self.send_penalty_log("🗑️ 작성 완료된 홍보글 유저 삭제 감지 (1회 제한은 유지됨)", message, owner)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not getattr(message.channel, "category_id", None):
            return

        if message.channel.id in self.exempt_channel_ids:
            return

        if message.channel.category_id not in self.category_ids.values() or not message.channel.name.startswith("⚡ㆍ"):
            return

        # 관리자 예외 처리
        if message.author.guild_permissions.administrator:
            return

        owner = self.get_channel_owner(message.channel)

        # 1. 타인 배너 채널 작성 차단
        if owner and message.author.id != owner.id:
            reason = f"타인 배너 채널 작성 시도 (채널 소유자: {owner.display_name})"
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} 타인의 배너 채널에는 글을 작성할 수 없습니다.", delete_after=5)
            await self.send_user_dm(message.author, "본인의 배너 채널에만 홍보글을 작성하실 수 있습니다.", message.channel.name, message.content)
            await self.send_penalty_log(reason, message, owner)
            return

        if not owner:
            owner = message.author

        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        current_minute = now.hour * 60 + now.minute
        today_date = now.strftime("%Y-%m-%d")

        # 2. 금지 시간대 검사 (00:31 ~ 08:29)
        if 31 <= current_minute <= 509:
            reason = "배너 활동 금지 시간 활동 (00:31~08:29)"
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} 현재는 배너 활동 금지 시간입니다.", delete_after=5)
            await self.send_user_dm(owner, "활동 금지 시간대(00:31~08:29)에 메시지가 작성되었습니다.", message.channel.name, message.content)
            await self.send_penalty_log(reason, message, owner)
            return

        # 3. 답장 꼼수 검사
        if message.reference:
            reason = "답장(끌올) 기능을 이용한 꼼수 활동"
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} 답장(끌올) 기능은 금지되어 있습니다.", delete_after=5)
            await self.send_user_dm(owner, "기존 메시지에 답장하여 끌어올리는 행위는 금지되어 있습니다.", message.channel.name, message.content)
            await self.send_penalty_log(reason, message, owner)
            return

        # 📱 4. [모바일 패치 반영] 검토 대기 중 분할 작성 자동 연동 처리
        if owner.id in self.pending_review:
            prev_msg_id = self.pending_review[owner.id]
            prev_msg = None
            try:
                prev_msg = await message.channel.fetch_message(prev_msg_id)
            except Exception:
                pass

            # 기존 메시지 + 새로 작성한 메시지의 내용 및 사진 합산 검사
            has_attachment = (len(message.attachments) > 0) or (prev_msg and len(prev_msg.attachments) > 0)
            combined_content = ((prev_msg.content if prev_msg else "") + " " + message.content).strip()
            has_link = ("http://" in combined_content) or ("https://" in combined_content)
            content_clean = combined_content.replace("@everyone", "").replace("@here", "").strip()
            has_long_text = len(content_clean) >= 10

            # 합쳐서 정상 홍보글 조건(10자 이상 + 이미지/링크)에 해당하면 자동 승인!
            if has_long_text and (has_attachment or has_link):
                del self.pending_review[owner.id]
                self.daily_activity[str(owner.id)] = today_date
                self.save_daily_activity()
                await message.channel.send(f"✅ {message.author.mention} 글과 사진이 연속으로 감지되어 오늘 홍보글이 정상 등록되었습니다! (모바일 분할 작성 자동 승인)", delete_after=5)
                return

            # 합쳤는데도 조건 미달이면 중복 작성 차단
            reason = "검토 대기 중 홍보글 중복 작성 시도"
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} 현재 스태프 검토 중인 홍보글이 있습니다. 검토 완료 후 이용해주세요.", delete_after=5)
            await self.send_penalty_log(reason, message, owner)
            return

        # 5. 하루 1회 작성 제한 초과 차단
        owner_id_str = str(owner.id)
        if self.daily_activity.get(owner_id_str) == today_date:
            reason = f"하루 1회 작성 제한 초과 (삭제 후 재작성 꼼수 시도 포함)"
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} 해당 배너 채널은 오늘 이미 작성 완료된 채널입니다. (글을 지워도 당일 재작성은 불가능합니다.)", delete_after=5)
            await self.send_user_dm(owner, "배너 채널에는 하루에 1번만 작성하실 수 있습니다. (기존 글을 삭제하셔도 당일 재작성은 불가능합니다.)", message.channel.name, message.content)
            await self.send_penalty_log(reason, message, owner)
            return

        has_attachment = len(message.attachments) > 0
        has_link = ("http://" in message.content) or ("https://" in message.content)
        content_clean = message.content.replace("@everyone", "").replace("@here", "").strip()
        has_long_text = len(content_clean) >= 10

        if has_long_text and (has_attachment or has_link):
            self.daily_activity[owner_id_str] = today_date
            self.save_daily_activity()
            return

        # 글만 올렸거나 사진만 올린 경우 검토 대기로 등록
        self.pending_review[owner.id] = message.id
        await self.send_to_review_channel(message, owner, today_date)
        await message.channel.send(f"ℹ️ {message.author.mention} 작성하신 글은 검토 대기 상태입니다. (모바일 유저의 경우 지금 바로 사진을 추가로 올리시면 자동 승인됩니다!)", delete_after=5)

    @commands.group(name="배너", invoke_without_command=True)
    async def banner(self, ctx):
        embed = discord.Embed(
            title="[ 배너 관리 명령어 사용법 ]",
            description=(
                "**생성:** `!배너 생성 [@유저] [카테고리(1:맞, 2:커뮤, 3:RP, 4:팩션)] [채널이름]`\n"
                "**삭제:** `!배너 삭제 [@유저] [#채널] [삭제사유]`\n"
                "**초기화:** `!배너 초기화 [@유저]` (1회 제한 및 검토 대기 해제)"
            ),
            color=discord.Color.purple(),
        )
        await ctx.send(embed=embed)

    @banner.command(name="초기화", aliases=["리셋", "해제"])
    @commands.has_permissions(manage_messages=True)
    async def banner_reset(self, ctx, user: discord.Member):
        user_id_str = str(user.id)
        cleared = False

        if user_id_str in self.daily_activity:
            del self.daily_activity[user_id_str]
            self.save_daily_activity()
            cleared = True

        if user.id in self.pending_review:
            del self.pending_review[user.id]
            cleared = True

        if cleared:
            await ctx.send(f"✅ {user.mention}님의 오늘 배너 작성 제한 및 검토 대기 상태가 초기화되었습니다.")
        else:
            await ctx.send(f"ℹ️ {user.mention}님은 오늘 등록된 배너 작성/검토 기록이 없습니다.")

    @banner.command(name="생성")
    @commands.has_permissions(administrator=True)
    async def banner_create(self, ctx, user: discord.Member, category_type: int, channel_name: str):
        if category_type not in self.category_ids:
            return await ctx.send("⚠️ 카테고리는 `1(맞)`, `2(커뮤)`, `3(RP)`, `4(팩션)` 중에서만 입력 가능합니다.")

        category = ctx.guild.get_channel(self.category_ids[category_type])
        if not category:
            return await ctx.send("⚠️ 카테고리를 찾을 수 없습니다.")

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }

        if not channel_name.startswith("⚡ㆍ"):
            channel_name = f"⚡ㆍ{channel_name}"

        channel = await ctx.guild.create_text_channel(
            name=channel_name, 
            category=category, 
            overwrites=overwrites,
            topic=f"owner_id:{user.id}"
        )
        await ctx.send(f"✅ {user.mention}님의 배너 채널({channel.mention})이 성공적으로 생성되었습니다.")

    @banner.command(name="삭제")
    @commands.has_permissions(administrator=True)
    async def banner_delete(self, ctx, user: discord.Member, channel: discord.TextChannel, *, reason: str):
        channel_name = channel.name
        await channel.delete(reason=f"배너 삭제 (관리자: {ctx.author.name})")
        await self.send_user_dm(user, f"관리자에 의해 배너 채널이 삭제되었습니다. (사유: {reason})", channel_name)
        await ctx.send(f"✅ `{channel_name}` 채널이 삭제되었습니다.")

async def setup(bot):
    await bot.add_cog(Banner(bot))