import copy
import json
import hashlib
import logging

from bot.common.bot.bot import bot
from bot.common.cache import RedisCache
from enum import Enum
from typing import Dict, Optional

from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def build_cache_value(thread, step, guild_id, message_id="", **kwargs):
    return json.dumps(
        {
            "thread": thread,
            "step": step,
            "guild_id": guild_id,
            "message_id": message_id,
            **kwargs,
        }
    )


class ThreadKeys(Enum):
    ONBOARDING = "onboarding"
    UPDATE_PROFILE = "update_profile"
    INITIAL_CONTRIBUTIONS = "initial_contributions"
    GUILD_SELECT = "guild_select"
    REPORT = "report"
    POINTS = "points"


class StepKeys(Enum):
    USER_DISPLAY_CONFIRM = "user_display_confirm"
    USER_DISPLAY_CONFIRM_EMOJI = "user_display_confirm_emoji"
    USER_DISPLAY_SUBMIT = "user_display_submit"
    ADD_USER_TWITTER = "add_user_twitter"
    ONBOARDING_CONGRATS = "onboarding_congrats"
    ADD_USER_WALLET_ADDRESS = "add_user_wallet_address"
    ADD_USER_DISCOURSE = "add_user_discourse"
    SELECT_GUILD_EMOJI = "select_guild_emoji"
    USER_UPDATE_FIELD_SELECT = "user_update_select"
    UPDATE_PROFILE_FIELD_EMOJI = "update_profile_field_emoji"
    UPDATE_FIELD = "update_field"
    CONGRATS_UPDATE_FIELD = "congrats_update_field"
    DISPLAY_NAME_REQUEST = "display_name_request"
    GOVRN_PROFILE_PROMPT = "govrn_profile_prompt"
    GOVRN_PROFILE_PROMPT_EMOJI = "govrn_profile_prompt_emoji"
    GOVRN_PROFILE_PROMPT_REJECT = "govrn_profile_prompt_reject"
    GOVRN_PROFILE_PROMPT_ACCEPT = "govrn_profile_prompt_accept"
    GOVRN_PROFILE_PROMPT_ACCEPT_EMOJI = "govrn_profile_prompt_accept_emoji"
    GOVRN_PROFILE_REUSE = "govrn_profile_reuse"
    END = "end"
    SEND_CONTRIBUTION_INSTRUCTION = "send_contribution_instruction"
    INITIAL_CONTRIBUTION_CONFIRM_EMOJI = "initial_contribution_confirm_emoji"
    INITIAL_CONTRIBUTION_ACCEPT = "inital_contribution_accept"
    INITIAL_CONTRIBUTION_REJECT = "inital_contribution_reject"
    INITIAL_CONTRIBUTION_REPORT_COMMAND = "initial_contribution_report_command"
    OVERRIDE_THREAD = "override_thread"
    REPORT = "report"
    DISPLAY_POINTS = "display_points"
    POINTS_CSV_PROMPT = "points_csv_prompt"
    POINTS_CSV_PROMPT_EMOJI = "points_csv_prompt_emoji"
    POINTS_CSV_PROMPT_ACCEPT = "points_csv_prompt_accept"


