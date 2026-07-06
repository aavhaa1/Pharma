from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User, Group

class UserManagementTests(TestCase):
    def setUp(self):
        # Create groups
        self.admin_group = Group.objects.create(name="Admin")
        self.pharmacist_group = Group.objects.create(name="Pharmacist")
        self.cashier_group = Group.objects.create(name="Cashier")

        # Create users with different roles
        self.admin_user = User.objects.create_user(username="admin_user", email="admin@test.com", password="SecurePassword123!")
        self.admin_user.groups.add(self.admin_group)

        self.pharmacist_user = User.objects.create_user(username="pharma_user", email="pharma@test.com", password="SecurePassword123!")
        self.pharmacist_user.groups.add(self.pharmacist_group)

        self.cashier_user = User.objects.create_user(username="cash_user", email="cash@test.com", password="SecurePassword123!")
        self.cashier_user.groups.add(self.cashier_group)

        self.superuser = User.objects.create_superuser(username="super_user", email="super@test.com", password="SecurePassword123!")

        # Common test URLs
        self.list_url = reverse("user_list")
        self.add_url = reverse("user_add")

    def test_anonymous_access_redirects(self):
        """Anonymous users must be redirected to the login page."""
        response = self.client.get(self.list_url)
        login_url = reverse("login")
        self.assertRedirects(response, f"{login_url}?next={self.list_url}")

    def test_role_based_access_restriction(self):
        """Only Superusers and Admin group members can access user management."""
        # Pharmacist should receive 403
        self.client.login(username="pharma_user", password="SecurePassword123!")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 403)
        self.client.logout()

        # Cashier should receive 403
        self.client.login(username="cash_user", password="SecurePassword123!")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 403)
        self.client.logout()

        # Admin user should receive 200
        self.client.login(username="admin_user", password="SecurePassword123!")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.client.logout()

        # Superuser should receive 200
        self.client.login(username="super_user", password="SecurePassword123!")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_user_creation_and_group_assignment(self):
        """Admin can create a user and assign a group automatically."""
        self.client.login(username="admin_user", password="SecurePassword123!")
        
        post_data = {
            "first_name": "Test",
            "last_name": "Pharmacist",
            "username": "new_pharma",
            "email": "new_pharma@test.com",
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
            "role": "Pharmacist",
            "is_active": True,
        }
        
        response = self.client.post(self.add_url, data=post_data)
        self.assertRedirects(response, self.list_url)
        
        # Verify user is created in DB
        user = User.objects.get(username="new_pharma")
        self.assertEqual(user.first_name, "Test")
        self.assertEqual(user.last_name, "Pharmacist")
        self.assertEqual(user.email, "new_pharma@test.com")
        self.assertTrue(user.is_active)
        self.assertTrue(user.groups.filter(name="Pharmacist").exists())

    def test_user_creation_validation(self):
        """Validation errors on create user form."""
        self.client.login(username="admin_user", password="SecurePassword123!")

        # 1. Non-matching passwords
        post_data = {
            "first_name": "Test",
            "last_name": "User",
            "username": "test_mismatch",
            "email": "mismatch@test.com",
            "password": "SecurePassword123!",
            "confirm_password": "DifferentPassword123!",
            "role": "Cashier",
            "is_active": True,
        }
        response = self.client.post(self.add_url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "confirm_password", "Passwords do not match.")

        # 2. Duplicate username
        post_data = {
            "first_name": "Test",
            "last_name": "User",
            "username": "pharma_user", # already exists
            "email": "new_unique@test.com",
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
            "role": "Cashier",
            "is_active": True,
        }
        response = self.client.post(self.add_url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "username", "A user with that username already exists.")

        # 3. Duplicate email
        post_data = {
            "first_name": "Test",
            "last_name": "User",
            "username": "unique_username",
            "email": "pharma@test.com", # already exists
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
            "role": "Cashier",
            "is_active": True,
        }
        response = self.client.post(self.add_url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "email", "A user with that email already exists.")

    def test_user_editing_and_role_change(self):
        """Admin can edit user details and change roles successfully."""
        self.client.login(username="admin_user", password="SecurePassword123!")
        
        edit_url = reverse("user_edit", kwargs={"pk": self.pharmacist_user.pk})
        
        post_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "username": "pharma_user_updated",
            "email": "pharma_updated@test.com",
            "role": "Cashier", # Changed role from Pharmacist to Cashier
            "is_active": True,
        }
        
        response = self.client.post(edit_url, data=post_data)
        self.assertRedirects(response, self.list_url)
        
        # Verify updates in DB
        self.pharmacist_user.refresh_from_db()
        self.assertEqual(self.pharmacist_user.username, "pharma_user_updated")
        self.assertEqual(self.pharmacist_user.first_name, "Updated")
        self.assertEqual(self.pharmacist_user.last_name, "Name")
        self.assertEqual(self.pharmacist_user.email, "pharma_updated@test.com")
        
        # Check groups updated
        self.assertFalse(self.pharmacist_user.groups.filter(name="Pharmacist").exists())
        self.assertTrue(self.pharmacist_user.groups.filter(name="Cashier").exists())

    def test_user_activation_deactivation(self):
        """Admin can activate and deactivate user accounts."""
        self.client.login(username="admin_user", password="SecurePassword123!")

        deactivate_url = reverse("user_deactivate", kwargs={"pk": self.pharmacist_user.pk})
        activate_url = reverse("user_activate", kwargs={"pk": self.pharmacist_user.pk})

        # 1. Deactivate
        # GET confirmation page
        response = self.client.get(deactivate_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/user_confirm_status.html")
        
        # POST deactivation
        response = self.client.post(deactivate_url)
        self.assertRedirects(response, self.list_url)
        self.pharmacist_user.refresh_from_db()
        self.assertFalse(self.pharmacist_user.is_active)

        # 2. Activate
        # GET confirmation page
        response = self.client.get(activate_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/user_confirm_status.html")
        
        # POST activation
        response = self.client.post(activate_url)
        self.assertRedirects(response, self.list_url)
        self.pharmacist_user.refresh_from_db()
        self.assertTrue(self.pharmacist_user.is_active)
