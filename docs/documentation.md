## URL Expander
This Python script expands short URLs from URL shortening services to their original long URLs using asynchronous HTTP requests. It reads a file containing short URLs, expands them, and writes the expanded URLs to an output file. The script provides options to filter URLs based on domain and length, and supports caching of expanded URLs.
### Features

- Expands short URLs to their original long URLs
- Asynchronous HTTP requests for efficient processing
- Filters URLs based on domain and length
- Caches expanded URLs for improved performance
- Configurable options for DNS cache TTL, maximum TCP connections, and request timeout
- Detailed logging and statistics tracking

### Installation

1. Clone the repository
2. Install the required dependencies:

```shell
pip install -r requirements.txt
```

### Running

```shell
unshorten <input_file> <output_file> [options]
```
### Arguments

- <input_file>: Path to the file containing short URLs, one per line.
- <output_file>: Path to the file where expanded URLs will be written.

### Options

- `-m LEN`, `--maxlen LEN`: Ignore domains longer than `LEN` characters.
- `-d PATH`, `--domains PATH`: Expand only if the domain is present in the CSV file at `PATH`.
- `--domains-noheader`: Specify that the CSV file with domains has no header row.
- `--no-cache`: Disable caching of expanded URLs.
- `--cache-redis`: Use Redis cache instead of an in-memory dictionary.
- `--debug`: Enable debug logging.

### Configuration
The script has the following configurable parameters:

- `TTL_DNS_CACHE`: Time-to-live of DNS cache in seconds (default: 300).
- `MAX_TCP_CONN`: Maximum number of simultaneous TCP connections (default: 200).
- `TIMEOUT_TOTAL`: Timeout for each request in seconds (default: 10).

### Examples
Expand URLs from `input.txt` and write the expanded URLs to `output.txt`:
```shell
unshorten input.txt output.txt
```
Expand URLs with a maximum length of 100 characters:
```shell
unshorten input.txt output.txt -m 100
```
Expand URLs only for domains listed in domains.csv:
```shell
unshorten input.txt output.txt -d domains.csv
```
Disable caching and enable debug logging:
```shell
unshorten input.txt output.txt --no-cache --debug
```

Use Redis cache instead of an in-memory dictionary:

```
unshorten input.txt output.txt --cache-redis
```
Logging and Statistics
The script uses the `logging` module to log information and errors. The log format is defined by `LOG_FMT`, and the log level can be set using the `--debug` option.
The script tracks various statistics in the `_STATS` dictionary:

- `ignored`: Number of URLs ignored due to domain or length filtering.
- `timeout`: Number of requests that timed out.
- `error`: Number of requests that encountered an error.
- `cached`: Number of URLs added to the cache.
- `cached_retrieved`: Number of URLs retrieved from the cache.
- `expanded`: Number of URLs successfully expanded.
- `elapsed_a`: List of elapsed times for all requests.
- `elapsed_e`: List of elapsed times for expanded URLs.

The statistics are logged at the end of the script's execution.