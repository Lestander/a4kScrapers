# -*- coding: utf-8 -*-

import threading
import time
import traceback

from urllib3.exceptions import ConnectTimeoutError
from requests.exceptions import ReadTimeout

from third_party import source_utils, cfscrape
from common_types import UrlParts
from utils import tools

class Request(object):
    def __init__(self, sequental=False, timeout=None, wait=1):
        self._request = source_utils.serenRequests()
        self._cfscrape = cfscrape.CloudflareScraper()
        self._sequental = sequental
        self._wait = wait
        self._lock = threading.Lock()
        self._timeout = 10
        if timeout is not None:
            self._timeout = timeout

    def _request_core(self, request, retry=True):
        response_err = lambda: None
        response_err.status_code = 501

        try:
            if self._sequental is False:
                return request()

            with self._lock:
                response = request()
                time.sleep(self._wait)
                return response
        except (ReadTimeout, ConnectTimeoutError):
            if not retry:
                return response_err

            return self._request_core(request, retry=False)
        except:
            traceback.print_exc()
            return response_err

    def _head(self, url):
        tools.log('HEAD: %s' % url, 'info')
        request = lambda: self._request.head(url, timeout=self._timeout)
        response = self._request_core(request)
        if self._cfscrape.is_cloudflare_on(response, allow_empty_body=True):
            response = lambda: None
            response.url = url
            response.status_code = 200
            return response

        if response.status_code == 302 or response.status_code == 301:
            redirect_url = response.headers['Location']
            if not redirect_url.endswith('127.0.0.1') and not redirect_url.endswith('localhost'):
                return self._head(redirect_url)

        return response

    def find_url(self, urls):
        if len(urls) == 1:
            return UrlParts(base=urls[0].base, search=urls[0].search)

        for url in urls:
            response = self._head(url.base)
            if response.status_code != 200:
                continue

            response_url = response.url

            if response_url.endswith("/"):
                response_url = response_url[:-1]

            return UrlParts(base=response_url, search=url.search)

        return None

    def get(self, url, headers={}, allow_redirects=True):
        tools.log('GET: %s' % url, 'info')
        request = lambda: self._cfscrape.get(url, headers=headers, timeout=self._timeout, allow_redirects=allow_redirects)
        return self._request_core(request)

    def post(self, url, data, headers={}):
        tools.log('POST: %s' % url, 'info')
        request = lambda: self._cfscrape.post(url, data, headers=headers, timeout=self._timeout)
        return self._request_core(request)
