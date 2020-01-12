from aiohttp import web

import pymorphy2

from process_article import get_rates, get_charged_words

async def handle(request):
    urls = request.query.get('urls')
    if urls:
        urls = urls.split(',')
    if len(urls) > 10:
        raise web.HTTPBadRequest(reason={"error": "too many urls in request, should be 10 or less"})
    result = await get_rates(urls, morph, charged_words)
    return web.json_response(result)

app = web.Application()
app.add_routes([web.get('/', handle)])


if __name__ == '__main__':
    morph = pymorphy2.MorphAnalyzer()
    charged_words = get_charged_words('charged_dict')
    web.run_app(app, port=8000)
