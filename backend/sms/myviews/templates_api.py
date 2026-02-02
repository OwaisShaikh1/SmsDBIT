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
            user=user
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


@login_required
def get_template(request, template_id):
    """Get a single template by ID."""
    try:
        template = Template.objects.get(id=template_id)
        
        # Check permissions
        user = request.user
        if user.role != "admin" and template.status != 'approved':
            return JsonResponse({"error": "Template not found or access denied"}, status=404)
        
        serializer = TemplateSerializer(template)
        return JsonResponse(serializer.data)
        
    except Template.DoesNotExist:
        return JsonResponse({"error": "Template not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["PUT", "PATCH"])
def update_template(request, template_id):
    """Update an existing template. Only admin can update templates."""
    user = request.user
    
    # Only admin can update templates
    if user.role != "admin":
        return JsonResponse({"error": "Only admins can update templates"}, status=403)
    
    try:
        template = Template.objects.get(id=template_id)
        data = json.loads(request.body)
        
        # Update fields if provided
        if 'title' in data:
            title = data['title'].strip()
            if not title:
                return JsonResponse({"error": "Title cannot be empty"}, status=400)
            template.title = title
        
        if 'content' in data:
            content = data['content'].strip()
            if not content:
                return JsonResponse({"error": "Content cannot be empty"}, status=400)
            if len(content) > 1600:
                return JsonResponse({"error": "Content cannot exceed 1600 characters"}, status=400)
            template.content = content
        
        if 'category' in data:
            category = data['category']
            if category not in ['student', 'teacher', 'common']:
                return JsonResponse({"error": "Invalid category"}, status=400)
            template.category = category
        
        if 'status' in data:
            status = data['status']
            if status not in ['approved', 'pending', 'rejected']:
                return JsonResponse({"error": "Invalid status"}, status=400)
            template.status = status
        
        if 'variable_schema' in data:
            template.variable_schema = data['variable_schema']
        
        if 'class_scope' in data:
            template.class_scope = data['class_scope']
        
        if 'is_active' in data:
            template.is_active = data['is_active']
        
        template.save()
        
        serializer = TemplateSerializer(template)
        return JsonResponse({
            "message": "Template updated successfully",
            "template": serializer.data
        })
        
    except Template.DoesNotExist:
        return JsonResponse({"error": "Template not found"}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_template(request, template_id):
    """Delete a template. Only admin can delete templates."""
    user = request.user
    
    # Only admin can delete templates
    if user.role != "admin":
        return JsonResponse({"error": "Only admins can delete templates"}, status=403)
    
    try:
        template = Template.objects.get(id=template_id)
        template_title = template.title
        template.delete()
        
        return JsonResponse({
            "message": f"Template '{template_title}' deleted successfully"
        })
        
    except Template.DoesNotExist:
        return JsonResponse({"error": "Template not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

