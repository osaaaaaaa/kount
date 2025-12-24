# https://github.com/osaaaaaaa
import re
import time
import random
import hashlib
import requests
import urllib.parse
import asyncio
from aiortc import RTCPeerConnection

# helpers

def get_session(session, homepage):
    try:
        r = session.get(homepage)
    except Exception:
        print("[error] bootstrap request failed")
        raise

    html = r.text
    try:
        m = re.search(r'var m\s*=\s*(\d+);', html).group(1)
        s = re.search(r"var msid\s*=\s*'([^']+)'", html).group(1)
    except Exception:
        print("[error] failed to parse merchant/session ids from homepage")
        raise

    return m, s


def get_logo(session, merchant_id, session_id):
    url = f"https://ssl.kaptcha.com/logo.htm?m={merchant_id}&s={session_id}"
    try:
        r = session.get(url)
    except Exception:
        print("[error] logo request failed")
        raise

    html = r.text
    try:
        powSeed = re.search(r'powSeed\s*=\s*"([^"]+)"', html).group(1)
        powComplexity = int(re.search(r'powComplexity\s*=\s*(\d+);', html).group(1))
        powMaxAttempts = int(re.search(r'powMaxAttempts\s*=\s*(\d+);', html).group(1))
        kddcgid = re.search(r'kddcgid\s*=\s*"([^"]+)"', html).group(1)
        cookieId = re.search(r"con\.cookieId\s*=\s*'([^']+)'", html).group(1)
        sessionId = re.search(r"con\.sessionId\s*=\s*'([^']+)'", html).group(1)
        merchantId = re.search(r"con\.merchantId\s*=\s*'([^']+)'", html).group(1)
    except Exception:
        print("[error] failed parsing logo response")
        raise

    return {
        "powSeed": powSeed,
        "powComplexity": powComplexity,
        "powMaxAttempts": powMaxAttempts,
        "kddcgid": kddcgid,
        "cookieId": cookieId,
        "sessionId": sessionId,
        "merchantId": merchantId,
        "referer": url,
    }


def sha256_hex(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()


def solve_pow(seed, complexity, max_attempts):
    prefix = "0" * complexity
    for answer in range(max_attempts):
        if sha256_hex(str(answer) + seed).startswith(prefix):
            return answer
    print("[error] pow solve failed")
    raise RuntimeError("pow failed")


def make_headers(info):
    return {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": f"k={info['cookieId']}",
        "Host": "ssl.kaptcha.com",
        "Origin": "https://ssl.kaptcha.com",
        "Referer": info["referer"],
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Storage-Access": "active",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
    }


def post_md(session, payload, info, group):
    data = payload.copy()
    data["s"] = info["sessionId"]
    data["m"] = info["merchantId"]
    data["n"] = group
    data["kddcgid"] = info["kddcgid"]

    try:
        r = session.post(f"https://ssl.kaptcha.com/md", headers=make_headers(info), data=data)
    except Exception:
        print(f"[error] post md/{group} failed")
        raise

    print(f"[→] post {group} :: {r.status_code} len={len(str(data))}")
    return r


def realistic_delay(min_ms, max_ms):
    ms = random.randint(min_ms, max_ms)
    time.sleep(ms / 1000.0)
    return ms


async def generate_sdp(label, stun_servers):
    configuration = {"iceServers": [{"urls": f"stun:{server}"} for server in stun_servers]}
    pc = RTCPeerConnection(configuration=configuration)
    pc.createDataChannel(label)

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    sdp_txt = pc.localDescription.sdp
    await pc.close()

    return urllib.parse.quote(sdp_txt, safe="")


def generate_all_sdps():
    stun_groups = {
        "GA": ["stun1.l.google.com:19302"],
        "KB": ["stun.kaptcha.com:53"],
        "KA": ["stun.kaptcha.com:123"],
    }

    results = {}
    for label, servers in stun_groups.items():
        results[label] = asyncio.run(generate_sdp(label, servers))
    return results


def run_synthetic(session, homepage):
    if not isinstance(session, requests.Session):
        raise TypeError("you need to pass a requests session")

    merchant_id, session_id = get_session(session, homepage)
    print("[*] session:", merchant_id, session_id)

    info = get_logo(session, merchant_id, session_id)
    print("[*] bootstrapped:", info)

    clientdata = {
        "ss": info["cookieId"],
        "ln": "en-US",
        "e": str(int(time.time() * 1000)),
        "t0": "420",
        "tf": "480",
        "ta": "420",
        "sa": "1407x2560",
        "cd": "24",
        "sd": "1440x2560",
        "fd": "1x1",
        "rm": "false",
        "lh": "9fc4c19727632d3c59628c98d704ff5e",
    }

    post_md(session, clientdata, info, "clientdata")
    realistic_delay(50, 150)

    pow_answer = solve_pow(
        info["powSeed"],
        info["powComplexity"],
        info["powMaxAttempts"],
    )

    post_md(session, {"a": str(pow_answer)}, info, "pow")
    print("pow solved =", pow_answer)
    realistic_delay(150, 300)

    sdps = generate_all_sdps()
    for label, sdp in sdps.items():
        post_md(session, {"d": sdp, "i": label}, info, "webrtc")
        realistic_delay(300, 600)

    realistic_delay(400, 700)

    try:
        r = session.post(
            f"https://ssl.kaptcha.com/fin",
            headers=make_headers(info),
            data={
                "s": info["sessionId"],
                "m": info["merchantId"],
                "n": "collect-end",
                "com": "true",
                "kddcgid": info["kddcgid"],
            },
        )
    except Exception:
        print("[error] fin failed")
        raise

    print("[→] fin ::", r.status_code)


if __name__ == "__main__":
    raise RuntimeError("import this file and call run_synthetic(session)")
