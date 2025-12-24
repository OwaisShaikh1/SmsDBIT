# -------------------------------------------------------------------------
# ✅ API ENDPOINTS
# -------------------------------------------------------------------------

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from ..models import StudentContact


@login_required
def get_contacts(request):
    user = request.user
    if user.role == "admin":
        contacts = StudentContact.objects.all()
    elif user.assigned_class:
        contacts = StudentContact.objects.filter(class_dept=user.assigned_class)
    else:
        contacts = StudentContact.objects.none()

    return JsonResponse(list(contacts.values()), safe=False)
    