class BaseThread:
    """Base class for handling multi-interaction bot conversations

    Developers define the interaction tree in a series of steps. In a
    conversation a user can either react to a message with an emoji or
    reply to a previous message. The thread will handle either of these
    scenarios and store the end state in a cache to pick up the current
    conversation whenever it is continued.

    Args:
      user_id: Discord user id of the user interacting with the bot
      current_step: A hash of the current step of the bot interaction
      message_id: The id of the last message sent in the interaction
      guild_id: the discord guild id the interaction applies to, this
        can be None in some situations
      cache: The cache to store the state at the end of a step
      discord_bot: The discord bot client used to interact with the
        discord api
      context: the context of the interaction which was triggered by
        the user

    Attributes:
      user_id: Discord user id of the user interacting with the bot
      message_id: The id of the last message sent in the interaction
      guild_id: the discord guild id the interaction applies to, this
        can be None in some situations
      current_step: A hash of the current step of the bot interaction
      skip: A boolean representing whether the next step should be skipped
      cache: The cache to store the state at the end of a step
      discord_bot: The discord bot client used to interact with the
        discord api
      steps: A tree of the interaction flow from the root node
      step: A Step object of the current step of the interaction

    """

    def __init__(
        self,
        user_id,
        current_step,
        message_id,
        guild_id,
        cache=None,
        discord_bot=None,
        context=None,
    ):
        if not current_step:
            raise Exception(f"No step for {current_step}")
        if cache is None:
            cache = RedisCache()
        self.user_id = user_id
        self.message_id = message_id
        self.guild_id = guild_id
        self.current_step = current_step
        self.skip = False
        self.cache = cache
        self.bot = discord_bot
        if not self.bot:
            self.bot = bot
        self.context = context

    @classmethod
    def find_step(cls, steps, hash_):
        """Finds step in the thread tree

        Gets the the step that corresponds to the the provide hash

        Args:
          steps: A tree of steps that comprise a discord bot conversation
          hash_: The sha256 of the step that needs to be found

        Returns:
          A Step object that matches the hash or None
        """
        if steps.hash_ == hash_:
            return steps
        for _, step in steps.next_steps.items():
            steps = cls.find_step(step, hash_)
            if steps:
                return steps
        return None

    def __await__(self):
        return self._init_steps().__await__()

    async def _init_steps(self):
        self.steps = await self.get_steps()
        self.step = self.find_step(self.steps, self.current_step)
        return self

    def _check_step(self):
        if not hasattr(self, "step"):
            raise Exception("Class was never awaited and step is not set!")

    async def send(self, message):
        """Run the send method on a step

        Given a message, execute the send command for the current step of
        the thread. If the step is an emoji step it cannot be run;
        if there is an override step that step will be run after the current
        step. If the current step has trigger set to true it will
        immediately run the next step

        Args:
          message: A discord message object with the users response
            to the last step

        Returns:
          A boolean indicating whether the next step was set in the cache
          or if it is the final step whether it was deleted from the cache
        """
        self._check_step()
        logger.info(f"Send {self.step.hash_}")
        if self.step.current.emoji is True:
            await message.channel.send(
                "Please react with one of the above emojis to continue!"
            )
            return
        if self._should_save_previous_step():
            await self._save_previous_step(message)
        msg, metadata = await self.step.current.send(message, self.user_id)

        if not metadata:
            u = await self.cache.get(self.user_id)
            if u:
                metadata = json.loads(u).get("metadata")
        if not self.step.next_steps:
            return await self.cache.delete(self.user_id)
        step = list(self.step.next_steps.values())[0]
        override_step = await self.step.current.control_hook(message, self.user_id)
        if override_step == StepKeys.END.value:
            return await self.cache.delete(self.user_id)
        if override_step:
            step = self.step.get_next_step(override_step)
            # TODO: I am guessing this metadata will need to be refactored
            self.step = step
            return await self.send(message)

        # Trigger next send
        if self.step.current.trigger:
            self.step = step
            return await self.send(msg)

        return await self.cache.set(
            self.user_id,
            build_cache_value(
                self.name,
                step.hash_,
                self.guild_id,
                msg.id,
                metadata=metadata,
            ),
        )

    async def _save_previous_step(self, message):
        return await self.step.previous_step.current.save(
            message, self.guild_id, self.user_id
        )

    def _should_save_previous_step(self):
        return (
            self.step.previous_step
            and self.step.previous_step.current
            and not self.skip
        )

    # TODO: assumption Emoji cannot follow emoji, message must follow emoji
    async def handle_reaction(self, reaction, user):
        """Run the handle emoji method on a step

        Given a reaction on the previous message and the user
        who has applied that reaction run the handle_emoji logic
        on the current step. If skip reaction then skip the next
        step (a send step). If the step is an end step remove thread
        from the cache

        Args:
          reaction: A discord reaction that holds the emoji applied to the
            last message in the thread.
          user: A discord user of the user who added the reaction

        Returns:
          None

        """
        self._check_step()
        logger.info(f"Emoji {reaction}")
        # TODO: Add some error handling
        channel = await self.bot.fetch_channel(reaction.channel_id)
        message = await channel.fetch_message(reaction.message_id)

        if reaction.message_id != self.message_id:
            await channel.send(
                "Emoji reaction on the wrong message., "
                "Please react to your most recent message"
            )
            return
        try:
            step_name, skip = await self.step.current.handle_emoji(reaction)
        except Exception:
            logger.exception("Failed to handle the emoji")
            await channel.send(
                "In order to move to the following step please "
                "react with one of the already existing emojis"
            )
            return

        self.skip = skip
        if skip is True:
            next_step = self.step
        else:
            if not step_name:
                if not list(self.step.next_steps.values()):
                    if self._should_save_previous_step():
                        await self._save_previous_step(message)
                    return await self.cache.delete(self.user_id)
                step_name = list(self.step.next_steps.values())[0].current.name
            next_step = self.step.get_next_step(step_name)
        if not next_step:
            return await self.cache.delete(self.user_id)
        self.step = next_step
        await self.send(message)


