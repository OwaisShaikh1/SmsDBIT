# 🔍 SMS Portal - Role-Based Code Audit Report

**Generated:** Comprehensive Code Audit  
**Scope:** Admin & Teacher Role Perspectives  
**Focus:** Bugs, Inconsistencies, Incomplete Functions, Authorization Issues

---

## Executive Summary

This report identifies **bugs, inconsistencies, incomplete functions, and authorization concerns** found during a comprehensive audit of the SMS Portal Django application, specifically from **Admin** and **Teacher** role perspectives.

---

## 🔴 CRITICAL ISSUES (2 remaining)

### 1. **Missing Template CRUD Operations**
**Severity:** Critical | **Affects:** Admin & Teacher  
**File:** `backend/sms/myviews/templates_api.py`

**Issue:** The templates API only has a `get_templates()` function. There are **NO endpoints** for:
- Creating templates
- Updating templates  
- Deleting templates
- Approving/rejecting templates (admin)

**Impact:** 
- Teachers cannot create templates via API
- Admin cannot manage template approvals (despite `/approvals/` page existing)
- The `Template.STATUS_CHOICES` (approved/pending/rejected) workflow is non-functional

**Missing Functions:**
```python
def create_template(request):  # POST - create new template
def update_template(request, template_id):  # PUT - modify template
def delete_template(request, template_id):  # DELETE - remove template
def approve_template(request, template_id):  # POST - admin approval workflow
def reject_template(request, template_id):  # POST - admin rejection workflow
```

---

### 2. **Contacts API Broken Filter Logic**
**Severity:** Critical | **Affects:** Teacher  
**File:** `backend/sms/myviews/contacts_api.py` (Lines 12-19)

**Issue:** The `get_contacts()` function has broken logic:

```python
# CURRENT CODE:
elif user.assigned_class:
    contacts = StudentContact.objects.filter(class_dept=user.assigned_class)
```

**Problems:**
1. `class_dept` is a **ForeignKey to `Group`**, NOT a string
2. `user.assigned_class` is a **CharField** (string like "Class 10A")
3. This comparison will NEVER match (FK vs string)
4. Teachers don't see contacts from universal groups they should have access to

**Correct Fix:**
```python
elif user.assigned_class:
    accessible_groups = Group.objects.filter(
        Q(is_universal=True) | Q(teacher=user)
    )
    contacts = StudentContact.objects.filter(class_dept__in=accessible_groups)
```

---

## 🟠 HIGH PRIORITY ISSUES (4)

### 7. **Teachers Can't See Own Templates**
**Severity:** High | **Affects:** Teacher  
**File:** `backend/sms/myviews/templates_api.py` (Lines 17-21)

**Issue:** Teachers only see `status='approved'` templates, but NOT their own pending/rejected templates:

```python
# CURRENT:
templates = Template.objects.filter(Q(status='approved')).distinct()
```

**Teacher Expectation:** See approved templates PLUS their own submissions (any status)

**Fix:**
```python
templates = Template.objects.filter(
    Q(status='approved') | Q(user=user)
).distinct()
```

---

### 9. **Missing Group Update Endpoint**
**Severity:** High | **Affects:** Admin & Teacher  
**File:** `backend/sms/myviews/groups_api.py`

**Issue:** No API endpoint to update group details (name, description, category).

---

### 10. **Excel Import Missing Universal Group Check**
**Severity:** High | **Affects:** Teacher  
**File:** `backend/sms/myviews/groups_api.py` (Lines 231-234)

**Issue:** `import_contacts_excel()` allows teachers to import to universal groups:

```python
# CURRENT (incomplete):
if request.user.role != 'admin' and group.teacher != request.user:
    return JsonResponse({"error": "Permission denied"}, status=403)
```

**Problem:** If `group.is_universal=True` and `group.teacher=None`, the condition passes because `None != request.user` is True.

**Fix - Add explicit check:**
```python
if group.is_universal and request.user.role != 'admin':
    return JsonResponse({"error": "Only admin can import to universal groups"}, status=403)
```

---

### 11. **No SenderID Management API**
**Severity:** High | **Affects:** Admin  
**Missing File:** `backend/sms/myviews/sender_ids_api.py`

**Issue:** The `SenderID` model exists with full CRUD potential, but there are NO API endpoints:
- Frontend page `/sender-ids/` exists but has no backend
- Cannot create, list, approve, or assign sender IDs via API

