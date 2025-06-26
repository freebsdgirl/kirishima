import asyncio

from shared.models.contacts import Contact
import app.user

async def handle_registration_response(ctx, response):
    """
    Handles the registration response from a Discord user.

    Depending on the user's response, this function either registers a new user or updates an existing user's contact information.

    Args:
        ctx: The Discord context object containing information about the command invocation and the user.
        response (str): The user's response, which can be "new" to register as a new user or an existing user ID to update contact information.

    Behavior:
        - If the response is "new", checks if the user is already registered. If not, registers the user as a new contact.
        - If the response is not "new", treats it as a user ID, verifies its validity, and attempts to update the contact with the current Discord user.
        - Sends appropriate feedback messages to the user based on the outcome of the registration or update process.
    """
    user = ctx.author

    if response.lower() == "new":
        # verify user isn't already registered
        contact = await app.user.get_contact_from_discord_id(user.id)
        if contact:
            # user is already registered
            await ctx.send(f"I know you, {contact.aliases[0]}! You're already registered.")
            return
        # if not, create an entry in contacts and register them to a new uuid.
        else:
            # register them as a new user
            await ctx.send(f"Hi {user.name}, registering you as a new user.")
            contact = await app.user.create_contact_from_discord_user(user)
    else:
        # verify id is valid
        contact = await app.user.get_contact_from_user_id(response)
        if not contact:
            await ctx.send("I don't know you. Please register as a new user.")
            return
        else:
            contact = await app.user.update_contact_from_discord(user, response)
            if not contact:
                await ctx.send("I couldn't update your contact. Please try again.")
                return
            await ctx.send(f"Hi {contact.aliases[0]}, updating your contact.")


def setup(bot):
    """
    Registers the 'register' command to the given Discord bot.

    The 'register' command is only available in direct messages (DMs) and prompts the user to enter their user ID or type 'NEW' to register as a new user. 
    The function tracks users who are expected to reply and waits for their response within a 120-second timeout. 
    If a response is received, it delegates handling to 'handle_registration_response'. 
    If the user does not respond in time, a timeout message is sent. 
    Regardless of the outcome, the user's ID is removed from the awaiting response set.

    Args:
        bot: The Discord bot instance to which the command is added.
    """
    @bot.command()
    async def register(ctx):
        if ctx.guild is not None:
            return  # Only respond to DMs

        await ctx.send("Enter your user id or type NEW to register as a new user.")

        # mark that we’re expecting a reply from this user
        bot.awaiting_response.add(ctx.author.id)

        try:
        # only grab messages from the same user & channel
            def check(m):
                return (
                    m.author.id == ctx.author.id and 
                    m.channel.id == ctx.channel.id
                )

            msg = await bot.wait_for('message', check=check, timeout=120)
            await handle_registration_response(ctx, msg.content)

        except asyncio.TimeoutError:
            await ctx.send("Too slow! ⏰")

        finally:
            # no matter what, stop ignoring them
            bot.awaiting_response.discard(ctx.author.id)
