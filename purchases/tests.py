from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal

from suppliers.models import Supplier
from medicines.models import Category, Medicine
from purchases.models import Purchase, PurchaseItem
from inventory.models import Inventory, InventoryHistory

User = get_user_model()

class PurchaseModuleTestCase(TestCase):
    def setUp(self):
        # Create user roles groups
        self.admin_group = Group.objects.create(name="Admin")
        self.pharmacist_group = Group.objects.create(name="Pharmacist")
        self.cashier_group = Group.objects.create(name="Cashier")
        
        # Create users
        self.admin_user = User.objects.create_user(username="admin_user", password="password123")
        self.admin_user.groups.add(self.admin_group)
        
        self.pharmacist_user = User.objects.create_user(username="pharmacist_user", password="password123")
        self.pharmacist_user.groups.add(self.pharmacist_group)
        
        self.cashier_user = User.objects.create_user(username="cashier_user", password="password123")
        self.cashier_user.groups.add(self.cashier_group)

        # Create Category and Medicine
        self.category = Category.objects.create(name="Antibiotics", description="Antibiotics drugs")
        self.medicine = Medicine.objects.create(
            name="Amoxicillin 500mg",
            category=self.category,
            purchase_price=Decimal('2.00'),
            selling_price=Decimal('3.00'),
            minimum_stock_level=10,
            is_active=True
        )

        # Create Supplier
        self.supplier = Supplier.objects.create(name="PharmaDistributors Inc", is_active=True)

    def test_purchase_creation_flow(self):
        self.client.login(username="pharmacist_user", password="password123")
        
        # Create purchase order
        url = reverse('purchase_add')
        data = {
            'supplier': self.supplier.pk,
            'invoice_number': 'INV-12345',
            'purchase_date': '2026-07-06',
            'remarks': 'Test PO creation',
            
            # Management Form keys for inline formset
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            
            # Formset item 1
            'items-0-medicine': self.medicine.pk,
            'items-0-batch_no': 'B-999',
            'items-0-expiry_date': '2027-12-31',
            'items-0-quantity': '50',
            'items-0-package_type': 'Box',
            'items-0-units_per_package': '1',
            'items-0-unit_cost': '2.50',
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302) # Redirects on success
        
        # Verify Purchase was saved correctly
        purchase = Purchase.objects.get(invoice_number='INV-12345')
        self.assertEqual(purchase.status, 'Pending')
        self.assertEqual(purchase.created_by, self.pharmacist_user)
        self.assertEqual(purchase.total_amount, Decimal('125.00')) # 50 * 2.50
        
        # Verify PurchaseItem was saved correctly
        self.assertEqual(purchase.items.count(), 1)
        item = purchase.items.first()
        self.assertEqual(item.quantity, 50)
        self.assertEqual(item.total_cost, Decimal('125.00'))

    def test_cashier_cannot_create_purchase(self):
        self.client.login(username="cashier_user", password="password123")
        url = reverse('purchase_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403) # Cashier gets 403 Forbidden

    def test_receive_purchase_updates_inventory_and_logs_history(self):
        # Setup pre-existing PO
        purchase = Purchase.objects.create(
            supplier=self.supplier,
            invoice_number='INV-REC-1',
            purchase_date=timezone.now().date(),
            created_by=self.admin_user,
            status='Pending'
        )
        item = PurchaseItem.objects.create(
            purchase=purchase,
            medicine=self.medicine,
            batch_no='BATCH-ABC',
            expiry_date=timezone.now().date() + timezone.timedelta(days=180),
            quantity=100,
            unit_cost=Decimal('1.50'),
            total_cost=Decimal('150.00')
        )
        
        self.client.login(username="admin_user", password="password123")
        
        # Verify inventory and history is currently empty
        self.assertEqual(Inventory.objects.filter(medicine=self.medicine, batch_no='BATCH-ABC').count(), 0)
        self.assertEqual(InventoryHistory.objects.count(), 0)

        # Post to receive PO
        url = reverse('purchase_receive', args=[purchase.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        
        # Reload PO
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'Received')
        
        # Verify Inventory has been updated
        inventory = Inventory.objects.get(medicine=self.medicine, batch_no='BATCH-ABC')
        self.assertEqual(inventory.quantity, 100)
        self.assertEqual(inventory.expiry_date, item.expiry_date)
        
        # Verify History Log
        self.assertEqual(InventoryHistory.objects.count(), 1)
        log = InventoryHistory.objects.first()
        self.assertEqual(log.inventory, inventory)
        self.assertEqual(log.action, 'Added')
        self.assertEqual(log.quantity_changed, 100)
        self.assertEqual(log.quantity_before, 0)
        self.assertEqual(log.quantity_after, 100)
        self.assertEqual(log.reason, 'New Stock')
        self.assertEqual(log.user, self.admin_user)

    def test_cancel_pending_purchase(self):
        purchase = Purchase.objects.create(
            supplier=self.supplier,
            invoice_number='INV-CAN-1',
            purchase_date=timezone.now().date(),
            created_by=self.admin_user,
            status='Pending'
        )
        
        self.client.login(username="pharmacist_user", password="password123")
        
        url = reverse('purchase_cancel', args=[purchase.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'Cancelled')
        
        # Verify no inventory was created
        self.assertEqual(Inventory.objects.count(), 0)
        self.assertEqual(InventoryHistory.objects.count(), 0)

    def test_cannot_edit_received_purchase(self):
        purchase = Purchase.objects.create(
            supplier=self.supplier,
            invoice_number='INV-EDIT-1',
            purchase_date=timezone.now().date(),
            created_by=self.admin_user,
            status='Received'
        )
        
        self.client.login(username="admin_user", password="password123")
        
        # Attempting to edit redirects to detail with error
        url = reverse('purchase_edit', args=[purchase.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
