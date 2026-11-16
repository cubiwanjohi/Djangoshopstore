
from django import forms

from store.models import Product
from .models import InventorySettings


class StockAdjustmentForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.all().order_by("name"),
        empty_label="Select a product",
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
        label="Product",
    )

    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": 1,
                "placeholder": "Enter quantity",
            }
        ),
        label="Quantity",
        help_text="Enter the number of units to adjust.",
    )

    note = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Enter the reason for this stock adjustment",
            }
        ),
        label="Reason / Note",
    )

class LowStockThresholdForm(forms.ModelForm):
    class Meta:
        model = InventorySettings
        fields = ["low_stock_threshold"]
        labels = {
            "low_stock_threshold": "Low Stock Threshold",
        }
        widgets = {
            "low_stock_threshold": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                    "placeholder": "Enter low-stock threshold",
                }
            ),
        }
