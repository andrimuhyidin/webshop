import frappe
from frappe import _

@frappe.whitelist()
def create_order(cart_items, transaction_payload=None):
	"""
	RPC endpoint to create a Sales Order with generic transaction payload.
	"""
	cart_items = frappe.parse_json(cart_items)
	payload = frappe.parse_json(transaction_payload or "{}")
	
	# Logic to create Sales Order would go here
	# This avoids standard "Add to Cart" flow and directly builds the SO
	
	# Placeholder return
	return {"status": "success", "message": "Order created", "order_name": "SO-00001"}

@frappe.whitelist()
def check_availability(item_code, required_qty, transaction_payload=None):
	"""
	Hook-based availability check.
	"""
	payload = frappe.parse_json(transaction_payload or "{}")
	
	# Trigger hooks from other apps (e.g., bizops_tour_travel)
	methods = frappe.get_hooks("webshop_check_availability")
	for method in methods:
		# If any hook returns False/Error, we block. 
		# Real implementation might aggregate results.
		status = frappe.call(method, item_code=item_code, qty=required_qty, payload=payload)
		if status and not status.get("available"):
			return {"available": False, "message": status.get("message")}
		
	return {"available": True}
