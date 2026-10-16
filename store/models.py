from django.db import models
from django.urls import reverse

class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('product_detail', args=[self.id])

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid')
    ]

    DELIVERY_STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()

    # Delivery details
    shipping_address = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    shipping_city = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    shipping_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default='processing'
    )

    def total(self):
        return sum(item.subtotal() for item in self.items.all())

class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        related_name='items',
        on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )

    def subtotal(self):
        return self.price * self.quantity

class Payment(models.Model):
    METHOD_CHOICES = [
        ('mpesa', 'M-Pesa'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    order = models.OneToOneField(Order, related_name='payment', on_delete=models.CASCADE)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='mpesa')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    mpesa_phone = models.CharField(max_length=20, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment for Order #{self.order.id} - {self.status}"