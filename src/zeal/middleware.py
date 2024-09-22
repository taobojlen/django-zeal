from asgiref.sync import iscoroutinefunction
from django.utils.decorators import sync_and_async_middleware

from .listeners import zeal_context


@sync_and_async_middleware
def zeal_middleware(get_response):
    if iscoroutinefunction(get_response):

        async def async_middleware(request):
            with zeal_context():
                response = await get_response(request)
            return response

        return async_middleware

    else:

        def middleware(request):
            with zeal_context():
                response = get_response(request)
            return response

        return middleware
