#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import subprocess
import requests
from seleniumbase import SB

LOGIN_URL = "https://justrunmy.app/id/Account/Login"
APP_URL   = "https://justrunmy.app/panel/application/56317"
DOMAIN    = "justrunmy.app"

# ============================================================
#  环境变量与全局变量
# ============================================================
EMAIL        = os.environ.get("ACC")
PASSWORD     = os.environ.get("ACC_PWD")
TG_BOT_TOKEN = os.environ.get("TG_TOKEN")
TG_CHAT_ID   = os.environ.get("TG_ID")
COOKIE_DATA  = os.environ.get("COOKIE")
ACC_INDEX    = os.environ.get("ACC_INDEX", "1")
GH_PAT       = os.environ.get("GH_PAT")
GITHUB_REPO  = os.environ.get("GITHUB_REPOSITORY")

if not EMAIL or not PASSWORD:
    print("致命错误：未找到 ACC 或 ACC_PWD 环境变量！")
    print("请检查 GitHub Repository Secrets 是否配置正确（EML_1, PWD_1...）。")
    sys.exit(1)

DYNAMIC_APP_NAME = "heisirenqi"

# ============================================================
#  Telegram 推送模块
# ============================================================
def send_tg_message(status_icon, status_text, time_left):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("未配置 TG_TOKEN 或 TG_ID，跳过 Telegram 推送。")
        return

    local_time = time.gmtime(time.time() + 8 * 3600)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    text = (
        f"{DYNAMIC_APP_NAME}\n"
        f"{status_icon} {status_text}\n"
        f"剩余: {time_left}\n"
        f"时间: {current_time_str}"
    )

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": text}
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("  Telegram 通知发送成功！")
        else:
            print(f"  Telegram 通知发送失败: {r.text}")
    except Exception as e:
        print(f"  Telegram 通知发送异常: {e}")

