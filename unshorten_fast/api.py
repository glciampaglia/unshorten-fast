""" Fast URL unshortener """

import re
import math
import time
import asyncio
import logging
import argparse

from statistics import mean, stdev
from urllib.parse import urlsplit
from typing import Optional, List, Awaitable, Union 
from importlib.resources import files

import aiohttp
from redis import asyncio as aioredis
import redis

TTL_DNS_CACHE = 300  # Time-to-live of DNS cache
MAX_TCP_CONN = 200  # Throttle at max these many simultaneous connections
TIMEOUT_TOTAL = 10  # Each request times out after these many seconds

# Using list from https://github.com/sambokai/ShortURL-Services-List
DOMAINS = files("unshorten_fast").joinpath("shorturl-services-list.csv")

LOG_FMT = "%(asctime)s:%(levelname)s:%(message)s"
logging.basicConfig(format=LOG_FMT, level="INFO")

def _reset_stats():
    global _STATS
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

_STATS = None
_reset_stats()


def _load_builtin_domains(path: str, 
                          skip_header: bool = True):
    with open(path) as f:
        if skip_header:
            f.readline()
        domains = [line.strip(',\n') for line in f]
        logging.debug(f"Loaded {len(domains)} from builtin list at {path}.")
        return domains


def make_parser() -> argparse.ArgumentParser:
    """
    Creates an ArgumentParser object with the script's command-line options. 

    Returns:
        An argparse.ArgumentParser object configured with the script's options.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.set_defaults(log_level="INFO", domains=_load_builtin_domains(DOMAINS))
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("-m",
                        "--maxlen",
                        type=int,
                        metavar="LEN",
                        help="Do not expand URLs longer than %(metavar)s")
    parser.add_argument("-n",
                        "--no-builtin-domains",
                        action="store_const",
                        dest="domains",
                        const=[],
                        help="Do not use builtin list of known URL shortening services")
    parser.add_argument("-d",
                        "--domains",
                        dest="domains",
                        action="extend",
                        nargs="+",
                        metavar="DOMAIN",
                        help="Expand if URL is from %(metavar)s")
    parser.add_argument("--no-cache",
                        action="store_true",
                        help="disable cache")
    parser.add_argument("--debug",
                        action="store_const",
                        const="DEBUG",
                        dest="log_level")
    parser.add_argument("--cache-redis",
                        action="store_true",
                        help="use redis cache")
    parser.add_argument("--cache-redis-host",
                        metavar="HOST",
                        default='localhost',
                        help="Connect to this host for Redis (default: %(default)s)")
    parser.add_argument("--cache-redis-port",
                        metavar="PORT",
                        type=int,
                        default=6379,
                        help="Connect to this port for Redis (default: %(default)d)")
    parser.add_argument("--cache-redis-db",
                        metavar="DB",
                        type=int,
                        default=0,
                        help="Connect to this db for Redis (default: %(default)d)")
    return parser


async def unshortenone(url: str, 
                       session: aiohttp.ClientSession,
                       pattern: Optional[re.Pattern] = None,
                       maxlen: Optional[int] = None,
                       cache: Union[aioredis.Redis, dict, None] = None,
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
        The expanded URL if successful, or the original URL if an error occurs
        or the URL is filtered out.
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
    if cache is not None:
        cached_url = None
        if isinstance(cache, dict) and url in cache:
            cached_url = str(cache.get(url))
        elif isinstance(cache, aioredis.Redis):
            in_cache = await cache.exists(url)
            if in_cache:
                longurl = await cache.get(url) 
                cached_url = str(longurl)
    if cache is not None and cached_url is not None:
        _STATS["cached_retrieved"] += 1
        return cached_url
    else:
        try:
            # await asyncio.sleep(0.01)
            req_start = time.time()
            resp = await session.head(url, timeout=timeout,
                                      ssl=False, allow_redirects=True)
            expanded_url = str(resp.url)
            req_stop = time.time()
            elapsed = req_stop - req_start
            _STATS['elapsed_a'].append(elapsed)
            if url != expanded_url:
                _STATS['expanded'] += 1
                _STATS['elapsed_e'].append(elapsed)
                if cache is not None:
                    _STATS["cached"] += 1
                    if isinstance(cache, dict):
                        cache[url] = expanded_url
                    else: # Redis
                        await cache.set(url, expanded_url)
            return expanded_url
        except (aiohttp.ClientError, asyncio.TimeoutError, UnicodeError) as e:
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


async def _unshorten(*urls: str,
                     no_cache: bool = False,
                     cache_redis: bool = False,
                     cache_redis_host: str = "localhost",
                     cache_redis_port: int = 6379,
                     cache_redis_db: int = 0,
                     domains: Optional[List[str]] = None,
                     maxlen: Optional[int] = None) -> List[str]:
    """
    See unshorten()
    """
    tic = time.time()
    if no_cache:
        cache = None
    else:
        if cache_redis:
            logging.info(f"Caching to redis://{cache_redis_host}" \
                            f":{cache_redis_port}/{cache_redis_db}")
            cache = aioredis.Redis(host=cache_redis_host, port=cache_redis_port,
                                   db=cache_redis_db)
            await cache.ping()
        else:
            logging.info("Caching to Python dict")
            cache = {}
    _reset_stats()
    if domains is None:
        # Use builtin list by default.
        domains = _load_builtin_domains(DOMAINS)
    if domains:
        # match only the tail end of netloc
        doms = (d + '$' for d in domains)
        pattern = re.compile(f"({'|'.join(doms)})", re.I)
    else:
        # domains is an empty list
        pattern = None
    conn = aiohttp.TCPConnector(ttl_dns_cache=TTL_DNS_CACHE, limit=None)
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_TOTAL)
    async with aiohttp.ClientSession(connector=conn) as session:
        try:
            u1 = unshortenone
            urliter = (u1(u, session, cache=cache, maxlen=maxlen, pattern=pattern, 
                          timeout=timeout) for u in urls)
            results = await gather_with_concurrency(MAX_TCP_CONN, *urliter)
        finally:
            if cache is not None and cache_redis:
                await cache.aclose()
    toc = time.time()
    elapsed = toc - tic
    rate = len(urls) / elapsed
    logging.info(f"Processed {len(urls)} urls in {elapsed:.2f}s ({rate:.2f} urls/s))")
    return results


def unshorten(*args, **kwargs) -> List[str]:
    """
    Expands multiple URLs concurrently using the specified options.

    Args:
        *urls: The URLs to expand.
        no_cache: Whether to disable the cache or not
        cache_redis: Whether to use Redis for the cache
        cache_redis_host: defaults to "localhost"
        cache_redis_port: defaults 6379
        cache_redis_db: defaults to 0
        domains: A list of known URL shortening domains. Will attempt
            unshortening an URL only if the domain is in this list. If None, load
            builtin list. Pass an empty list to disable checking known domains.
        maxlen: The maximum length of the URLs to expand.

    Returns:
        A list of the expanded URLs.
    """
    try:
        return asyncio.run(_unshorten(*args, **kwargs))
    finally:
        _log_elapsed_ms(_STATS['elapsed_a'], "Elapsed (all)")
        _log_elapsed_ms(_STATS['elapsed_e'], "Elapsed (expanded)")
        logging.info(f"Ignored: {_STATS['ignored']:.0f}")
        logging.info(f"Expanded: {_STATS['expanded']:.0f}")
        logging.info(f"Cached: {_STATS['cached']:.0f} ({_STATS['cached_retrieved']:.0f} hits)")
        logging.info(f"Errors: {_STATS['error']:.0f} ({_STATS['timeout']:.0f} timed out)")


def _log_elapsed_ms(seq: List[float], what: str):
    """
    Log elapsed time
    """
    if seq:
        elap_av = mean(seq) * 1e3
        if len(seq) > 1:
            elap_sd = stdev(seq) * 1e3
        else:
            elap_sd = math.nan
        logging.info(f"{what}: {elap_av:.2f}±{elap_sd:.2f} ms")
    else:
        logging.info(f"{what}: N/A")


def _main(args: argparse.Namespace) -> None:
    """
    Main function that reads input, processes URLs, and writes output.

    Args:
        args: An argparse.Namespace object containing the script's command-line
        arguments.
    """
    try:
        logging.basicConfig(level=args.log_level, format=LOG_FMT, force=True)
        logging.info(args)
        with open(args.input, encoding="utf8") as inputf:
            shorturls = (url.strip(" \n") for url in inputf)
            try:
                urls = unshorten(*shorturls, no_cache=args.no_cache, 
                                cache_redis=args.cache_redis, domains=args.domains,
                                maxlen=args.maxlen)
            except redis.ConnectionError:
                logging.error("Failed to connect to redis cache! Is Redis running?")
                import sys
                sys.exit(1)
        with open(args.output, "w", encoding="utf8") as outf:
            outf.writelines((u + "\n" for u in urls))
    except KeyboardInterrupt:
        import sys
        print(file=sys.stderr)
        logging.info("Interrupted by user.")


def main() -> None:
    """
    Entry point of the script, parses command-line arguments and calls _main().
    """
    parser = make_parser()
    args = parser.parse_args()
    _main(args)


if __name__ == "__main__":
    main()
