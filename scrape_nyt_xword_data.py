import os
import argparse
import json
import asyncio
from datetime import date, timedelta

import aiohttp
import aiofiles
import requests


# Heavily borrowed from https://github.com/mattdodge/nyt-crossword-stats;
# refactored and tweaked for async requests

LOGIN_URL = "https://myaccount.nytimes.com/svc/ios/v2/login"
API_URL = "https://nyt-games-prd.appspot.com/svc/crosswords/"
PUZZLE_URL = API_URL + "v2/puzzle/daily-{}.json"
SOLVE_URL = API_URL + "v2/game/{}.json"
DATE_FORMAT = "%Y-%m-%d"


# synchronous, needed for all requets
def get_auth_cookie(username, password):
    data = {"login": username, "password": password}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "client_id": "ios.crosswords",
    }
    resp = requests.post(LOGIN_URL, data=data, headers=headers)
    resp.raise_for_status()
    for cookie in resp.json()["data"]["cookies"]:
        if cookie["name"] == "NYT-S":
            return {"NYT-S": cookie["cipheredValue"]}
    raise RuntimeError("Could not get authentication cookie from login.")


async def fetch(url, session):
    resp = await session.request(method="GET", url=url)
    resp.raise_for_status()
    content = await resp.json()
    return content


async def write(data, filename):
    async with aiofiles.open(filename, "w") as f:
        await f.write(json.dumps(data))


async def task(date, fname_fmt, session):
    puzz_url = PUZZLE_URL.format(date.isoformat())
    puzz_data = await fetch(puzz_url, session)
    puzz_id = puzz_data["results"][0]["puzzle_id"]
    solve_url = SOLVE_URL.format(puzz_id)
    solve_data = await fetch(solve_url, session)
    await write(puzz_data, fname_fmt.format("puzzle"))
    await write(solve_data, fname_fmt.format("solve"))
    print(f"Done with {date.isoformat()}")


def _get_filename_fmt(date, output_dir=None):
    fname = date.isoformat() + "_{}.json"
    if output_dir:
        return os.path.join(output_dir, fname)
    return fname


async def main(username, password, start_date, end_date, output_dir=None):
    auth_cookie = get_auth_cookie(username, password)
    async with aiohttp.ClientSession(cookies=auth_cookie) as session:
        tasks = []
        date = start_date
        while date <= end_date:
            fname_fmt = _get_filename_fmt(date, output_dir)
            tasks.append(task(date, fname_fmt, session))
            date += timedelta(days=1)
        await asyncio.gather(*tasks)


def _parse_args():
    parser = argparse.ArgumentParser(description="Asynchronously scrape NYT crossword data.")
    parser.add_argument("-u", "--username", help="NYT login email")
    parser.add_argument("-p", "--password", help="NYT login password")
    parser.add_argument("-s", "--start-date", help="Start date, (default today)",
                        type=date.fromisoformat, default=date.today())
    parser.add_argument("-e", "--end-date", help="End date (default today)",
                        type=date.fromisoformat, default=date.today())
    parser.add_argument("-o", "--output-dir", default=None, help="Output directory")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(args.username, args.password, args.start_date,
                     args.end_date, args.output_dir))
