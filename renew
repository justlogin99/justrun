#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import subprocess
import requests
from seleniumbase import SB


# ============================================================
# 基础配置
# ============================================================

LOGIN_URL = "https://justrunmy.app/id/Account/Login"
DOMAIN = "justrunmy.app"

EMAIL = os.environ.get("ACC", "").strip()
PASSWORD = os.environ.get("ACC_PWD", "")
COOKIE_DATA = os.environ.get("COOKIE", "").strip()

ACC_INDEX = os.environ.get("ACC_INDEX", "1").strip()
APP_ID = os.environ.get("APP_ID", "").strip()

TG_BOT_TOKEN = os.environ.get("TG_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_ID", "").strip()

GH_PAT = os.environ.get("GH_PAT", "").strip()
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "").strip()

PROXY_URL = os.environ.get("PROXY_URL", "").strip()

PROXY_HANDLER = os.environ.get(
    "PROXY_HANDLER",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "proxy_handler.py")
)

DYNAMIC_APP_NAME = os.environ.get("APP_NAME", "heisirenqi")

if not EMAIL or not PASSWORD:
    print("❌ 致命错误：未找到 ACC 或 ACC_PWD")
    sys.exit(1)

if not APP_ID:
    print("❌ 致命错误：未找到 APP_ID")
    sys.exit(1)

APP_URL = f"https://{DOMAIN}/panel/application/{APP_ID}/"


# ============================================================
# Telegram
# ============================================================

def send_tg_message(status_icon, status_text, time_left):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("未配置 Telegram，跳过通知。")
        return

    local_time = time.gmtime(time.time() + 8 * 3600)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    text = (
        f"【JRM】{DYNAMIC_APP_NAME}\n"
        f"账号: {EMAIL}\n"
        f"{status_icon} {status_text}\n"
        f"剩余: {time_left}\n"
        f"时间: {current_time_str}"
    )

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text
    }

    try:
        r = requests.post(url, json=payload, timeout=10)

        if r.status_code == 200:
            print("Telegram 通知发送成功。")
        else:
            print(f"Telegram 通知失败: {r.text}")

    except Exception as e:
        print(f"Telegram 通知异常: {e}")


# ============================================================
# GitHub Secret Cookie 同步
# ============================================================

def update_github_secret(new_cookie_json: str):
    if not GH_PAT or not GITHUB_REPO:
        print("未配置 GH_PAT，跳过 Cookie Secret 更新。")
        return

    secret_name = f"COOKIE_{ACC_INDEX}"

    print(f"🔄 正在更新 GitHub Secret: {secret_name}")

    try:
        env_vars = dict(os.environ)
        env_vars["GH_TOKEN"] = GH_PAT

        cmd = [
            "gh",
            "secret",
            "set",
            secret_name,
            "--repo",
            GITHUB_REPO,
            "--body",
            new_cookie_json,
        ]

        result = subprocess.run(
            cmd,
            env=env_vars,
            capture_output=True,
            text=True,
            timeout=20,
        )

        if result.returncode == 0:
            print(f"✅ Cookie 已更新到 Secret: {secret_name}")
        else:
            print(f"⚠️ Cookie Secret 更新失败: {result.stderr.strip()}")

    except Exception as e:
        print(f"⚠️ gh secret set 异常: {e}")


def dump_and_sync_cookies(sb):
    try:
        try:
            cookies = sb.get_cookies()
        except Exception:
            cookies = sb.driver.get_cookies()

        if not cookies:
            print("⚠️ 没有获取到 Cookie")
            return

        valid_keys = [
            ".AspNetCore.Identity.Application",
            "idsrv.session",
            "_jrnm_clct",
            ".AspNetCore.Antiforgery.NCGjD_ZE8w",
        ]

        filtered = [
            c for c in cookies
            if c.get("name") in valid_keys
            or "AspNetCore" in c.get("name", "")
        ]

        cookie_payload = filtered if filtered else cookies

        cookie_json = json.dumps(
            cookie_payload,
            ensure_ascii=False
        )

        update_github_secret(cookie_json)

    except Exception as e:
        print(f"提取 Cookie 异常: {e}")


