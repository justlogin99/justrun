#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
proxy_handler.py

多节点 sing-box 代理管理器。

PROXY_URL 支持：

1. 换行：
   vless://...
   hysteria2://...
   tuic://...

2. 逗号：
   vless://...,hysteria2://...,tuic://...

支持：

socks5://
http://
https://
vless://
vmess://
hy2://
hysteria2://
tuic://
anytls://

控制：

python proxy_handler.py start
python proxy_handler.py next
python proxy_handler.py current
python proxy_handler.py stop

本地 HTTP 代理：

127.0.0.1:8080
"""

import os
import sys
import json
import base64
import time
import subprocess
import signal
import re

import requests

from urllib.parse import (
    urlparse,
    parse_qs,
    unquote
)


LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8080

STATE_FILE = ".proxy_state.json"
CONFIG_FILE = "config.json"
PID_FILE = ".singbox.pid"

SINGBOX_BIN = os.environ.get(
    "SINGBOX_BIN",
    "./sing-box"
)


# ============================================================
# 节点列表
# ============================================================

def get_proxy_urls():

    raw = os.environ.get(
        "PROXY_URL",
        ""
    ).strip()

    if not raw:
        return []

    # 支持换行、逗号
    parts = re.split(
        r"[\r\n,]+",
        raw
    )

    result = []

    for item in parts:

        item = item.strip()

        if item:
            result.append(item)

    return result


# ============================================================
# state
# ============================================================

def load_state():

    if not os.path.exists(STATE_FILE):

        return {
            "index": -1
        }

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return {
            "index": -1
        }


def save_state(index):

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            {
                "index": index
            },
            f
        )


# ============================================================
# sing-box PID
# ============================================================

def read_pid():

    if not os.path.exists(PID_FILE):
        return None

    try:

        with open(
            PID_FILE,
            "r"
        ) as f:

            return int(
                f.read().strip()
            )

    except Exception:

        return None


def stop_singbox():

    pid = read_pid()

    if pid:

        try:

            os.kill(
                pid,
                signal.SIGTERM
            )

        except Exception:
            pass

        for _ in range(20):

            time.sleep(0.2)

            try:
                os.kill(pid, 0)
            except OSError:
                break
            except Exception:
                break

        try:

            os.kill(
                pid,
                signal.SIGKILL
            )

        except Exception:
            pass

    try:

        os.remove(PID_FILE)

    except Exception:
        pass

    # 防止旧进程残留
    subprocess.run(
        ["pkill", "-f", "sing-box.*config.json"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


# ============================================================
# Protocol Parsers
# ============================================================

def parse_socks5(parsed):

    outbound = {
        "type": "socks",
        "tag": "proxy",
        "server": parsed.hostname,
        "server_port": parsed.port or 1080,
        "version": "5"
    }

    if parsed.username:
        outbound["username"] = unquote(
            parsed.username
        )

    if parsed.password:
        outbound["password"] = unquote(
            parsed.password
        )

    return outbound


def parse_http(parsed):

    outbound = {
        "type": "http",
        "tag": "proxy",
        "server": parsed.hostname,
        "server_port": parsed.port or 8080
    }

    if parsed.username:
        outbound["username"] = unquote(
            parsed.username
        )

    if parsed.password:
        outbound["password"] = unquote(
            parsed.password
        )

    if parsed.scheme == "https":

        outbound["tls"] = {
            "enabled": True
        }

    return outbound


def parse_vless(parsed, params):

    outbound = {
        "type": "vless",
        "tag": "proxy",
        "server": parsed.hostname,
        "server_port": parsed.port or 443,
        "uuid": unquote(
            parsed.username or ""
        )
    }

    flow = params.get(
        "flow",
        [""]
    )[0]

    if flow:
        outbound["flow"] = flow

    security = params.get(
        "security",
        [""]
    )[0]

    if security in (
        "tls",
        "reality"
    ):

        tls = {
            "enabled": True
        }

        sni = params.get(
            "sni",
            [""]
        )[0]

        if sni:
            tls["server_name"] = sni

        fp = params.get(
            "fp",
            [""]
        )[0]

        if fp:

            tls["utls"] = {
                "enabled": True,
                "fingerprint": fp
            }

        alpn = params.get(
            "alpn",
            [""]
        )[0]

        if alpn:
            tls["alpn"] = alpn.split(",")

        insecure = params.get(
            "insecure",
            params.get(
                "allowInsecure",
                ["0"]
            )
        )[0]

        if insecure == "1":
            tls["insecure"] = True

        if security == "reality":

            reality = {
                "enabled": True
            }

            pbk = params.get(
                "pbk",
                [""]
            )[0]

            if pbk:
                reality["public_key"] = pbk

            sid = params.get(
                "sid",
                [""]
            )[0]

            if sid:
                reality["short_id"] = sid

            tls["reality"] = reality

        outbound["tls"] = tls

    net_type = params.get(
        "type",
        [""]
    )[0]

    if net_type == "ws":

        transport = {
            "type": "ws"
        }

        path = params.get(
            "path",
            [""]
        )[0]

        if path:
            transport["path"] = unquote(path)

        host = params.get(
            "host",
            [""]
        )[0]

        if host:
            transport["headers"] = {
                "Host": host
            }

        outbound["transport"] = transport

    elif net_type == "grpc":

        transport = {
            "type": "grpc"
        }

        sn = params.get(
            "serviceName",
            [""]
        )[0]

        if sn:
            transport["service_name"] = sn

        outbound["transport"] = transport

    elif net_type in (
        "http",
        "h2"
    ):

        transport = {
            "type": "http"
        }

        path = params.get(
            "path",
            [""]
        )[0]

        if path:
            transport["path"] = unquote(path)

        host = params.get(
            "host",
            [""]
        )[0]

        if host:
            transport["host"] = [host]

        outbound["transport"] = transport

    return outbound


def parse_vmess(url_str):

    encoded = url_str[
        len("vmess://"):
    ]

    encoded = encoded.strip()

    # 兼容 URL 中可能出现的空格
    encoded = encoded.replace(
        " ",
        ""
    )

    pad = 4 - len(encoded) % 4

    if pad != 4:
        encoded += "=" * pad

    decoded = base64.b64decode(
        encoded
    ).decode("utf-8")

    cfg = json.loads(decoded)

    outbound = {
        "type": "vmess",
        "tag": "proxy",
        "server": cfg.get("add", ""),
        "server_port": int(
            cfg.get("port", 443)
        ),
        "uuid": cfg.get("id", ""),
        "security": cfg.get(
            "scy",
            "auto"
        ),
        "alter_id": int(
            cfg.get("aid", 0)
        )
    }

    if cfg.get("tls") == "tls":

        tls = {
            "enabled": True
        }

        sni = cfg.get(
            "sni",
            ""
        )

        if sni:
            tls["server_name"] = sni

        elif cfg.get("host"):
            tls["server_name"] = cfg["host"]

        alpn = cfg.get(
            "alpn",
            ""
        )

        if alpn:
            tls["alpn"] = alpn.split(",")

        outbound["tls"] = tls

    net = cfg.get(
        "net",
        "tcp"
    )

    if net == "ws":

        transport = {
            "type": "ws"
        }

        if cfg.get("path"):
            transport["path"] = cfg["path"]

        if cfg.get("host"):
            transport["headers"] = {
                "Host": cfg["host"]
            }

        outbound["transport"] = transport

    elif net == "grpc":

        transport = {
            "type": "grpc"
        }

        if cfg.get("path"):
            transport["service_name"] = cfg["path"]

        outbound["transport"] = transport

    elif net in (
        "h2",
        "http"
    ):

        transport = {
            "type": "http"
        }

        if cfg.get("path"):
            transport["path"] = cfg["path"]

        if cfg.get("host"):
            transport["host"] = [cfg["host"]]

        outbound["transport"] = transport

    return outbound


def parse_hysteria2(parsed, params):

    outbound = {
        "type": "hysteria2",
        "tag": "proxy",
        "server": parsed.hostname,
        "server_port": parsed.port or 443,
        "password": unquote(
            parsed.username or ""
        )
    }

    tls = {
        "enabled": True
    }

    sni = params.get(
        "sni",
        [""]
    )[0]

    if sni:
        tls["server_name"] = sni

    insecure = params.get(
        "insecure",
        params.get(
            "allowInsecure",
            ["0"]
        )
    )[0]

    if insecure == "1":
        tls["insecure"] = True

    alpn = params.get(
        "alpn",
        [""]
    )[0]

    if alpn:
        tls["alpn"] = alpn.split(",")

    outbound["tls"] = tls

    obfs = params.get(
        "obfs",
        [""]
    )[0]

    if obfs:

        obfs_pwd = params.get(
            "obfs-password",
            [""]
        )[0]

        outbound["obfs"] = {
            "type": obfs,
            "password": obfs_pwd
        }

    return outbound


def parse_anytls(parsed, params):

    outbound = {
        "type": "anytls",
        "tag": "proxy",
        "server": parsed.hostname,
        "server_port": parsed.port or 443,
        "password": unquote(
            parsed.username or ""
        )
    }

    tls = {
        "enabled": True
    }

    sni = params.get(
        "sni",
        [""]
    )[0]

    if sni:
        tls["server_name"] = sni

    insecure = params.get(
        "insecure",
        params.get(
            "allowInsecure",
            ["0"]
        )
    )[0]

    if insecure == "1":
        tls["insecure"] = True

    alpn = params.get(
        "alpn",
        [""]
    )[0]

    if alpn:
        tls["alpn"] = alpn.split(",")

    outbound["tls"] = tls

    return outbound


def parse_tuic(parsed, params):

    outbound = {
        "type": "tuic",
        "tag": "proxy",
        "server": parsed.hostname,
        "server_port": parsed.port or 443,
        "uuid": "",
        "password": "",
        "congestion_control": params.get(
            "congestion_control",
            ["bbr"]
        )[0]
    }

    user_part = unquote(
        parsed.username or ""
    )

    pass_part = unquote(
        parsed.password or ""
    )

    if ":" in user_part and not pass_part:

        outbound["uuid"], outbound["password"] = \
            user_part.split(":", 1)

    else:

        outbound["uuid"] = user_part
        outbound["password"] = pass_part

    tls = {
        "enabled": True
    }

    sni = params.get(
        "sni",
        [""]
    )[0]

    if sni:
        tls["server_name"] = sni

    insecure = params.get(
        "insecure",
        params.get(
            "allowInsecure",
            ["0"]
        )
    )[0]

    if insecure == "1":
        tls["insecure"] = True

    alpn = params.get(
        "alpn",
        [""]
    )[0]

    if alpn:
        tls["alpn"] = alpn.split(",")

    outbound["tls"] = tls

    return outbound


# ============================================================
# 解析一个节点
# ============================================================

def parse_proxy(url_str):

    scheme = url_str.split(
        "://",
        1
    )[0].lower()

    if scheme == "vmess":

        return parse_vmess(url_str)

    parsed = urlparse(url_str)

    params = parse_qs(
        parsed.query
    )

    if scheme == "socks5":

        return parse_socks5(parsed)

    if scheme in (
        "http",
        "https"
    ):

        return parse_http(parsed)

    if scheme == "vless":

        return parse_vless(
            parsed,
            params
        )

    if scheme in (
        "hy2",
        "hysteria2"
    ):

        return parse_hysteria2(
            parsed,
            params
        )

    if scheme == "tuic":

        return parse_tuic(
            parsed,
            params
        )

    if scheme == "anytls":

        return parse_anytls(
            parsed,
            params
        )

    raise ValueError(
        f"Unsupported protocol: {scheme}"
    )


# ============================================================
# 生成 config
# ============================================================

def generate_config(outbound):

    config = {
        "log": {
            "level": "info",
            "timestamp": True
        },

        "inbounds": [
            {
                "type": "http",
                "tag": "http-in",
                "listen": LISTEN_HOST,
                "listen_port": LISTEN_PORT
            }
        ],

        "outbounds": [
            outbound,
            {
                "type": "direct",
                "tag": "direct"
            }
        ]
    }

    with open(
        CONFIG_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            config,
            f,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# 测试当前代理
# ============================================================

def test_proxy():

    proxies = {
        "http": f"http://{LISTEN_HOST}:{LISTEN_PORT}",
        "https": f"http://{LISTEN_HOST}:{LISTEN_PORT}"
    }

    try:

        r = requests.get(
            "https://api.ipify.org",
            proxies=proxies,
            timeout=12
        )

        if r.status_code == 200 and r.text.strip():

            print(
                f"✅ 代理测试成功，出口 IP: "
                f"{r.text.strip()}"
            )

            return True

    except Exception as e:

        print(
            f"代理测试失败: {type(e).__name__}"
        )

    return False


# ============================================================
# 启动 sing-box
# ============================================================

def start_singbox():

    stop_singbox()

    if not os.path.exists(SINGBOX_BIN):

        print(
            f"❌ 找不到 sing-box: {SINGBOX_BIN}"
        )

        return False

    log_file = open(
        "singbox.log",
        "a",
        encoding="utf-8"
    )

    process = subprocess.Popen(
        [
            SINGBOX_BIN,
            "run",
            "-c",
            CONFIG_FILE
        ],
        stdout=log_file,
        stderr=log_file,
        start_new_session=True
    )

    with open(
        PID_FILE,
        "w"
    ) as f:

        f.write(
            str(process.pid)
        )

    # 等 sing-box 初始化
    for _ in range(20):

        time.sleep(0.5)

        if test_proxy():

            return True

        if process.poll() is not None:

            print(
                "❌ sing-box 已退出"
            )

            break

    stop_singbox()

    return False


# ============================================================
# 使用指定节点
# ============================================================

def use_node(index):

    nodes = get_proxy_urls()

    if not nodes:

        print(
            "❌ PROXY_URL 没有任何节点"
        )

        return False

    if index < 0 or index >= len(nodes):

        return False

    url = nodes[index]

    print(
        "\n" + "=" * 60
    )

    print(
        f"尝试节点 {index + 1}/{len(nodes)}"
    )

    # 不打印完整节点，避免密码/UUID泄露
    scheme = url.split(
        "://",
        1
    )[0].lower()

    print(
        f"协议: {scheme}"
    )

    try:

        outbound = parse_proxy(url)

    except Exception as e:

        print(
            f"❌ 节点解析失败: {type(e).__name__}"
        )

        return False

    generate_config(
        outbound
    )

    if start_singbox():

        save_state(index)

        print(
            f"✅ 当前节点: {index + 1}"
        )

        return True

    print(
        f"❌ 节点 {index + 1} 无法正常出网"
    )

    return False


# ============================================================
# start
#
# 从第一个节点开始。
# 不通自动跳下一个。
# ============================================================

def command_start():

    nodes = get_proxy_urls()

    if not nodes:

        print(
            "❌ PROXY_URL 为空"
        )

        return 1

    print(
        f"检测到 {len(nodes)} 个代理节点"
    )

    stop_singbox()

    for index in range(
        len(nodes)
    ):

        if use_node(index):

            return 0

    print(
        "\n❌ 所有代理节点均无法连接"
    )

    return 2


# ============================================================
# next
#
# 从当前节点下一个开始。
# 自动跳过不通节点。
# 不循环回已经尝试过的节点。
# ============================================================

def command_next():

    nodes = get_proxy_urls()

    if not nodes:

        print(
            "❌ 没有代理节点"
        )

        return 1

    state = load_state()

    current = int(
        state.get(
            "index",
            -1
        )
    )

    start = current + 1

    print(
        f"当前节点: {current + 1}"
    )

    print(
        f"从节点 {start + 1} 开始寻找下一个可用节点"
    )

    stop_singbox()

    for index in range(
        start,
        len(nodes)
    ):

        if use_node(index):

            return 0

    print(
        "\n❌ 没有剩余可用节点"
    )

    return 2


# ============================================================
# current
# ============================================================

def command_current():

    nodes = get_proxy_urls()

    state = load_state()

    index = int(
        state.get(
            "index",
            -1
        )
    )

    if (
        index < 0
        or index >= len(nodes)
    ):

        print(
            "当前没有有效节点"
        )

        return 1

    print(
        f"当前节点: {index + 1}/{len(nodes)}"
    )

    return 0


# ============================================================
# stop
# ============================================================

def command_stop():

    stop_singbox()

    print(
        "sing-box 已停止"
    )

    return 0


# ============================================================
# main
# ============================================================

def main():

    command = (
        sys.argv[1].lower()
        if len(sys.argv) > 1
        else "start"
    )

    if command == "start":
        return command_start()

    if command == "next":
        return command_next()

    if command == "current":
        return command_current()

    if command == "stop":
        return command_stop()

    print(
        "用法:"
    )

    print(
        "  python proxy_handler.py start"
    )

    print(
        "  python proxy_handler.py next"
    )

    print(
        "  python proxy_handler.py current"
    )

    print(
        "  python proxy_handler.py stop"
    )

    return 1


if __name__ == "__main__":

    sys.exit(
        main()
    )
