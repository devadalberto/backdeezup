from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

@staff_member_required
@ensure_csrf_cookie
def admin_ops_view(request):
    return render(request, "admin/gmb_ops.html", {"title": "Media pipeline"})
