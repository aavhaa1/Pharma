from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal

from medicines.models import Category, Medicine
from inventory.models import Inventory, InventoryHistory
from sales.models import Sale, SaleItem

User = get_user_model()

class SalesTestCase(TestCase):
    def setUp(self):
        # Create groups and cashier
        self.cashier_group = Group.objects.create(name="Cashier")
        self.cashier_user = User.objects.create_user(username="cashier_user", password="password123")
        self.cashier_user.groups.add(self.cashier_group)

        # Create Category and Medicine
        self.category = Category.objects.create(name="Painkillers", description="Relieve pain")
        self.medicine = Medicine.objects.create(
            name="Paracetamol 500mg",
            category=self.category,
            purchase_price=Decimal('1.00'),
            selling_price=Decimal('1.50'),
            minimum_stock_level=5,
            is_active=True
        )

        # Create unexpired batches (FIFO: Batch A expires first, Batch B expires later)
        self.batch_a = Inventory.objects.create(
            medicine=self.medicine,
            batch_no="BATCH-A",
            expiry_date=timezone.now().date() + timezone.timedelta(days=10),
            quantity=30
        )
        self.batch_b = Inventory.objects.create(
            medicine=self.medicine,
            batch_no="BATCH-B",
            expiry_date=timezone.now().date() + timezone.timedelta(days=90),
            quantity=50
        )

    def test_session_cart_addition_and_validation(self):
        self.client.login(username="cashier_user", password="password123")
        
        # Test adding to cart
        url = reverse('cart_view')
        response = self.client.post(url, {
            'action': 'add',
            'medicine_id': self.medicine.pk,
            'quantity': '10'
        })
        self.assertEqual(response.status_code, 302) # Redirect to catalogue
        
        cart = self.client.session['cart']
        self.assertIn(str(self.medicine.pk), cart)
        self.assertEqual(cart[str(self.medicine.pk)]['quantity'], 10)

        # Test adding more than available stock (max available is 80)
        response2 = self.client.post(url, {
            'action': 'add',
            'medicine_id': self.medicine.pk,
            'quantity': '75' # Total 10 + 75 = 85 > 80
        })
        self.assertEqual(response2.status_code, 302)
        # Should stay at previous quantity
        self.assertEqual(self.client.session['cart'][str(self.medicine.pk)]['quantity'], 10)

    def test_fifo_checkout_deduction_and_history(self):
        self.client.login(username="cashier_user", password="password123")
        
        # Add 40 units to cart (which should exhaust Batch A of 30 units and take 10 units from Batch B)
        session = self.client.session
        session['cart'] = {
            str(self.medicine.pk): {'quantity': 40}
        }
        session.save()

        url = reverse('checkout_view')
        # Post checkout form
        response = self.client.post(url, {
            'customer_name': 'John Doe',
            'payment_method': 'Cash',
            'discount': '5.00',
            'tax': '2.50'
        })
        self.assertEqual(response.status_code, 302) # Redirects to detail
        
        # Verify Sale entry
        sale = Sale.objects.first()
        self.assertIsNotNone(sale)
        self.assertEqual(sale.invoice_number, "INV-00001")
        self.assertEqual(sale.customer_name, "John Doe")
        # Subtotal: 40 * 1.50 = 60.00
        # Grand Total: 60 - 5 + 2.50 = 57.50
        self.assertEqual(sale.subtotal, Decimal('60.00'))
        self.assertEqual(sale.total_amount, Decimal('57.50'))

        # Verify FIFO Inventory changes
        self.batch_a.refresh_from_db()
        self.batch_b.refresh_from_db()
        self.assertEqual(self.batch_a.quantity, 0) # Batch A fully exhausted
        self.assertEqual(self.batch_b.quantity, 40) # 50 - 10 = 40

        # Verify SaleItems created
        sale_items = SaleItem.objects.all().order_by('id')
        self.assertEqual(sale_items.count(), 2)
        self.assertEqual(sale_items[0].inventory_batch, self.batch_a)
        self.assertEqual(sale_items[0].quantity, 30)
        self.assertEqual(sale_items[1].inventory_batch, self.batch_b)
        self.assertEqual(sale_items[1].quantity, 10)

        # Verify History Logs in InventoryHistory
        history = InventoryHistory.objects.filter(action='Removed').order_by('id')
        self.assertEqual(history.count(), 2)
        self.assertEqual(history[0].inventory, self.batch_a)
        self.assertEqual(history[0].quantity_changed, -30)
        self.assertEqual(history[1].inventory, self.batch_b)
        self.assertEqual(history[1].quantity_changed, -10)

    def test_printable_invoice_and_pdf_download(self):
        sale = Sale.objects.create(
            invoice_number="INV-TEST-99",
            customer_name="Jane Smith",
            payment_method="Card",
            subtotal=Decimal('30.00'),
            discount=Decimal('0.00'),
            tax=Decimal('0.00'),
            total_amount=Decimal('30.00'),
            cashier=self.cashier_user
        )
        SaleItem.objects.create(
            sale=sale,
            medicine=self.medicine,
            inventory_batch=self.batch_a,
            quantity=20,
            unit_price=Decimal('1.50'),
            total_price=Decimal('30.00')
        )

        self.client.login(username="cashier_user", password="password123")
        
        # Test printable page view
        url = reverse('invoice_view', args=[sale.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jane Smith")

        # Test PDF format download
        response_pdf = self.client.get(url + "?format=pdf")
        self.assertEqual(response_pdf.status_code, 200)
        self.assertEqual(response_pdf['content-type'], 'application/pdf')
