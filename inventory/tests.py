from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from medicines.models import Medicine, Category
from inventory.models import Inventory, InventoryHistory
from inventory.forms import InventoryForm, StockAdjustmentForm

User = get_user_model()

class InventoryTestCase(TestCase):
    def setUp(self):
        # Create groups
        self.admin_group = Group.objects.create(name="Admin")
        self.pharmacist_group = Group.objects.create(name="Pharmacist")
        self.cashier_group = Group.objects.create(name="Cashier")

        # Create users
        self.admin_user = User.objects.create_user(username="admin", password="password123")
        self.admin_user.groups.add(self.admin_group)

        self.pharmacist_user = User.objects.create_user(username="pharmacist", password="password123")
        self.pharmacist_user.groups.add(self.pharmacist_group)

        self.cashier_user = User.objects.create_user(username="cashier", password="password123")
        self.cashier_user.groups.add(self.cashier_group)

        # Create Category & Medicine
        self.category = Category.objects.create(name="Antibiotics", is_active=True)
        self.medicine = Medicine.objects.create(
            name="Amoxicillin",
            brand="Amoxil",
            category=self.category,
            unit="capsule",
            requires_prescription=True,
            purchase_price=10.00,
            selling_price=15.00,
            minimum_stock_level=10,
            is_active=True
        )

    def test_inventory_creation_validations(self):
        # 1. Valid inventory creation
        today = timezone.now().date()
        inv = Inventory(
            medicine=self.medicine,
            batch_no="BATCH001",
            expiry_date=today,
            quantity=100
        )
        inv.full_clean()
        inv.save()
        self.assertEqual(inv.quantity, 100)

        # 2. Expiry date in past validation when creating
        yesterday = today - timedelta(days=1)
        past_inv = Inventory(
            medicine=self.medicine,
            batch_no="BATCH002",
            expiry_date=yesterday,
            quantity=50
        )
        with self.assertRaises(ValidationError):
            past_inv.full_clean()

        # 3. Negative quantity validation
        neg_inv = Inventory(
            medicine=self.medicine,
            batch_no="BATCH003",
            expiry_date=today,
            quantity=-10
        )
        with self.assertRaises(ValidationError):
            neg_inv.full_clean()

    def test_history_creation_on_save_with_history(self):
        today = timezone.now().date()
        inv = Inventory(
            medicine=self.medicine,
            batch_no="BATCH123",
            expiry_date=today,
            quantity=50
        )
        inv.save_with_history(
            user=self.admin_user,
            action="Added",
            quantity_changed=50,
            reason="New Stock",
            quantity_before=0
        )
        
        self.assertEqual(InventoryHistory.objects.count(), 1)
        log = InventoryHistory.objects.first()
        self.assertEqual(log.inventory, inv)
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.action, "Added")
        self.assertEqual(log.quantity_before, 0)
        self.assertEqual(log.quantity_after, 50)
        self.assertEqual(log.quantity_changed, 50)
        self.assertEqual(log.reason, "New Stock")

    def test_inventory_form(self):
        today = timezone.now().date()
        # Valid data
        form = InventoryForm(data={
            "medicine": self.medicine.pk,
            "batch_no": "BATCH-A",
            "expiry_date": today,
            "quantity": 50,
            "location": "Shelf 1"
        })
        self.assertTrue(form.is_valid())

        # Invalid: quantity <= 0
        form_zero = InventoryForm(data={
            "medicine": self.medicine.pk,
            "batch_no": "BATCH-A",
            "expiry_date": today,
            "quantity": 0,
            "location": "Shelf 1"
        })
        self.assertFalse(form_zero.is_valid())
        self.assertIn("Quantity must be greater than 0.", form_zero.errors["quantity"])

        # Invalid: past expiry
        yesterday = today - timedelta(days=1)
        form_past = InventoryForm(data={
            "medicine": self.medicine.pk,
            "batch_no": "BATCH-A",
            "expiry_date": yesterday,
            "quantity": 20,
            "location": "Shelf 1"
        })
        self.assertFalse(form_past.is_valid())
        self.assertIn("Expiry date must be today or in the future.", form_past.errors["expiry_date"])

    def test_stock_adjustment_validation(self):
        # Setup initial stock of 20
        today = timezone.now().date()
        inv = Inventory.objects.create(
            medicine=self.medicine,
            batch_no="BATCH-ADJ",
            expiry_date=today,
            quantity=20
        )

        # 1. Decrease by 10 (Valid: new quantity is 10)
        form_valid = StockAdjustmentForm(
            inventory=inv,
            data={
                "inventory": inv.pk,
                "adjustment_type": "Decrease",
                "quantity_changed": 10,
                "reason": "Damaged"
            }
        )
        self.assertTrue(form_valid.is_valid())

        # 2. Decrease by 25 (Invalid: quantity becomes -5)
        form_invalid = StockAdjustmentForm(
            inventory=inv,
            data={
                "inventory": inv.pk,
                "adjustment_type": "Decrease",
                "quantity_changed": 25,
                "reason": "Damaged"
            }
        )
        self.assertFalse(form_invalid.is_valid())
        self.assertIn("Stock cannot become negative.", form_invalid.non_field_errors())

    def test_role_based_permissions(self):
        # Setup batch
        today = timezone.now().date()
        inv = Inventory.objects.create(
            medicine=self.medicine,
            batch_no="BATCH-PERM",
            expiry_date=today,
            quantity=10
        )

        # 1. Cashier attempts to adjust stock -> should get 403 Forbidden
        self.client.login(username="cashier", password="password123")
        response = self.client.get(reverse("inventory_adjust", kwargs={"pk": inv.pk}))
        self.assertEqual(response.status_code, 403)
        
        response_post = self.client.post(reverse("inventory_adjust", kwargs={"pk": inv.pk}), data={
            "adjustment_type": "Increase",
            "quantity_changed": 5,
            "reason": "Correction"
        })
        self.assertEqual(response_post.status_code, 403)

        # Cashier views list/detail/history -> should get 200 OK
        response_list = self.client.get(reverse("inventory_list"))
        self.assertEqual(response_list.status_code, 200)

        response_detail = self.client.get(reverse("inventory_detail", kwargs={"pk": inv.pk}))
        self.assertEqual(response_detail.status_code, 200)

        response_history = self.client.get(reverse("inventory_history"))
        self.assertEqual(response_history.status_code, 200)

        # 2. Pharmacist attempts to adjust stock -> should get 200 OK (GET) and proceed on POST
        self.client.login(username="pharmacist", password="password123")
        response_pharm = self.client.get(reverse("inventory_adjust", kwargs={"pk": inv.pk}))
        self.assertEqual(response_pharm.status_code, 200)
