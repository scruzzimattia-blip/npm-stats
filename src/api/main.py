from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.database import cache_result, get_blocklist_with_ai_status, get_database_info, get_redis, load_traffic_df

app = FastAPI(title="NPM Monitor API", description="Backend API for NPM Monitor Enterprise", version="2.0.0")


# Pydantic Models
class IPBlock(BaseModel):
    ip_address: str
    reason: str
    block_until: datetime


class SystemStats(BaseModel):
    total_rows: int
    blocked_count: int
    table_size: str


@app.get("/")
async def root():
    return {"status": "online", "service": "NPM Monitor API", "version": "2.0.0"}


@app.get("/stats", response_model=SystemStats)
async def get_stats():
    """Get global system statistics."""
    try:
        info = get_database_info()
        return SystemStats(**info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None


@app.get("/blocklist")
async def get_active_blocks():
    """Get all active IP blocks."""
    try:
        # Try Redis cache first
        redis_client = get_redis()
        cache_key = "api:blocklist"
        cached = redis_client.get(cache_key)
        if cached:
            import json

            return json.loads(cached)

        result = get_blocklist_with_ai_status()
        # Cache for 30 seconds
        redis_client.setex(cache_key, 30, json.dumps(result, default=str))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None


@app.get("/traffic/top-ips")
async def get_top_ips(limit: int = 10):
    """Get top IP addresses by request count."""
    try:
        from src.database import get_top_ips_summary
        import json

        # Try Redis cache first
        redis_client = get_redis()
        cache_key = f"api:top_ips:{limit}"
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        df = get_top_ips_summary(limit=limit)
        result = df.to_dict(orient="records")
        # Cache for 60 seconds
        redis_client.setex(cache_key, 60, json.dumps(result, default=str))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None


@app.get("/traffic/recent")
async def get_recent_traffic(limit: int = 100):
    """Get the most recent traffic logs."""
    try:
        import json

        # Try Redis cache first
        redis_client = get_redis()
        cache_key = f"api:recent_traffic:{limit}"
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        df = load_traffic_df(limit=limit)
        df["time"] = df["time"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        result = df.to_dict(orient="records")
        # Cache for 30 seconds
        redis_client.setex(cache_key, 30, json.dumps(result, default=str))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None


@app.post("/blocking/unblock/{ip}")
async def unblock_ip(ip: str):
    """Manually unblock an IP address."""
    try:
        from src.database import unblock_ip as db_unblock

        if db_unblock(ip):
            # Invalidate cache
            redis_client = get_redis()
            redis_client.delete("api:blocklist")
            return {"status": "success", "message": f"IP {ip} unblocked"}
        else:
            raise HTTPException(status_code=404, detail=f"IP {ip} not found or already unblocked")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None
