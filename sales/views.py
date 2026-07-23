from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum, F
from django.utils import timezone
from decimal import Decimal
from django.http import HttpResponse

from medicines.models import Medicine
from inventory.models import Inventory
from .models import Sale, SaleItem

class SaleListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'sales/sale_list.html'
    context_object_name = 'sales'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Search by Invoice or Customer
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(invoice_number__icontains=q) |
                Q(customer_name__icontains=q)
            )

        # Date Filter
        date_filter = self.request.GET.get('date', '').strip()
        if date_filter:
            queryset = queryset.filter(sale_date=date_filter)

        # Payment Filter
        payment = self.request.GET.get('payment_method', '').strip()
        if payment:
            queryset = queryset.filter(payment_method=payment)

        return queryset


class SaleCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'sales/sale_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Search medicine to add to cart
        q = self.request.GET.get('q', '').strip()
        medicines = Medicine.objects.filter(is_active=True)
        if q:
            medicines = medicines.filter(
                Q(name__icontains=q) |
                Q(brand__icontains=q)
            )
        context['medicines'] = medicines[:10]
        context['cart'] = self.request.session.get('cart', {})
        return context


class CartView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        cart = request.session.get('cart', {})
        # Load actual medicine objects to get selling price, unit, and name
        cart_items = []
        subtotal = Decimal('0.00')
        
        for med_id, item in cart.items():
            medicine = get_object_or_404(Medicine, pk=med_id)
            total = Decimal(str(item['quantity'])) * medicine.selling_price
            subtotal += total
            cart_items.append({
                'medicine': medicine,
                'quantity': item['quantity'],
                'total_price': total
            })
            
        return render(request, 'sales/cart.html', {
            'cart_items': cart_items,
            'subtotal': subtotal
        })

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        medicine_id = request.POST.get('medicine_id')
        
        cart = request.session.get('cart', {})
        
        if action == 'add':
            qty = int(request.POST.get('quantity', 1))
            if qty <= 0:
                messages.error(request, "Quantity must be greater than zero.")
                return redirect('sale_new')
                
            medicine = get_object_or_404(Medicine, pk=medicine_id, is_active=True)
            
            # Check unexpired stock
            today = timezone.now().date()
            available_stock = Inventory.objects.filter(
                medicine=medicine,
                expiry_date__gte=today,
                quantity__gt=0
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            current_cart_qty = cart.get(str(medicine_id), {}).get('quantity', 0)
            new_qty = current_cart_qty + qty
            
            if new_qty > available_stock:
                messages.error(request, f"Insufficient stock for {medicine.name}. Available unexpired: {available_stock}")
                return redirect('sale_new')
                
            cart[str(medicine_id)] = {
                'quantity': new_qty
            }
            request.session['cart'] = cart
            messages.success(request, f"Item added to cart.")
            
        elif action == 'update':
            qty = int(request.POST.get('quantity', 1))
            if qty <= 0:
                cart.pop(str(medicine_id), None)
            else:
                medicine = get_object_or_404(Medicine, pk=medicine_id, is_active=True)
                today = timezone.now().date()
                available_stock = Inventory.objects.filter(
                    medicine=medicine,
                    expiry_date__gte=today,
                    quantity__gt=0
                ).aggregate(total=Sum('quantity'))['total'] or 0
                
                if qty > available_stock:
                    messages.error(request, f"Cannot update. Max available unexpired: {available_stock}")
                    return redirect('cart_view')
                    
                cart[str(medicine_id)] = {
                    'quantity': qty
                }
            request.session['cart'] = cart
            messages.success(request, "Item quantity updated.")
            
        elif action == 'remove':
            cart.pop(str(medicine_id), None)
            request.session['cart'] = cart
            messages.success(request, "Item removed from cart.")
            
        elif action == 'clear':
            request.session['cart'] = {}
            messages.success(request, "Cart cleared.")
            
        return redirect('cart_view')


class CheckoutView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        cart = request.session.get('cart', {})
        if not cart:
            messages.error(request, "Your cart is empty.")
            return redirect('sale_new')
            
        cart_items = []
        subtotal = Decimal('0.00')
        for med_id, item in cart.items():
            medicine = get_object_or_404(Medicine, pk=med_id)
            total = Decimal(str(item['quantity'])) * medicine.selling_price
            subtotal += total
            cart_items.append({
                'medicine': medicine,
                'quantity': item['quantity'],
                'total_price': total
            })
            
        return render(request, 'sales/checkout.html', {
            'cart_items': cart_items,
            'subtotal': subtotal
        })

    def post(self, request, *args, **kwargs):
        cart = request.session.get('cart', {})
        if not cart:
            messages.error(request, "Your cart is empty.")
            return redirect('sale_new')

        customer_name = request.POST.get('customer_name', '').strip()
        payment_method = request.POST.get('payment_method', 'Cash')
        discount = Decimal(request.POST.get('discount', '0.00') or '0.00')
        tax = Decimal(request.POST.get('tax', '0.00') or '0.00')
        
        today = timezone.now().date()
        
        try:
            with transaction.atomic():
                # 1. Validate items stock and status before deduction
                subtotal = Decimal('0.00')
                sale_items_data = []
                
                for med_id, item in cart.items():
                    medicine = get_object_or_404(Medicine, pk=med_id)
                    if not medicine.is_active:
                        raise ValueError(f"{medicine.name} is no longer active.")
                        
                    qty_requested = item['quantity']
                    
                    # Unexpired batches for this medicine ordered by expiry date (FIFO)
                    batches = Inventory.objects.filter(
                        medicine=medicine,
                        expiry_date__gte=today,
                        quantity__gt=0
                    ).order_by('expiry_date')
                    
                    total_available = batches.aggregate(total=Sum('quantity'))['total'] or 0
                    if qty_requested > total_available:
                        raise ValueError(f"Not enough unexpired stock for {medicine.name}. Requested: {qty_requested}, Available: {total_available}")
                        
                    subtotal += Decimal(str(qty_requested)) * medicine.selling_price
                    sale_items_data.append((medicine, qty_requested, batches))
                
                # 2. Create Sale
                invoice_number = Sale.generate_next_invoice_number()
                total_amount = subtotal - discount + tax
                if total_amount < 0:
                    total_amount = Decimal('0.00')
                    
                sale = Sale.objects.create(
                    invoice_number=invoice_number,
                    customer_name=customer_name,
                    payment_method=payment_method,
                    subtotal=subtotal,
                    discount=discount,
                    tax=tax,
                    total_amount=total_amount,
                    cashier=request.user
                )

                # 3. Deduct FIFO stock and log history
                for medicine, qty_requested, batches in sale_items_data:
                    remaining_qty = qty_requested
                    for batch in batches:
                        if remaining_qty <= 0:
                            break
                            
                        deduct_qty = min(remaining_qty, batch.quantity)
                        
                        # Create SaleItem
                        SaleItem.objects.create(
                            sale=sale,
                            medicine=medicine,
                            inventory_batch=batch,
                            quantity=deduct_qty,
                            unit_price=medicine.selling_price,
                            total_price=Decimal(str(deduct_qty)) * medicine.selling_price
                        )
                        
                        # Deduct from batch
                        quantity_before = batch.quantity
                        batch.quantity -= deduct_qty
                        batch.save_with_history(
                            user=request.user,
                            action="Removed",
                            quantity_changed=-deduct_qty,
                            reason="Sale",
                            quantity_before=quantity_before
                        )
                        
                        remaining_qty -= deduct_qty
                
                # Clear Cart
                request.session['cart'] = {}
                messages.success(request, "Sale completed successfully.")
                messages.info(request, "Invoice generated successfully.")
                return redirect('sale_detail', pk=sale.pk)
                
        except Exception as e:
            messages.error(request, f"Checkout failed: {str(e)}")
            return redirect('checkout_view')


class SaleDetailView(LoginRequiredMixin, DetailView):
    model = Sale
    template_name = 'sales/sale_detail.html'
    context_object_name = 'sale'


class InvoiceView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        sale = get_object_or_404(Sale, pk=pk)
        
        # Check if PDF download is requested
        if request.GET.get('format') == 'pdf':
            return self.generate_pdf(sale)
            
        return render(request, 'sales/invoice.html', {
            'sale': sale
        })

    def generate_pdf(self, sale):
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{sale.invoice_number}.pdf"'

        doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        story = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            textColor=colors.HexColor('#0d6efd'),
            fontSize=24,
            spaceAfter=12
        )
        meta_style = ParagraphStyle(
            'MetaStyle',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#333333')
        )
        
        # Pharmacy Header
        story.append(Paragraph("PharmaCare Pharmacy", title_style))
        story.append(Paragraph("123 Health Street, Clinic District<br/>Phone: +1-555-0199 | Email: contact@pharmacare.com", meta_style))
        story.append(Spacer(1, 20))
        
        # Invoice Meta Columns
        meta_data = [
            [Paragraph(f"<b>Invoice No:</b> {sale.invoice_number}", meta_style), Paragraph(f"<b>Date:</b> {sale.sale_date}", meta_style)],
            [Paragraph(f"<b>Cashier:</b> {sale.cashier.username}", meta_style), Paragraph(f"<b>Customer:</b> {sale.customer_name or 'Walk-in Customer'}", meta_style)],
            [Paragraph(f"<b>Payment Method:</b> {sale.payment_method}", meta_style), ""]
        ]
        meta_table = Table(meta_data, colWidths=[270, 270])
        meta_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 20))
        
        # Items Table header and rows
        table_style = ParagraphStyle('TableStyle', parent=styles['Normal'], fontSize=9, leading=11)
        header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=colors.white)
        
        table_data = [
            [
                Paragraph("Medicine", header_style),
                Paragraph("Batch No", header_style),
                Paragraph("Qty", header_style),
                Paragraph("Unit Price", header_style),
                Paragraph("Total", header_style)
            ]
        ]
        
        for item in sale.items.all():
            table_data.append([
                Paragraph(item.medicine.name, table_style),
                Paragraph(item.inventory_batch.batch_no, table_style),
                Paragraph(str(item.quantity), table_style),
                Paragraph(f"Nrs. {item.unit_price}", table_style),
                Paragraph(f"Nrs. {item.total_price}", table_style)
            ])
            
        # Pricing totals rows
        table_data.append(["", "", "", Paragraph("<b>Subtotal:</b>", table_style), Paragraph(f"Nrs. {sale.subtotal}", table_style)])
        table_data.append(["", "", "", Paragraph("<b>Discount:</b>", table_style), Paragraph(f"-Nrs. {sale.discount}", table_style)])
        table_data.append(["", "", "", Paragraph("<b>Tax:</b>", table_style), Paragraph(f"+Nrs. {sale.tax}", table_style)])
        table_data.append(["", "", "", Paragraph("<b>Grand Total:</b>", table_style), Paragraph(f"Nrs. {sale.total_amount}", table_style)])
        
        col_widths = [200, 100, 60, 90, 90]
        items_table = Table(table_data, colWidths=col_widths)
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-5), 0.5, colors.HexColor('#dddddd')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LINEABOVE', (3,-4), (4,-1), 1, colors.HexColor('#000000')),
        ]))
        
        story.append(items_table)
        story.append(Spacer(1, 30))
        story.append(Paragraph("<center>Thank you for choosing PharmaCare!</center>", meta_style))
        
        doc.build(story)
        return response
