from .listeners import zealot_context


def zealot_middleware(get_response):
    def middleware(request):
        with zealot_context():
            response = get_response(request)
        return response

    return middleware
