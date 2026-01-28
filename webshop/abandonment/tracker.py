# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Cart activity tracking functions.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime


def track_cart_activity(doc, method=None):
	"""
	Track cart activity when quotation is updated.
	
	Called via doc_events hook on Quotation.on_update.
	
	Args:
		doc: Quotation document
		method: Hook method name (unused)
	"""
	# Only track shopping cart quotations
	if doc.order_type != "Shopping Cart":
		return
	
	# Only track draft quotations
	if doc.docstatus != 0:
		return
	
	# Check if there's an abandoned cart for this quotation
	abandoned_cart = frappe.db.get_value(
		"Abandoned Cart",
		{"quotation": doc.name, "status": ["in", ["Abandoned", "Notified"]]},
		"name"
	)
	
	if abandoned_cart:
		# Update last activity time
		frappe.db.set_value(
			"Abandoned Cart",
			abandoned_cart,
			"last_activity_at",
			now_datetime(),
			update_modified=False
		)


def mark_cart_recovered(doc, method=None):
	"""
	Mark abandoned cart as recovered when quotation is submitted.
	
	Called via doc_events hook on Quotation.on_submit.
	
	Args:
		doc: Quotation document
		method: Hook method name (unused)
	"""
	# Only process shopping cart quotations
	if doc.order_type != "Shopping Cart":
		return
	
	# Find abandoned cart for this quotation
	abandoned_cart = frappe.db.get_value(
		"Abandoned Cart",
		{"quotation": doc.name, "status": ["in", ["Abandoned", "Notified"]]},
		"name"
	)
	
	if abandoned_cart:
		cart_doc = frappe.get_doc("Abandoned Cart", abandoned_cart)
		cart_doc.mark_as_recovered(source="Direct")


def mark_cart_recovered_from_order(doc, method=None):
	"""
	Mark abandoned cart as recovered when sales order is created.
	
	Called via doc_events hook on Sales Order.on_submit.
	
	Args:
		doc: Sales Order document
		method: Hook method name (unused)
	"""
	# Get source quotation
	for item in doc.items:
		if item.prevdoc_doctype == "Quotation" and item.prevdoc_docname:
			abandoned_cart = frappe.db.get_value(
				"Abandoned Cart",
				{
					"quotation": item.prevdoc_docname,
					"status": ["in", ["Abandoned", "Notified"]]
				},
				"name"
			)
			
			if abandoned_cart:
				cart_doc = frappe.get_doc("Abandoned Cart", abandoned_cart)
				cart_doc.mark_as_recovered(sales_order=doc.name, source="Direct")
				break


def get_abandonment_stats(days: int = 30) -> dict:
	"""
	Get cart abandonment statistics.
	
	Args:
		days: Number of days to analyze
		
	Returns:
		Dictionary with statistics
	"""
	from frappe.utils import add_days
	
	start_date = add_days(now_datetime(), -days)
	
	# Total abandoned carts
	total_abandoned = frappe.db.count(
		"Abandoned Cart",
		{"abandoned_at": [">=", start_date]}
	)
	
	# Recovered carts
	recovered = frappe.db.count(
		"Abandoned Cart",
		{
			"abandoned_at": [">=", start_date],
			"status": "Recovered"
		}
	)
	
	# Total value abandoned
	abandoned_value = frappe.db.sql("""
		SELECT COALESCE(SUM(cart_value), 0) as total
		FROM `tabAbandoned Cart`
		WHERE abandoned_at >= %s
	""", (start_date,))[0][0] or 0
	
	# Recovered value
	recovered_value = frappe.db.sql("""
		SELECT COALESCE(SUM(cart_value), 0) as total
		FROM `tabAbandoned Cart`
		WHERE abandoned_at >= %s
		AND status = 'Recovered'
	""", (start_date,))[0][0] or 0
	
	recovery_rate = (recovered / total_abandoned * 100) if total_abandoned > 0 else 0
	
	return {
		"total_abandoned": total_abandoned,
		"recovered": recovered,
		"expired": frappe.db.count("Abandoned Cart", {
			"abandoned_at": [">=", start_date],
			"status": "Expired"
		}),
		"pending": frappe.db.count("Abandoned Cart", {
			"abandoned_at": [">=", start_date],
			"status": ["in", ["Abandoned", "Notified"]]
		}),
		"recovery_rate": round(recovery_rate, 2),
		"abandoned_value": abandoned_value,
		"recovered_value": recovered_value,
		"lost_value": abandoned_value - recovered_value
	}
