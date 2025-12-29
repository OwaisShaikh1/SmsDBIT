from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_http_methods
import json
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


@login_required
@require_http_methods(["POST"])
def create_template(request):
    """Create a new template. Only admin can create templates."""
    user = request.user
    
    # Only admin can create templates
    if user.role != "admin":
        return JsonResponse({"error": "Only admins can create templates"}, status=403)
    
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        category = data.get('category', '').strip()
        
        if not title or not content or not category:
            return JsonResponse({"error": "Title, content, and category are required"}, status=400)
        
        # Validate category
        if category not in ['student', 'teacher', 'common']:
            return JsonResponse({"error": "Invalid category. Must be student, teacher, or common"}, status=400)
        
        # Validate content length
        if len(content) > 1600:
            return JsonResponse({"error": "Content cannot exceed 1600 characters"}, status=400)
        
        # Create template
        template = Template.objects.create(
            title=title,
            content=content,
            category=category,
            status=data.get('status', 'pending'),
            variable_schema=data.get('variable_schema'),
            class_scope=data.get('class_scope'),
            is_active=data.get('is_active', True),
            created_by=user
        )
        
        serializer = TemplateSerializer(template)
        return JsonResponse({
            "message": "Template created successfully",
            "template": serializer.data
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