# ============================================================
# Turnstile JS
# ============================================================

_EXPAND_JS = """
(function() {
    var ts = document.querySelector('input[name="cf-turnstile-response"]');
    if (!ts) return 'no-turnstile';

    var el = ts;

    for (var i = 0; i < 20; i++) {
        el = el.parentElement;

        if (!el) break;

        var s = window.getComputedStyle(el);

        if (
            s.overflow === 'hidden' ||
            s.overflowX === 'hidden' ||
            s.overflowY === 'hidden'
        ) {
            el.style.overflow = 'visible';
        }

        el.style.minWidth = 'max-content';
    }

    document.querySelectorAll('iframe').forEach(function(f) {
        if (
            f.src &&
            f.src.includes('challenges.cloudflare.com')
        ) {
            f.style.width = '300px';
            f.style.height = '65px';
            f.style.minWidth = '300px';
            f.style.visibility = 'visible';
            f.style.opacity = '1';
        }
    });

    return 'done';
})()
"""


_EXISTS_JS = """
(function() {
    return document.querySelector(
        'input[name="cf-turnstile-response"]'
    ) !== null;
})()
"""


_SOLVED_JS = """
(function() {
    var i = document.querySelector(
        'input[name="cf-turnstile-response"]'
    );

    return !!(
        i &&
        i.value &&
        i.value.length > 20
    );
})()
"""


_COORDS_JS = """
(function() {

    var iframes = document.querySelectorAll('iframe');

    for (var i = 0; i < iframes.length; i++) {

        var src = iframes[i].src || '';

        if (
            src.includes('cloudflare') ||
            src.includes('turnstile') ||
            src.includes('challenges')
        ) {

            var r = iframes[i].getBoundingClientRect();

            if (r.width > 0 && r.height > 0) {

                return {
                    cx: Math.round(r.x + 30),
                    cy: Math.round(r.y + r.height / 2)
                };

            }
        }
    }

    var inp = document.querySelector(
        'input[name="cf-turnstile-response"]'
    );

    if (inp) {

        var p = inp.parentElement;

        for (var j = 0; j < 5; j++) {

            if (!p) break;

            var r = p.getBoundingClientRect();

            if (
                r.width > 100 &&
                r.height > 30
            ) {

                return {
                    cx: Math.round(r.x + 30),
                    cy: Math.round(r.y + r.height / 2)
                };
            }

            p = p.parentElement;
        }
    }

    return null;

})()
"""


_WININFO_JS = """
(function() {

    return {
        sx: window.screenX || 0,
        sy: window.screenY || 0,
        oh: window.outerHeight,
        ih: window.innerHeight
    };

})()
"""


# ============================================================
# JS 填写输入框
# ============================================================

def js_fill_input(sb, selector, text):
    safe_text = (
        text
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )

    sb.execute_script(
        f"""
        (function() {{

            var el = document.querySelector('{selector}');

            if (!el) return;

            var setter =
                Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype,
                    "value"
                ).set;

            if (setter) {{
                setter.call(el, "{safe_text}");
            }} else {{
                el.value = "{safe_text}";
            }}

            el.dispatchEvent(
                new Event('input', {{ bubbles: true }})
            );

            el.dispatchEvent(
                new Event('change', {{ bubbles: true }})
            );

        }})()
        """
    )


# ============================================================
# xdotool
# ============================================================

def _activate_window():

    for cls in [
        "chrome",
        "chromium",
        "Chromium",
        "Chrome",
        "google-chrome"
    ]:

        try:

            r = subprocess.run(
                [
                    "xdotool",
                    "search",
                    "--onlyvisible",
                    "--class",
                    cls
                ],
                capture_output=True,
                text=True,
                timeout=3
            )

            wids = [
                w
                for w in r.stdout.strip().split("\n")
                if w.strip()
            ]

            if wids:

                subprocess.run(
                    [
                        "xdotool",
                        "windowactivate",
                        "--sync",
                        wids[0]
                    ],
                    timeout=3,
                    stderr=subprocess.DEVNULL
                )

                time.sleep(0.2)
                return

        except Exception:
            pass


