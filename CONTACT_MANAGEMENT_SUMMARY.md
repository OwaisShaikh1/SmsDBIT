# Groups Contact Management - Implementation Summary

## Changes Made

### 1. Fixed Field Reference Bug
**Problem**: Groups API was using non-existent `user` field causing "Cannot resolve keyword 'user' into field" error.

**Solution**: Updated views to use correct field names:
- Changed `user` → `teacher` (ForeignKey to User model)
- Changed `category` → `class_dept` (CharField for department/class)
- Removed reference to non-existent `is_active` field

**Files Modified**:
- `backend/sms/views.py`:
  - Fixed `get_groups()` function (lines 188-213)
  - Fixed `create_group()` function (lines 214-260)

---

### 2. Contact Management Features

#### Backend API Endpoints (backend/sms/views.py)

**A. Get Group Contacts** (`get_group_contacts`)
- **URL**: `GET /api/groups/<group_id>/contacts/`
- **Permission**: Admin or group teacher only
- **Returns**: List of contacts with id, name, phone_number, meta, created_at

**B. Add Contacts** (`add_contacts_to_group`)
- **URL**: `POST /api/groups/<group_id>/contacts/add/`
- **Two modes**:
  1. Manual: Send array of `{name, phone_number}` objects
  2. Copy: Send `source_group_id` to copy all contacts from another group
- **Returns**: `added_count` and `errors` array

**C. Import from Excel** (`import_contacts_excel`)
- **URL**: `POST /api/groups/<group_id>/contacts/import/`
- **Format**: Multipart form-data with Excel file
- **Excel Requirements**: Columns named `name` and `phone_number` (or `phone`)
- **Returns**: `added_count` and `errors` array (first 10 errors)

**D. Delete Contact** (`delete_contact_from_group`)
- **URL**: `DELETE /api/contacts/<contact_id>/delete/`
- **Permission**: Admin or group teacher only
- **Returns**: Success message

#### URL Routes (backend/sms/urls.py)
Added 4 new routes:
```python
path('groups/<int:group_id>/contacts/', views.get_group_contacts, name='get_group_contacts'),
path('groups/<int:group_id>/contacts/add/', views.add_contacts_to_group, name='add_contacts_to_group'),
path('groups/<int:group_id>/contacts/import/', views.import_contacts_excel, name='import_contacts_excel'),
path('contacts/<int:contact_id>/delete/', views.delete_contact_from_group, name='delete_contact_from_group'),
```

---

### 3. Frontend UI (backend/frontend/templates/groups/groups.html)

#### New Modal: Manage Contacts
- **Tabs**:
  1. **View Contacts**: Table displaying all contacts with delete button
  2. **Add Manually**: Dynamic form to add multiple contacts (name + phone)
  3. **Import Excel**: File upload for .xlsx/.xls files
  4. **Copy from Group**: Dropdown to select source group and bulk copy

#### JavaScript Functions
- `openManageContactsModal(groupId, groupName)`: Opens modal and loads data
- `loadGroupContacts(groupId)`: Fetches and displays contact list
- `loadGroupsForCopy()`: Populates dropdown with available groups
- `addContactRow()`: Adds new input row for manual entry
- `removeContactRow(btn)`: Removes input row
- `submitManualContacts()`: Submits manually entered contacts
- `importExcel()`: Handles Excel file upload and import
- `copyFromGroup()`: Copies contacts from selected source group
- `deleteContact(contactId)`: Deletes individual contact

#### Updated Table
- Added **"Actions"** column with "Manage Contacts" button
- Updated to display `contacts_count` from API response

---

### 4. Dependencies

#### Added to requirements.txt:
- `pandas>=2.3.0` - For Excel file parsing
- `openpyxl>=3.1.2` - For .xlsx file support

#### Installation:
```bash
pip install pandas openpyxl
```

**Status**: ✅ Successfully installed
- pandas version: 2.3.3
- openpyxl version: 3.1.2

---

## Excel Import Format

Your Excel file should have these columns:
- **name** (required): Contact name
- **phone_number** or **phone** (required): Phone number

Example:
| name | phone_number |
|------|--------------|
| John Doe | +919876543210 |
| Jane Smith | +919876543211 |

---

## Usage Instructions

### Adding Contacts Manually
1. Click "Manage Contacts" button in the Actions column
2. Go to "Add Manually" tab
3. Enter name and phone number
4. Click "+ Add More" to add additional contacts
5. Click "Add Contacts" to save

### Importing from Excel
1. Prepare Excel file with `name` and `phone_number` columns
2. Click "Manage Contacts" button
3. Go to "Import Excel" tab
4. Choose your Excel file
5. Click "Import Contacts"

### Copying from Another Group
1. Click "Manage Contacts" button
2. Go to "Copy from Group" tab
3. Select source group from dropdown
4. Click "Copy Contacts"
5. All contacts from source group will be copied

### Deleting Contacts
1. Click "Manage Contacts" button
2. View contacts in "View Contacts" tab
3. Click "Delete" button next to contact
4. Confirm deletion

---

## Permission Model

- **Admins**: Can view and manage contacts in all groups
- **Teachers**: Can only view and manage contacts in their own groups
- **Unauthorized**: Cannot access contact management APIs

---

## Error Handling

All endpoints return meaningful error messages:
- Missing required fields
- Invalid Excel format
- Duplicate phone numbers (unique constraint)
- Permission denied
- Group not found

Frontend displays alerts with error messages and success confirmations.

---

## Testing Checklist

- [x] Fixed field reference bug (user → teacher)
- [x] Backend API endpoints implemented
- [x] URL routes configured
- [x] Frontend UI and modals created
- [x] JavaScript functions implemented
- [x] pandas and openpyxl installed
- [ ] Manual contact addition tested
- [ ] Excel import tested with sample file
- [ ] Copy from group tested
- [ ] Contact deletion tested
- [ ] Permission checks verified
- [ ] Error scenarios tested

---

## Next Steps

1. Start Django development server
2. Navigate to groups page
3. Test all contact management features:
   - Add contacts manually
   - Import from Excel (prepare sample .xlsx)
   - Copy from existing group
   - Delete contacts
4. Verify permission checks work correctly
5. Test error handling with invalid inputs
