# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

"""
API endpoints for cart abandonment and recovery.
"""

import frappe
from frappe import _
from frappe.utils import nowdatetime


@frappe.whitelist(allow_guest=True)
def recover_cart(token: str):
	"""
	Handle cart recovery link click.
	
	Args:
		token: Recovery token from abandoned cart
		
	Returns:
		Redirects to cart page or shows error
	"""
	if not token:
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/cart?error=invalid_token"
		return
	
	# Find abandoned cart by token
	abandoned_cart = frappe.db.get_value(
		"Abandoned Cart",
		{"recovery_token": token},
		["name", "quotation", "status", "customer_email"],
		as_dict=True
	)
	
	if not abandoned_cart:
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/cart?error=cart_not_found"
		return
	
	if abandoned_cart.status in ["Expired"]:
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/cart?error=cart_expired"
		return
	
	if abandoned_cart.status in ["Recovered", "Converted"]:
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/cart"
		return
	
	# Check if quotation still exists
	if not frappe.db.exists("Quotation", abandoned_cart.quotation):
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/cart?error=cart_not_found"
		return
	
	# Log recovery attempt
	frappe.logger().info(
		f"Cart recovery attempt: {abandoned_cart.name} via email link"
	)
	
	# Update abandoned cart status
	cart_doc = frappe.get_doc("Abandoned Cart", abandoned_cart.name)
	cart_doc.mark_as_recovered(source="Email Link")
	
	# If user is not logged in, redirect to login first
	if frappe.session.user == "Guest" and abandoned_cart.customer_email:
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = f"/login?redirect-to=/cart"
		return
	
	# Redirect to cart
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = "/cart"


@frappe.whitelist()
def get_abandonment_stats(days: int = 30):
	"""
	Get cart abandonment statistics.
	
	Args:
		days: Number of days to analyze
		
	Returns:
		Dictionary with statistics
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication required"))
	
	from webshop.abandonment.tracker import get_abandonment_stats as _get_stats
	return _get_stats(int(days))


@frappe.whitelist()
def resend_notification(abandoned_cart: str):
	"""
	Manually resend notification for an abandoned cart.
	
	Args:
		abandoned_cart: Name of the Abandoned Cart document
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication required"))
	
	if not frappe.has_permission("Abandoned Cart", "write", abandoned_cart):
		frappe.throw(_("Permission denied"))
	
	cart = frappe.get_doc("Abandoned Cart", abandoned_cart)
	
	if not cart.customer_email:
		frappe.throw(_("No email address available for this cart"))
	
	if cart.status in ["Recovered", "Expired", "Converted"]:
		frappe.throw(_("Cannot send notification for {0} cart").format(cart.status))
	
	from webshop.abandonment.notifications import send_abandonment_email
	send_abandonment_email(cart.name)
	
	return {"success": True, "message": _("Notification sent successfully")}


@frappe.whitelist()
def mark_as_recovered(abandoned_cart: str, source: str = "Other"):
	"""
	Manually mark an abandoned cart as recovered.
	
	Args:
		abandoned_cart: Name of the Abandoned Cart document
		source: Recovery source
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication required"))
	
	if not frappe.has_permission("Abandoned Cart", "write", abandoned_cart):
		frappe.throw(_("Permission denied"))
	
	cart = frappe.get_doc("Abandoned Cart", abandoned_cart)
	cart.mark_as_recovered(source=source)
	
	return {"success": True, "message": _("Cart marked as recovered")}


@frappe.whitelist()
def get_cart_details(abandoned_cart: str):
	"""
	Get detailed information about an abandoned cart.
	
	Args:
		abandoned_cart: Name of the Abandoned Cart document
		
	Returns:
		Dictionary with cart details and items
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication required"))
	
	if not frappe.has_permission("Abandoned Cart", "read", abandoned_cart):
		frappe.throw(_("Permission denied"))
	
	cart = frappe.get_doc("Abandoned Cart", abandoned_cart)
	quotation = frappe.get_doc("Quotation", cart.quotation)
	
	items = []
	for item in quotation.items:
		items.append({
			"item_code": item.item_code,
			"item_name": item.item_name,
			"qty": item.qty,
			"rate": item.rate,
			"amount": item.amount,
			"image": item.image
		})
	
	return {
		"cart": {
			"name": cart.name,
			"status": cart.status,
			"customer_name": cart.customer_name,
			"customer_email": cart.customer_email,
			"cart_value": cart.cart_value,
			"items_count": cart.items_count,
			"abandoned_at": cart.abandoned_at,
			"notification_count": cart.notification_count
		},
		"items": items,
		"quotation": {
			"name": quotation.name,
			"grand_total": quotation.grand_total,
			"currency": quotation.currency
		}
	}