def _xdotool_click(x, y):

    _activate_window()

    try:

        subprocess.run(
            [
                "xdotool",
                "mousemove",
                "--sync",
                str(x),
                str(y)
            ],
            timeout=3,
            stderr=subprocess.DEVNULL
        )

        time.sleep(0.15)

        subprocess.run(
            [
                "xdotool",
                "click",
                "1"
            ],
            timeout=2,
            stderr=subprocess.DEVNULL
        )

    except Exception:
        pass


def _click_turnstile(sb):

    try:
        coords = sb.execute_script(_COORDS_JS)
    except Exception as e:
        print(f"获取 Turnstile 坐标失败: {e}")
        return False

    if not coords:
        print("无法定位 Turnstile 坐标")
        return False

    try:
        wi = sb.execute_script(_WININFO_JS)
    except Exception:
        wi = {
            "sx": 0,
            "sy": 0,
            "oh": 800,
            "ih": 768
        }

    bar = wi["oh"] - wi["ih"]

    ax = coords["cx"] + wi["sx"]
    ay = coords["cy"] + wi["sy"] + bar

    print(
        f"物理点击 Turnstile: ({ax}, {ay})"
    )

    _xdotool_click(ax, ay)

    return True


# ============================================================
# Turnstile
#
# 单次调用内部最多 6 轮
# 如果整个函数失败，上层负责刷新页面
# ============================================================

def handle_turnstile(sb):

    print("处理 Cloudflare Turnstile...")

    time.sleep(3)

    try:
        if sb.execute_script(_SOLVED_JS):
            print("✅ Turnstile 已静默通过")
            return True
    except Exception:
        pass

    for _ in range(3):

        try:
            sb.execute_script(_EXPAND_JS)
        except Exception:
            pass

        time.sleep(0.5)

    for attempt in range(6):

        try:

            if sb.execute_script(_SOLVED_JS):

                print(
                    f"✅ Turnstile 通过 "
                    f"(第 {attempt + 1} 轮)"
                )

                return True

        except Exception:
            pass

        try:
            sb.execute_script(_EXPAND_JS)
        except Exception:
            pass

        time.sleep(0.3)

        _click_turnstile(sb)

        for _ in range(8):

            time.sleep(0.5)

            try:

                if sb.execute_script(_SOLVED_JS):

                    print(
                        f"✅ Turnstile 通过 "
                        f"(第 {attempt + 1} 轮)"
                    )

                    return True

            except Exception:
                pass

        print(
            f"Turnstile 第 {attempt + 1} 轮未通过"
        )

    print("❌ Turnstile 6 轮均失败")

    return False


# ============================================================
# Cookie 登录
# ============================================================

def try_cookie_login(sb):

    if not COOKIE_DATA:

        print(
            "没有 COOKIE，直接使用账号密码登录。"
        )

        return False

    print("🔑 尝试历史 Cookie 登录...")

    try:

        sb.open(
            "https://justrunmy.app/robots.txt"
        )

        time.sleep(2)

        raw_cookie = COOKIE_DATA.strip()

        if raw_cookie.startswith("["):

            cookies = json.loads(raw_cookie)

            for c in cookies:

                cookie_dict = {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get(
                        "domain",
                        ".justrunmy.app"
                    ),
                    "path": c.get(
                        "path",
                        "/"
                    )
                }

                try:
                    sb.driver.add_cookie(
                        cookie_dict
                    )
                except Exception:
                    pass

        else:

            for item in raw_cookie.split(";"):

                if "=" not in item:
                    continue

                k, v = item.strip().split(
                    "=",
                    1
                )

                try:

                    sb.driver.add_cookie(
                        {
                            "name": k,
                            "value": v,
                            "domain": ".justrunmy.app",
                            "path": "/"
                        }
                    )

                except Exception:
                    pass

        sb.open(APP_URL)

        time.sleep(6)

        curr_url = sb.get_current_url().lower()

        if (
            "/account/login" not in curr_url
            and not sb.is_element_visible(
                'input[name="Password"]'
            )
        ):

            print(
                "🎉 Cookie 登录成功"
            )

            return True

        print(
            "⚠️ Cookie 已失效"
        )

        return False

    except Exception as e:

        print(
            f"Cookie 登录异常: {e}"
        )

        return False


