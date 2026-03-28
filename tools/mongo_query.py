import logging
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient

from config import settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    """Get or create the singleton motor client."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def close_client():
    """Close the motor client. Call on app shutdown."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_collection():
    """Get the configured transactions collection."""
    client = get_client()
    db = client[settings.mongodb_db]
    return db[settings.mongodb_collection]


async def fetch_records(period: dict, partner: str) -> list[dict]:
    """Fetch internal records from MongoDB for the given period and partner.

    Args:
        period: {"start": datetime, "end": datetime}
        partner: Service provider name to filter on.

    Returns:
        List of dicts in canonical schema.
    """
    collection = get_collection()

    query = {
        "params.serviceProvider": partner,
        "status": "completed",
        "createdAt": {
            "$gte": period["start"],
            "$lte": period["end"],
        },
    }

    # Only fetch fields we need — full documents are too large and slow over the network
    projection = {
        "params.transactionReference": 1,
        "params.amount": 1,
        "status": 1,
        "createdAt": 1,
    }

    logger.info(f"Querying MongoDB: {settings.mongodb_db}.{settings.mongodb_collection} "
                f"for partner={partner}, status=completed, period {period['start']} to {period['end']}")

    records = []
    cursor = collection.find(query, projection)

    async for doc in cursor:
        params = doc.get("params", {})
        record = {
            "referenceId": str(params.get("transactionReference", "")),
            "amount": params.get("amount"),
            "status": doc.get("status"),
            "timestamp": doc.get("createdAt"),
            "raw": {
                "_id": str(doc.get("_id")),
                "transactionReference": params.get("transactionReference"),
                "amount": params.get("amount"),
                "status": doc.get("status"),
                "createdAt": doc.get("createdAt").isoformat() if isinstance(doc.get("createdAt"), datetime) else doc.get("createdAt"),
            },
        }
        records.append(record)

    logger.info(f"Fetched {len(records)} records from MongoDB")
    return records
