import os
import json
import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta

# --- 1. 짧은 홍보글 승인/거절 검토 버튼 뷰 ---
class PromoReviewView(discord.ui.View):
    def __init__(self, cog, target_message: discord.Message, owner: discord.Member, today_date: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.target_message = target_message
        self.owner = owner
        self.today_date = today_date

    @discord.ui.button(label="✅ 승인 (유지)", style=discord.ButtonStyle.success, custom_id="btn_promo_approve")
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

    @discord.ui.button(label="❌ 거절 (삭제)", style=discord.ButtonStyle.danger, custom_id="btn_promo_reject")
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


# --- 2. 패널 전용 모달 (생성/삭제/초기화) ---
class BannerCreateModal(discord.ui.Modal, title="➕ 배너 채널 생성"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    user_input = discord.ui.TextInput(
        label="👤 유저 (ID 또는 멘션)",
        placeholder="예: 123456789012345678 또는 @유저",
        required=True
    )
    category_type_input = discord.ui.TextInput(
        label="📁 카테고리 번호 (1:맞, 2:커뮤, 3:RP, 4:팩션)",
        placeholder="1, 2, 3, 4 중 하나 입력",
        max_length=1,
        required=True
    )
    channel_name_input = discord.ui.TextInput(
        label="📝 생성할 채널명",
        placeholder="채널 이름을 입력하세요. (⚡ㆍ자동 부착됨)",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        cat_type_str = self.category_type_input.value.strip()

        if not cat_type_str.isdigit() or int(cat_type_str) not in self.cog.category_ids:
            return await interaction.response.send_message("⚠️ 카테고리는 `1(맞)`, `2(커뮤)`, `3(RP)`, `4(팩션)` 중에서만 입력해 주세요.", ephemeral=True)

        cat_type = int(cat_type_str)
        category = guild.get_channel(self.cog.category_ids[cat_type])
        if not category:
            return await interaction.response.send_message("❌ 지정된 카테고리를 서버에서 찾을 수 없습니다.", ephemeral=True)

        user_raw = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        target_user = guild.get_member(int(user_raw)) if user_raw.isdigit() else None
        if not target_user:
            return await interaction.response.send_message("❌ 해당 유저를 서버에서 찾을 수 없습니다.", ephemeral=True)

        channel_name = self.channel_name_input.value.strip()
        if not channel_name.startswith("⚡ㆍ"):
            channel_name = f"⚡ㆍ{channel_name}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            target_user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }

        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"owner_id:{target_user.id}"
            )
            await interaction.response.send_message(f"✅ {target_user.mention}님의 배너 채널({channel.mention})이 성공적으로 생성되었습니다!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 채널 생성 실패: `{e}`", ephemeral=True)


class BannerDeleteModal(discord.ui.Modal, title="🗑️ 배너 채널 삭제"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    user_input = discord.ui.TextInput(
        label="👤 유저 (ID 또는 멘션)",
        placeholder="예: 123456789012345678 또는 @유저",
        required=True
    )
    channel_id_input = discord.ui.TextInput(
        label="📢 삭제할 채널 ID",
        placeholder="삭제할 배너 채널의 ID를 입력하세요.",
        required=True
    )
    reason_input = discord.ui.TextInput(
        label="📝 삭제 사유",
        style=discord.TextStyle.paragraph,
        placeholder="배너 채널 삭제 사유를 입력하세요.",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        ch_id_raw = self.channel_id_input.value.strip()

        if not ch_id_raw.isdigit():
            return await interaction.response.send_message("❌ 채널 ID는 숫자 형식이어야 합니다.", ephemeral=True)

        channel = guild.get_channel(int(ch_id_raw))
        if not channel or not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("❌ 삭제할 채널을 찾을 수 없습니다.", ephemeral=True)

        user_raw = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        target_user = guild.get_member(int(user_raw)) if user_raw.isdigit() else None

        channel_name = channel.name
        reason = self.reason_input.value.strip()

        try:
            await channel.delete(reason=f"배너 삭제 (스태프: {interaction.user.name}) - 사유: {reason}")
            if target_user:
                await self.cog.send_user_dm(target_user, f"관리자에 의해 배너 채널이 삭제되었습니다. (사유: {reason})", channel_name)

            await interaction.response.send_message(f"✅ `{channel_name}` 채널이 성공적으로 삭제되었습니다.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 채널 삭제 실패: `{e}`", ephemeral=True)


class BannerResetModal(discord.ui.Modal, title="🔄 배너 제한/검토 초기화"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    user_input = discord.ui.TextInput(
        label="👤 유저 (ID 또는 멘션)",
        placeholder="초기화할 유저의 ID 또는 멘션을 입력하세요.",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user_raw = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        target_user = guild.get_member(int(user_raw)) if user_raw.isdigit() else None

        if not target_user:
            return await interaction.response.send_message("❌ 유저를 찾을 수 없습니다.", ephemeral=True)

        user_id_str = str(target_user.id)
        cleared = False

        if user_id_str in self.cog.daily_activity:
            del self.cog.daily_activity[user_id_str]
            self.cog.save_daily_activity()
            cleared = True

        if target_user.id in self.cog.pending_review:
            del self.cog.pending_review[target_user.id]
            cleared = True

        if cleared:
            await interaction.response.send_message(f"✅ {target_user.mention}님의 오늘 배너 작성 제한 및 검토 대기 상태가 초기화되었습니다.", ephemeral=True)
        else:
            await interaction.response.send_message(f"ℹ️ {target_user.mention}님은 오늘 등록된 배너 작성/검토 기록이 없습니다.", ephemeral=True)


# --- 3. 배너 관리 패널 버튼 뷰 ---
class BannerPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="배너 생성", style=discord.ButtonStyle.primary, emoji="➕", custom_id="btn_panel_banner_create")
    async def btn_create(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BannerCreateModal(self.cog))

    @discord.ui.button(label="배너 삭제", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="btn_panel_banner_delete")
    async def btn_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BannerDeleteModal(self.cog))

    @discord.ui.button(label="제한 초기화", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="btn_panel_banner_reset")
    async def btn_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BannerResetModal(self.cog))


# --- 4. 메인 Cog 클래스 ---
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

    async def cog_load(self):
        """코그 로드 시 persistent 뷰 등록"""
        self.bot.add_view(BannerPanelView(self))

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
                description=f"**#{channel_name}** 채널 관련 안내사항입니다.",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="📝 처리 내용 / 사유", value=f"**{reason}**", inline=False)
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
            try:
                review_channel = await self.bot.fetch_channel(self.review_channel_id)
            except Exception as e:
                print(f"[배너 ERROR] 검토 채널(ID: {self.review_channel_id})을 불러올 수 없습니다: {e}")
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

        # 4. 검토 대기 중 분할 작성 자동 연동 처리
        if owner.id in self.pending_review:
            prev_msg_id = self.pending_review[owner.id]
            prev_msg = None
            try:
                prev_msg = await message.channel.fetch_message(prev_msg_id)
            except Exception:
                pass

            has_attachment = (len(message.attachments) > 0) or (prev_msg and len(prev_msg.attachments) > 0)
            combined_content = ((prev_msg.content if prev_msg else "") + " " + message.content).strip()
            has_link = ("http://" in combined_content) or ("https://" in combined_content)
            content_clean = combined_content.replace("@everyone", "").replace("@here", "").strip()
            has_long_text = len(content_clean) >= 10

            if has_long_text and (has_attachment or has_link):
                del self.pending_review[owner.id]
                self.daily_activity[str(owner.id)] = today_date
                self.save_daily_activity()
                await message.channel.send(f"✅ {message.author.mention} 글과 사진이 연속으로 감지되어 오늘 홍보글이 정상 등록되었습니다! (모바일 분할 작성 자동 승인)", delete_after=5)
                return

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

        self.pending_review[owner.id] = message.id
        await self.send_to_review_channel(message, owner, today_date)
        await message.channel.send(f"ℹ️ {message.author.mention} 작성하신 글은 검토 대기 상태입니다. (모바일 유저의 경우 지금 바로 사진을 추가로 올리시면 자동 승인됩니다!)", delete_after=5)

    # --- 배너 관리 패널 전송 명령어 (!배너패널 또는 !배너) ---
    @commands.command(name="배너패널", aliases=["배너"])
    async def setup_banner_panel(self, ctx):
        if not ctx.author.guild_permissions.administrator and not ctx.author.guild_permissions.manage_channels:
            return await ctx.send("❌ 이 명령어를 실행하려면 디스코드 **'관리자'** 또는 **'채널 관리'** 권한이 필요합니다.")

        embed = discord.Embed(
            title="🖼️ 배너 채널 관리 패널",
            description=(
                "스태프 전용 배너 컨트롤 도구입니다.\n\n"
                "• **➕ 배너 생성**: 유저, 카테고리(1~4), 채널명을 입력하여 전용 배너 채널을 생성합니다.\n"
                "• **🗑️ 배너 삭제**: 유저, 채널 ID, 삭제 사유를 입력하여 배너 채널을 삭제합니다.\n"
                "• **🔄 제한 초기화**: 특정 유저의 하루 작성 제한 및 검토 대기 상태를 리셋합니다."
            ),
            color=discord.Color.dark_embed()
        )
        await ctx.send(embed=embed, view=BannerPanelView(self))

async def setup(bot):
    await bot.add_cog(Banner(bot))