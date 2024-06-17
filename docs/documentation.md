# Unshorten-Fast

This Python script expands short URLs created with URL shortening services to
their original long URLs using asynchronous HTTP requests. It reads a file
containing a URL per line and writes an output with short URLs replaced with
their expanded version. The script provides options to expand URLs based on
their domain (if a list of URL shortening services domains is provided) and on
their total length, and supports caching of expanded URLs to reduce the number
of requests. 

## Features

- Expands short URLs to their original long URLs
- Asynchronous HTTP requests for efficient processing
- Apply expansion of URLs based on domain and length
- Caches expanded URLs for improved performance
- Detailed logging and statistics tracking

## Installation

1. Clone the repository
2. Install the package along with its required dependencies:

```shell
pip install .
```

## Running

```shell
unshorten <input_file> <output_file> [options]
```

### Arguments

- `<input_file>`: Path to the file containing short URLs, one per line.
- `<output_file>`: Path to the file where expanded URLs will be written.

### Options

- `-m LEN`, `--maxlen LEN`: Ignore domains longer than `LEN` characters.
- `-d PATH`, `--domains PATH`: Expand only if the domain is present in the CSV file at `PATH`.
- `--domains-noheader`: Specify that the CSV file with domains has no header row.
- `--no-cache`: Disable caching of expanded URLs.
- `--cache-redis`: Use Redis cache instead of an in-memory dictionary.
- `--debug`: Enable debug logging.

## Examples

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

```shell
unshorten input.txt output.txt --cache-redis
```

## Logging and Statistics

The script uses the `logging` module to log information and errors. The log
level can be set using the `--debug` option. The script outputs various
statistics at the end of execution:

- `ignored`: Number of URLs ignored due to domain or length filtering.
- `timeout`: Number of requests that timed out.
- `error`: Number of requests that encountered an error.
- `cached`: Number of URLs added to the cache.
- `cached_retrieved`: Number of URLs retrieved from the cache.
- `expanded`: Number of URLs successfully expanded.
- `elapsed_a`: List of elapsed times for all requests.
- `elapsed_e`: List of elapsed times for expanded URLs.
