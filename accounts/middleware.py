from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages

class RoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)