**Missing Endpoints:**
```python
get_sender_ids(request)  # List all (admin) or assigned (teacher)
create_sender_id(request)  # Admin creates new sender ID
approve_sender_id(request, sender_id)  # Admin approves
assign_sender_id(request, sender_id)  # Admin assigns to user
delete_sender_id(request, sender_id)  # Admin removes
```

---

## 🟡 MEDIUM PRIORITY ISSUES (6)

### 13. **Reports Using Mock Category Data**
**Severity:** Medium | **Affects:** Admin & Teacher  
**File:** `backend/sms/myviews/Reports_api.py` (Lines 59-64)

**Issue:** Message categories are hardcoded percentages, not real data:

```python
categories = [
    {'name': 'Academic', 'count': int(total_messages * 0.41), 'percentage': 41.0},
    {'name': 'Administrative', 'count': int(total_messages * 0.265), 'percentage': 26.5},
    {'name': 'Events', 'count': int(total_messages * 0.196), 'percentage': 19.6},
    {'name': 'Emergency', 'count': int(total_messages * 0.129), 'percentage': 12.9}
]
```

**Fix:** Calculate based on `Template.category` used in messages.

---

### 14. **Test SMS Not Actually Sent**
**Severity:** Medium | **Affects:** Admin & Teacher  
**File:** `backend/sms/myviews/Settings_api.py` (Lines 146-150)

**Issue:** The `test_sms_settings()` function has a TODO comment - test SMS is never sent:

```python
# TODO: Actually send test SMS
# For now, just validate credentials are configured
return JsonResponse({
    "success": True,
    "message": f"Test message would be sent to {phone}. Credentials validated."
})
```

---

### 15. **Missing User List API for Admin**
**Severity:** Medium | **Affects:** Admin  
**File:** `backend/sms/myviews/user_management_api.py`

**Issue:** No JSON API to get user list. The `/users/` page uses server-rendered context, but no API for dynamic operations like search, filter, or AJAX refresh.

---

### 16. **Missing User Update API**
**Severity:** Medium | **Affects:** Admin  
**File:** `backend/sms/myviews/user_management_api.py`

**Issue:** Can create and delete users, but cannot UPDATE:
- Change role
- Assign class
- Update credits
- Modify details

---

### 17. **Broken Contacts Route Template Path**
**Severity:** Medium | **Affects:** All  
**File:** `backend/sms_portal/urls.py` (Line 26)

**Issue:** Route points to non-existent template:

```python
path("contacts/", login_required(lambda request: render(request, "contacts.html"))),
```

**Actual template location:** `templates/contacts/contacts.html`

**Fix:** Change to `render(request, "contacts/contacts.html")`

---

### 18. **Inconsistent CSRF Handling**
**Severity:** Medium | **Affects:** Security  
**Files:** Various API files

**Issue:** Some POST endpoints have `@csrf_exempt`, others don't. Frontend AJAX may not send CSRF token consistently.

**Recommendation:** Standardize: either use `@csrf_exempt` for all API endpoints and handle auth via tokens, OR ensure all frontend AJAX includes CSRF header.

---

## 🟢 LOW PRIORITY / CODE QUALITY (7)

### 19. **Inconsistent API Response Format**
**Affects:** Frontend Integration

Some endpoints return `{"success": True, ...}` wrapper, others return data directly.

| Endpoint | Format |
|----------|--------|
| `get_groups()` | Returns `[{...}]` array directly |
| `create_group()` | Returns `{"success": True, "group": {...}}` |
| `get_templates()` | Returns `[{...}]` array directly |

**Recommendation:** Standardize all responses to `{"success": true, "data": [...], "message": "..."}` format.

---

### 20. **Activity Log Only Tracks SMS**
**File:** `backend/sms/services.py` (AdminAnalyticsService)

**Issue:** `get_activity_logs()` only returns SMS message events. Should also track:
- User creation/deletion
- Template submissions/approvals
- Group changes
- Login/logout events

---

### 21. **Redundant Imports**
**File:** `backend/sms_portal/frontend_views.py`

**Issue:** Same imports repeated multiple times:
- `from django.contrib.auth.decorators import login_required` appears 3 times
- `from django.db.models import Sum, Count` appears 2 times

---

### 22. **views.py Contains Orphaned Code**
**File:** `backend/sms/views.py`

**Issue:** File header says "ALL VIEWS MIGRATED TO MYVIEWS FOLDER" but still contains `get_contacts()` function. Should be removed to avoid confusion.

---

### 23. **Hardcoded Default Sender ID**
**File:** `backend/sms/myviews/send_sms_api.py` (Line 26)

**Issue:** Default sender ID hardcoded as `"BOMBYS"`:

