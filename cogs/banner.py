import os
import json
import asyncio
import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta

# 📌 지정된 공식 문의처 링크 상수 정의
INQUIRY_URL = "https://discord.com/channels/1417202549295153305/1490073588655718541/1545055510590660739"


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

        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        now_ts = now.timestamp()
        
        self.cog.record_post(str(self.owner.id), self.today_date, now_ts)
        self.cog.pending_review.pop(self.owner.id, None)

        is_booster = any(role.id == self.cog.booster_role_id for role in self.owner.roles)
        is_event = self.cog.is_event_period(now)
        has_benefit = is_booster or is_event

        user_act = self.cog.get_user_activity(str(self.owner.id), self.today_date)
        count = user_act["count"]

        if has_benefit:
            if count >= 3:
                await self.cog.lock_channel_for_owner(self.target_message.channel, self.owner, "오늘 작성 완료(3회)로 인한 채널 잠금")
                status_msg = "🎉 승인 완료! 오늘 혜택(3회)을 모두 소진하여 채널이 내일까지 잠깁니다."
            else:
                await self.cog.lock_channel_for_owner(self.target_message.channel, self.owner, "홍보글 승인 완료로 인한 3시간 채널 잠금")
                status_msg = f"🎉 승인 완료! 3시간 쿨타임 동안 채널이 잠깁니다. (남은 횟수: {3 - count}회)"
        else:
            await self.cog.lock_channel_for_owner(self.target_message.channel, self.owner, "배너 홍보글 승인 완료로 인한 채널 잠금")
            status_msg = "🎉 승인 완료! 오늘 작성을 모두 마쳐 채널이 내일까지 잠겼습니다."

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "✅ 배너 홍보글 승인 완료 (채널 잠금 적용)"
        embed.set_footer(text=f"처리 스태프: {interaction.user.display_name} | 승인 일시: {now.strftime('%Y-%m-%d %H:%M')}")

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ {self.owner.mention}님의 배너 홍보글이 승인되었으며, 권한 동기화가 적용되었습니다.", ephemeral=True)

        try:
            await self.owner.send(f"**#{self.target_message.channel.name}** 채널의 배너 홍보글이 정상 승인되었습니다!\n> {status_msg}")
        except discord.Forbidden:
            await self.target_message.channel.send(f"{self.owner.mention} 님, {status_msg}", delete_after=10)

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
        embed.set_footer(text=f"처리 스태프: {interaction.user.display_name} | 거절 일시: {datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')}")

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"❌ {self.owner.mention}님의 홍보글이 삭제 처리되었습니다.", ephemeral=True)

        try:
            await self.owner.send(f"⚠️ **#{self.target_message.channel.name}** 채널의 홍보글이 스태프 검토 결과 규정 미달로 삭제되었습니다.")
        except discord.Forbidden:
            await self.target_message.channel.send(f"⚠️ {self.owner.mention} 님의 홍보글이 스태프 검토 결과 규정 미달로 삭제되었습니다.", delete_after=10)


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

        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        current_minute = now.hour * 60 + now.minute
        today_date = now.strftime("%Y-%m-%d")
        now_ts = now.timestamp()

        is_booster = any(role.id == self.cog.booster_role_id for role in target_user.roles)
        is_event = self.cog.is_event_period(now)
        has_benefit = is_booster or is_event

        user_act = self.cog.get_user_activity(str(target_user.id), today_date)
        count = user_act["count"]
        last_ts = user_act["last_timestamp"]

        if has_benefit:
            is_cooldown = (count > 0 and count < 3 and (now_ts - last_ts) < 10800)
            should_lock = (count >= 3) or is_cooldown
        else:
            is_forbidden_time = (31 <= current_minute <= 509)
            should_lock = is_forbidden_time or (count >= 1)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            target_user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=not should_lock,
                attach_files=True,
                embed_links=True
            ),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }

        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"owner_id:{target_user.id}"
            )

            role = guild.get_role(self.cog.banner_role_id)
            role_msg = ""
            if role:
                try:
                    await target_user.add_roles(role, reason="배너 채널 생성에 따른 역할 지급")
                    role_msg = f"\n🎗️ **{role.name}** 역할이 지급되었습니다."
                except Exception:
                    role_msg = "\n⚠️ 역할 지급 권한 부족."

            rules_embed = discord.Embed(
                title="📜 [홍보나라] 배너 채널 생성 및 상세 이용 규정",
                description=(
                    f"안녕하세요, **{target_user.display_name}**님!\n"
                    f"요청하신 배너 채널 **{channel.mention}** 이(가) 개설되었습니다.\n\n"
                    f"🔗 **[공식 문의처 바로가기]({INQUIRY_URL})**"
                ),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            if is_event:
                rules_embed.title = "📜 [홍보나라] 배너 채널 개설 (추석 이벤트 적용 중!)"
                rules_embed.add_field(name="🌕 추석 이벤트 혜택", value="• 전 유저 1일 최대 3회 작성 (3시간 쿨타임)\n• 심야 활동 금지 시간 면제\n• @everyone 멘션 허용", inline=False)
            else:
                rules_embed.add_field(name="1️⃣ 작성 규칙", value="• 기본 유저 하루 1회 작성\n• 활동 금지 시간: 00:31 ~ 08:29", inline=False)
                rules_embed.add_field(name="🚀 부스터 혜택", value="• 금지 시간 면제\n• 하루 최대 3회 작성 (3시간 쿨타임)\n• @everyone 멘션 허용", inline=False)
                
            rules_embed.add_field(name="🚨 금지 사항", value=f"• **스태프 개인 DM 문의 절대 금지**\n• 모든 문의는 [공식 문의처]({INQUIRY_URL}) 또는 티켓을 이용해 주세요.", inline=False)
            rules_embed.set_footer(text="문의사항은 위 공식 문의처 링크를 이용해 주시기 바랍니다.")

            try:
                await target_user.send(embed=rules_embed)
            except discord.Forbidden:
                content_msg = f"🔔 {target_user.mention} 님, DM 차단되어 규정 안내를 채널에 게시합니다."
                await channel.send(content=content_msg, embed=rules_embed)

            await interaction.response.send_message(f"✅ {target_user.mention}님의 배너 채널({channel.mention}) 생성 완료!{role_msg}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 채널 생성 실패: `{e}`", ephemeral=True)


class BannerRenameModal(discord.ui.Modal, title="✏️ 배너 채널 이름 변경"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    channel_id_input = discord.ui.TextInput(label="📢 변경할 채널 ID", required=True)
    new_name_input = discord.ui.TextInput(label="📝 새 채널명 (⚡ㆍ자동 부착)", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        ch_id_raw = self.channel_id_input.value.strip()
        if not ch_id_raw.isdigit():
            return await interaction.response.send_message("❌ 채널 ID는 숫자여야 합니다.", ephemeral=True)

        channel = interaction.guild.get_channel(int(ch_id_raw))
        if not channel or not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("❌ 배너 채널을 찾을 수 없습니다.", ephemeral=True)

        new_name = self.new_name_input.value.strip()
        if not new_name.startswith("⚡ㆍ"):
            new_name = f"⚡ㆍ{new_name}"

        try:
            await channel.edit(name=new_name, reason=f"스태프 요청: {interaction.user.name}")
            await interaction.response.send_message(f"✅ 채널 이름 변경 완료: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 실패: `{e}`", ephemeral=True)


class BannerDeleteModal(discord.ui.Modal, title="🗑️ 배너 채널 삭제"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    user_input = discord.ui.TextInput(label="👤 유저 ID 또는 멘션", required=True)
    channel_id_input = discord.ui.TextInput(label="📢 삭제할 채널 ID", required=True)
    reason_input = discord.ui.TextInput(label="📝 삭제 사유", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        ch_id_raw = self.channel_id_input.value.strip()
        if not ch_id_raw.isdigit():
            return await interaction.response.send_message("❌ 채널 ID는 숫자여야 합니다.", ephemeral=True)

        channel = guild.get_channel(int(ch_id_raw))
        if not channel or not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("❌ 채널을 찾을 수 없습니다.", ephemeral=True)

        user_raw = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        target_user = guild.get_member(int(user_raw)) if user_raw.isdigit() else None
        reason = self.reason_input.value.strip()

        try:
            await channel.delete(reason=f"배너 삭제 (스태프: {interaction.user.name}) - {reason}")
            role_msg = ""
            if target_user:
                await self.cog.send_user_dm(target_user, f"채널 삭제 사유: {reason}", channel_name=channel.name)
                role = guild.get_role(self.cog.banner_role_id)
                if role and role in target_user.roles:
                    await target_user.remove_roles(role, reason=reason)
                    role_msg = " (역할 회수 완료)"

            await interaction.response.send_message(f"✅ 채널 삭제 완료{role_msg}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 삭제 실패: `{e}`", ephemeral=True)


class BannerResetModal(discord.ui.Modal, title="🔄 배너 제한/검토 초기화"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    user_input = discord.ui.TextInput(label="👤 유저 ID 또는 멘션", required=True)

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
            await self.cog.unlock_channel_if_eligible(target_user, guild)
            await interaction.response.send_message(f"✅ {target_user.mention}님의 배너 기록이 초기화되었습니다.", ephemeral=True)
        else:
            await interaction.response.send_message(f"ℹ️ 기록이 없습니다.", ephemeral=True)


class BannerNoticeModal(discord.ui.Modal, title="📢 배너 이용자 전체 공지"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    title_input = discord.ui.TextInput(label="📌 공지 제목", required=True, max_length=100)
    content_input = discord.ui.TextInput(label="📝 공지 내용", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        
        embed_desc = f"{self.content_input.value.strip()}\n\n🔗 **[공식 문의처 바로가기]({INQUIRY_URL})**"
        embed = discord.Embed(title=f"📢 [배너 공지] {self.title_input.value.strip()}", description=embed_desc, color=discord.Color.blue(), timestamp=discord.utils.utcnow())
        embed.set_footer(text=f"발송: {interaction.user.display_name}")

        success, fail = 0, 0
        for channel in guild.text_channels:
            if channel.category_id in self.cog.category_ids.values() and channel.name.startswith("⚡"):
                try:
                    owner = self.cog.get_channel_owner(channel)
                    await channel.send(content=owner.mention if owner else "", embed=embed)
                    success += 1
                    await asyncio.sleep(0.3)
                except Exception:
                    fail += 1

        await interaction.followup.send(f"✅ 공지 발송 완료 (성공: {success}, 실패: {fail})", ephemeral=True)


class BannerPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="배너 생성", style=discord.ButtonStyle.primary, emoji="➕", custom_id="btn_panel_banner_create", row=0)
    async def btn_create(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BannerCreateModal(self.cog))

    @discord.ui.button(label="이름 변경", style=discord.ButtonStyle.secondary, emoji="✏️", custom_id="btn_panel_banner_rename", row=0)
    async def btn_rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BannerRenameModal(self.cog))

    @discord.ui.button(label="배너 삭제", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="btn_panel_banner_delete", row=1)
    async def btn_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BannerDeleteModal(self.cog))

    @discord.ui.button(label="제한 초기화", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="btn_panel_banner_reset", row=1)
    async def btn_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BannerResetModal(self.cog))

    @discord.ui.button(label="전체 공지", style=discord.ButtonStyle.success, emoji="📢", custom_id="btn_panel_banner_notice", row=2)
    async def btn_notice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BannerNoticeModal(self.cog))


class Banner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = 1417208003027009636
        self.review_channel_id = 1500079277977112606
        self.exempt_channel_ids = [1520094510464499887]
        self.banner_role_id = 1417209680559603953
        self.cs_channel_id = 1417202550016311449
        self.booster_role_id = 1540636332404252734

        self.category_ids = {
            1: 1541419838977745037, 
            2: 1493997022108319827, 
            3: 1528717688887840898,
            4: 1537118596814217296
        }
        self.data_file = "daily_activity.json"
        self.daily_activity = self.load_daily_activity()
        self.pending_review = {}

        self.auto_lock_task.start()

    def cog_unload(self):
        self.auto_lock_task.cancel()

    async def cog_load(self):
        self.bot.add_view(BannerPanelView(self))

    # 📌 추석 이벤트 기간 확인 함수 (9월 22일 ~ 9월 27일)
    def is_event_period(self, current_time: datetime) -> bool:
        event_start = datetime(2026, 9, 22, 0, 0, tzinfo=timezone(timedelta(hours=9)))
        event_end = datetime(2026, 9, 27, 23, 59, 59, tzinfo=timezone(timedelta(hours=9)))
        return event_start <= current_time <= event_end

    def get_user_activity(self, user_id_str: str, today_date: str) -> dict:
        data = self.daily_activity.get(user_id_str)
        if isinstance(data, str):
            if data == today_date:
                return {"date": today_date, "count": 1, "last_timestamp": 0}
            else:
                return {"date": today_date, "count": 0, "last_timestamp": 0}
        elif isinstance(data, dict):
            if data.get("date") == today_date:
                return data
        return {"date": today_date, "count": 0, "last_timestamp": 0}

    def record_post(self, user_id_str: str, today_date: str, now_ts: float):
        data = self.get_user_activity(user_id_str, today_date)
        data["count"] += 1
        data["last_timestamp"] = now_ts
        data["date"] = today_date
        self.daily_activity[user_id_str] = data
        self.save_daily_activity()

    async def lock_channel_for_owner(self, channel: discord.TextChannel, owner: discord.Member, reason: str = "배너 채널 잠금"):
        try:
            overwrite = channel.overwrites_for(owner)
            overwrite.send_messages = False
            await channel.set_permissions(owner, overwrite=overwrite, reason=reason)
        except Exception as e:
            print(f"[배너] 채널 잠금 실패 ({channel.name}): {e}")

    async def unlock_channel_if_eligible(self, owner: discord.Member, guild: discord.Guild):
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        current_minute = now.hour * 60 + now.minute
        today_date = now.strftime("%Y-%m-%d")
        now_ts = now.timestamp()

        is_booster = any(role.id == self.booster_role_id for role in owner.roles)
        is_event = self.is_event_period(now)
        has_benefit = is_booster or is_event

        user_act = self.get_user_activity(str(owner.id), today_date)
        
        if not has_benefit and (31 <= current_minute <= 509):
            return

        if has_benefit:
            if user_act["count"] >= 3:
                return
            if user_act["count"] > 0 and (now_ts - user_act["last_timestamp"] < 10800):
                return
        else:
            if user_act["count"] >= 1:
                return

        for channel in guild.text_channels:
            if channel.category_id in self.category_ids.values() and channel.name.startswith("⚡"):
                ch_owner = self.get_channel_owner(channel)
                if ch_owner and ch_owner.id == owner.id:
                    try:
                        overwrite = channel.overwrites_for(owner)
                        overwrite.send_messages = True
                        await channel.set_permissions(owner, overwrite=overwrite, reason="쿨타임 해제")
                    except Exception:
                        pass

    def get_channel_owner(self, channel: discord.TextChannel) -> discord.Member:
        if channel.topic and "owner_id:" in channel.topic:
            try:
                owner_id = int(channel.topic.split("owner_id:")[1].split()[0])
                member = channel.guild.get_member(owner_id)
                if member:
                    return member
            except (ValueError, IndexError):
                pass

        for target in channel.overwrites.keys():
            if isinstance(target, discord.Member) and not target.bot:
                if not target.guild_permissions.administrator and not target.guild_permissions.manage_channels:
                    return target
        return None

    async def sync_all_banner_permissions(self) -> tuple[int, int]:
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        current_minute = now.hour * 60 + now.minute
        today_date = now.strftime("%Y-%m-%d")
        now_ts = now.timestamp()

        is_forbidden_time = (31 <= current_minute <= 509)
        synced_count, skipped_count = 0, 0

        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                if channel.category_id in self.category_ids.values() and channel.name.startswith("⚡"):
                    owner = self.get_channel_owner(channel)
                    if not owner:
                        continue

                    is_booster = any(role.id == self.booster_role_id for role in owner.roles)
                    is_event = self.is_event_period(now)
                    has_benefit = is_booster or is_event

                    user_act = self.get_user_activity(str(owner.id), today_date)
                    count = user_act["count"]
                    last_ts = user_act["last_timestamp"]

                    if has_benefit:
                        is_cooldown = (count > 0 and count < 3 and (now_ts - last_ts) < 10800)
                        should_lock = (count >= 3) or is_cooldown
                    else:
                        should_lock = is_forbidden_time or (count >= 1)

                    overwrite = channel.overwrites_for(owner)
                    current_send_perm = overwrite.send_messages

                    if should_lock and current_send_perm != False:
                        overwrite.send_messages = False
                        try:
                            await channel.set_permissions(owner, overwrite=overwrite, reason="동기화 잠금")
                            synced_count += 1
                            await asyncio.sleep(0.2)
                        except Exception:
                            pass
                    elif not should_lock and current_send_perm != True:
                        overwrite.send_messages = True
                        try:
                            await channel.set_permissions(owner, overwrite=overwrite, reason="동기화 해제")
                            synced_count += 1
                            await asyncio.sleep(0.2)
                        except Exception:
                            pass
                    else:
                        skipped_count += 1

        return synced_count, skipped_count

    @tasks.loop(minutes=1)
    async def auto_lock_task(self):
        await self.bot.wait_until_ready()
        await self.sync_all_banner_permissions()

    def load_daily_activity(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_daily_activity(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.daily_activity, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    async def send_user_dm(self, member: discord.Member, reason: str, channel: discord.TextChannel = None, channel_name: str = "", original_content: str = ""):
        ch_name = channel.name if channel else channel_name
        try:
            embed = discord.Embed(
                title="🚨 배너 홍보 규정 위반 안내", 
                description=f"**#{ch_name}** 채널 안내\n\n🚫 **스태프 개인 DM 문의 금지**\n🔗 [공식 문의처 바로가기]({INQUIRY_URL})", 
                color=discord.Color.orange(), 
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="사유", value=f"**{reason}**", inline=False)
            await member.send(embed=embed)
        except discord.Forbidden:
            if channel:
                try:
                    await channel.send(content=f"🔔 {member.mention} (DM 차단으로 채널에 안내됨)", embed=embed, delete_after=10)
                except Exception:
                    pass

    async def send_penalty_log(self, reason: str, message: discord.Message, owner: discord.Member = None):
        log_channel = self.bot.get_channel(self.log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(title="🚨 배너 규정 위반", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        if owner:
            embed.add_field(name="채널 소유자", value=f"{owner.mention}", inline=True)
        embed.add_field(name="작성자", value=f"{message.author.mention}", inline=True)
        embed.add_field(name="채널", value=message.channel.mention, inline=True)
        embed.add_field(name="사유", value=f"**{reason}**", inline=False)
        await log_channel.send(embed=embed)

    async def send_to_review_channel(self, message: discord.Message, owner: discord.Member, today_date: str):
        review_channel = self.bot.get_channel(self.review_channel_id)
        if not review_channel:
            return

        is_booster = any(role.id == self.booster_role_id for role in owner.roles)
        is_event = self.is_event_period(datetime.now(timezone(timedelta(hours=9))))
        
        if is_event:
            badge = "🌕 [이벤트]"
        else:
            badge = "💎 [부스터]" if is_booster else "👤 [일반]"

        embed = discord.Embed(title=f"🔍 {badge} 짧은 홍보글 승인 검토", color=discord.Color.gold(), timestamp=discord.utils.utcnow())
        embed.add_field(name="소유자", value=f"{owner.mention}", inline=True)
        embed.add_field(name="작성자", value=f"{message.author.mention}", inline=True)
        embed.add_field(name="채널", value=message.channel.mention, inline=True)
        embed.add_field(name="바로가기", value=f"[이동]({message.jump_url})", inline=False)

        view = PromoReviewView(self, message, owner, today_date)
        await review_channel.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not getattr(message.channel, "category_id", None) or message.author.guild_permissions.administrator:
            return
        if message.channel.category_id not in self.category_ids.values() or not message.channel.name.startswith("⚡"):
            return
        owner = self.get_channel_owner(message.channel) or message.author
        if owner.id in self.pending_review and self.pending_review[owner.id] == message.id:
            del self.pending_review[owner.id]
            await self.send_penalty_log("⚠️ 검토 대기 중 삭제 (취소됨)", message, owner)
        else:
            await self.send_penalty_log("🗑️ 작성 완료된 글 삭제 (제한 유지)", message, owner)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not getattr(message.channel, "category_id", None) or message.channel.id in self.exempt_channel_ids:
            return
        if message.channel.category_id not in self.category_ids.values() or not message.channel.name.startswith("⚡"):
            return
        if message.author.guild_permissions.administrator:
            return

        owner = self.get_channel_owner(message.channel)
        if owner and message.author.id != owner.id:
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} 타인의 배너 채널입니다.", delete_after=5)
            await self.send_user_dm(message.author, "본인 배너 채널에만 작성해주세요.", channel=message.channel)
            await self.send_penalty_log("타인 채널 작성 시도", message, owner)
            return

        if not owner:
            owner = message.author

        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        current_minute = now.hour * 60 + now.minute
        today_date = now.strftime("%Y-%m-%d")
        now_ts = now.timestamp()
        owner_id_str = str(owner.id)

        is_booster = any(role.id == self.booster_role_id for role in owner.roles)
        is_event = self.is_event_period(now)
        has_benefit = is_booster or is_event

        user_act = self.get_user_activity(owner_id_str, today_date)
        count = user_act["count"]
        last_ts = user_act["last_timestamp"]

        if not has_benefit and (31 <= current_minute <= 509):
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} 활동 금지 시간입니다.", delete_after=5)
            await self.send_user_dm(owner, "활동 금지 시간대(00:31~08:29) 작성", channel=message.channel)
            await self.send_penalty_log("금지 시간 활동", message, owner)
            return

        if message.reference:
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} 답장(끌올) 금지", delete_after=5)
            await self.send_user_dm(owner, "답장 기능 이용 금지", channel=message.channel)
            await self.send_penalty_log("답장(끌올) 꼼수", message, owner)
            return

        has_attachment = len(message.attachments) > 0
        has_link = ("http://" in message.content) or ("https://" in message.content)
        content_clean = message.content.replace("@everyone", "").replace("@here", "").strip()
        has_long_text = len(content_clean) >= 10

        if owner.id in self.pending_review:
            prev_msg_id = self.pending_review[owner.id]
            prev_msg = None
            try:
                prev_msg = await message.channel.fetch_message(prev_msg_id)
            except Exception:
                pass

            comb_attach = has_attachment or (prev_msg and len(prev_msg.attachments) > 0)
            combined_content = ((prev_msg.content if prev_msg else "") + " " + message.content).strip()
            comb_link = ("http://" in combined_content) or ("https://" in combined_content)
            comb_clean = combined_content.replace("@everyone", "").replace("@here", "").strip()
            comb_long = len(comb_clean) >= 10

            if comb_long and (comb_attach or comb_link):
                del self.pending_review[owner.id]
                self.record_post(owner_id_str, today_date, now_ts)
                new_count = self.get_user_activity(owner_id_str, today_date)["count"]
                
                if has_benefit:
                    if new_count >= 3:
                        await self.lock_channel_for_owner(message.channel, owner, "작성 3회 완료 채널 잠금")
                        await message.channel.send(f"✅ {message.author.mention} 혜택(3회) 모두 소진! 내일까지 채널 잠금", delete_after=10)
                    else:
                        await self.lock_channel_for_owner(message.channel, owner, "3시간 쿨타임 잠금")
                        await message.channel.send(f"✅ {message.author.mention} 등록 완료! 3시간 쿨타임 시작 (남은 횟수: {3 - new_count}회)", delete_after=10)
                else:
                    await self.lock_channel_for_owner(message.channel, owner, "작성 완료 채널 잠금")
                    await message.channel.send(f"✅ {message.author.mention} 등록 완료! 채널 잠금", delete_after=10)
                return

            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} 검토 중인 글이 있습니다.", delete_after=5)
            await self.send_penalty_log("검토 중 중복 작성", message, owner)
            return

        if has_benefit:
            if count >= 3:
                await message.delete()
                await message.channel.send(f"⚠️ {message.author.mention} 오늘 작성 횟수(3회)를 모두 소진하셨습니다.", delete_after=5)
                await self.send_user_dm(owner, "하루 3회 소진", channel=message.channel)
                await self.send_penalty_log("횟수 초과", message, owner)
                return
            if count > 0 and (now_ts - last_ts) < 10800:
                remain = int(10800 - (now_ts - last_ts))
                h, m = remain // 3600, (remain % 3600) // 60
                await message.delete()
                await message.channel.send(f"⚠️ {message.author.mention} 쿨타임 대기 중 ({h}시간 {m}분 남음)", delete_after=5)
                await self.send_user_dm(owner, f"쿨타임 미준수 ({h}시간 {m}분 남음)", channel=message.channel)
                await self.send_penalty_log("쿨타임 위반", message, owner)
                return
        else:
            if count >= 1:
                await message.delete()
                await message.channel.send(f"⚠️ {message.author.mention} 오늘 이미 작성하셨습니다.", delete_after=5)
                await self.send_user_dm(owner, "하루 1회 제한 초과", channel=message.channel)
                await self.send_penalty_log("일반 횟수 초과", message, owner)
                return

        if has_long_text and (has_attachment or has_link):
            self.record_post(owner_id_str, today_date, now_ts)
            new_count = self.get_user_activity(owner_id_str, today_date)["count"]
            
            if has_benefit:
                if new_count >= 3:
                    await self.lock_channel_for_owner(message.channel, owner, "작성 3회 완료 채널 잠금")
                    await message.channel.send(f"🔒 {message.author.mention} 3회 작성 완료! 내일까지 채널 잠금", delete_after=10)
                else:
                    await self.lock_channel_for_owner(message.channel, owner, "3시간 쿨타임 잠금")
                    await message.channel.send(f"🔒 {message.author.mention} 3시간 쿨타임 시작! (남은 횟수: {3 - new_count}회)", delete_after=10)
            else:
                await self.lock_channel_for_owner(message.channel, owner, "작성 완료 채널 잠금")
                await message.channel.send(f"🔒 {message.author.mention} 작성 완료로 채널이 잠겼습니다.", delete_after=10)
            return

        self.pending_review[owner.id] = message.id
        await self.send_to_review_channel(message, owner, today_date)
        await message.channel.send(f"ℹ️ {message.author.mention} 검토 대기 중입니다.", delete_after=5)

    @commands.command(name="배너패널", aliases=["배너"])
    async def setup_banner_panel(self, ctx):
        if not ctx.author.guild_permissions.administrator and not ctx.author.guild_permissions.manage_channels:
            return await ctx.send("❌ 관리자 권한이 필요합니다.", delete_after=5)

        try:
            await ctx.message.delete()
        except Exception:
            pass

        embed = discord.Embed(
            title="🖼️ 배너 채널 관리 패널", 
            description=f"스태프 전용 배너 컨트롤 도구\n\n🔗 [공식 문의처 바로가기]({INQUIRY_URL})", 
            color=discord.Color.dark_embed()
        )
        await ctx.send(embed=embed, view=BannerPanelView(self))

    @commands.command(name="배너동기화", aliases=["동기화"])
    async def sync_banner_command(self, ctx):
        if not ctx.author.guild_permissions.administrator and not ctx.author.guild_permissions.manage_channels:
            return await ctx.send("❌ 관리자 권한이 필요합니다.", delete_after=5)

        try:
            await ctx.message.delete()
        except Exception:
            pass

        msg = await ctx.send("🔄 권한 및 부스터 쿨타임 동기화 중...")
        synced, skipped = await self.sync_all_banner_permissions()
        kst = timezone(timedelta(hours=9))
        now_str = datetime.now(kst).strftime("%H:%M")
        await msg.edit(content=f"✅ 동기화 완료 (`{now_str}`)\n• 수정/해제: `{synced}`개\n• 유지: `{skipped}`개")

async def setup(bot):
    await bot.add_cog(Banner(bot))
