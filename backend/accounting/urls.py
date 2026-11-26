from rest_framework.routers import SimpleRouter

from accounting import views

# SimpleRouter: the browsable "API root" page already comes from companies' router.
router = SimpleRouter()
router.register("customers", views.CustomerViewSet, basename="customer")
router.register("suppliers", views.SupplierViewSet, basename="supplier")
router.register("invoices", views.InvoiceViewSet, basename="invoice")
router.register("payments", views.PaymentViewSet, basename="payment")
router.register("purchases", views.PurchaseViewSet, basename="purchase")
router.register("expenses", views.ExpenseViewSet, basename="expense")

urlpatterns = router.urls
