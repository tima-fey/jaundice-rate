import asyncio
import pymorphy2

from process_article import get_charged_words_async, get_rates

TEST_ARTICLES = ['https://inosmi.ru/social/20200106/246417526.html',
                 'https://inosmi.ru/politic/20200106/246566787.html',
                 'https://inosmi.ru/politic/20200106/246566637.html',
                 'https://inosmi.ru/social/20200106/246553081.html',
                 'https://inosmi.ru/social/20200106/246566705.html',
                 'test',
                 'https://yandex.ru/social/20200106/246566705.html']

async def main():
    charged_words = await get_charged_words_async('charged_dict')
    morph = pymorphy2.MorphAnalyzer()
    result = await get_rates(TEST_ARTICLES, morph, charged_words)
    print(result)

if __name__ == '__main__':
    asyncio.run(main())
