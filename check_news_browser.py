"""Check that Bypass Paywalls Clean is enabled in the connected news browser.

This inspects browser configuration, not article access or full-text completeness.
Only the background tab created by this check is closed.
"""

import argparse
import asyncio
import json
import os
import sys

from playwright.async_api import async_playwright


INSPECT_EXTENSIONS = """async () => {
  const extensions = await new Promise((resolve, reject) => {
    chrome.developerPrivate.getExtensionsInfo(
      {includeDisabled: true, includeTerminated: true}, info => {
        if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
        else resolve(info);
      });
  });
  const profile = await new Promise(resolve => chrome.developerPrivate.getProfileConfiguration(resolve));
  return {
    developer_mode: profile.inDeveloperMode,
    extensions: extensions.filter(e => e.name === 'Bypass Paywalls Clean').map(e => ({
      name: e.name, version: e.version, state: e.state,
      user_scripts: e.userScriptsAccess,
      disable_reasons: e.disableReasons
    }))
  };
}"""


async def inspect_browser(endpoint):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(endpoint, timeout=10000)
        session = await browser.new_browser_cdp_session()
        target_id = None
        baseline = {page for context in browser.contexts for page in context.pages}
        try:
            target_id = (await session.send('Target.createTarget', {
                'url': 'chrome://extensions/', 'background': True
            }))['targetId']
            deadline = asyncio.get_running_loop().time() + 10
            page = None
            while page is None and asyncio.get_running_loop().time() < deadline:
                for context in browser.contexts:
                    for candidate in context.pages:
                        if candidate in baseline:
                            continue
                        probe = await context.new_cdp_session(candidate)
                        try:
                            info = await probe.send('Target.getTargetInfo')
                            if info['targetInfo']['targetId'] == target_id:
                                page = candidate
                        finally:
                            await probe.detach()
                        if page:
                            break
                    if page:
                        break
                if page is None:
                    await asyncio.sleep(0.1)
            if page is None:
                raise TimeoutError('Extension settings tab did not become available')
            await page.wait_for_load_state('domcontentloaded', timeout=10000)
            report = await page.evaluate(INSPECT_EXTENSIONS)
            report['browser'] = browser.version
            report['ok'] = any(item['state'] == 'ENABLED' for item in report['extensions'])
            report['scope'] = 'Extension is enabled; article access still requires a real URL check.'
            return report
        finally:
            if target_id:
                await session.send('Target.closeTarget', {'targetId': target_id})
            await session.detach()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default=os.environ.get('NEWS_BRIEFING_CDP', 'http://127.0.0.1:9230'))
    args = parser.parse_args()
    try:
        report = asyncio.run(inspect_browser(args.endpoint))
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
