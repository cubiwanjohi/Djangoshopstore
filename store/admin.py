from django.contrib import admin
from .models import Product, Order, OrderItem, Payment

admin.site.register(Product)

class OrderItemInline(admin.TabularInline):
    model = OrderItem

class PaymentInline(admin.StackedInline):
    model = Payment

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer_name', 'status', 'delivery_status', 'created_at']
    list_filter = ['status', 'delivery_status']
    inlines = [OrderItemInline, PaymentInline]