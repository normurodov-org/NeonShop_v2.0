import asyncio
from pyrogram import Client

API_ID = 36071234      # o'zgaring! .env dagi haqiqiy ID
API_HASH = "17c9b87b674d19978500efecc2206daa"     # o'zgaring! .env dagi haqiqiy HASH

async def main():
    async with Client("tmp", api_id=API_ID, api_hash=API_HASH, in_memory=True) as app:
        s = await app.export_session_string()
        print("\nSESSION_STRING =")
        print(s)

asyncio.run(main())
