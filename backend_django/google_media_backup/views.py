from django.shortcuts import render
def query_page(request):
    return render(request, "query.html")
