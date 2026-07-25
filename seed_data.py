import os
import django
import random
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacare.settings')
django.setup()

from django.contrib.auth.models import User, Group
from django.utils import timezone
from medicines.models import Category, Medicine
from suppliers.models import Supplier
from inventory.models import Inventory, InventoryBatch, InventoryHistory
from purchases.models import Purchase, PurchaseItem
from sales.models import Sale, SaleItem

def seed_data():
    print("Seeding database with comprehensive dummy data...")

    # 1. Groups & Users
    admin_group, _ = Group.objects.get_or_create(name="Admin")
    pharmacist_group, _ = Group.objects.get_or_create(name="Pharmacist")
    cashier_group, _ = Group.objects.get_or_create(name="Cashier")

    # Pharmacist user
    if not User.objects.filter(username="pharmacist").exists():
        u = User.objects.create_user("pharmacist", "pharmacist@example.com", "password123", first_name="Sarah", last_name="Jenkins")
        u.groups.add(pharmacist_group)
        print("Created Pharmacist user (pharmacist / password123)")

    # Cashier user
    if not User.objects.filter(username="cashier").exists():
        u = User.objects.create_user("cashier", "cashier@example.com", "password123", first_name="Alex", last_name="Rivera")
        u.groups.add(cashier_group)
        print("Created Cashier user (cashier / password123)")

    admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()

    # 2. Categories
    categories_data = [
        ("Antibiotics", "Medications used to treat bacterial infections."),
        ("Analgesics & Pain Relief", "Pain relievers and anti-inflammatory drugs."),
        ("Cardiovascular", "Medications for heart and blood pressure management."),
        ("Vitamins & Supplements", "Dietary supplements and daily vitamins."),
        ("Dermatological", "Skin care treatments, ointments, and creams."),
        ("Respiratory & Cold", "Cough syrups, antihistamines, and decongestants."),
        ("Gastrointestinal", "Digestive health, antacids, and probiotics."),
        ("Diabetes Care", "Insulin, testing supplies, and blood sugar management."),
    ]
    categories = []
    for name, desc in categories_data:
        cat, _ = Category.objects.get_or_create(name=name, defaults={"description": desc, "is_active": True})
        categories.append(cat)

    # 3. Suppliers
    suppliers_data = [
        ("Himalaya Pharma Pvt Ltd", "Rajesh Sharma", "9841234567", "contact@himalayapharma.com", "Kathmandu, Nepal"),
        ("Medisales Nepal Supplier", "Sita Thapa", "9801987654", "sales@medisales.com.np", "Lalitpur, Nepal"),
        ("Everest Healthcare Corp", "Bikash Shrestha", "9851011223", "info@everesthealth.com", "Pokhara, Nepal"),
        ("Apex BioMed Distributors", "Pooja Gurung", "9812334455", "support@apexbiomed.com", "Biratnagar, Nepal"),
        ("Global LifeCare Pharma", "Anil Karki", "9860998877", "orders@globallifecare.com", "Chitwan, Nepal"),
    ]
    suppliers = []
    for name, contact, phone, email, addr in suppliers_data:
        sup, _ = Supplier.objects.get_or_create(
            name=name,
            defaults={
                "contact_person": contact,
                "phone": phone,
                "email": email,
                "address": addr,
                "is_active": True
            }
        )
        suppliers.append(sup)

    # 4. Medicines
    medicines_data = [
        # Name, Category Name, Purchase Price, Selling Price, Box Unit, Rx, LowStockLevel
        ("Amoxicillin 500mg Capsule", "Antibiotics", 12.00, 18.00, 10, True, 50),
        ("Azithromycin 250mg Tablet", "Antibiotics", 25.00, 38.00, 6, True, 30),
        ("Ciprofloxacin 500mg", "Antibiotics", 15.00, 22.50, 10, True, 40),
        ("Paracetamol 650mg (Dolo)", "Analgesics & Pain Relief", 2.00, 3.50, 15, False, 100),
        ("Ibuprofen 400mg Tablet", "Analgesics & Pain Relief", 3.50, 5.50, 10, False, 80),
        ("Combiflam Pain Relief", "Analgesics & Pain Relief", 4.00, 6.50, 10, False, 60),
        ("Amlodipine 5mg Tablet", "Cardiovascular", 5.00, 8.00, 14, True, 40),
        ("Telmisartan 40mg", "Cardiovascular", 8.50, 13.00, 10, True, 30),
        ("Atorvastatin 10mg", "Cardiovascular", 11.00, 17.50, 10, True, 25),
        ("Vitamin C 500mg Chewable", "Vitamins & Supplements", 1.50, 3.00, 20, False, 150),
        ("Multivitamin + Zinc Cap", "Vitamins & Supplements", 8.00, 14.00, 10, False, 50),
        ("Vitamin D3 60K Softgel", "Vitamins & Supplements", 18.00, 28.00, 4, False, 20),
        ("Hydrocortisone Cream 1%", "Dermatological", 45.00, 70.00, 1, False, 15),
        ("Ketoconazole Anti-Dandruff Shampoo", "Dermatological", 120.00, 185.00, 1, False, 10),
        ("Benadryl Cough Syrup 100ml", "Respiratory & Cold", 65.00, 95.00, 1, False, 20),
        ("Cetirizine 10mg Tablet", "Respiratory & Cold", 1.20, 2.50, 10, False, 100),
        ("Pantoprazole 40mg Gastro-Resistant", "Gastrointestinal", 6.00, 9.50, 10, True, 60),
        ("Digene Antacid Gel 200ml", "Gastrointestinal", 85.00, 125.00, 1, False, 15),
        ("Metformin 500mg SR Tablet", "Diabetes Care", 3.00, 5.00, 15, True, 100),
        ("Glimepiride 2mg Tablet", "Diabetes Care", 6.50, 10.00, 10, True, 40),
    ]

    medicines = []
    for name, cat_name, p_price, s_price, units_pkg, rx, min_stock in medicines_data:
        cat = next(c for c in categories if c.name == cat_name)
        med, _ = Medicine.objects.get_or_create(
            name=name,
            defaults={
                "category": cat,
                "purchase_price": Decimal(str(p_price)),
                "selling_price": Decimal(str(s_price)),
                "units_per_package": units_pkg,
                "requires_prescription": rx,
                "minimum_stock_level": min_stock,
                "is_active": True
            }
        )
        medicines.append(med)

    print(f"Created/Verified {len(medicines)} medicines across {len(categories)} categories.")

    # 5. Purchases & Inventory Batches
    today = timezone.now().date()
    batch_counter = 1001

    for i in range(8):
        sup = random.choice(suppliers)
        p_date = today - timedelta(days=random.randint(5, 60))
        inv_num = f"INV-2026-{batch_counter}"
        batch_counter += 1

        purchase, created = Purchase.objects.get_or_create(
            invoice_number=inv_num,
            defaults={
                "supplier": sup,
                "purchase_date": p_date,
                "total_amount": Decimal('0.00'),
                "remarks": f"Bulk seasonal shipment from {sup.name}",
                "created_by": admin_user
            }
        )

        if created:
            total_purch_amt = Decimal('0.00')
            # Select 3-5 random medicines for this purchase
            sample_meds = random.sample(medicines, random.randint(3, 5))

            for med in sample_meds:
                pkgs = random.randint(5, 20)
                total_qty = pkgs * med.units_per_package
                unit_cost = med.purchase_price
                line_total = Decimal(str(total_qty)) * unit_cost

                # Expiry date (mix of active and 1-2 near-expiry/expired for testing reports)
                if random.random() < 0.15:
                    exp_date = today - timedelta(days=random.randint(1, 30)) # Expired
                elif random.random() < 0.25:
                    exp_date = today + timedelta(days=random.randint(5, 25)) # Expiring soon
                else:
                    exp_date = today + timedelta(days=random.randint(90, 400)) # Fresh

                batch_no = f"BAT-{random.randint(10000, 99999)}"

                PurchaseItem.objects.create(
                    purchase=purchase,
                    medicine=med,
                    batch_no=batch_no,
                    expiry_date=exp_date,
                    quantity=total_qty,
                    package_type="Box",
                    units_per_package=med.units_per_package,
                    unit_cost=unit_cost,
                    total_cost=line_total
                )

                # Create Inventory Batch
                inv_batch = InventoryBatch(
                    medicine=med,
                    batch_no=batch_no,
                    expiry_date=exp_date,
                    quantity=total_qty
                )
                super(InventoryBatch, inv_batch).save()

                # History log
                InventoryHistory.objects.create(
                    inventory=inv_batch,
                    user=admin_user,
                    action="Added",
                    quantity_changed=total_qty,
                    quantity_before=0,
                    quantity_after=total_qty,
                    reason="Purchase Order Received"
                )

                # Update Aggregate Inventory
                inv_record, _ = Inventory.objects.get_or_create(medicine=med)
                inv_record.update_stock()

                total_purch_amt += line_total

            purchase.total_amount = total_purch_amt
            purchase.save()

    print("Created Purchases & Inventory Batches.")

    # 6. Sales History (spanning last 30 days)
    customer_names = [
        "Ramesh Adhikari", "Priya Sharma", "Sunil Maharjan", "Gita Karki",
        "Deepak Joshi", "Sujata Bhattarai", "Bishal Shrestha", "Walk-in Customer"
    ]
    payment_methods = ["Cash", "Card", "Mobile Payment"]

    for d in range(25, -1, -1):
        sale_date = timezone.now() - timedelta(days=d, hours=random.randint(1, 8))
        num_sales_today = random.randint(1, 4)

        for _ in range(num_sales_today):
            inv_no = Sale.generate_next_invoice_number()
            cust = random.choice(customer_names)
            pm = random.choice(payment_methods)

            # Pick 1-3 available medicines with stock
            avail_meds = [m for m in medicines if m.available_stock > 5]
            if not avail_meds:
                continue

            chosen_meds = random.sample(avail_meds, min(len(avail_meds), random.randint(1, 3)))

            subtotal = Decimal('0.00')
            items_to_create = []

            for med in chosen_meds:
                qty = random.randint(1, 5)
                unit_price = med.selling_price
                line_total = Decimal(str(qty)) * unit_price
                subtotal += line_total
                items_to_create.append((med, qty, unit_price, line_total))

            disc = Decimal(str(random.choice([0, 0, 5, 10, 15]))) if subtotal > 20 else Decimal('0.00')
            tax = Decimal('0.00')
            total_amt = subtotal - disc + tax

            sale = Sale.objects.create(
                invoice_number=inv_no,
                customer_name=cust,
                cashier=admin_user,
                payment_method=pm,
                subtotal=subtotal,
                discount=disc,
                tax=tax,
                total_amount=total_amt,
                created_at=sale_date
            )

            for med, qty, unit_price, line_total in items_to_create:
                # Find available batch
                batch = InventoryBatch.objects.filter(medicine=med, quantity__gte=qty).first()
                if not batch:
                    batch = InventoryBatch.objects.filter(medicine=med, quantity__gt=0).first()
                if not batch:
                    batch = InventoryBatch.objects.filter(medicine=med).first()

                if batch:
                    SaleItem.objects.create(
                        sale=sale,
                        medicine=med,
                        inventory_batch=batch,
                        quantity=qty,
                        unit_price=unit_price,
                        total_price=line_total
                    )
                    if batch.quantity >= qty:
                        batch.quantity -= qty
                    else:
                        batch.quantity = 0
                    batch.save()

                    inv_rec, _ = Inventory.objects.get_or_create(medicine=med)
                    inv_rec.update_stock()

    print("Seeded Sales history successfully!")
    print("Database seeding completed cleanly!")

if __name__ == "__main__":
    seed_data()
