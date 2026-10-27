from django.http import JsonResponse
from django.shortcuts import render


def discovery_view(request):
    return render(request, 'discovery_app/discovery.html', {})


def recommendations_api(request):
    return JsonResponse({'count': 0, 'results': []})
