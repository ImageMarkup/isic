from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.shortcuts import render


@staff_member_required
def staff_list(request):
    users = User.objects.filter(is_staff=True).order_by('email')
    return render(request, 'core/staff_list.html', {'users': users, 'total_users': User.objects})