# ============================================================
# 账号密码登录
#
# retry_after_refresh=True：
# 第一次 CF 失败后刷新页面，再尝试一次
# ============================================================

def form_login(sb, retry_after_refresh=True):

    print(
        f"打开登录页面: {LOGIN_URL}"
    )

    sb.uc_open_with_reconnect(
        LOGIN_URL,
        reconnect_time=5
    )

    time.sleep(4)

    try:

        sb.wait_for_element(
            'input[name="Email"]',
            timeout=15
        )

    except Exception:

        print(
            "❌ 登录表单没有加载出来"
        )

        sb.save_screenshot(
            "login_load_fail.png"
        )

        return False

    # Cookie 弹窗
    try:

        for btn in sb.find_elements(
            "button"
        ):

            if "Accept" in (btn.text or ""):

                btn.click()

                time.sleep(0.5)

                break

    except Exception:
        pass

    def fill_and_submit():

        print("填写邮箱...")

        js_fill_input(
            sb,
            'input[name="Email"]',
            EMAIL
        )

        time.sleep(0.3)

        print("填写密码...")

        js_fill_input(
            sb,
            'input[name="Password"]',
            PASSWORD
        )

        time.sleep(1)

        try:

            if sb.execute_script(_EXISTS_JS):

                print(
                    "检测到 Turnstile"
                )

                if not handle_turnstile(sb):

                    return False

            else:

                print(
                    "未检测到 Turnstile"
                )

        except Exception as e:

            print(
                f"Turnstile 检测异常: {e}"
            )

            return False

        print(
            "点击登录按钮..."
        )

        try:

            if sb.is_element_visible(
                'button[type="submit"]'
            ):

                sb.click(
                    'button[type="submit"]'
                )

            else:

                sb.press_keys(
                    'input[name="Password"]',
                    "\n"
                )

        except Exception:

            try:
                sb.press_keys(
                    'input[name="Password"]',
                    "\n"
                )
            except Exception:
                pass

        print(
            "等待登录..."
        )

        for _ in range(15):

            time.sleep(1)

            try:

                curr_url = (
                    sb.get_current_url()
                    .lower()
                )

                if "/panel" in curr_url:

                    return True

            except Exception:
                pass

        return False

    # 第一次
    if fill_and_submit():

        print(
            "✅ 登录成功"
        )

        return True

    # ========================================================
    # CF 第一次失败：
    # 刷新一次页面，然后重新完整执行登录/CF
    # ========================================================

    if retry_after_refresh:

        print(
            "⚠️ 第一次登录/CF失败"
        )

        print(
            "🔄 刷新登录页面后重新尝试..."
        )

        try:

            sb.refresh()

            time.sleep(5)

            sb.wait_for_element(
                'input[name="Email"]',
                timeout=15
            )

            if fill_and_submit():

                print(
                    "✅ 刷新页面后登录成功"
                )

                return True

        except Exception as e:

            print(
                f"刷新后重试异常: {e}"
            )

    print(
        "❌ 当前节点登录/CF最终失败"
    )

    try:
        sb.save_screenshot(
            "login_failed.png"
        )
    except Exception:
        pass

    return False


# ============================================================
# 代理节点切换
# ============================================================

