# kount

this module emits a single kount collection run, effectively bypassing terribly-implemented anti bot and anti abuse systems implemented with kount kaptcha.

it is intended to be called before interacting with a site using kount, while reusing the
same session, cookies, ip/proxy, user-agent, and tls context that will be used for the actual
interaction (ie creating accounts, purchases, etc). nothing is fully anonymized because the goal is to pass any anti-bot systems efficiently, so you still need to handle ip rotation, session management, etc. the script basically just grants clearance to a given requests.session for a specific site.

some of the values are hardcoded for simplicity (ie useragent & plugin hash). when doing something like mass account creation, the script as-is will effectively bypass auto-bans, but if youre doing something like high risk purchases that rely on device detection, you need to make your own patch.

**requirements**

you must provide a homepage url that:
- contains the kount bootstrap variables (`m` and `msid`), or makes a request to `logo.htm` on `ssl.kaptcha.com` when opening network inspector and refreshing the page in a fresh incognito session

this is usually the site’s main landing page or signup page, or maybe a checkout page if you are using this for a shopping site.

**usage**

keep in mind that the proper order with this goes: cloudflare/sitewide level clearance > kount level clearance > actual captchas or anything else. so make sure your session(s) that you hand to kount.py already have cf clearance beforehand if they need it.

1. create a requests.session outside of the module

the session should have:
- a proxy / ip configured (if needed for your case, required for duplicate account bypass)
- any preloaded cookies (e.g. cf clearance)

example:

```python
import requests

session = requests.Session()

session.proxies = {
    "http": "http://user:pass@ip:port",
    "https": "http://user:pass@ip:port",
}

session.headers.update({
    "User-Agent": "Mozilla/5.0 ...",
    "Accept-Language": "en-US,en;q=0.9",
})
```

2. call `run_synthetic(session, homepage)` before interacting w site

in a real application, the kount calculations would execute silently before a real user performs any actions. to replicate this, import the function and call it once per logical browser/session, using the same requests.session object that you will later use for said interaction.

```python
from kount import run_synthetic

homepage = "https://target-site.com/"

run_synthetic(session, homepage)

# continue using `session` for account creation, checkout, etc
```

any cookies set by kount during the synthetic run will persist in the session and will be sent automatically on subsequent requests to the target site. so use the same session, for example, that now holds cf+kount clearance to create an account rather then using requests bare (as this will treat it as a fresh session). if you create a new session, you are creating a new identity, meaning you need to run the function again to keep clearance. clearance is on a session-by-session basis.

if you are doing something like mass creating accounts and you want to prevent auto-bans, you should have a fresh session per each account with a unique proxy ip in every session. kount will, despite the hard coded values, see these as different households, stopping any bans. if you wanted to take it a step further you could also implement proper user-agent switching. if an employee of a site you are targeting goes through the kount logs, they will see the same shared useragent among other client hints. the point of the function is to stop immediate auto-bans.
