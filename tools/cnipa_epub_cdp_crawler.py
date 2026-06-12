# -*- coding: utf-8 -*-
"""
中国专利公布公告网站点：http://epub.cnipa.gov.cn/ 首页检索的 CDP 实现。

本文件保留原 Playwright 版脚本的能力边界：使用真实 Chromium 页面等待站点前端脚本完成，
再提交首页 #searchStr / #indexForm，并把结果页 HTML 交给 cnipa_epub_parse.py 解析。

默认连接 http://127.0.0.1:9222；若端口不可用，会尝试用本机 Chrome/Chromium 启动一个
remote-debugging 实例。整个实现只使用 Python 标准库，不安装或调用 Playwright。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from cnipa_epub_parse import EpubSearchHit, parse_search_result_html

EPUB_BASE = "http://epub.cnipa.gov.cn/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class CdpError(RuntimeError):
    pass


class _CdpWebSocket:
    def __init__(self, websocket_url: str):
        parsed = urllib.parse.urlparse(websocket_url)
        if parsed.scheme != "ws":
            raise CdpError(f"unsupported websocket url: {websocket_url}")
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 80
        self.path = parsed.path
        if parsed.query:
            self.path += "?" + parsed.query
        self.sock = socket.create_connection((self.host, self.port), timeout=15)
        self.sock.settimeout(30)
        self._handshake()

    def _handshake(self) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode("ascii"))
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            data += chunk
        if b" 101 " not in data.split(b"\r\n", 1)[0]:
            raise CdpError("CDP websocket handshake failed")
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        )
        if accept not in data:
            raise CdpError("CDP websocket accept header mismatch")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def send_json(self, payload: dict) -> None:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        header = bytearray([0x81])
        if len(raw) < 126:
            header.append(0x80 | len(raw))
        elif len(raw) < 65536:
            header.extend([0x80 | 126])
            header.extend(struct.pack("!H", len(raw)))
        else:
            header.extend([0x80 | 127])
            header.extend(struct.pack("!Q", len(raw)))
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(raw))
        self.sock.sendall(bytes(header) + mask + masked)

    def recv_json(self, timeout: float = 30) -> dict:
        old_timeout = self.sock.gettimeout()
        self.sock.settimeout(timeout)
        try:
            while True:
                opcode, payload = self._recv_frame()
                if opcode == 0x1:
                    return json.loads(payload.decode("utf-8", errors="replace"))
                if opcode == 0x8:
                    raise CdpError("CDP websocket closed")
                if opcode == 0x9:
                    self._send_pong(payload)
        finally:
            self.sock.settimeout(old_timeout)

    def _recv_exact(self, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise CdpError("CDP websocket closed while reading")
            data += chunk
        return data

    def _recv_frame(self) -> tuple[int, bytes]:
        first, second = self._recv_exact(2)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length) if length else b""
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return opcode, payload

    def _send_pong(self, payload: bytes) -> None:
        header = bytearray([0x8A])
        header.append(0x80 | len(payload))
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + mask + masked)


class _CdpSession:
    def __init__(self, websocket_url: str):
        self.ws = _CdpWebSocket(websocket_url)
        self.next_id = 0

    def close(self) -> None:
        self.ws.close()

    def call(self, method: str, params: dict | None = None, timeout: float = 30) -> dict:
        self.next_id += 1
        msg_id = self.next_id
        self.ws.send_json({"id": msg_id, "method": method, "params": params or {}})
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self.ws.recv_json(max(0.1, deadline - time.time()))
            if msg.get("id") != msg_id:
                continue
            if "error" in msg:
                raise CdpError(f"{method} failed: {msg['error']}")
            return msg.get("result", {})
        raise TimeoutError(f"CDP command timed out: {method}")

    def wait_event(self, method: str, timeout: float = 30) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self.ws.recv_json(max(0.1, deadline - time.time()))
            if msg.get("method") == method:
                return True
        return False


@dataclass
class _BrowserHandle:
    endpoint: str
    proc: subprocess.Popen | None = None
    temp_dir: tempfile.TemporaryDirectory | None = None

    def close(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.temp_dir:
            self.temp_dir.cleanup()


def _endpoint() -> str:
    return (
        os.environ.get("CDP_ENDPOINT")
        or os.environ.get("CDP_URL")
        or f"http://127.0.0.1:{os.environ.get('CDP_PORT', '9222')}"
    ).rstrip("/")


def _http_json(url: str, *, method: str = "GET", timeout: float = 5) -> dict | list:
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _endpoint_alive(endpoint: str) -> bool:
    try:
        _http_json(endpoint + "/json/version", timeout=2)
        return True
    except Exception:
        return False


def _find_chrome() -> str | None:
    env = os.environ.get("CHROME_BIN", "").strip()
    candidates = [
        env,
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "/opt/google/chrome/chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for item in candidates:
        if not item:
            continue
        if os.path.isabs(item) and Path(item).exists():
            return item
        found = shutil.which(item)
        if found:
            return found
    return None


def _launch_or_connect() -> _BrowserHandle:
    endpoint = _endpoint()
    if _endpoint_alive(endpoint):
        return _BrowserHandle(endpoint=endpoint)

    chrome = _find_chrome()
    if not chrome:
        raise CdpError(
            "no live CDP endpoint and no Chrome/Chromium found; set CDP_ENDPOINT or CHROME_BIN"
        )
    parsed = urllib.parse.urlparse(endpoint)
    port = parsed.port or int(os.environ.get("CDP_PORT", "9222"))
    tmp = tempfile.TemporaryDirectory(prefix="cnipa-cdp-")
    args = [
        chrome,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={tmp.name}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-sandbox",
    ]
    if os.environ.get("CDP_HEADED", "").strip().lower() not in ("1", "true", "yes"):
        args.append("--headless=new")
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 20
    while time.time() < deadline:
        if _endpoint_alive(endpoint):
            return _BrowserHandle(endpoint=endpoint, proc=proc, temp_dir=tmp)
        time.sleep(0.5)
    proc.terminate()
    tmp.cleanup()
    raise TimeoutError(f"Chrome CDP endpoint not ready: {endpoint}")


def _new_target(endpoint: str, url: str = "about:blank") -> dict:
    quoted = urllib.parse.quote(url, safe="")
    api = f"{endpoint}/json/new?{quoted}"
    try:
        return _http_json(api, method="PUT", timeout=5)  # Chrome 113+
    except urllib.error.HTTPError:
        return _http_json(api, method="GET", timeout=5)


def _close_target(endpoint: str, target_id: str | None) -> None:
    if not target_id:
        return
    try:
        urllib.request.urlopen(f"{endpoint}/json/close/{target_id}", timeout=2).read()
    except Exception:
        pass


def _max_wait_sec() -> float:
    return float(os.environ.get("EPUB_WAF_MAX_WAIT_SEC", "180"))


def _eval(session: _CdpSession, expression: str, *, timeout: float = 30) -> object:
    result = session.call(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": True},
        timeout=timeout,
    )
    if "exceptionDetails" in result:
        raise CdpError(f"Runtime.evaluate exception: {result['exceptionDetails']}")
    return result.get("result", {}).get("value")


def _wait_selector(session: _CdpSession, selector: str, *, max_wait_sec: float) -> None:
    deadline = time.time() + max_wait_sec
    expr = f"Boolean(document.querySelector({json.dumps(selector)}))"
    while time.time() < deadline:
        if _eval(session, expr, timeout=5):
            return
        time.sleep(3)
    raise TimeoutError(f"{max_wait_sec}s no selector: {selector}")


def _wait_result_page_settled(session: _CdpSession) -> None:
    session.wait_event("Page.loadEventFired", timeout=45)
    time.sleep(float(os.environ.get("EPUB_SETTLE_SEC", "1.2")))


def fetch_epub_result_html(keyword: str) -> str:
    browser = _launch_or_connect()
    target: dict | None = None
    session: _CdpSession | None = None
    try:
        target = _new_target(browser.endpoint)
        ws_url = target.get("webSocketDebuggerUrl")
        if not ws_url:
            raise CdpError("CDP target has no webSocketDebuggerUrl")
        session = _CdpSession(ws_url)
        session.call("Page.enable")
        session.call("Runtime.enable")
        session.call("Network.enable")
        session.call("Network.setUserAgentOverride", {"userAgent": DEFAULT_USER_AGENT})
        session.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False},
        )
        session.call("Page.navigate", {"url": EPUB_BASE}, timeout=10)
        session.wait_event("Page.loadEventFired", timeout=60)
        _wait_selector(session, "#searchStr", max_wait_sec=_max_wait_sec())
        script = f"""
        (() => {{
          const input = document.querySelector('#searchStr');
          if (!input) throw new Error('missing #searchStr');
          input.value = {json.dumps(keyword)};
          input.dispatchEvent(new Event('input', {{ bubbles: true }}));
          input.dispatchEvent(new Event('change', {{ bubbles: true }}));
          const form = document.querySelector('#indexForm');
          if (form) {{ form.submit(); return true; }}
          throw new Error('missing #indexForm');
        }})()
        """
        _eval(session, script, timeout=10)
        _wait_result_page_settled(session)
        html = _eval(session, "document.documentElement.outerHTML", timeout=20)
        if not isinstance(html, str):
            raise CdpError("failed to read result page html")
        return html
    finally:
        if session:
            session.close()
        if target:
            _close_target(browser.endpoint, target.get("id"))
        browser.close()


def search_epub_keyword(keyword: str) -> tuple[str, list[EpubSearchHit]]:
    html = fetch_epub_result_html(keyword)
    return html, parse_search_result_html(html)
