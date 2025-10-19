from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
import json

User = get_user_model()


class AuthEndpointsTestCase(APITestCase):
    """Test authentication endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('sms:register')
        self.login_url = reverse('sms:login') 
        self.profile_url = reverse('sms:profile')
        
        # Create a test user
        self.test_user = User.objects.create_user(
            email='testuser@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            role='teacher'
        )
    
    def test_user_registration_success(self):
        """Test successful user registration"""
        data = {
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'teacher'
        }
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('tokens', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['email'], 'newuser@example.com')
    
    def test_user_registration_duplicate_email(self):
        """Test registration with duplicate email returns JSON error"""
        data = {
            'email': 'testuser@example.com',  # Already exists
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'teacher'
        }
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_user_login_success(self):
        """Test successful login"""
        data = {
            'email': 'testuser@example.com',
            'password': 'testpass123'
        }
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)
        self.assertIn('user', response.data)
    
    def test_user_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        data = {
            'email': 'testuser@example.com',
            'password': 'wrongpassword'
        }
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_profile_endpoint_authenticated(self):
        """Test profile endpoint with valid token"""
        # Get token for test user
        refresh = RefreshToken.for_user(self.test_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'testuser@example.com')
    
    def test_profile_endpoint_unauthenticated(self):
        """Test profile endpoint without token returns 401"""
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SidebarEndpointTestCase(APITestCase):
    """Test sidebar endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.sidebar_url = reverse('sms:api_sidebar')
        
        # Create test user
        self.test_user = User.objects.create_user(
            email='testuser@example.com',
            password='testpass123',
            role='teacher'
        )
        
        # Get auth token
        refresh = RefreshToken.for_user(self.test_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_sidebar_endpoint_authenticated(self):
        """Test sidebar returns HTML for authenticated user"""
        response = self.client.get(self.sidebar_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/html', response['Content-Type'])
        # Should contain sidebar HTML structure
        self.assertIn('sidebar', response.content.decode())
    
    def test_sidebar_endpoint_unauthenticated(self):
        """Test sidebar requires authentication"""
        client = APIClient()  # No auth
        response = client.get(self.sidebar_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class FrontendRoutesTestCase(TestCase):
    """Test frontend HTML routes work"""
    
    def setUp(self):
        # Create test user for login-required views
        self.test_user = User.objects.create_user(
            email='testuser@example.com',
            password='testpass123',
            role='teacher'
        )
    
    def test_login_page_loads(self):
        """Test login page loads correctly"""
        response = self.client.get('/login/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, 'login', html=False)  # Should contain login form/content
    
    def test_dashboard_requires_login(self):
        """Test dashboard redirects unauthenticated users"""
        response = self.client.get('/dashboard/')
        
        # Should redirect to login or return 302
        self.assertIn(response.status_code, [302, 403])
    
    def test_dashboard_loads_for_authenticated_user(self):
        """Test dashboard loads for authenticated user"""
        # Login the user
        self.client.login(email='testuser@example.com', password='testpass123')
        
        response = self.client.get('/dashboard/')
        
        # Should load successfully or redirect to proper auth
        self.assertIn(response.status_code, [200, 302])


if __name__ == '__main__':
    import django
    from django.conf import settings
    from django.test.utils import get_runner
    
    # Run tests
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["tests"])