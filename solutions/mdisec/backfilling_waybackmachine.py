import asyncpg
from playwright.async_api import async_playwright
from waybackpy import WaybackMachineCDXServerAPI
import asyncio
import json
from urllib.parse import urlparse
import socket
import aiohttp
import aiofiles
import requests
import os
import re

DATABASE_URL = "postgres://VnWkeHccfIBKBnsoxKoxiRaRBLnUTfly:4oacvcUhEcxMp2EEyfEZZMuspAQI596RXlAOAHyQZXPXHrZefVPdKBK75E63sxVt@localhost:5432/mycvecom"

# Function to initialize the PostgreSQL database
async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS waybackmachine_results (
            id SERIAL PRIMARY KEY,
            url TEXT NOT NULL,
            waybackmachine_url TEXT NOT NULL,
            html_content TEXT NOT NULL,
            status TEXT NOT NULL
        )
    ''')
    await conn.close()

async def fetch_urls():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT * FROM unique_cve_entries WHERE status = 'failed'")
    await conn.close()
    return rows

async def fetch_page_content(url, page):
    await page.goto(url)
    content = await page.content()
    return content

# Asynchronous function to fetch the latest snapshot from the Wayback Machine
async def fetch_wayback_snapshot(url, semaphore):
    async with semaphore:
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            # Skip the URL if its already being saved in the database
            row = await conn.fetchrow("SELECT * FROM waybackmachine_results WHERE url = $1 and status = 'success'", url)
            if row:
                print(f'Skipping {url} as it has already been saved')
                return
            cdx = WaybackMachineCDXServerAPI(url)
            if ss := cdx.oldest():
                async with aiohttp.ClientSession() as session:
                    async with session.get(ss.archive_url) as resp:
                        if resp.status == 200:
                            print(f'Fetching {ss.archive_url} for {url}')
                            content = await resp.text()
                            await conn.execute('''
                                INSERT INTO waybackmachine_results (url, waybackmachine_url, html_content, status)
                                VALUES ($1, $2, $3, $4)
                            ''', url, ss.archive_url, content, 'success')
                        else:
                            await conn.execute('''
                                INSERT INTO waybackmachine_results (url, waybackmachine_url, html_content, status)
                                VALUES ($1, $2, $3, $4)
                            ''', url, ss.archive_url, '', f'failed: {resp.status} {resp.reason}')
        except Exception as e:
            print(f'Error fetching {url}: {str(e)}')
            await conn.execute('''
                INSERT INTO waybackmachine_results (url, waybackmachine_url, html_content, status)
                VALUES ($1, $2, $3, $4)
            ''', url, '', '', f'error: {str(e)}')

async def process_chunk(chunk, semaphore):
    tasks = [fetch_wayback_snapshot(row['url'], semaphore) for row in chunk]
    await asyncio.gather(*tasks)

async def main():
    await init_db()
    urls = await fetch_urls()
    semaphore = asyncio.Semaphore(5)  # Limit to 3 concurrent requests

    chunk_size = len(urls) // 10
    tasks = []
    for i in range(0, len(urls), chunk_size):
        chunk = urls[i:i + chunk_size]
        tasks.append(asyncio.create_task(process_chunk(chunk, semaphore)))

    await asyncio.gather(*tasks)

# To run the main function
asyncio.run(main())