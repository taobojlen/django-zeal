from .listeners import zeal_context


def zeal_middleware(get_response):
    def middleware(request):
        with zeal_context():
            response = get_response(request)
        return response

    return middleware
