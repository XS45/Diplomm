from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import asyncio
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncssh
import aioping
import aiofiles
import os

# Config
INVENTORY_FILE = "inventory.json"
LOG_FILE = "controller_log.jsonl"
SSH_TIMEOUT = 8

app = FastAPI()
# mount static directory (make sure "static" folder exists next to this file)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve SPA index
@app.get("/")
async def root():
    idx = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(idx)

@dataclass
class Device:
    name: str
    ip: str
    user: str
    password: str
    type: str = "generic"

# Storage helpers
async def load_inventory() -> List[Device]:
    try:
        async with aiofiles.open(INVENTORY_FILE, "r", encoding="utf-8") as f:
            s = await f.read()
            data = json.loads(s)
            return [Device(**d) for d in data]
    except FileNotFoundError:
        return []
    except Exception:
        return []

async def save_inventory(devs: List[Device]):
    async with aiofiles.open(INVENTORY_FILE, "w", encoding="utf-8") as f:
        await f.write(json.dumps([asdict(d) for d in devs], ensure_ascii=False, indent=2))

async def append_log(entry: Dict[str, Any]):
    entry["ts"] = datetime.utcnow().isoformat() + "Z"
    async with aiofiles.open(LOG_FILE, "a", encoding="utf-8") as f:
        await f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# Network/SSH helpers
async def ping_icmp(ip: str, timeout: float = 1.0) -> bool:
    try:
        await aioping.ping(ip, timeout=timeout)
        return True
    except Exception:
        return False

async def tcp_probe(ip: str, port: int = 22, timeout: float = 1.0) -> bool:
    try:
        fut = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False

async def is_reachable(ip: str) -> bool:
    # try ICMP first, fallback to TCP port 22
    if await ping_icmp(ip):
        return True
    return await tcp_probe(ip, 22, timeout=0.8)

async def run_ssh_command(device: Device, command: str, timeout: int = 10) -> Dict[str, Any]:
    res = {"ok": False, "stdout": "", "stderr": "", "error": None}
    try:
        conn = await asyncio.wait_for(
            asyncssh.connect(device.ip, username=device.user, password=device.password),
            timeout=SSH_TIMEOUT
        )
        async with conn:
            proc = await asyncio.wait_for(conn.create_process(command), timeout=timeout)
            out = await proc.stdout.read()
            err = await proc.stderr.read()
            rc = await proc.wait()
            res.update({"ok": rc == 0, "stdout": out, "stderr": err})
    except Exception as e:
        res["error"] = str(e)
    return res

# In-memory cache + lock
_inventory_lock = asyncio.Lock()
_inventory_cache: List[Device] = []

async def get_inventory() -> List[Device]:
    global _inventory_cache
    async with _inventory_lock:
        if not _inventory_cache:
            _inventory_cache = await load_inventory()
        return _inventory_cache

async def save_inventory_cache(devs: List[Device]):
    global _inventory_cache
    async with _inventory_lock:
        _inventory_cache = devs
        await save_inventory(devs)

# API endpoints
@app.get("/api/devices")
async def api_devices():
    devs = await get_inventory()
    return [asdict(d) for d in devs]

@app.post("/api/devices")
async def api_add_device(payload: Dict[str, Any]):
    # payload must contain name, ip, user, password
    required = ("name", "ip", "user", "password")
    if not all(k in payload for k in required):
        raise HTTPException(status_code=400, detail="Missing fields")
    devs = await get_inventory()
    if any(d.name == payload["name"] for d in devs):
        raise HTTPException(status_code=400, detail="Device name exists")
    new = Device(**{k: payload[k] for k in ("name","ip","user","password","type") if k in payload} )
    devs.append(new)
    await save_inventory_cache(devs)
    await append_log({"action":"add_device","device":asdict(new)})
    return {"ok": True}

@app.delete("/api/devices/{name}")
async def api_delete_device(name: str):
    devs = await get_inventory()
    new = [d for d in devs if d.name != name]
    if len(new) == len(devs):
        raise HTTPException(status_code=404, detail="Not found")
    await save_inventory_cache(new)
    await append_log({"action":"delete_device","name":name})
    return {"ok": True}

@app.post("/api/devices/{name}/check")
async def api_check(name: str):
    devs = await get_inventory()
    d = next((x for x in devs if x.name == name), None)
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    reachable = await is_reachable(d.ip)
    ssh_info = None
    if reachable:
        ssh_info = await run_ssh_command(d, "uname -a")
    await append_log({"action":"status","device":asdict(d),"reachable":reachable,"ssh":ssh_info})
    return {"device": asdict(d), "reachable": reachable, "ssh": ssh_info}

@app.post("/api/devices/{name}/run")
async def api_run(name: str, body: Dict[str, Any]):
    cmd = body.get("cmd")
    if not cmd:
        raise HTTPException(status_code=400, detail="Missing cmd")
    devs = await get_inventory()
    d = next((x for x in devs if x.name == name), None)
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    res = await run_ssh_command(d, cmd)
    await append_log({"action":"run_cmd","device":asdict(d),"cmd":cmd,"result":res})
    return res

@app.post("/api/devices/{name}/reboot")
async def api_reboot(name: str):
    devs = await get_inventory()
    d = next((x for x in devs if x.name == name), None)
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    if not await is_reachable(d.ip):
        await append_log({"action":"reboot","device":asdict(d),"result":"unreachable"})
        raise HTTPException(status_code=409, detail="Device unreachable")
    res = await run_ssh_command(d, "sudo reboot", timeout=5)
    await append_log({"action":"reboot","device":asdict(d),"result":res})
    return res

@app.get("/api/logs")
async def api_logs(limit: int = 200):
    try:
        async with aiofiles.open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = await f.readlines()
            parsed = [json.loads(l) for l in lines[-limit:]]
            return parsed
    except FileNotFoundError:
        return []

# Simple health
@app.get("/api/health")
async def health():
    return {"status":"ok", "time": datetime.utcnow().isoformat() + "Z"}