import asyncio

from datetime import datetime
from pyairtable import Table
from pyairtable.formulas import match
from bot.config import AIRTABLE_BASE, AIRTABLE_KEY


async def find_user(user_id, guild_id):

    """Return airtable record number in users table given user_id and guild_id."""

    loop = asyncio.get_running_loop()

    def _find_user():
        table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Users")
        records = table.all(
            formula=match({"discord_id": str(user_id), "guild_id": str(guild_id)})
        )
        if len(records) == 1:
            record_id = records[0].get("id")
        else:
            record_id = ""
        return record_id

    return await loop.run_in_executor(None, _find_user)


async def get_user_record(user_id, guild_id):

    """Return airtable record number in users table given user_id and guild_id."""

    loop = asyncio.get_running_loop()

    def _find_user():
        table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Users")
        records = table.all(
            formula=match({"discord_id": str(user_id), "guild_id": str(guild_id)})
        )
        if len(records) == 1:
            record_id = records[0]
        else:
            record_id = None
        return record_id

    return await loop.run_in_executor(None, _find_user)


async def get_contribution_records(guild_id):

    """"""

    loop = asyncio.get_running_loop()

    def _get_contribution():
        table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Contribution Flow")
        records = table.all(formula=match({"Guilds": str(guild_id)}))
        if records:
            record_id = records
        else:
            record_id = None
        return record_id

    return await loop.run_in_executor(None, _get_contribution)


async def get_highest_contribution_records(guild_id, user_id, total):

    """"""

    loop = asyncio.get_running_loop()

    def _get_contribution():
        table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Contribution Flow")
        records = table.all(
            formula=match(
                {
                    "guilds": str(guild_id),
                    "users": str(f"{guild_id}_{user_id}"),
                    "order": total,
                }
            )
        )
        if records:
            record_id = records[0]
        else:
            record_id = None
        return record_id

    return await loop.run_in_executor(None, _get_contribution)


# cannot use in async
def find_discord(user_id):

    """Return airtable record number in global table given user_id."""
    table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "global")
    records = table.all(formula=match({"discord_id": user_id}))
    if len(records) == 1:
        record_id = records[0].get("id")
    else:
        record_id = ""
    return record_id


async def get_discord_record(user_id):

    """Return airtable record number in global table given user_id."""
    loop = asyncio.get_running_loop()

    def _get_discord_record():
        table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "global")
        records = table.all(formula=match({"discord_id": user_id}))
        record = None
        if len(records) == 1:
            record = records[0]
        return record

    return await loop.run_in_executor(None, _get_discord_record)


async def find_guild(guild_id):

    """Return airtable record number in guild table given guild_id."""

    loop = asyncio.get_running_loop()

    def _find_guild():
        table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Guilds")
        records = table.all(formula=match({"guild_id": guild_id}))
        if len(records) == 1:
            record_id = records[0].get("id")
        else:
            record_id = ""
        return record_id

    return await loop.run_in_executor(None, _find_guild)


async def get_guild_by_guild_id(guild_id):

    """Return airtable record number in guild table given guild_id."""

    loop = asyncio.get_running_loop()

    def _find_guild():
        table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "guilds")
        records = table.all(formula=match({"guild_id": guild_id}))
        if len(records) == 1:
            record_id = records[0]
        else:
            record_id = ""
        return record_id

    return await loop.run_in_executor(None, _find_guild)


async def get_guild(record_id):

    """Return airtable record number in guild table given guild_id."""

    loop = asyncio.get_running_loop()

    def _find_guild():
        table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "guilds")
        records = table.get(str(record_id))
        record = {}
        if records:
            record = records.get("fields")
        return record

    return await loop.run_in_executor(None, _find_guild)