class BaseStep:
    """A base class that holds logic for Step objects

    When implemented this class will have the logic
    necessary to move on to the next step with the
    typical methods being a send, save, handle_emoji
    and control_hook.

    Attributes:
      emoji: A boolean indicating whether this is an emoji
        step
      trigger: A boolean indicating whether to immediately
        run the next step.

    """

    emoji = False
    trigger = False

    async def save(self, message, guild_id, user_id):
        pass

    async def control_hook(self, message, user_id):
        pass


# TODO: There is an issue here if the same class is used on a branch
# Make sure that at a the a fork can use a previous branch
@dataclass
class Step:
    current: BaseStep
    next_steps: Optional[Dict[str, BaseStep]] = field(default_factory=dict)
    previous_step: Optional[BaseStep] = field(default=None)
    hash_: str = hashlib.sha256("".encode()).hexdigest()

    def add_next_step(self, step):
        """Add a new Step after the current

        Adds a step that the current steps points to
        and derives a hash from the current and next
        step.

        Args:
          step: A Step object representing the next step

        Returns:
          A Step obeject representing the next step
        """
        if isinstance(step, BaseStep):
            step = Step(current=step)
        step.previous_step = self
        step.hash_ = hashlib.sha256(
            f"{self.hash_}{step.current.name}".encode()
        ).hexdigest()
        self.next_steps[step.current.name] = step
        return step

    def fork(self, logic_steps):
        """Add multiple branches to the current step

        If a reaction or response causes a branching then
        the root of each of these branches can be added
        with this method.

        Args:
          logic_steps: An Iterable of step objects that
            represent each branch of the fork

        Returns:
          The current Step

        """
        if not logic_steps:
            Exception("No steps specified")
        for step in logic_steps:
            if isinstance(step, BaseStep):
                step = Step(current=step)
            step.previous_step = self
            step.hash_ = hashlib.sha256(
                f"{self.hash_}{step.current.name}".encode()
            ).hexdigest()

            self.next_steps[step.current.name] = self._copy_children(step)

        return self

    def _copy_children(self, step):
        next_steps = {}
        for k, s in step.next_steps.items():
            c = copy.copy(s)
            x = self._copy_children(c)
            next_steps[k] = x
        step.next_steps = next_steps
        return copy.copy(step)

    def build(self):
        """Finds the root node

        Gets the root node from any position in the tree

        Returns:
          The root Step

        """
        previous = self.previous_step
        while previous:
            if not previous.previous_step:
                break
            previous = previous.previous_step
        if previous is None:
            return self
        return previous

    def get_next_step(self, key):
        """Gets next step by name

        Args:
          key: a string that corresponds to the name that is being
            fetched.

        Raises:
          Exception: If the key does not correspond to one of the next
            steps.

        """
        step = self.next_steps.get(key, "")
        if step == "":
            raise Exception(
                f"Not a valid next step! current {self.current.name} and next: {key}"
                f" Valid next steps: {list(self.next_steps.keys())}"
            )
        return step
