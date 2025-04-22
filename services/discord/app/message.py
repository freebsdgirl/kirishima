import shared.consul

from shared.models.discord import DiscordDirectMessage

from shared.log_config import get_logger
logger = get_logger(f"discord.{__name__}")

import httpx

from fastapi import HTTPException, status


def setup(bot):
    @bot.event
    async def on_message(message):
        try:
            logger.debug(f"Received message: {message.clean_content}")
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
            
            # only process DMs for now.
            if message.guild is None:
                print(f"Received DM from {message.author.name} ({message.author.id}): {message.clean_content}")
                logger.debug(f"Received DM from {message.author.name} ({message.author.id}): {message.clean_content}")

                discord_message = DiscordDirectMessage(
                    message_id=message.id,
                    content=message.clean_content,
                    author_id=message.author.id,
                    display_name=message.author.display_name
                )

                async with httpx.AsyncClient(timeout=60) as client:
                    try:
                        brain_address, brain_port = shared.consul.get_service_address('brain')
                    
                        response = await client.post(
                            f"http://{brain_address}:{brain_port}/discord/message/incoming", json=discord_message.model_dump())
                        response.raise_for_status()
                        return response.json()

                    except Exception as e:
                        logger.exception("Error retrieving service address for ledger:", e)

                    except httpx.HTTPStatusError as http_err:
                        logger.error(f"HTTP error forwarding from ledger: {http_err.response.status_code} - {http_err.response.text}")

                        raise HTTPException(
                            status_code=http_err.response.status_code,
                            detail=f"Error from ledger: {http_err.response.text}"
                        )

                    except httpx.RequestError as req_err:
                        logger.error(f"Request error when contacting ledger: {req_err}")

                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Connection error: {req_err}"
                        )

            await bot.process_commands(message)  # Ensure commands still work
        except Exception as e:
            logger.exception("Exception in on_message handler")

    @bot.event
    async def on_error(event_method, *args, **kwargs):
        print(f"Unhandled error in event: {event_method}")
        logger.exception(f"Unhandled error in event: {event_method}")