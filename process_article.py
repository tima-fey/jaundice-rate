import logging
from contextlib import contextmanager
from enum import Enum
from urllib.parse import urlparse
import time
import asyncio
import pytest

import aiohttp
from aiofile import AIOFile
import aionursery

from async_timeout import timeout
from func_timeout import FunctionTimedOut
import pymorphy2

from adapters import SANITIZERS
from text_tools import split_by_words, calculate_jaundice_rate

class ProcessingStatus(Enum):
    OK = 'OK'
    FETCH_ERROR = 'FETCH_ERROR'
    PARSING_ERROR = 'PARSING_ERROR'
    BAD_URL = 'BAD_URL'
    REMOTE_TIMEOUT = 'REMOTE_TIMEOUT'
    LOCAL_TIMEOUT = 'LOCAL_TIMEOUT'

logging.basicConfig(level=logging.INFO)

@contextmanager
def timer():
    start_time = time.monotonic()
    try:
        yield
    finally:
        logging.info(time.monotonic() - start_time)

async def fetch(session, url, remote_timeout):
    async with timeout(remote_timeout):
        async with session.get(url, ssl=False, raise_for_status=True) as response:
            return await response.text()

async def get_charged_words_async(dir_name):
    async with AIOFile("{}/negative_words.txt".format(dir_name), 'r') as _file:
        negative_words = await _file.read()
    words = negative_words.split('\n')[:-1]
    async with AIOFile("{}/positive_words.txt".format(dir_name), 'r') as _file:
        positive_words = await _file.read()
    words.extend(positive_words.split('\n')[:-1])
    return words

def get_charged_words(dir_name):
    with open("{}/negative_words.txt".format(dir_name), 'r') as _file:
        negative_words = _file.read()
    words = negative_words.split('\n')[:-1]
    with open("{}/positive_words.txt".format(dir_name), 'r') as _file:
        positive_words = _file.read()
    words.extend(positive_words.split('\n')[:-1])
    return words

async def analize_article(morph, charged_words, html):
    with timer():
        clered_text = SANITIZERS['inosmi.ru'](html, plaintext=True)
        try:
            words = split_by_words(morph, clered_text)
        except FunctionTimedOut:
            return None, None, ProcessingStatus.LOCAL_TIMEOUT.name
        score = calculate_jaundice_rate(words, charged_words)
        return score, len(words), ProcessingStatus.OK.name

async def process_article(session, morph, charged_words, url, remote_timeout=2):
    fqdn = urlparse(url).hostname
    if not fqdn:
        return {'url':url,
                'status':ProcessingStatus.BAD_URL.name,
                'score':None,
                'word count':None}
    if fqdn.startswith('www.'):
        fqdn = fqdn[4:]
    if fqdn not in SANITIZERS.keys():
        return {'url':url,
                'status':ProcessingStatus.PARSING_ERROR.name,
                'score':None,
                'word count':None}
    try:
        html = await fetch(session, url, remote_timeout)
    except asyncio.TimeoutError:
        return {'url':url,
                'status':ProcessingStatus.REMOTE_TIMEOUT.name,
                'score':None,
                'word count':None}
    except aiohttp.ClientError:
        return {'url':url,
                'status':ProcessingStatus.FETCH_ERROR.name,
                'score':None,
                'word count':None}
    async with timeout(0.01):                                                               # why doesn't work?
        score, words_count, status = await analize_article(morph, charged_words, html)
    return {'url':url,
            'status':status,
            'score':score,
            'word count':words_count}


async def get_rates(urls, morph, charged_words):
    all_requests = []
    async with aiohttp.ClientSession() as session:
        async with aionursery.Nursery() as nursery:
            for url in urls:
                a_request = nursery.start_soon(process_article(session, morph, charged_words, url))
                all_requests.append(a_request)
            results = await asyncio.wait(all_requests)
    return [result.result() for result in results[0]]

@pytest.mark.asyncio
async def test_process_article():
    class DummyMorph:
        def __init__(self, sleep=0):
            self.sleep = sleep

        def parse(self, *_):
            time.sleep(self.sleep)
            return []

    async with aiohttp.ClientSession() as session:
        bad_url = await process_article(session, 'dummy_morph', 'dummy_charged_words', 'bad_url')
        assert bad_url['status'] == ProcessingStatus.BAD_URL.name
        wrong_url = await process_article(session, 'dummy_morph', 'dummy_charged_words', 'http://yandex.ru/blabla')
        assert wrong_url['status'] == ProcessingStatus.PARSING_ERROR.name
        remote_timeout_error = await process_article(session, 'dummy_morph', 'dummy_charged_words', 'https://inosmi.ru/social/20200106/246417526.html', 0.1)
        assert remote_timeout_error['status'] == ProcessingStatus.REMOTE_TIMEOUT.name
        client_error = await process_article(session, 'dummy_morph', 'dummy_charged_words', 'https://inosmi.ru/social/20200106/11111111.html')
        assert client_error['status'] == ProcessingStatus.FETCH_ERROR.name
        morph = DummyMorph(2.1)
        timeout_error = await process_article(session, morph, 'dummy_charged_words', 'https://inosmi.ru/social/20200106/246417526.html')
        assert timeout_error['status'] == ProcessingStatus.LOCAL_TIMEOUT.name
        morph = pymorphy2.MorphAnalyzer()
        status_ok = await process_article(session, morph, ['bad', 'words'], 'https://inosmi.ru/social/20200106/246417526.html')
        assert status_ok['status'] == ProcessingStatus.OK.name
        status_ok = await process_article(session, morph, ['bad', 'words'], 'https://www.inosmi.ru/social/20200106/246417526.html')
        assert status_ok['status'] == ProcessingStatus.OK.name
