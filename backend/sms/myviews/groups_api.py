from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from ..models import Group
from ..models import StudentContact
import json

# =========================================================================
# GROUPS MANAGEMENT API
# =========================================================================

@login_required
def get_groups(request):
    user = request.user
    # Admins see all groups. Other users see universal groups + their own personal groups.
    if user.role == "admin":
        groups = Group.objects.all()
    else:
        groups = Group.objects.filter(Q(is_universal=True) | Q(teacher=user)).distinct()

    # Include contact count in response
    groups_data = []
    for g in groups:
        groups_data.append({
            'id': g.id,
            'name': g.name,
            'class_dept': g.class_dept,
            'description': g.description,
            'created_at': g.created_at.isoformat(),
            'teacher_id': g.teacher.id if g.teacher else None,
            'teacher_name': g.teacher.username if g.teacher else ('Universal' if g.is_universal else None),
            'contacts_count': g.contacts.count(),
            'is_universal': bool(g.is_universal),
        })

    return JsonResponse(groups_data, safe=False)

@login_required
def create_group(request):
    """Create a new group"""
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST method allowed"}, status=405)
    
    try:
        import json
        data = json.loads(request.body)
        
        name = data.get('name', '').strip()
        category = data.get('category', '').strip()
        description = data.get('description', '').strip()
        is_universal = bool(data.get('is_universal', False))
        
        if not name:
            return JsonResponse({"error": "Group name is required"}, status=400)
        
        if not category:
            return JsonResponse({"error": "Category is required"}, status=400)
            
        # Admins may create universal groups; non-admins cannot.
        if is_universal and request.user.role != 'admin':
            return JsonResponse({"error": "Only admins can create universal groups"}, status=403)

        # Check duplicate for this scope
        if is_universal:
            if Group.objects.filter(name=name, is_universal=True).exists():
                return JsonResponse({"error": "A universal group with this name already exists"}, status=400)
            group = Group.objects.create(
                name=name,
                class_dept=category,
                description=description,
                is_universal=True,
                teacher=None
            )
        else:
            if Group.objects.filter(name=name, teacher=request.user).exists():
                return JsonResponse({"error": "Group with this name already exists"}, status=400)
            group = Group.objects.create(
                name=name,
                class_dept=category,
                description=description,
                teacher=request.user
            )
        
        return JsonResponse({
            "success": True,
            "message": "Group created successfully",
            "group": {
                "id": group.id,
                "name": group.name,
                "class_dept": group.class_dept,
                "description": group.description,
                "contacts": 0,  # New group starts with 0 contacts
                "created_at": group.created_at.isoformat() if hasattr(group, 'created_at') else None,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def get_group_contacts(request, group_id):
    """Get all contacts in a specific group"""
    try:
        group = Group.objects.get(id=group_id)
        
        # Check permission
        # Admins can access any group. Universal groups are readable by everyone.
        if request.user.role != 'admin':
            if group.is_universal:
                # allowed to read universal groups
                pass
            elif group.teacher != request.user:
                return JsonResponse({"error": "Permission denied"}, status=403)
        
        contacts = StudentContact.objects.filter(class_dept=group)
        contacts_data = [{
            'id': c.id,
            'name': c.name,
            'phone_number': c.phone_number,
            'meta': c.meta or {},
            'created_at': c.created_at.isoformat()
        } for c in contacts]
        
        print(contacts_data)

        return JsonResponse({
            'group_id': group.id,
            'group_name': group.name,
            'contacts': contacts_data
        })
    
    except Group.DoesNotExist:
        return JsonResponse({"error": "Group not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def add_contacts_to_group(request, group_id):
    """Add contacts to a group (manual or from another group)"""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        group = Group.objects.get(id=group_id)
        
        # Check permission: only admins or the owning teacher can modify personal groups.
        if group.is_universal and request.user.role != 'admin':
            return JsonResponse({"error": "Permission denied: universal groups are admin-managed"}, status=403)

        if not group.is_universal and request.user.role != 'admin' and group.teacher != request.user:
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        data = json.loads(request.body)
        contacts_data = data.get('contacts', [])
        source_group_id = data.get('source_group_id')
        
        added_count = 0
        errors = []
        
        # If copying from another group
        if source_group_id:
            try:
                source_group = Group.objects.get(id=source_group_id)
                # If source is universal and user is not admin, copying is allowed (read),
                # but adding into a personal group still must obey permissions for target group above.
                source_contacts = StudentContact.objects.filter(class_dept=source_group)
                
                for contact in source_contacts:
                    try:
                        StudentContact.objects.create(
                            name=contact.name,
                            phone_number=contact.phone_number,
                            class_dept=group,
                            meta=contact.meta
                        )
                        added_count += 1
                    except Exception as e:
                        errors.append(f"{contact.name}: {str(e)}")
            except Group.DoesNotExist:
                return JsonResponse({"error": "Source group not found"}, status=404)
        
        # Add individual contacts
        for contact_data in contacts_data:
            name = contact_data.get('name', '').strip()
            phone = contact_data.get('phone_number', '').strip()
            
            if not name or not phone:
                errors.append(f"Missing name or phone for: {name or phone}")
                continue
            
            try:
                StudentContact.objects.create(
                    name=name,
                    phone_number=phone,
                    class_dept=group,
                    meta=contact_data.get('meta', {})
                )
                added_count += 1
            except Exception as e:
                errors.append(f"{name}: {str(e)}")
        
        return JsonResponse({
            "success": True,
            "message": f"Added {added_count} contacts",
            "added_count": added_count,
            "errors": errors
        })
        
    except Group.DoesNotExist:
        return JsonResponse({"error": "Group not found"}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def import_contacts_excel(request, group_id):
    """Import contacts from Excel file"""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        import pandas as pd
        from io import BytesIO
        
        group = Group.objects.get(id=group_id)
        
        # Check permission
        if request.user.role != 'admin' and group.teacher != request.user:
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        if 'file' not in request.FILES:
            return JsonResponse({"error": "No file uploaded"}, status=400)
        
        excel_file = request.FILES['file']
        
        # Read Excel file - first read without header to find the header row
        df_raw = pd.read_excel(BytesIO(excel_file.read()), header=None)
        
        # Find the header row (row that contains "name" and "phone" keywords)
        header_row = None
        name_col_idx = None
        phone_col_idx = None
        
        for row_idx in range(min(20, len(df_raw))):  # Check first 20 rows
            row_values = df_raw.iloc[row_idx].astype(str).str.lower().str.strip()
            
            # Look for name column
            name_patterns = ['name', 'student', 'contact', 'full']
            for col_idx, val in enumerate(row_values):
                if any(pattern in val for pattern in name_patterns):
                    name_col_idx = col_idx
                    break
            
            # Look for phone column
            phone_patterns = ['phone', 'mobile', 'number', 'contact']
            for col_idx, val in enumerate(row_values):
                if any(pattern in val for pattern in phone_patterns) and col_idx != name_col_idx:
                    phone_col_idx = col_idx
                    break
            
            if name_col_idx is not None and phone_col_idx is not None:
                header_row = row_idx
                break
        
        if header_row is None:
            return JsonResponse({
                "error": "Could not find header row with name and phone columns. Please ensure your Excel has column headers."
            }, status=400)
        
        # Re-read the Excel file with the correct header row
        excel_file.seek(0)  # Reset file pointer
        df = pd.read_excel(BytesIO(excel_file.read()), header=header_row)
        
        # Get the actual column names
        name_col = df.columns[name_col_idx]
        phone_col = df.columns[phone_col_idx]
        
        added_count = 0
        errors = []
        
        for index, row in df.iterrows():
            name = str(row.get(name_col, '')).strip()
            phone = str(row.get(phone_col, '')).strip()
            
            if not name or not phone or phone == 'nan':
                errors.append(f"Row {index + 2}: Missing name or phone")
                continue
            
            try:
                StudentContact.objects.create(
                    name=name,
                    phone_number=phone,
                    class_dept=group,
                    meta={}
                )
                added_count += 1
            except Exception as e:
                errors.append(f"Row {index + 2} ({name}): {str(e)}")
        
        return JsonResponse({
            "success": True,
            "message": f"Imported {added_count} contacts from Excel",
            "added_count": added_count,
            "errors": errors[:10]  # Limit error messages
        })
        
    except Group.DoesNotExist:
        return JsonResponse({"error": "Group not found"}, status=404)
    except ImportError:
        return JsonResponse({"error": "pandas library not installed. Run: pip install pandas openpyxl"}, status=500)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def delete_contact_from_group(request, contact_id):
    """Delete a contact from a group"""
    if request.method != 'DELETE':
        return JsonResponse({"error": "DELETE method required"}, status=405)
    
    try:
        contact = StudentContact.objects.get(id=contact_id)
        group = contact.class_dept
        
        # Check permission
        if request.user.role != 'admin' and group.teacher != request.user:
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        contact.delete()
        
        return JsonResponse({
            "success": True,
            "message": "Contact deleted successfully"
        })
        
    except StudentContact.DoesNotExist:
        return JsonResponse({"error": "Contact not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def delete_group(request, group_id):
    """Delete a group. Admin can delete any group, teachers can only delete their own."""
    if request.method != 'DELETE':
        return JsonResponse({"error": "DELETE method required"}, status=405)
    
    try:
        group = Group.objects.get(id=group_id)
        
        # Permission check
        if group.is_universal and request.user.role != 'admin':
            return JsonResponse({"error": "Only admin can delete universal groups"}, status=403)
        
        if not group.is_universal and group.teacher != request.user and request.user.role != 'admin':
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        group_name = group.name
        group.delete()
        
        return JsonResponse({
            "success": True,
            "message": f"Group '{group_name}' deleted successfully"
        })
        
    except Group.DoesNotExist:
        return JsonResponse({"error": "Group not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)