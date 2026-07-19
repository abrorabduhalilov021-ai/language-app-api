class ApiLoggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        print("=" * 50)
        print("IP:", request.META.get("REMOTE_ADDR"))
        print("Method:", request.method)
        print("Path:", request.path)
        print("Query:", request.GET)

        response = self.get_response(request)

        print("Status:", response.status_code)
        print("=" * 50)

        return response