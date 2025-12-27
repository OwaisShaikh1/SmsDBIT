from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
from sms.models import Campaign

# =========================================================================
# CAMPAIGNS API
# =========================================================================

@login_required
def get_campaigns(request):
    """Return user's own campaigns (latest first). Each user only sees their own campaigns."""
    campaigns = Campaign.objects.filter(user=request.user).order_by('-created_at')
    data = [
        {
            "id": c.id,
            "title": c.title or f"Untitled Campaign {c.id}",
            "status": c.status or "draft",
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M")
        }
        for c in campaigns
    ]
    return JsonResponse(data, safe=False)

@csrf_exempt
@login_required
def create_campaign(request):
    """Create a new campaign."""
    print("Create_campaign called")
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            title = data.get('title', '').strip() or None

            if not title:
                # Auto title fallback if blank
                from django.utils import timezone
                title = f"Campaign {timezone.now().strftime('%d %b %Y %H:%M')}"

            campaign = Campaign.objects.create(
                user=request.user,
                title=title,
                status='draft'
            )
            return JsonResponse({
                "id": campaign.id,
                "title": campaign.title,
                "status": campaign.status,
                "created_at": campaign.created_at.strftime("%Y-%m-%d %H:%M")
            })
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "POST only"}, status=405)
