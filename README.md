# HeaderProxy

HeaderProxy is a simple HTTP proxy that forwards requests and returns response headers along with the original content. It is designed to be used with **[changedetection.io](https://github.com/dgtlmoon/changedetection.io)** to help detect changes in response headers, but can be used for other purposes as well.

## Features
- Supports different HTTP methods (GET, POST, PUT, DELETE, etc.)
- Can follow or prevent redirects
- Optionally encodes binary content in Base64

## Usage

### Running HeaderProxy

Install dependencies and run:
```sh
pip install -r requirements.txt
python proxy.py --listen-port 8090
```

Or use Docker:
```sh
docker run --rm -it -p 8090:8090 ghcr.io/stek29/headerproxy
```

### Configuration Options
| Argument                    | Default        | Description |
|-----------------------------|----------------|-------------|
| `--listen-host`             | `0.0.0.0`      | Host to bind the server |
| `--listen-port`             | `8090`         | Port to bind the server |
| `--default-allow-redirects` | `True`         | Whether redirects should be followed by default |
| `--default-base64-encode`   | `False`        | Whether to Base64 encode responses by default |
| `--log-level`               | `INFO`         | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |

## API Reference

### `GET /fetch/{url}`
Fetches the specified URL and returns headers along with the content.

#### Path Parameters:
| Parameter  | Description |
|------------|-------------|
| `url`      | The target URL to fetch |

#### Headers:
| Header Name          | Description |
|----------------------|-------------|
| `X-Request-Method`   | Override the HTTP method for the upstream request (e.g., `PUT`, `DELETE`) |
| `X-Allow-Redirects`  | Set to `false` to prevent redirects (default: `true`) |
| `X-Base64-Encode`    | Set to `true` to return the response content as a Base64-encoded string |

#### Response Format:
| Field             | Type    | Description |
|-------------------|---------|-------------|
| `upstream_url`    | string  | The final URL after following redirects (if applicable) |
| `upstream_method` | string  | The HTTP method used for the upstream request |
| `status_code`     | integer | The HTTP response status code from the upstream server |
| `headers`         | object  | A dictionary of response headers received from the upstream server |
| `content`         | string  | The response body (either plain text or Base64-encoded) |
| `content_mode`    | string  | Indicates if the content is `text` or `base64` |

## Examples

### GET Request
```sh
curl "http://localhost:8090/fetch/https://httpbin.org/get?query=example"
```

```json
{
  "upstream_url": "https://httpbin.org/get?query=example",
  "upstream_method": "GET",
  "status_code": 200,
  "headers": {
    "Date": "Thu, 20 Feb 2025 13:12:13 GMT",
    "Content-Type": "application/json",
    "Content-Length": "336",
    "Connection": "keep-alive",
    "Server": "gunicorn/19.9.0",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Credentials": "true"
  },
  "content": "{\n  \"args\": {\n    \"query\": \"example\"\n  }, \n  \"headers\": {\n    \"Accept\": \"*/*\", \n    \"Accept-Encoding\": \"gzip, deflate\", \n    \"Host\": \"httpbin.org\", \n    \"User-Agent\": \"curl/8.7.1\", \n    \"X-Amzn-Trace-Id\": \"Root=...\"\n  }, \n  \"origin\": \"...\", \n  \"url\": \"https://httpbin.org/get?query=example\"\n}\n",
  "content_mode": "text"
}
```

### Override Method (PUT)
```sh
curl "http://localhost:8090/fetch/https://httpbin.org/put" -H "X-Request-Method: PUT" -d "key=value"
```

```json
{
  "upstream_url": "https://httpbin.org/put",
  "upstream_method": "PUT",
  "status_code": 200,
  "headers": {
    "Date": "...",
    "Content-Type": "application/json",
    "Content-Length": "...",
    "Connection": "keep-alive",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Credentials": "true"
  },
  "content": "{\n  \"args\": {}, \n  \"data\": \"\", \n  \"files\": {}, \n  \"form\": {\n    \"key\": \"value\"\n  }, \n  \"headers\": {\n    \"Accept\": \"*/*\", \n    \"Accept-Encoding\": \"gzip, deflate\", \n    \"Content-Length\": \"9\", \n    \"Content-Type\": \"application/x-www-form-urlencoded\", \n    \"Host\": \"httpbin.org\", \n    \"User-Agent\": \"curl/8.7.1\", \n    \"X-Amzn-Trace-Id\": \"Root=...\"\n  }, \n  \"json\": null, \n  \"origin\": \"...\", \n  \"url\": \"https://httpbin.org/put\"\n}\n",
  "content_mode": "text"
}
```

### Disable Redirects
```sh
curl "http://localhost:8090/fetch/https://httpbin.org/redirect/1" -H "X-Allow-Redirects: false"
```

```json
{
  "upstream_url": "https://httpbin.org/redirect/1",
  "upstream_method": "GET",
  "status_code": 302,
  "headers": {
    "Date": "...",
    "Content-Type": "text/html; charset=utf-8",
    "Content-Length": "215",
    "Connection": "keep-alive",
    "Server": "gunicorn/19.9.0",
    "Location": "/get",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Credentials": "true"
  },
  "content": "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 3.2 Final//EN\">\n<title>Redirecting...</title>\n<h1>Redirecting...</h1>\n<p>You should be redirected automatically to target URL: <a href=\"/get\">/get</a>.  If not click the link.",
  "content_mode": "text"
}
```

### Base64 Encoding
```sh
curl "http://localhost:8090/fetch/https://httpbin.org/image/png" -H "X-Base64-Encode: true"
```

```json
{
  "upstream_url": "https://httpbin.org/image/png",
  "upstream_method": "GET",
  "status_code": 200,
  "headers": {
    "Date": "...",
    "Content-Type": "image/png",
    "Content-Length": "8090",
    "Connection": "keep-alive",
    "Server": "gunicorn/19.9.0",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Credentials": "true"
  },
  "content": "iVBORw0KG...",
  "content_mode": "base64"
}
```
