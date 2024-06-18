# unshorten-fast

This Python script expands short URLs created with URL shortening services
(like bit.ly) to their original long URLs _really fast_. It does so by using
[asynchronous HTTP requests](https://docs.aiohttp.org/) to run multiple web
requests concurrently. It reads a file containing a URL per line and writes an
output with short URLs replaced with their expanded version. The script
provides options to expand URLs based on their domain (if a list of URL
shortening services domains is provided) and on their total length, and
supports caching of expanded URLs to reduce the number of requests. 

## Features

- Single-threaded, asynchronous I/O for low CPU footprint;
- Uses HTTP's HEAD command instead of GET to reduce bandwidth;
- Caching to reduce amount of requests sent;
  - In-memory dictionary (default)
  - Redis queue (_requires Redis installed_)
- Flexible inclusion criteria:
  + User-defined domain inclusion list;
  - URL length;
- Detailed logging and statistics tracking

## Installation

Depending on how you want to use the tool, there are different recommended
installation methods. If you want to primarily use it as a standalone script
from the command line, then the recommended method is via
[pipx](https://github.com/pypa/pipx). Otherwise, if you plan to use it in your
own code, you can use pip or any another dependency management tool. For both
of these methods, point your package installer tool to the
`glciampaglia/unshorten-fast` repository on Github. Finally, if you plan to
modify the tool (for example with an editable install) and want to work in the
exact same development environment, the recommended tool is
[pipenv](https://pipenv.pypa.io/en/latest/), though we also provide a
`requirements.txt` file pinned to the same environment.

### Recommended (as a standalone script): using pipx

If you just care about using `unshorten` from the command line, then the best
is to install it in its own separate virtual environment.  

1. Install pipx using [these instructions](https://pipx.pypa.io/stable/installation/)
2. Run the following to install **unshorten-fast**:

```shell
pipx install git+https://github.com/glciampaglia/unshorten-fast.git
```

### Recommended (as a dependency): using pip

If you are looking to import `unshorten_fast` in your code, you will need to install it in your environment. At the moment the package has not been published on PyPI yet, so the simplest way is to point `pip` directly to a Github repository, for example the main one (`glciampaglia/unshorten-fast`).

```shell
pip install git+https://github.com/glciampaglia/unshorten-fast.git
```

If you want to install a forked version, then you will need to change
`glciampaglia/` to your forked version.

### Additional method (as a development environment): using pipenv

If you plan to make changes to **unshorten-fast**, you will probably want to checkout the code from Github and create an editable install that allows you to modify the code but still make use of the command line tool as an entry point. To reproduce the same environment used to develop **unshorten-fast**, the recommended way is to use [Pipenv](https://pipenv/pypa.io), a dependency management tool. This will checkout **unshorten-fast**'s code and create 

```shell
git clone https://github.com/glciampaglia/unshorten-fast.git
cd unshorten-fast
pipenv sync
pipenv shell
pip install -e .
```

Note that if you are working from a
forked version, then you will need to change `glciampaglia/` to your forked
version.

See the recommended [Pipenv
workflow](https://pipenv.pypa.io/en/latest/workflows.html) for how to add new
packages to the development environment. 

### Additional method (as a development environment): using pip

If not using `pipenv`, a `requirements.txt` file pinned to the same environment from Pipenv's lock file is provided for compability:

```shell
git clone https://github.com/glciampaglia/unshorten-fast.git
cd unshorten-fast
pip install -e . -r requirements.txt
```

## Usage

```shell
unshorten <input_file> <output_file> [options]
```

### Arguments

- `<input_file>`: Path to the file containing short URLs, one per line.
- `<output_file>`: Path to the file where expanded URLs will be written.

### Options

- `-m LEN`, `--maxlen LEN`: Ignore domains longer than `LEN` characters.
- `-d PATH`, `--domains PATH`: Expand a URL only if its domain is present in the CSV
  file at `PATH`.
- `--domains-noheader`: Specify that the CSV file with domains has no header row.
- `--no-cache`: Disable caching of expanded URLs.
- `--cache-redis`: Use Redis cache instead of an in-memory dictionary. This
  allows to reuse cache across multiple usages.
- `--debug`: Enable debug logging.
- `--cache-redis-host`: Connect to this host when using Redis (default: localhost)
- `--cache-redis-port`: Connect to this port when using Redis (default: 6379)
- `--cache-redis-db`: Connect to this db when using Redis (default: 0)

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
