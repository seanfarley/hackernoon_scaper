#!/usr/bin/env python3

import argparse
import asyncio

import aiohttp
import bs4


async def fetch_html(url: str, session: aiohttp.ClientSession) -> str:
    """GET request wrapper to fetch page HTML.

    kwargs are passed to `session.request()`.
    """
    resp = await session.request(method="GET", url=url)
    resp.raise_for_status()
    html = await resp.text()
    return html


async def parse_and_queue(level: str, url: str, session: aiohttp.ClientSession,
                          q: asyncio.Queue) -> None:
    """Parses urls on a page to drill down into and queues them.

    e.g. Iterate over all the years in an archive page to then drill down into
    the months.
    """
    print(f"Fetching url {url}")
    try:
        html = await fetch_html(url, session)
    except aiohttp.ClientError as e:
        print(f"aiohttp exception for {url} [{e.status}]: {e.message}")
        return None
    except Exception as e:
        print(f"Unknown exception for {url} [{e.status}]: {e.message}")
        return None

    soup = bs4.BeautifulSoup(html, 'html.parser')

    # opportunity here for object-oriented programming here
    new_level = None
    if level == "root":
        new_level = "year"
    elif level == "year":
        new_level = "month"

    if new_level is None:
        return None

    for item in soup.select('div[class~=timebucket] a'):
        item_url = item.attrs['href']
        print(f"  Queueing {item.text} url {item_url}")
        await q.put((new_level, item_url, session))


async def consume(level: str, q: asyncio.Queue) -> None:
    while True:
        l, url, session = await q.get()
        print(f"Consuming {url}")
        await parse_and_queue(l, url, session, q)
        q.task_done()


async def main(ncon: int) -> None:
    q = asyncio.Queue()
    async with aiohttp.ClientSession() as session:
        await q.put(("root", "https://hackernoon.com/archive", session))
        consumers = [asyncio.create_task(consume(n, q)) for n in range(ncon)]
        await q.join()
        for c in consumers:
            print(f"Cancelling consumer <{c}>")
            c.cancel()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-c", "--ncon", type=int, default=10)

    ns = parser.parse_args()

    asyncio.run(main(**ns.__dict__))
