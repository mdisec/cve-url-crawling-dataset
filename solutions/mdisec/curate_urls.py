import json
from urllib.parse import urlparse
import socket
import asyncio
import aiohttp
import aiofiles
import requests
from waybackpy import WaybackMachineCDXServerAPI
import os
import asyncpg
import re

# Load the JSON data from the file
# with open('dataset.json', 'r') as file:
with open('small_sample_data.json', 'r') as file:
    data = json.load(file)

# Extract URLs and create a unique list
unique_urls = set()
for entry in data:
    for url in entry['urls']:
        unique_urls.add(url)

# Convert the set back to a list
unique_urls = list(unique_urls)

# Extract domain names and create a unique list
unique_domains = set()
for url in unique_urls:
    domain = urlparse(url).netloc
    unique_domains.add(domain)

# Convert the set back to a list
unique_domains = list(unique_domains)

# Ensure the results directory exists
os.makedirs('results', exist_ok=True)

# Function to initialize the PostgreSQL database
async def init_db(db_url):
    conn = await asyncpg.connect(db_url)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id SERIAL PRIMARY KEY,
            url TEXT NOT NULL,
            title TEXT,
            status_code INTEGER,
            response_headers JSON,
            content TEXT NOT NULL,
            is_crawled BOOLEAN DEFAULT FALSE
        )
    ''')
    await conn.close()

# Function to extract the title from the HTML content using regex
def extract_title(content):
    match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

# Function to save failed URLs to a JSON file
async def save_failed_urls(failed_urls, folder='results'):
    try:
        filename = os.path.join(folder, 'failed.json')
        async with aiofiles.open(filename, 'w') as file:
            await file.write(json.dumps(failed_urls, indent=4))
    except Exception as e:
        print(f"Error saving failed URLs: {e}")

# Function to save results to the database
async def save_results_to_db(resolved_urls, html_contents, unresolved_urls, wayback_urls, fetch_wayback_for_unresolved, db_url):
    for url, content in zip(resolved_urls, html_contents):
        if content:
            await save_content_to_db(url, content, db_url)

    if fetch_wayback_for_unresolved:
        for url, content in zip(unresolved_urls, wayback_urls):
            if content:
                await save_content_to_db(url, content, db_url)

# Asynchronous function to check if a domain has a resolution
async def check_domain_resolution(domain):
    loop = asyncio.get_event_loop()
    try:
        await loop.getaddrinfo(domain, None, proto=socket.IPPROTO_TCP)
        return domain
    except socket.gaierror:
        return None

# Asynchronous function to fetch the latest snapshot from the Wayback Machine
async def fetch_wayback_snapshot(url):
    try:
        cdx = WaybackMachineCDXServerAPI(url)
        if ss := cdx.newest():
            async with aiohttp.ClientSession() as session:
                async with session.get(ss.archive_url) as resp:
                    if resp.status == 200:
                        return await resp.text(), None
                    else:
                        return None, {"url": url, "status": resp.status, "reason": resp.reason}
    except Exception as e:
        return None, {"url": url, "status": "error", "reason": str(e)}

async def resolve_domains(domains):
    print("Resolving domains...")
    resolved_domains = []
    unresolved_domains = []
    # Check if the JSON files exist
    if os.path.exists('results/resolved_domains.json'):
        async with aiofiles.open('results/resolved_domains.json', 'r') as file:
            resolved_domains = json.loads(await file.read())
    if os.path.exists('results/unresolved_domains.json'):
        async with aiofiles.open('results/unresolved_domains.json', 'r') as file:
            unresolved_domains = json.loads(await file.read())

    # Filter out already resolved and unresolved domains
    domains_to_check = [domain for domain in domains if domain not in resolved_domains and domain not in unresolved_domains]

    print(f"Domains to check: {len(domains_to_check)}")
    # Resolve the remaining domains
    tasks = [check_domain_resolution(domain) for domain in domains_to_check]
    resolved_results = await asyncio.gather(*tasks)
    new_resolved_domains = [domain for domain in resolved_results if domain]
    new_unresolved_domains = [domain for domain in domains_to_check if domain not in new_resolved_domains]

    # Update the lists
    resolved_domains.extend(new_resolved_domains)
    unresolved_domains.extend(new_unresolved_domains)

    # Save the updated lists to JSON files
    async with aiofiles.open('results/resolved_domains.json', 'w') as file:
        await file.write(json.dumps(resolved_domains, indent=4))
    async with aiofiles.open('results/unresolved_domains.json', 'w') as file:
        await file.write(json.dumps(unresolved_domains, indent=4))

    return resolved_domains

# Update filter_urls_by_resolution function to save URLs to JSON files
async def filter_urls_by_resolution(urls, resolved_domains):
    print("Filtering URLs by resolution...")
    resolved_urls, unresolved_urls = [], []
    # Read the JSON files if they exist
    if os.path.exists('results/resolved_urls.json'):
        async with aiofiles.open('results/resolved_urls.json', 'r') as file:
            resolved_urls = json.loads(await file.read())
    if os.path.exists('results/unresolved_urls.json'):
        async with aiofiles.open('results/unresolved_urls.json', 'r') as file:
            unresolved_urls = json.loads(await file.read())
    
    # return the URLs if the both JSON files exist
    if resolved_urls and unresolved_urls:
        return resolved_urls, unresolved_urls

    resolved_urls = [url for url in urls if urlparse(url).netloc in resolved_domains]
    unresolved_urls = [url for url in urls if urlparse(url).netloc not in resolved_domains]

    try:
        resolved_filename = os.path.join('results', 'resolved_urls.json')
        unresolved_filename = os.path.join('results', 'unresolved_urls.json')
        async with aiofiles.open(resolved_filename, 'w') as resolved_file:
            await resolved_file.write(json.dumps(resolved_urls, indent=4))
        async with aiofiles.open(unresolved_filename, 'w') as unresolved_file:
            await unresolved_file.write(json.dumps(unresolved_urls, indent=4))
    except Exception as e:
        print(f"Error saving URLs to JSON: {e}")

    return resolved_urls, unresolved_urls

# Asynchronous function to fetch the HTML content of a URL using aiohttp
async def fetch_html_content(url, db_url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5, connect=3)) as response:
                print(f"Fetching URL: {url}")
                content = await response.text()
                headers = dict(response.headers)
                await save_content_to_db(url, response.status, headers, content, db_url)
                return content, None
    except Exception as e:
        print(f"Error fetching URL {url}: {e}")
        return None, {"url": url, "status": "error", "reason": str(e)}

# Function to save content to the PostgreSQL database
async def save_content_to_db(url, status_code, headers, content, db_url):
    try:
        title = extract_title(content)
        conn = await asyncpg.connect(db_url)
        # skip if the URL is already in the database
        existing_url = await conn.fetchval('SELECT url FROM urls WHERE url = $1', url)
        if existing_url:
            print(f"URL {url} already exists in the database")
            await conn.close()
            return
        
        is_crawled = False      
        if status_code == 200:
            is_crawled = True
            
        await conn.execute('''
            INSERT INTO urls (url, title, status_code, response_headers, content, is_crawled) VALUES ($1, $2, $3, $4, $5, $6)
        ''', url, title, status_code, json.dumps(headers), content, is_crawled)
        await conn.close()
        print(f"Saved content for URL: {url}")
    except Exception as e:
        print(f"Error saving content for {url}: {e}")

async def fetch_html_contents(urls, db_url):
    async def fetch_in_thread(urls_subset):
        print(f"Fetching {len(urls_subset)} URLs in a thread...")
        tasks = [fetch_html_content(url, db_url) for url in urls_subset]
        results = await asyncio.gather(*tasks)
        return results

    # Split URLs into 20 chunks
    chunk_size = max(1, len(urls) // 1000)
    url_chunks = [urls[i:i + chunk_size] for i in range(0, len(urls), chunk_size)]

    # Create tasks for each chunk
    """
    tasks = [fetch_in_thread(chunk) for chunk in url_chunks]
    results = await asyncio.gather(*tasks)
    """
    for chunk in url_chunks:
        results = await fetch_in_thread(chunk)

    # Flatten the results
    results = [item for sublist in results for item in sublist]
    html_contents = [result[0] for result in results if result[0]]
    failed_urls = [result[1] for result in results if result[1]]
    return html_contents, failed_urls

async def fetch_wayback_snapshots(urls):
    tasks = [fetch_wayback_snapshot(url) for url in urls]
    results = await asyncio.gather(*tasks)
    wayback_urls = [result[0] for result in results]
    failed_urls = [result[1] for result in results if result[1]]
    return wayback_urls, failed_urls

# Main function to check all domains and fetch Wayback Machine snapshots
async def main(fetch_wayback_for_unresolved=True):
    db_url = "postgres://VnWkeHccfIBKBnsoxKoxiRaRBLnUTfly:4oacvcUhEcxMp2EEyfEZZMuspAQI596RXlAOAHyQZXPXHrZefVPdKBK75E63sxVt@localhost:5432/mycvecom"
    await init_db(db_url)
    resolved_domains = await resolve_domains(unique_domains)

    resolved_urls, unresolved_urls = await filter_urls_by_resolution(unique_urls, resolved_domains)
    html_contents, failed_urls = await fetch_html_contents(resolved_urls, db_url)

    wayback_urls = []
    if fetch_wayback_for_unresolved:
        wayback_urls, wayback_failed_urls = await fetch_wayback_snapshots(unresolved_urls)
        failed_urls.extend(wayback_failed_urls)

    await save_results_to_db(resolved_urls, html_contents, unresolved_urls, wayback_urls, fetch_wayback_for_unresolved, db_url)
    await save_failed_urls(failed_urls)

asyncio.run(main(fetch_wayback_for_unresolved=False))