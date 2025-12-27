from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from sms.models import Template
from sms.serializers import TemplateSerializer

# =========================================================================
# TEMPLATES API
# =========================================================================

@login_required
def get_templates(request):
    """Admins see all templates; teachers see their own templates and approved ones."""
    user = request.user
    if user.role == "admin":
        templates = Template.objects.all()
    else:
        # Teachers can see approved templates
        templates = Template.objects.filter(
            Q(status='approved')
        ).distinct()

    # Use serializer to properly handle JSONField (variable_schema)
    serializer = TemplateSerializer(templates, many=True)
    return JsonResponse(serializer.data, safe=False)
