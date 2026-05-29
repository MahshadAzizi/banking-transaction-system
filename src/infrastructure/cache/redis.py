from redis.asyncio import Redis


async def build_redis_client(url: str):
    client = Redis.from_url(url, decode_responses=True)
    yield client
    await client.aclose()
