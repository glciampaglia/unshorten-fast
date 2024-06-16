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