async def get_contribution_count(user_id, base_id):

    """Get a count of contributions a user has made to a given guild"""

    loop = asyncio.get_running_loop()

    def _count():
        # Add logic to get count
        table = Table(AIRTABLE_KEY, base_id, "Activity History Staging")

        user_table = Table(AIRTABLE_KEY, base_id, "Member")
        users = user_table.all(formula=match({"community_id": user_id}))
        if not users:
            raise Exception(f"Failed to fetch user from base {base_id}")
        user_display_name = users[0].get("fields").get("Name")
        records = table.all(formula=match({"member": user_display_name}))
        count = 0
        for record in records:
            count += 1
        return count

    return await loop.run_in_executor(None, _count)


async def get_contributions(global_id, date):

    """Get a count of contributions a user has made to a given guild"""

    loop = asyncio.get_running_loop()

    def _contributions(date=date):
        table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Activity History Staging")

        member_table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Members")
        members = member_table.all(formula=match({"global_id": global_id}))
        if not members:
            raise Exception(f"Failed to fetch user from base {AIRTABLE_BASE}")
        user_display_name = members[0].get("fields").get("Name")
        if not date:
            date = datetime.now()
        formatted_date = date.strftime("%Y-%m-%dT%H:%M::%S.%fZ")

        records = table.all(
            formula=f"AND({{member}}='{user_display_name}',{{DateOfSubmission}}>='{formatted_date}')"  # noqa: E501
        )
        return records

    return await loop.run_in_executor(None, _contributions)


async def update_user(record_id, id_field, id_val):

    """Add or update user ID info given ID field, value,
    and user table airtable record number."""

    loop = asyncio.get_running_loop()

    def _update_user():
        table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Users")
        table.update(record_id, {id_field: id_val})

    return await loop.run_in_executor(None, _update_user)


async def update_member(record_id, id_field, id_val):

    """Add or update member ID given ID field, value,
    and member table airtable record number."""

    loop = asyncio.get_running_loop()

    def _update_member():
        table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Members")
        table.update(record_id, {id_field: id_val})

    return await loop.run_in_executor(None, _update_member)


async def add_user_to_contribution(guild_id, user_id, order):

    """Add or update user ID info given ID field, value,
    and user table airtable record number."""

    loop = asyncio.get_running_loop()

    def _update_user():
        table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Contribution Flow")
        records = table.all(formula=match({"guilds": str(guild_id), "order": order}))
        record = records[0]

        table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Users")
        user = table.all(
            formula=match({"discord_id": str(user_id), "guild_id": str(guild_id)})
        )
        user_fields = user[0]
        user_record_id = user_fields.get("id")

        record_id = record.get("id")

        table.update(
            record_id,
            {
                "users": list(
                    {
                        user_record_id,
                        *record.get("fields", {"users": []}).get("users", []),
                    }
                )
            },
        )

    return await loop.run_in_executor(None, _update_user)


async def create_user(user_id, guild_id):

    """Return new airtable record # in users table given user_id & guild_id.
    If user table record for combo already exist, return existing record_id."""

    loop = asyncio.get_running_loop()

    record_id = await find_user(user_id, guild_id)
    guild_record = await find_guild(guild_id)

    def _create_user():
        global_table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "global")
        user_table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Users")
        guild_table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Guilds")
        member_table = Table(AIRTABLE_KEY, AIRTABLE_BASE, "Members")

        # check if user, guild combo already exists
        if record_id != "":  # existing combo
            return record_id
        else:  # new combo
            # add discord id to global table if user completely new
            discord_record = find_discord(user_id)
            if discord_record == "":
                global_table.create({"discord_id": str(user_id)})
                discord_record = find_discord(user_id)
            user_dao_id = (
                guild_table.get(guild_record).get("fields").get("total_members") + 1
            )
            i = user_table.create(
                {
                    "discord_id": [discord_record],
                    "guild_id": [guild_record],
                    "user_dao_id": str(user_dao_id),
                }
            )
            member_id = member_table.create(
                {"global_id": [i.get("id")], "Name": i.get("fields").get("Name")}
            )
            i.update({"Members": (member_id)})

            return record_id

    return await loop.run_in_executor(None, _create_user)
