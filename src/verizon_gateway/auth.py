"""Browser authentication only; cookies never leave process memory."""

import asyncio
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

from .config import Config, GatewayError


async def _login(config: Config):
    password = config.secret()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(channel=config.browser_channel, headless=True)
            try:
                context = await browser.new_context()

                async def guard(route):
                    request = route.request
                    parsed = urlsplit(request.url)
                    origin = f"{parsed.scheme}://{parsed.netloc}"
                    if origin != config.url or (
                        request.method not in ("GET", "HEAD")
                        and not (request.method == "POST"
                                 and parsed.path.rstrip("/") == "/cgi-bin/luci")
                    ):
                        await route.abort()
                    else:
                        await route.continue_()

                await context.route("**/*", guard)
                page = await context.new_page()
                await page.goto(config.url + "/cgi-bin/luci", wait_until="domcontentloaded",
                                timeout=30000)
                await page.locator("#srp_username").evaluate(
                    "(el, value) => { el.value = value; }", config.username)
                await page.locator("#srp_password").fill(password)
                await page.locator("#sign-me-in").click()
                await page.locator("#btn-system-settings").wait_for(timeout=20000)
                cookies = {c["name"]: c["value"] for c in await context.cookies(config.url)}
                if not cookies:
                    raise GatewayError("authentication_failed")
                return cookies
            finally:
                await browser.close()
    except GatewayError:
        raise
    except Exception:
        raise GatewayError("authentication_failed") from None


def login(config: Config):
    return asyncio.run(_login(config))
