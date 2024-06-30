from .listeners import queryspy_context


def queryspy_middleware(get_response):
    def middleware(request):
        with queryspy_context():
            response = get_response(request)
        return response

    return middleware
