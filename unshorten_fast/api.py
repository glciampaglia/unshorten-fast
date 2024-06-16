"""
Expand URLs from shortening services.

This script takes a file containing short URLs as input, expands them to their original long URLs using asynchronous HTTP requests, and writes the expanded URLs to an output file. It provides options to filter URLs based on domain and length, and supports caching of expanded URLs.

Usage:
    python api.py <input_file> <output_file> [options]

Arguments:
    input_file: Path to the file containing short URLs, one per line.
    output_file: Path to the file where expanded URLs will be written.

Options:
    -m LEN, --maxlen LEN: Ignore domains longer than LEN characters.
    -d PATH, --domains PATH: Expand only if the domain is present in the CSV file at PATH.
    --domains-noheader: Specify that the CSV file with domains has no header row.
    --no-cache: Disable caching of expanded URLs.
    --debug: Enable debug logging.

Configuration:
    TTL_DNS_CACHE: Time-to-live of DNS cache in seconds (default: 300).
    MAX_TCP_CONN: Maximum number of simultaneous TCP connections (default: 50).
    TIMEOUT_TOTAL: Timeout for each request in seconds (default: 10).

Functions:
    make_parser(): Creates an ArgumentParser object with the script's command-line options.
    unshortenone(url, session, pattern=None, maxlen=None, cache=None, timeout=None): Expands a single short URL using an aiohttp session.
    gather_with_concurrency(n, *tasks): Runs tasks concurrently with a maximum of n simultaneous tasks.
    _unshorten(*urls, cache=None, domains=None, maxlen=None): Expands multiple URLs concurrently using the specified options.
    unshorten(*args, **kwargs): Calls _unshorten() using the provided arguments and keyword arguments.
    _main(args): Main function that reads input, processes URLs, and writes output.
    main(): Entry point of the script, parses command-line arguments and calls _main().

Logging:
    The script uses the logging module to log information and errors. The log format is defined by LOG_FMT, and the log level can be set using the --debug option.

Statistics:
    The script keeps track of various statistics in the _STATS dictionary:
        - ignored: Number of URLs ignored due to domain or length filtering.
        - timeout: Number of requests that timed out.
        - error: Number of requests that encountered an error.
        - cached: Number of URLs added to the cache.
        - cached_retrieved: Number of URLs retrieved from the cache.
        - expanded: Number of URLs successfully expanded.

Examples:
    Expand URLs from input.txt and write the expanded URLs to output.txt:
        python expand_urls.py input.txt output.txt

    Expand URLs with a maximum length of 100 characters:
        python expand_urls.py input.txt output.txt -m 100

    Expand URLs only for domains listed in domains.csv:
        python expand_urls.py input.txt output.txt -d domains.csv

    Disable caching and enable debug logging:
        python expand_urls.py input.txt output.txt --no-cache --debug
"""

import aiohttp
import argparse
import asyncio
import time
from statistics import mean, median, stdev
import logging
from urllib.parse import urlsplit
import re
from typing import Optional, List, Awaitable
import redis



TTL_DNS_CACHE=300  # Time-to-live of DNS cache
MAX_TCP_CONN=200  # Throttle at max these many simultaneous connections
TIMEOUT_TOTAL=10  # Each request times out after these many seconds


LOG_FMT = "%(asctime)s:%(levelname)s:%(message)s"
logging.basicConfig(format=LOG_FMT, level="INFO")
_STATS = {
    "ignored": 0,
    "timeout": 0,
    "error": 0,
    "cached": 0,
    "cached_retrieved": 0,
    "expanded": 0,
    "elapsed_a": [],
    "elapsed_e": [],
}