def proxy_command(command):

    if not PROXY_URL:

        print(
            "⚠️ PROXY_URL 为空"
        )

        return False

    cmd = [
        sys.executable,
        PROXY_HANDLER,
        command
    ]

    print(
        f"代理控制: {command}"
    )

    try:

        result = subprocess.run(
            cmd,
            env=os.environ.copy(),
            timeout=90
        )

        if result.returncode == 0:
            return True

        print(
            f"代理控制失败，返回码: "
            f"{result.returncode}"
        )

        return False

    except Exception as e:

        print(
            f"代理控制异常: {e}"
        )

        return False


# ============================================================
# 获取当前出口 IP
# ============================================================

def show_current_ip():

    try:

        proxies = {
            "http": "http://127.0.0.1:8080",
            "https": "http://127.0.0.1:8080"
        }

        r = requests.get(
            "https://api.ipify.org",
            proxies=proxies,
            timeout=10
        )

        print(
            f"当前代理出口 IP: {r.text.strip()}"
        )

        return r.text.strip()

    except Exception as e:

        print(
            f"无法获取代理出口 IP: {e}"
        )

        return ""


# ============================================================
# Reset Timer
# ============================================================

def click_just_reset_button(sb):

    print(
        "定位 Just Reset 确认按钮..."
    )

    selectors = [
        'button:contains("Just Reset")',
        '//button[contains(., "Just Reset")]',
        'div.fixed button:contains("Just Reset")',
        'button.border-slate-200'
    ]

    for sel in selectors:

        try:

            if sb.is_element_visible(sel):

                sb.click(sel)

                print(
                    f"✅ 点击 Just Reset: {sel}"
                )

                return True

        except Exception:
            continue

    try:

        clicked = sb.execute_script(
            """
            var buttons =
                document.querySelectorAll('button');

            for (var btn of buttons) {

                if (
                    btn.textContent &&
                    btn.textContent.includes(
                        'Just Reset'
                    )
                ) {

                    btn.click();

                    return true;
                }
            }

            return false;
            """
        )

        if clicked:

            print(
                "✅ JS 点击 Just Reset 成功"
            )

            return True

    except Exception as e:

        print(
            f"JS 点击异常: {e}"
        )

    return False


def renew(sb):

    print("\n" + "=" * 50)
    print("开始自动续期")
    print(f"应用 ID: {APP_ID}")
    print(f"应用地址: {APP_URL}")
    print("=" * 50)

    print(
        "进入应用详情页..."
    )

    sb.open(APP_URL)

    time.sleep(6)

    selectors = [
        'button[aria-label="Reset timer"]',
        'button[title="Reset timer"]',
        'button:contains("Reset timer")',
        'section button'
    ]

    btn_found = False

    for sel in selectors:

        try:

            if sb.is_element_visible(sel):

                sb.click(sel)

                btn_found = True

                print(
                    f"✅ 点击 Reset timer: {sel}"
                )

                time.sleep(3)

                break

        except Exception:
            continue

    if not btn_found:

        try:

            sb.wait_for_element(
                'button[aria-label="Reset timer"]',
                timeout=10
            )

            sb.click(
                'button[aria-label="Reset timer"]'
            )

            btn_found = True

            time.sleep(3)

        except Exception as e:

            print(
                f"❌ 找不到 Reset timer: {e}"
            )

            sb.save_screenshot(
                "renew_reset_btn_not_found.png"
            )

            send_tg_message(
                "❌",
                "续期失败(找不到入口按钮)",
                "未知"
            )

            return False

    # 弹窗 CF
    try:

        if sb.execute_script(_EXISTS_JS):

            print(
                "检测到续期弹窗 Turnstile"
            )

            if not handle_turnstile(sb):

                print(
                    "❌ 续期弹窗 CF 验证失败"
                )

                sb.save_screenshot(
                    "renew_turnstile_fail.png"
                )

                send_tg_message(
                    "❌",
                    "续期失败(弹窗CF验证失败)",
                    "未知"
                )

                return False

        else:

            print(
                "续期弹窗没有 Turnstile"
            )

    except Exception:
        pass

    time.sleep(1)

    if not click_just_reset_button(sb):

        print(
            "❌ 无法点击 Just Reset"
        )

        sb.save_screenshot(
            "renew_just_reset_not_found.png"
        )

        send_tg_message(
            "❌",
            "续期失败(无法点击确认按钮)",
            "未知"
        )

        return False

    print(
        "提交续期请求..."
    )

    time.sleep(6)

    try:

        sb.refresh()

        time.sleep(5)

        dump_and_sync_cookies(sb)

        timer_text = "已提交重置"

        selectors = [
            'span.font-mono',
            'section div'
        ]

        for sel in selectors:

            try:

                if sb.is_element_visible(sel):

                    txt = sb.get_text(sel)

                    if (
                        "day" in txt
                        or "hour" in txt
                        or ":" in txt
                    ):

                        timer_text = txt

                        break

            except Exception:
                continue

        print(
            f"当前剩余时间: {timer_text}"
        )

        sb.save_screenshot(
            "renew_success.png"
        )

        send_tg_message(
            "✅",
            "续期完成",
            timer_text
        )

        return True

    except Exception as e:

        print(
            f"读取续期状态异常: {e}"
        )

        send_tg_message(
            "⚠️",
            "续期已执行(状态读取异常)",
            "未知"
        )

        return True


