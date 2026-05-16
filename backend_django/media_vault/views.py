from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def review_view(request):
    return render(request, "media_vault/review.html", {"title": "Media Review"})
