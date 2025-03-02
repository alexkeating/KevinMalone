import logging

from bot.common.threads.thread_builder import (
    BaseThread,
    ThreadKeys,
    BaseStep,
    StepKeys,
    Step,
)
from bot.config import read_file
from bot.common.airtable import (
    get_guild_by_guild_id,
    get_contribution_count,
    get_user_record,
)
from bot.common.cache import build_congrats_key

logger = logging.getLogger(__name__)


class ReportStep(BaseStep):
    """Sends a link for a user to report their contributions"""

    name = StepKeys.USER_DISPLAY_CONFIRM.value

    def __init__(self, guild_id, cache, bot, channel=None):
        self.guild_id = guild_id
        self.cache = cache
        self.bot = bot
        self.channel = channel

    async def send(self, message, user_id):
        channel = self.channel
        if message:
            channel = message.channel

        airtableLinks = read_file()
        airtableLink = airtableLinks.get(str(self.guild_id))

        msg = (
            f"Woohoo! Nice job! Community contributions are what keeps"
            " your community thriving 🌞. "
            f"Report you contributions via the form 👉 {airtableLink}"
        )
        if message:
            await channel.send(msg)
        if not await self.cache.get(build_congrats_key(user_id)):
            fields = await get_guild_by_guild_id(self.guild_id)
            congrats_channel_id = fields.get("fields").get("congrats_channel_id")
            base_id = fields.get("fields").get("base_id")
            if not congrats_channel_id:
                logger.warn("No congrats channel id!")
                return None, {"msg": msg}
            channel = self.bot.get_channel(int(congrats_channel_id))
            user = self.bot.get_user(user_id)
            # get count of uses
            record = await get_user_record(user_id, self.guild_id)
            fields = record.get("fields")
            user_dao_id = fields.get("user_dao_id")
            count = await get_contribution_count(user_dao_id, base_id)
            await channel.send(
                f"Congrats {user.display_name} for reporting {count} "
                "engagements this week!"
            )
            await self.cache.set(
                build_congrats_key(user_id), "True", ex=60 * 60
            )  # Expires in an hour

        return None, {"msg": msg}


class Report(BaseThread):
    name = ThreadKeys.REPORT.value

    async def get_steps(self):
        return Step(
            current=ReportStep(guild_id=self.guild_id, cache=self.cache, bot=self.bot)
        ).build()
