"""
HTTP proxy utilities and retry logic.
Set the ENV variable PROXY_LIST to a ;-separated list of {ip}:{port} values to
specify the list of proxies to use. If PROXY_LIST a default list will be loaded
from proxyscrape.com (note the default proxies can be very slow).
"""
import os
import random
import re
import time

import requests


PROXY_LIST = []  # Current list of proxy servers to choose from

RECENT_PROXIES = []  # Recently used proxies (to avoid using too often)
RECENT_MAX = 3  # Rotatate between at least 3 proxy servers

MAYBE_BROKEN_PROXIES = {}  # {proxy: error_list} to keep track of proxy errors
ERROR_FORGET_TIME = 10  # Ignore proxy errors that are older than 10 mins
ERROR_THRESHOLD = 3  # Add to broken list if encounter 3 errs in 10 mins

BROKEN_PROXIES = []  # Known-bad proxies (we want to void choosing these)
BROKEN_PROXIES_CACHE_FILENAME = "broken_proxies.list"
BROKEN_CACHE_EXPIRE_MINS = 2 * 24 * 60  # Ignore broken proxy cache older than 2 days


# LOADERS
################################################################################


def load_env_proxies():
    """
    Load data from the ENV variable PROXY_LIST (a ;-sparated list of proxies).
    """
    proxy_list_env_var = os.getenv("PROXY_LIST", None)
    proxy_list_env_var = proxy_list_env_var.strip(";").strip()
    if proxy_list_env_var:
        return [proxy.strip() for proxy in proxy_list_env_var.split(";")]
    else:
        return []


def load_broken_proxies_cache():
    """
    Load data from 'broken_proxies.list' if the file not too old.
    """
    if not os.path.exists(BROKEN_PROXIES_CACHE_FILENAME):
        return []
    mtime = os.path.getmtime(BROKEN_PROXIES_CACHE_FILENAME)
    if (time.time() - mtime) > 60 * BROKEN_CACHE_EXPIRE_MINS:
        os.remove(BROKEN_PROXIES_CACHE_FILENAME)
        return []
    broken_proxies = []
    with open(BROKEN_PROXIES_CACHE_FILENAME, "r") as bpl_file:
        for line in bpl_file.readlines():
            line = line.strip()
            if line and not line.startswith("#"):
                broken_proxy = line.split("#")[0].strip()
                broken_proxies.append(broken_proxy)
    return broken_proxies


def get_proxyscape_proxies():
    """
    Loads a list of `{ip_address}:{port}` for public proxy servers.
    """
    PROXY_TIMOUT_LIMIT = "1000"
    url = "https://api.proxyscrape.com/?request=getproxies"
    url += "&proxytype=http&country=all&ssl=yes&anonymity=all"
    url += "&timeout=" + PROXY_TIMOUT_LIMIT
    r = requests.get(url)
    return r.text.split("\r\n")


def get_sslproxies_proxies():
    r = requests.get("https://sslproxies.org")
    matches = re.findall(r"<td>\d+\.\d+\.\d+\.\d+</td><td>\d+</td>", r.text)
    revised = [m.replace("<td>", "") for m in matches]
    proxies = [s.replace("</td>", ":")[:-1] for s in revised]
    return proxies


def get_proxies(refresh=False):
    """
    Returns current list of proxies to sample from (contents of PROXY_LIST).
    Use `refresh=True` to reload proxy list.
    """
    global PROXY_LIST

    if len(PROXY_LIST) == 0 or refresh:
        # This is either the first run or force-refresh of the list is requested
        if os.getenv("PROXY_LIST", None):
            proxy_list = load_env_proxies()  # (re)load ;-spearated list from ENV
        else:
            proxy_list = get_proxyscape_proxies()
        broken_proxy_list = load_broken_proxies_cache()
        for proxy in proxy_list:
            if proxy not in broken_proxy_list:
                PROXY_LIST.append(proxy)

    return PROXY_LIST


# MAIN
################################################################################


def choose_proxy():
    """
    Main function called externally to get a random proxy from the PROXY_LIST.
    """
    global RECENT_PROXIES

    proxies = get_proxies()

    chosen = False
    proxy = None
    max_attempts = 30
    retry_attempts = 10
    attempt = 0
    attempts_made = 0
    while not chosen:
        proxy = random.choice(proxies)
        if proxy not in RECENT_PROXIES:
            chosen = True
            RECENT_PROXIES.append(proxy)
            if len(RECENT_PROXIES) > RECENT_MAX:
                RECENT_PROXIES.pop(0)
        else:
            attempt += 1
            attempts_made += 1
            if attempts_made > max_attempts:
                break

            # Some chefs can take hours or days, so our proxy list may be stale.
            # Try refreshing the proxy list.
            if attempt == retry_attempts:
                attempt = 0
                proxies = get_proxies(refresh=True)

    return proxy


# ERROR LOGIC
################################################################################


def record_error_for_proxy(proxy, exception=None):
    """
    Record a problem with the proxy server `proxy`, optionally passing in the
    exact exception that occured in the calling code.
    """
    global MAYBE_BROKEN_PROXIES

    error_dict = dict(proxy=proxy, timestamp=time.time(), exception=exception)
    if proxy in MAYBE_BROKEN_PROXIES:
        proxy_errors = MAYBE_BROKEN_PROXIES[proxy]
        recent_proxy_errors = []
        for proxy_error in proxy_errors:
            if (time.time() - proxy_error["timestamp"]) < ERROR_FORGET_TIME * 60:
                recent_proxy_errors.append(proxy_error)
        recent_proxy_errors.append(error_dict)
        MAYBE_BROKEN_PROXIES[proxy] = recent_proxy_errors
        if len(recent_proxy_errors) >= ERROR_THRESHOLD:
            reason = str(exception).split("\n")[0] if exception else None
            add_to_broken_proxy_list(proxy, reason=reason)
    else:
        MAYBE_BROKEN_PROXIES[proxy] = [error_dict]


def add_to_broken_proxy_list(proxy, reason=""):
    global BROKEN_PROXIES

    if proxy not in BROKEN_PROXIES:
        BROKEN_PROXIES.append(proxy)
        with open(BROKEN_PROXIES_CACHE_FILENAME, "a") as bpl_file:
            line = proxy
            if reason:
                line += " # " + str(reason)
            bpl_file.write(line + "\n")

    if proxy in PROXY_LIST:
        PROXY_LIST.remove(proxy)


def reset_broken_proxy_list():
    global BROKEN_PROXIES, MAYBE_BROKEN_PROXIES
    BROKEN_PROXIES = []
    MAYBE_BROKEN_PROXIES = {}
