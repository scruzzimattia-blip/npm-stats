from fastapi import FastAPI, HTTPException, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from pydantic import BaseModel

from src.database import (
    get_connection, 
    get_blocklist_with_ai_status, 
    get_database_info,
    load_traffic_df
)
from src.config import app_config

app = FastAPI(
    title="NPM Monitor API",
    description="Backend API for NPM Monitor Enterprise",
    version="2.0.0"
)

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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/blocklist")
async def get_active_blocks():
    """Get all active IP blocks."""
    try:
        return get_blocklist_with_ai_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/traffic/top-ips")
async def get_top_ips(limit: int = 10):
    """Get top IP addresses by request count."""
    try:
        from src.database import get_top_ips_summary
        df = get_top_ips_summary(limit=limit)
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/traffic/recent")
async def get_recent_traffic(limit: int = 100):
    """Get the most recent traffic logs."""
    try:
        df = load_traffic_df(limit=limit)
        # Convert timestamp to ISO string for JSON
        df['time'] = df['time'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/blocking/unblock/{ip}")
async def unblock_ip(ip: str):
    """Manually unblock an IP address."""
    try:
        from src.database import unblock_ip as db_unblock
        if db_unblock(ip):
            return {"status": "success", "message": f"IP {ip} unblocked"}
        else:
            raise HTTPException(status_code=404, detail=f"IP {ip} not found or already unblocked")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