# ============================================================
# 单节点完整业务尝试
# ============================================================

def try_current_node():

    print("\n" + "=" * 60)
    print("开始尝试当前代理节点")
    print("=" * 60)

    try:

        ip = show_current_ip()

        if not ip:

            print(
                "❌ 当前代理没有正常出网"
            )

            return False

    except Exception:
        return False

    sb_kwargs = {
        "uc": True,
        "test": True,
        "headless": False,
        "proxy": "http://127.0.0.1:8080"
    }

    try:

        with SB(**sb_kwargs) as sb:

            print(
                "浏览器已启动"
            )

            # ------------------------------------------------
            # Cookie 登录
            # ------------------------------------------------

            if try_cookie_login(sb):

                print(
                    "✅ Cookie 登录成功"
                )

            else:

                # Cookie失效 → 账号密码
                if not form_login(
                    sb,
                    retry_after_refresh=True
                ):

                    print(
                        "❌ 当前节点最终无法登录"
                    )

                    return False

            # ------------------------------------------------
            # 登录成功 → 续期
            # ------------------------------------------------

            return renew(sb)

    except Exception as e:

        print(
            f"浏览器/业务异常: {e}"
        )

        return False


# ============================================================
# 主流程
# ============================================================

def main():

    print("=" * 60)
    print("JustRunMy 自动登录与续期")
    print("=" * 60)

    print(
        f"账号索引: {ACC_INDEX}"
    )

    print(
        f"应用 ID: {APP_ID}"
    )

    print(
        f"应用地址: {APP_URL}"
    )

    if not PROXY_URL:

        print(
            "❌ 当前版本要求配置 PROXY_URL"
        )

        send_tg_message(
            "❌",
            "续期失败(未配置代理)",
            "未知"
        )

        sys.exit(1)

    # ========================================================
    # 当前节点已经由 workflow / proxy_handler start 准备
    # ========================================================

    while True:

        success = try_current_node()

        if success:

            print(
                "\n🎉 当前节点完成续期！"
            )

            return

        # ====================================================
        # 当前节点业务失败
        # 浏览器已经因为 with SB 自动关闭
        # ====================================================

        print(
            "\n⚠️ 当前节点业务失败"
        )

        print(
            "🔄 请求代理程序切换到下一个节点..."
        )

        switched = proxy_command("next")

        if not switched:

            print(
                "\n❌ 所有代理节点均无法完成任务"
            )

            send_tg_message(
                "❌",
                "续期失败(所有代理节点均不可用或无法通过CF)",
                "未知"
            )

            sys.exit(1)

        print(
            "\n✅ 已切换到新的代理节点"
        )

        time.sleep(3)


if __name__ == "__main__":
    main()