```python
sender_id = data.get("sender_id", "BOMBYS")
```

Should use user's default approved sender ID from settings or SenderID model.

---

### 24. **No Pagination in List APIs**
**Affects:** Performance at scale

List endpoints return all records without pagination:
- `get_groups()` - all groups
- `get_templates()` - all templates
- `get_contacts()` - all contacts
- `get_campaigns()` - all campaigns

Will cause performance issues with large datasets.

---

### 25. **Debug Print Statement**
**File:** `backend/sms/myviews/groups_api.py` (Line 117)

**Issue:** Debug print left in production code:

```python
print(contacts_data)
```

Should be removed or converted to logger.debug().

---

## 📊 Authorization Matrix

| Endpoint | Admin | Teacher | Current Status |
|----------|-------|---------|----------------|
| Send SMS | ✅ | ✅ | Working |
| View Own Campaigns | ✅ | ✅ | Working |
| View ALL Campaigns | ❌ | N/A | **BROKEN** - Admin can't see all |
| Create Template | ❌ | ❌ | **MISSING** |
| Approve Template | ❌ | N/A | **MISSING** |
| View Own Templates | ✅ | ❌ | **BROKEN** - Teachers can't see own |
| Create Group | ✅ | ✅ | Working |
| Delete Group | ❌ | ❌ | **MISSING** |
| Create Universal Group | ✅ | ❌ | Working |
| Manage Users | ✅ | N/A | Partial |
| View Reports | ✅ | ✅ | Working (mock data) |
| Manage SenderIDs | ❌ | N/A | **MISSING** |
| Settings | ✅ | ✅ | Working |

---

## 📋 Recommended Fix Priority

### Phase 1: Critical Fixes (Immediate)
1. ✅ Fix contacts API broken filter (#2)
2. ✅ Add credit check before sending (#4)
3. ✅ Add credit deduction after sending (#3)
4. ✅ Remove duplicate return statement (#5)

### Phase 2: High Priority (This Week)
5. ✅ Add template CRUD operations (#1)
6. ✅ Fix admin campaign visibility (#6)
7. ✅ Fix teachers seeing own templates (#7)
8. ✅ Add group delete/update (#8, #9)
9. ✅ Add SenderID management API (#11)

### Phase 3: Medium Priority (This Sprint)
10. ✅ Complete dashboard context (#12)
11. ✅ Implement real test SMS (#14)
12. ✅ Add user list/update APIs (#15, #16)
13. ✅ Fix contacts route (#17)

### Phase 4: Cleanup (Backlog)
14. Standardize API responses (#19)
15. Add pagination (#24)
16. Remove debug prints (#25)
17. Clean up redundant imports (#21)

---

## Summary Table

| Severity | Count | Examples |
|----------|-------|----------|
| 🔴 Critical | 2 | Missing template CRUD, broken contacts filter |
| 🟠 High | 4 | Teachers can't see own templates, missing group update |
| 🟡 Medium | 6 | Mock data, test SMS not sent, missing user APIs |
| 🟢 Low | 7 | Code quality, inconsistent formats, debug prints |

**Total Remaining Issues: 19**

---

## ✅ RESOLVED ISSUES

### ~~3. SMS Send Doesn't Deduct Credits~~ ✅ FIXED
- Added credit deduction after successful SMS send in `send_sms_api.py`
- Updates `remaining_credits` and `total_sent` in `SMSUsageStats`

### ~~4. No Credit Validation Before Sending~~ ✅ FIXED
- Added credit check at start of `send_sms_api()` 
- Returns 400 error if insufficient credits or no SMS credits allocated

### ~~5. Duplicate Return Statement~~ ✅ FIXED
- Removed unreachable duplicate return statement in `groups_api.py`

### ~~12. Dashboard Missing Context Variables~~ ✅ FIXED
- Added `groups_count`, `templates_count`, `pending_templates`, `success_rate` to dashboard context
- Admin sees system-wide stats; Teachers see their own data + accessible groups

### ~~6. Admin Can't See All Campaigns~~ ✅ FIXED
- Updated `get_campaigns()` in `Campaign_api.py` to check user role
- Admin now sees all campaigns system-wide; Teachers see only their own

### ~~8. Missing Group Delete Endpoint~~ ✅ FIXED
- Added `delete_group()` function in `groups_api.py`
- Added URL route `DELETE /api/groups/<group_id>/`
- Proper permission checks: admin can delete any, teachers only their own

---

*Report generated for SMS Portal Django Application - Admin/Teacher Role Audit*
