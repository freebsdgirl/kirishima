from app.config import ADMIN_ID


def setup(bot):
    @bot.event
    async def on_message(message):# get a Command Context for this message
        ctx = await bot.get_context(message)

        # 1) Never ignore your own bot
        if message.author.bot:
            return

        # 2) If we’re awaiting this user, skip all custom logic
        if message.author.id in bot.awaiting_response:
            # (you can still choose to process_commands here if needed)
            return

        # if it's a valid command, let commands.Bot handle it and then return
        if ctx.command is not None:
            await bot.process_commands(message)
            return
        
        # Only process DMs from the specific user (replace USER_ID with the actual ID)
        if message.guild is None and message.author.id == ADMIN_ID:
            print(f"[DM from {message.author}] {message.content}")
        await bot.process_commands(message)  # Ensure commands still workill work