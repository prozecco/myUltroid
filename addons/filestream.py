#    Ultroid - UserBot
#    Copyright 2021 (c) TeamUltroid
#
#    This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
#    Please read the GNU Affero General Public License in
#    <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.

"""
✘ Commands Available -
• `{i}stream <reply to media>`
    Get an instant HTTP streaming/direct download link for the media file.
"""

import socket
import re
import urllib.parse
import asyncio
from aiohttp import web
from . import *

port = 8082
runner = None
site = None

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

async def handle_stream(request):
    try:
        chat_id = int(request.match_info['chat_id'])
        msg_id = int(request.match_info['msg_id'])
    except ValueError:
        return web.HTTPBadRequest(text="Invalid parameters")
        
    try:
        # Fetch the message
        message = await ultroid_bot.get_messages(chat_id, ids=msg_id)
        if not message or not message.media:
            return web.HTTPNotFound(text="Media message not found")
            
        file_size = message.file.size
        if not file_size:
            return web.HTTPNotFound(text="File size is zero or not found")
            
        mime_type = message.file.mime_type or "application/octet-stream"
        filename = message.file.name or f"file_{msg_id}"
        
        range_header = request.headers.get("Range")
        start = 0
        end = file_size - 1
        
        if range_header:
            match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if match:
                start = int(match.group(1))
                if match.group(2):
                    end = int(match.group(2))
                    
        if start >= file_size or start > end:
            return web.HTTPRequestedRangeNotSatisfiable(
                headers={"Content-Range": f"bytes */{file_size}"}
            )
            
        length = end - start + 1
        
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": mime_type,
            "Content-Length": str(length),
            "Content-Disposition": f'attachment; filename="{urllib.parse.quote(filename)}"'
        }
        if range_header:
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            
        response = web.StreamResponse(
            status=206 if range_header else 200,
            reason="Partial Content" if range_header else "OK",
            headers=headers
        )
        
        await response.prepare(request)
        
        # Telethon iter_download offset must be divisible by 4096 (4KB)
        aligned_start = (start // 4096) * 4096
        skip_bytes = start - aligned_start
        
        bytes_written = 0
        async for chunk in ultroid_bot.iter_download(message.media, offset=aligned_start):
            if not chunk:
                break
                
            if skip_bytes > 0:
                if skip_bytes >= len(chunk):
                    skip_bytes -= len(chunk)
                    continue
                else:
                    chunk = chunk[skip_bytes:]
                    skip_bytes = 0
                    
            remaining = length - bytes_written
            if len(chunk) > remaining:
                chunk = chunk[:remaining]
                
            await response.write(chunk)
            bytes_written += len(chunk)
            if bytes_written >= length:
                break
                
        await response.write_eof()
        return response
    except Exception as e:
        LOGS.exception(e)
        return web.HTTPInternalServerError(text=str(e))

async def start_server():
    global runner, site, port
    app = web.Application()
    app.router.add_get("/stream/{chat_id}/{msg_id}/{filename}", handle_stream)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    for p in range(8082, 8095):
        try:
            site = web.TCPSite(runner, "0.0.0.0", p)
            await site.start()
            port = p
            LOGS.info(f"File Stream Server started on port {port}!")
            break
        except OSError:
            LOGS.info(f"Port {p} is in use, trying next...")
    else:
        LOGS.error("Failed to start File Stream Server: all ports 8082-8094 in use")

# Start server in the background
asyncio.get_event_loop().create_task(start_server())

@ultroid_cmd(pattern="stream ?(.*)")
async def stream_command(event):
    if not event.reply_to:
        return await event.eor("Reply to a media file to get stream link!")
    
    reply = await event.get_reply_message()
    if not (reply and reply.media):
        return await event.eor("Replied message has no media!")
        
    xx = await event.eor("`Generating stream link...`")
    
    chat_id = event.chat_id
    msg_id = reply.id
    
    filename = "stream"
    if reply.file:
        filename = reply.file.name or reply.file.title or f"file_{msg_id}"
        # Make filename URL-safe
        filename = urllib.parse.quote(filename)
        
    base_url = udB.get_key("STREAM_URL")
    if not base_url:
        base_url = f"http://{get_local_ip()}:{port}"
        
    stream_url = f"{base_url}/stream/{chat_id}/{msg_id}/{filename}"
    
    text = (
        f"**File Stream Link Generated!**\n\n"
        f"**File:** `{reply.file.name or 'Unknown'}`\n"
        f"**Size:** `{reply.file.size / (1024*1024):.2f} MB`\n\n"
        f"🔗 **Link:** [Click to Stream/Download]({stream_url})\n"
        f"💻 **Raw URL:** `{stream_url}`"
    )
    await xx.edit(text, link_preview=False)