def make_parser() -> argparse.ArgumentParser:
    """
    Creates an ArgumentParser object with the script's command-line options.

    Returns:
        An argparse.ArgumentParser object configured with the script's options.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("-m",
                        "--maxlen",
                        type=int,
                        metavar="LEN",
                        help="Ignore domains longer than %(metavar)s")
    parser.add_argument("-d",
                        "--domains",
                        dest="domains_path",
                        metavar="PATH",
                        help="Expand if domain is present in CSV file at %(metavar)s")
    parser.add_argument("--domains-noheader",
                        action="store_false",
                        dest="skip_header",
                        help="CSV file with domains has no header")
    parser.add_argument("--no-cache",
                        action="store_true",
                        help="disable cache")
    parser.add_argument("--debug",
                        action="store_const",
                        const="DEBUG",
                        dest="log_level")
    parser.set_defaults(log_level="INFO")
    return parser


async def unshortenone(url: str, session: aiohttp.ClientSession, pattern: Optional[re.Pattern] = None,
                       maxlen: Optional[int] = None, cache: Optional[redis.Redis] = None,
                       timeout: Optional[aiohttp.ClientTimeout] = None) -> str:
    """
    Expands a single short URL using an aiohttp session.

    Args:
        url: The short URL to expand.
        session: An aiohttp.ClientSession object for making HTTP requests.
        pattern: A compiled regular expression to match against the URL's domain.
        maxlen: The maximum length of the URL to expand.
        cache: A dictionary for caching expanded URLs.
        timeout: An aiohttp.ClientTimeout object specifying the request timeout.

    Returns:
        The expanded URL if successful, or the original URL if an error occurs or the URL is filtered out.
    """
    # If user specified list of domains, check netloc is in it, otherwise set
    # to False (equivalent of saying there is always a match against the empty list)
    if pattern is not None:
        domain = urlsplit(url).netloc
        match = re.search(pattern, domain)
        no_match = (match is None)
    else:
        no_match = False
    # If user specified max URL length, check length, otherwise set to False
    # (equivalent to setting max length to infinity -- any length is OK)
    too_long = (maxlen is not None and len(url) > maxlen)
    # Ignore if either of the two exclusion criteria applies.
    if too_long or no_match:
        _STATS["ignored"] += 1
        return url
    # if cache is not None and url in cache:
    #     _STATS["cached_retrieved"] += 1
    #     return str(cache[url])
    cached_ans = cache.get(url) if cache is not None else None

    if cached_ans is not None:
        _STATS["cached_retrieved"] += 1
        return cached_ans.decode('UTF-8')
    else:
        try:
            # await asyncio.sleep(0.01)
            req_start = time.time()
            resp = await session.head(url, timeout=timeout,
                                      ssl=False, allow_redirects=True)
            req_stop = time.time()
            elapsed = req_stop - req_start
            expanded_url = str(resp.url)
            _STATS['elapsed_a'].append(elapsed)
            if url != expanded_url:
                _STATS['expanded'] += 1
                _STATS['elapsed_e'].append(elapsed)
                # if cache is not None and url not in cache:
                if cache is not None and cache.get(url) is None:
                    # update cache if needed
                    _STATS["cached"] += 1
                    # cache[url] = expanded_url
                    cache.set(url, expanded_url)
            return expanded_url
        except (aiohttp.ClientError, asyncio.TimeoutError, UnicodeError) as e:
            req_stop = time.time()
            elapsed = req_stop - req_start
            _STATS['elapsed_a'].append(elapsed)
            _STATS["error"] += 1
            if isinstance(e, asyncio.TimeoutError):
                _STATS["timeout"] += 1
            logging.debug(f"{e.__class__.__name__}: {e}: {url}")
            return url


# Thanks: https://blog.jonlu.ca/posts/async-python-http
async def gather_with_concurrency(n: int, *tasks: Awaitable) -> List:
    """
    Runs tasks concurrently with a maximum of n simultaneous tasks.

    Args:
        n: The maximum number of tasks to run concurrently.
        *tasks: The tasks to run.

    Returns:
        A list of the results of the completed tasks.
    """
    semaphore = asyncio.Semaphore(n)

    async def sem_task(task):
        async with semaphore:
            return await task
    return await asyncio.gather(*(sem_task(task) for task in tasks))


async def _unshorten(*urls: str, cache: Optional[dict] = None, domains: Optional[List[str]] = None,
                     maxlen: Optional[int] = None) -> List[str]:
    """
    Expands multiple URLs concurrently using the specified options.

    Args:
        *urls: The URLs to expand.
        cache: A dictionary for caching expanded URLs.
        domains: A list of domains to filter URLs by.
        maxlen: The maximum length of the URLs to expand.

    Returns:
        A list of the expanded URLs.
    """
    if domains is not None:
        pattern = re.compile(f"({'|'.join(domains)})", re.I)
    else:
        pattern = None
    conn = aiohttp.TCPConnector(ttl_dns_cache=TTL_DNS_CACHE, limit=None)
    u1 = unshortenone
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_TOTAL)
    async with aiohttp.ClientSession(connector=conn) as session:
        return await gather_with_concurrency(MAX_TCP_CONN,
                                             *(u1(u, session, cache=cache,
                                                  maxlen=maxlen,
                                                  pattern=pattern,
                                                  timeout=timeout) for u in urls))

# def unshorten(*args, **kwargs):
def unshorten(*args, **kwargs) -> List[str]:
    """
    Calls _unshorten() using the provided arguments and keyword arguments.

    Args:
        *args: Positional arguments to pass to _unshorten().
        **kwargs: Keyword arguments to pass to _unshorten().

    Returns:
        A list of the expanded URLs.
    """

    return asyncio.run(_unshorten(*args, **kwargs))


def _log_elapsed_ms(seq, what):
    if seq:
        elap_av = mean(seq) / 1e3
        elap_sd = stdev(seq) / 1e3
        logging.info(f"{what}: {elap_av:.5f}±{elap_sd:.5f} ms")
    else:
        logging.info(f"{what}: N/A")


def _main(args: argparse.Namespace) -> None:
    """
    Main function that reads input, processes URLs, and writes output.

    Args:
        args: An argparse.Namespace object containing the script's command-line arguments.
    """

    try:
        logging.basicConfig(level=args.log_level, format=LOG_FMT, force=True)
        logging.info(args)
        if args.domains_path is not None:
            with open(args.domains_path) as f:
                if args.skip_header:
                    f.readline()
                domains = [line.strip(',\n') for line in f]
        else:
            domains = None
        if args.no_cache:
            cache = None
        else:
            # cache = {}
            cache = redis.Redis()
        tic = time.time()
        with open(args.input, encoding="utf8") as inputf:
            shorturls = (url.strip(" \n") for url in inputf)
            urls = unshorten(*shorturls, cache=cache, domains=domains,
                             maxlen=args.maxlen)
        with open(args.output, "w", encoding="utf8") as outf:
            outf.writelines((u + "\n" for u in urls))
        toc = time.time()
        elapsed = toc - tic
        rate = len(urls) / elapsed
        logging.info(f"Processed {len(urls)} urls in {elapsed:.2f}s ({rate:.2f} urls/s))")
    except KeyboardInterrupt:
        import sys
        print(file=sys.stderr)
        logging.info("Interrupted by user.")
    finally:
        _log_elapsed_ms(_STATS['elapsed_a'], "Elapsed (all)")
        _log_elapsed_ms(_STATS['elapsed_e'], "Elapsed (expanded)")
        logging.info(f"Ignored: {_STATS['ignored']:.0f}")
        logging.info(f"Expanded: {_STATS['expanded']:.0f}")
        logging.info(f"Cached: {_STATS['cached']:.0f} ({_STATS['cached_retrieved']:.0f} hits)")
        logging.info(f"Errors: {_STATS['error']:.0f} ({_STATS['timeout']:.0f} timed out)")


def main() -> None:
    """
    Entry point of the script, parses command-line arguments and calls _main().
    """
    parser = make_parser()
    args = parser.parse_args()
    _main(args)


if __name__ == "__main__":
    main()