# ============================================================
#  GitHub Secrets 自动同步覆盖模块
# ============================================================
def update_github_secret(new_cookie_json: str):
    if not GH_PAT or not GITHUB_REPO:
        print("ℹ️ 未配置 GH_PAT 或不在 Actions 环境中，跳过自动更新 Secret。")
        return

    secret_name = f"COOKIE_{ACC_INDEX}"
    print(f"🔄 正在同步更新 GitHub Secret: {secret_name}...")
    try:
        env_vars = dict(os.environ, GH_TOKEN=GH_PAT)
        cmd = ["gh", "secret", "set", secret_name, "--repo", GITHUB_REPO, "--body", new_cookie_json]
        res = subprocess.run(cmd, env=env_vars, capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            print(f"✅ 成功将最新 Cookie 同步并覆盖到 Secrets: {secret_name}")
        else:
            print(f"⚠️ 更新 Secret 失败: {res.stderr.strip()}")
    except Exception as e:
        print(f"⚠️ 执行 gh secret set 出现异常: {e}")

def dump_and_sync_cookies(sb):
    try:
        cookies = sb.driver.get_cookies()
        if not cookies:
            return
        cookie_json = json.dumps(cookies)
        update_github_secret(cookie_json)
    except Exception as e:
        print(f"提取 Cookie 失败: {e}")

# ============================================================
#  页面注入脚本 (Turnstile 辅助)
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
        if (s.overflow === 'hidden' || s.overflowX === 'hidden' || s.overflowY === 'hidden')
            el.style.overflow = 'visible';
        el.style.minWidth = 'max-content';
    }
    document.querySelectorAll('iframe').forEach(function(f){
        if (f.src && f.src.includes('challenges.cloudflare.com')) {
            f.style.width = '300px'; f.style.height = '65px';
            f.style.minWidth = '300px';
            f.style.visibility = 'visible'; f.style.opacity = '1';
        }
    });
    return 'done';
})()
"""

_EXISTS_JS = """
(function(){
    return document.querySelector('input[name="cf-turnstile-response"]') !== null;
})()
"""

_SOLVED_JS = """
(function(){
    var i = document.querySelector('input[name="cf-turnstile-response"]');
    return !!(i && i.value && i.value.length > 20);
})()
"""

_COORDS_JS = """
(function(){
    var iframes = document.querySelectorAll('iframe');
    for (var i = 0; i < iframes.length; i++) {
        var src = iframes[i].src || '';
        if (src.includes('cloudflare') || src.includes('turnstile') || src.includes('challenges')) {
            var r = iframes[i].getBoundingClientRect();
            if (r.width > 0 && r.height > 0)
                return {cx: Math.round(r.x + 30), cy: Math.round(r.y + r.height / 2)};
        }
    }
    var inp = document.querySelector('input[name="cf-turnstile-response"]');
    if (inp) {
        var p = inp.parentElement;
        for (var j = 0; j < 5; j++) {
            if (!p) break;
            var r = p.getBoundingClientRect();
            if (r.width > 100 && r.height > 30)
                return {cx: Math.round(r.x + 30), cy: Math.round(r.y + r.height / 2)};
            p = p.parentElement;
        }
    }
    return null;
})()
"""

_WININFO_JS = """
(function(){
    return {
        sx: window.screenX || 0,
        sy: window.screenY || 0,
        oh: window.outerHeight,
        ih: window.innerHeight
    };
})()
"""

def js_fill_input(sb, selector: str, text: str):
    safe_text = text.replace('\\', '\\\\').replace('"', '\\"')
    sb.execute_script(f"""
    (function(){{
        var el = document.querySelector('{selector}');
        if (!el) return;
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        if (nativeInputValueSetter) {{
            nativeInputValueSetter.call(el, "{safe_text}");
        }} else {{
            el.value = "{safe_text}";
        }}
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }})()
    """)

def _activate_window():
    for cls in ["chrome", "chromium", "Chromium", "Chrome", "google-chrome"]:
        try:
            r = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", cls], capture_output=True, text=True, timeout=3)
            wids = [w for w in r.stdout.strip().split("\n") if w.strip()]
            if wids:
                subprocess.run(["xdotool", "windowactivate", "--sync", wids[0]], timeout=3, stderr=subprocess.DEVNULL)
                time.sleep(0.2)
                return
        except Exception:
            pass
    try:
        subprocess.run(["xdotool", "getactivewindow", "windowactivate"], timeout=3, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def _xdotool_click(x: int, y: int):
    _activate_window()
    try:
        subprocess.run(["xdotool", "mousemove", "--sync", str(x), str(y)], timeout=3, stderr=subprocess.DEVNULL)
        time.sleep(0.15)
        subprocess.run(["xdotool", "click", "1"], timeout=2, stderr=subprocess.DEVNULL)
    except Exception:
        os.system(f"xdotool mousemove {x} {y} click 1 2>/dev/null")

def _click_turnstile(sb):
    try:
        coords = sb.execute_script(_COORDS_JS)
    except Exception as e:
        print(f"  获取 Turnstile 坐标失败: {e}")
        return
    if not coords:
        print("  无法定位 Turnstile 坐标")
        return
    try:
        wi = sb.execute_script(_WININFO_JS)
    except Exception:
        wi = {"sx": 0, "sy": 0, "oh": 800, "ih": 768}
        
    bar = wi["oh"] - wi["ih"]
    ax  = coords["cx"] + wi["sx"]
    ay  = coords["cy"] + wi["sy"] + bar
    print(f"  物理级点击 Turnstile ({ax}, {ay})")
    _xdotool_click(ax, ay)

def handle_turnstile(sb) -> bool:
    print("处理 Cloudflare Turnstile 验证...")
    time.sleep(3)
    
    if sb.execute_script(_SOLVED_JS):
        print("  已静默通过")
        return True

    for _ in range(3):
        try: sb.execute_script(_EXPAND_JS)
        except Exception: pass
        time.sleep(0.5)

    for attempt in range(6):
        if sb.execute_script(_SOLVED_JS):
            print(f"  Turnstile 通过（第 {attempt + 1} 次尝试）")
            return True
        try: sb.execute_script(_EXPAND_JS)
        except Exception: pass
        time.sleep(0.3)
        
        _click_turnstile(sb)
        
        for _ in range(8):
            time.sleep(0.5)
            if sb.execute_script(_SOLVED_JS):
                print(f"  Turnstile 通过（第 {attempt + 1} 次尝试）")
                return True
        print(f"  第 {attempt + 1} 次未通过，重试...")

    print("  Turnstile 6 次均失败")
    return False

# ============================================================
#  登录控制模块 (优先 Cookie，回退账密)
# ============================================================
def try_cookie_login(sb) -> bool:
    if not COOKIE_DATA:
        print("未检测到 COOKIE Secret，直接使用账号密码登录。")
        return False

    print("🔑 检测到历史 Cookie，尝试通过 Cookie 快速登录...")
    try:
        sb.open("https://justrunmy.app/robots.txt")
        time.sleep(2)

        raw_cookie = COOKIE_DATA.strip()
        if raw_cookie.startswith("["):
            cookies = json.loads(raw_cookie)
            for c in cookies:
                cookie_dict = {
                    'name': c['name'],
                    'value': c['value'],
                    'domain': c.get('domain', '.justrunmy.app'),
                    'path': c.get('path', '/')
                }
                try: sb.driver.add_cookie(cookie_dict)
                except Exception: pass
        else:
            for item in raw_cookie.split(';'):
                if '=' in item:
                    k, v = item.strip().split('=', 1)
                    try:
                        sb.driver.add_cookie({'name': k, 'value': v, 'domain': '.justrunmy.app', 'path': '/'})
                    except Exception: pass

        print(f"Cookie 注入完成，验证登录态: {APP_URL}")
        sb.open(APP_URL)
        time.sleep(6)

        curr_url = sb.get_current_url().lower()
        if "/account/login" not in curr_url and not sb.is_element_visible('input[name="Password"]'):
            print("🎉 Cookie 登录成功！已直达应用管理页。")
            return True
        else:
            print("⚠️ Cookie 已失效，降级为账号密码登录。")
            return False
    except Exception as e:
        print(f"⚠️ Cookie 登录流程异常: {e}，将尝试账号密码登录。")
        return False


def renew(sb) -> bool:
    global DYNAMIC_APP_NAME
    print("\n" + "=" * 50)
    print("   开始自动续期流程")
    print("=" * 50)
    
    if "panel/application/56317" not in sb.get_current_url().lower():
        print(f"进入应用详情页: {APP_URL}")
        sb.open(APP_URL)
        time.sleep(6)

    # 尝试多种选择器定位 Reset timer 按钮
    btn_selectors = [
        'button[aria-label="Reset timer"]',
        'button[title="Reset timer"]',
        'button:contains("Reset timer")',
        'section button'
    ]
    
    btn_found = False
    print("定位并点击 Reset timer 按钮...")
    for sel in btn_selectors:
        try:
            if sb.is_element_visible(sel):
                sb.click(sel)
                btn_found = True
                print(f"成功点击按钮 (选择器: {sel})")
                time.sleep(3)
                break
        except Exception:
            continue

    if not btn_found:
        print("找不到 Reset timer 按钮，尝试等待加载...")
        try:
            sb.wait_for_element('button[aria-label="Reset timer"]', timeout=10)
            sb.click('button[aria-label="Reset timer"]')
            btn_found = True
            time.sleep(3)
        except Exception as e:
            print(f"无法定位到 Reset timer 按钮: {e}")
            sb.save_screenshot("renew_reset_btn_not_found.png")
            send_tg_message("❌", "续期失败(找不到按钮)", "未知")
            return False

    # 检查弹窗人机验证
    if sb.execute_script(_EXISTS_JS):
        print("检查续期弹窗内是否需要 CF 验证...")
        if not handle_turnstile(sb):
            print("弹窗内的 Turnstile 验证失败")
            sb.save_screenshot("renew_turnstile_fail.png")
            send_tg_message("❌", "续期失败(弹窗人机验证未过)", "未知")
            return False

    # 确认提交
    print("点击 Just Reset 确认续期...")
    try:
        confirm_selector = 'button:contains("Just Reset"), button:contains("Reset")'
        sb.wait_for_element(confirm_selector, timeout=10)
        sb.click(confirm_selector)
        print("提交续期请求，等待服务器处理...")
        time.sleep(5)
    except Exception as e:
        print(f"未出现确认弹窗或已直接生效: {e}")

    # 读取倒计时并完成回写
    try:
        sb.refresh()
        time.sleep(4)
        timer_text = "已提交重置"
        for sel in ['span.font-mono', 'section div']:
            if sb.is_element_visible(sel):
                txt = sb.get_text(sel)
                if "day" in txt or "hour" in txt or ":" in txt:
                    timer_text = txt
                    break

        print(f"当前应用剩余时间: {timer_text}")
        sb.save_screenshot("renew_success.png")
        send_tg_message("✅", "续期完成", timer_text)
        
        # 流程全部成功后再更新 Secrets
        dump_and_sync_cookies(sb)
        return True
    except Exception as e:
        print(f"读取状态异常: {e}")
        sb.save_screenshot("renew_timer_read_fail.png")
        send_tg_message("⚠️", "续期已执行(状态读取异常)", "未知")
        return True

def main():
    print("=" * 50)
    print("   JustRunMy.app 自动登录与续期脚本")
    print("=" * 50)
    
    proxy_url_env = os.environ.get("PROXY_URL", "").strip()
    sb_kwargs = {"uc": True, "test": True, "headless": False}
    
    if proxy_url_env:
        local_proxy = "http://127.0.0.1:8080"
        print(f"检测到代理配置，挂载本地通道: {local_proxy}")
        sb_kwargs["proxy"] = local_proxy
    
    with SB(**sb_kwargs) as sb:
        print("浏览器已启动")
        try:
            sb.open("https://api.ipify.org/?format=json")
            print(f"当前出口 IP: {sb.get_text('body')}")
        except Exception:
            pass

        # 优先使用 Cookie 登录，失败再走账号密码
        if try_cookie_login(sb) or form_login(sb):
            renew(sb)
        else:
            print("\n登录环节失败，终止后续续期操作。")
            send_tg_message("❌", "登录失败", "未知")

if __name__ == "__main__":
    main()
