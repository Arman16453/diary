from app.models.transactions import MilkTransaction as Transaction
from app.models.transactions import DeliveryTransaction, PurchaseTransaction, DairyStock, Inventory, InventoryTransaction, MilkQualityMixin

# This file provides compatibility for singular imports (transaction) when the actual models
# are defined in the plural file (transactions) 