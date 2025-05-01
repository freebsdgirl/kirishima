from app.config import SUMMARY_DAILY_MAX_TOKENS, SUMMARY_WEEKLY_MAX_TOKENS, SUMMARY_MONTHLY_MAX_TOKENS

from shared.config import TIMEOUT

from shared.models.summary import SummaryCreateRequest, SummaryMetadata, Summary, CombinedSummaryRequest

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from app.util import get_user_alias

import httpx

from fastapi import HTTPException, status, APIRouter
router = APIRouter()


@router.post("/summary/combined/daily", status_code=status.HTTP_201_CREATED)
async def create_daily_summary(request: SummaryCreateRequest):
    # although period is passed as part of the request, we'll ignore it and just use daily.
    # get all summaries that match night, morning, afternoon, evening
    if request.period != "daily":
        logger.error(f"Invalid period specified: {request.period}. Expected 'daily'.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period specified. Expected 'daily'."
        )

    logger.debug(f"Creating daily summary for date: {request.date}")

    try:
        summaries = []

        chromadb_address, chromadb_port = shared.consul.get_service_address('chromadb')

        for summary_type in ["night", "morning", "afternoon", "evening"]:
            try:
                url = f"http://{chromadb_address}:{chromadb_port}/summary?type={summary_type}"

                if summary_type != "night":
                    url += f"&timestamp_begin={request.date}%2000:00:00&timestamp_end={request.date}%2023:59:59"

                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    summaries.extend(response.json())

            except httpx.HTTPStatusError as e:
                if e.response.status_code == status.HTTP_404_NOT_FOUND:
                    logger.info(f"No {summary_type} summaries found for {request.date}, skipping.")
                    continue
                else:
                    logger.error(f"HTTP error from chromadb: {e.response.status_code} - {e.response.text}")
                    raise

    except Exception as e:
        logger.error(f"Failed to contact chromadb to get a list of summaries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summaries: {e}")

    if not summaries:
        logger.warning("No summaries found for the specified period.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No summaries found for the specified period."
        )

    # summmaries is a list of Summary objects.
    # determine a list of user_ids from these objects using metadata.user_id
    user_ids = set()
    for summary in summaries:
        user_ids.add(summary["metadata"]["user_id"])

    # step through each user id and take the summaries for that user id
    # and send it to the proxy service for re-summarization.
    for user_id in user_ids:
        user_summaries = [s for s in summaries if s["metadata"]["user_id"] == user_id]
        logger.debug(f"Creating summary for user {user_id} with summaries: {user_summaries}")

        payload = CombinedSummaryRequest(
            summaries=user_summaries,
            user_alias=await get_user_alias(user_id),
            max_tokens=SUMMARY_DAILY_MAX_TOKENS
        )

        proxy_address, proxy_port = shared.consul.get_service_address('proxy')
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(f"http://{proxy_address}:{proxy_port}/summary/user/combined", json=payload.model_dump())
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error creating summary: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"An error occurred while creating summary: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create summary: {e}"
            )
        

        summary = response.json()

        metadata = SummaryMetadata(
            user_id=user_id,
            summary_type="daily",
            timestamp_begin=payload.summaries[0].metadata.timestamp_begin,
            timestamp_end=payload.summaries[-1].metadata.timestamp_end
        )
        summary = Summary(
            content=summary['summary'],
            metadata=metadata
        )
        logger.debug(f"Summary created for user {user_id}: {summary}")

        # write the summary to chromadb for daily/weekly/monthly
        chromadb_address, chromadb_port = shared.consul.get_service_address('chromadb')

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(f"http://{chromadb_address}:{chromadb_port}/summary", json=summary.model_dump())
                response.raise_for_status()

                summary = response.json()
                logger.debug(f"Summary written to chromadb: {summary['id']}")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error writing summary to chromadb: {e.response.text}"
            )

        except Exception as e:
            logger.error(f"An error occurred while writing summary to chromadb: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to write summary to chromadb: {e}"
            )

        # if the period is daily and the summary was written to chromadb, delete
        # the morning, evening, afternoon, and night summaries for that user id.
        for summary in user_summaries:
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    response = await client.delete(f"http://{chromadb_address}:{chromadb_port}/summary/{summary['id']}")
                    response.raise_for_status()
                    logger.debug(f"Deleted summary {summary['id']} from chromadb")

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"Error deleting summary: {e.response.text}"
                )

            except Exception as e:
                logger.error(f"An error occurred while deleting summary: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete summary: {e}"
                )
