import aiohttp
import asyncio
import base64
import logging
import argparse
import urllib.parse
from aiohttp import web
from typing import Optional, Dict, Any, Set
from dataclasses import dataclass, field


@dataclass
class ProxyConfig:
    listen_host: str
    listen_port: int
    allow_redirects: bool
    base64_encode: bool
    log_level: str
    max_body_size: int = 10 * 1024 * 1024  # 10MB
    timeout: int = 30
    allowed_schemes: Set[str] = field(default_factory=lambda: {"http", "https"})
    header_request_method: str = "X-Request-Method"
    header_allow_redirects: str = "X-Allow-Redirects"
    header_base64_encode: str = "X-Base64-Encode"
    excluded_headers: Set[str] = field(init=False)

    def __post_init__(self):
        self.excluded_headers = {
            "host",
            "content-length",
            "content-encoding",
            "connection",
            "transfer-encoding",
            self.header_request_method.lower(),
            self.header_allow_redirects.lower(),
            self.header_base64_encode.lower(),
        }


class ProxyError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ProxyServer:
    def __init__(self, config: ProxyConfig):
        self.config = config
        self.logger = self._setup_logger()
        self.routes = web.RouteTableDef()
        self._setup_routes()

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger(__name__)
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, self.config.log_level.upper(), logging.INFO))
        return logger

    def _setup_routes(self):
        self.routes.route("*", "/fetch/{target_url:.*}")(self.fetch_url)

    def get_boolean_header(
        self, headers: Dict[str, str], key: str, default: bool = False
    ) -> bool:
        value = headers.get(key)
        return value.lower() == "true" if value else default

    def validate_url(self, url: str) -> None:
        if not url:
            raise ProxyError("URL parameter is required")

        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in self.config.allowed_schemes:
            raise ProxyError(
                f"URL scheme must be one of: {', '.join(self.config.allowed_schemes)}"
            )

    async def fetch_url(self, request: web.Request) -> web.Response:
        try:
            target_url = request.match_info["target_url"]
            self.validate_url(target_url)

            upstream_method = request.headers.get(
                self.config.header_request_method, request.method
            ).upper()
            allow_redirects = self.get_boolean_header(
                request.headers,
                self.config.header_allow_redirects,
                self.config.allow_redirects,
            )
            base64_encode = self.get_boolean_header(
                request.headers,
                self.config.header_base64_encode,
                self.config.base64_encode,
            )

            client_headers = {
                k: v
                for k, v in request.headers.items()
                if k.lower() not in self.config.excluded_headers
            }

            data = (
                await request.read()
                if upstream_method in {"POST", "PUT", "PATCH"}
                else None
            )

            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.request(
                        method=upstream_method,
                        url=target_url,
                        headers=client_headers,
                        params=(
                            request.rel_url.query if upstream_method == "GET" else None
                        ),
                        data=data,
                        allow_redirects=allow_redirects,
                        ssl=True,
                    ) as response:
                        response_data = await self._process_response(
                            response, base64_encode
                        )
                        self.logger.info(
                            f"Fetched {response.url} with method {upstream_method}, status {response.status}"
                        )
                        return web.json_response(response_data)
                except aiohttp.ClientError as e:
                    raise ProxyError(f"Failed to fetch URL: {str(e)}", 502)
                except asyncio.TimeoutError:
                    raise ProxyError("Request timed out", 504)

        except ProxyError as e:
            self.logger.error(f"Proxy error: {e.message}")
            return web.json_response({"error": e.message}, status=e.status_code)
        except Exception as e:
            self.logger.exception("Unexpected error")
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _process_response(
        self, response: aiohttp.ClientResponse, base64_encode: bool
    ) -> Dict[str, Any]:
        content = await response.read()
        if base64_encode:
            content = base64.b64encode(content).decode("utf-8")
            content_mode = "base64"
        else:
            try:
                content = content.decode("utf-8")
                content_mode = "text"
            except UnicodeDecodeError:
                content = base64.b64encode(content).decode("utf-8")
                content_mode = "base64"

        return {
            "upstream_url": str(response.url),
            "upstream_method": response.method,
            "status_code": response.status,
            "headers": dict(response.headers),
            "content": content,
            "content_mode": content_mode,
        }


def parse_args() -> ProxyConfig:
    parser = argparse.ArgumentParser(description="Async HTTP Proxy Server")
    parser.add_argument(
        "--listen-host", type=str, default="0.0.0.0", help="Host to bind the server"
    )
    parser.add_argument(
        "--listen-port", type=int, default=8090, help="Port to bind the server"
    )
    parser.add_argument(
        "--default-allow-redirects",
        type=bool,
        default=True,
        help="Default allow redirects setting",
    )
    parser.add_argument(
        "--default-base64-encode",
        type=bool,
        default=False,
        help="Default base64 encode setting",
    )
    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level")
    parser.add_argument(
        "--max-body-size",
        type=int,
        default=10 * 1024 * 1024,
        help="Maximum request body size in bytes",
    )
    parser.add_argument(
        "--timeout", type=int, default=30, help="Request timeout in seconds"
    )
    args = parser.parse_args()

    return ProxyConfig(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        allow_redirects=args.default_allow_redirects,
        base64_encode=args.default_base64_encode,
        log_level=args.log_level,
        max_body_size=args.max_body_size,
        timeout=args.timeout,
    )


async def init_app(config: ProxyConfig) -> web.Application:
    server = ProxyServer(config)
    app = web.Application(client_max_size=config.max_body_size)
    app.add_routes(server.routes)
    return app


if __name__ == "__main__":
    config = parse_args()
    web.run_app(init_app(config), host=config.listen_host, port=config.listen_port)
