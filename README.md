
# URL Crawler with Wayback Machine Recovery


I have a dataset of **1 million URLs**, and approximately **40% of them are dead links**. The goal is to efficiently crawl these URLs, store their HTML content in a database, and recover content for dead links using the **Wayback Machine**.

## Requirements
1. **Crawling Active URLs**: Fetch and store the full HTML content of each live URL.
2. **Handling SPA Apps**: Use **Playwright** or a similar headless browser to render JavaScript-heavy pages.
3. **Dead Link Recovery**: If a URL is dead, extract and store its content from the **Wayback Machine**.
4. **Database Storage**: Store all results in a SQLite database.

## Expected Output
- A **SQLite file** containing the HTML content of all processed URLs.
- Properly handled rendering for **JavaScript-based pages**.
- Recovered content for dead links from the **Wayback Machine**.

## How to Contribute
If you're interested and confident in tackling this, feel free to **DM me**. I'll provide the dataset, and in return, I expect the processed **SQLite database file** containing the cve_id, url, and HTML Result.

All the CVE that has any reference URL related with it is stored as following format.

```
{'cve_id': 'CVE-2023-52905',
 'urls': ['https://git.kernel.org/stable/c/53da7aec32982f5ee775b69dce06d63992ce4af3',
  'https://git.kernel.org/stable/c/c8ca0ad10df08ea36bcac1288062d567d22604c9',
  'https://lore.kernel.org/linux-cve-announce/2024082113-CVE-2023-52905-53fd@gregkh/T',
  'https://nvd.nist.gov/vuln/detail/CVE-2023-52905',
  'https://www.cve.org/CVERecord?id=CVE-2023-52905']}
```

## Tech Stack Suggestions
Any tech you would like to use.
- **Python** (requests, BeautifulSoup, Playwright, SQLite)
- **Wayback Machine API** for retrieving archived content
- **Async processing** for efficiency

Feel free to fork, contribute, or reach out if you want to collaborate!