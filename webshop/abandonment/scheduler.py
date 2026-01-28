# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Scheduler functions for cart abandonment tracking.
"""

import frappe
from frappe.utils import nowdatetime, add_hours
from webshop.abandonment.notifications import send_abandonment_email


def detect_abandoned_carts():
	"""
	Hourly job to detect and track abandoned shopping carts.
	
	Finds draft quotations with order_type='Shopping Cart' that haven't
	been modified within the configured threshold hours.
	"""
	settings = frappe.get_cached_doc("Webshop Settings")
	
	# Check if cart abandonment is enabled
	if not getattr(settings, "enable_cart_abandonment", False):
		return
	
	threshold_hours = getattr(settings, "abandonment_threshold_hours", 24) or 24
	threshold_time = add_hours(nowdatetime(), -threshold_hours)
	
	# Find abandoned carts (draft quotations not modified within threshold)
	abandoned_quotations = frappe.db.sql("""
		SELECT q.name, q.modified, q.party_name, q.contact_email, q.grand_total
		FROM `tabQuotation` q
		WHERE q.order_type = 'Shopping Cart'
		AND q.docstatus = 0
		AND q.modified < %s
		AND q.grand_total > 0
		AND NOT EXISTS (
			SELECT 1 FROM `tabAbandoned Cart` ac
			WHERE ac.quotation = q.name
			AND ac.status NOT IN ('Expired')
		)
	""", (threshold_time,), as_dict=True)
	
	created_count = 0
	
	for quotation in abandoned_quotations:
		try:
			# Create Abandoned Cart record
			abandoned_cart = frappe.get_doc({
				"doctype": "Abandoned Cart",
				"quotation": quotation.name,
				"abandoned_at": quotation.modified,
				"status": "Abandoned"
			})
			abandoned_cart.insert(ignore_permissions=True)
			created_count += 1
			
			# Send first notification if email available
			if abandoned_cart.customer_email and abandoned_cart.can_send_notification():
				frappe.enqueue(
					send_abandonment_email,
					abandoned_cart=abandoned_cart.name,
					queue="short"
				)
				
		except frappe.DuplicateEntryError:
			# Cart already tracked
			continue
		except Exception as e:
			frappe.log_error(
				f"Error creating abandoned cart for {quotation.name}: {str(e)}",
				"Cart Abandonment Error"
			)
	
	if created_count > 0:
		frappe.logger().info(f"Detected {created_count} abandoned carts")


def send_abandonment_notifications():
	"""
	Hourly job to send follow-up notifications for abandoned carts.
	"""
	settings = frappe.get_cached_doc("Webshop Settings")
	
	if not getattr(settings, "enable_cart_abandonment", False):
		return
	
	# Find carts eligible for notification
	abandoned_carts = frappe.get_all(
		"Abandoned Cart",
		filters={
			"status": ["in", ["Abandoned", "Notified"]],
			"customer_email": ["is", "set"]
		},
		fields=["name"]
	)
	
	for cart in abandoned_carts:
		try:
			cart_doc = frappe.get_doc("Abandoned Cart", cart.name)
			
			if cart_doc.can_send_notification():
				send_abandonment_email(cart_doc.name)
				
		except Exception as e:
			frappe.log_error(
				f"Error sending notification for {cart.name}: {str(e)}",
				"Cart Notification Error"
			)


def cleanup_expired_carts():
	"""
	Daily job to cleanup expired abandoned carts.
	"""
	now = nowdatetime()
	
	# Find expired carts
	expired_carts = frappe.get_all(
		"Abandoned Cart",
		filters={
			"status": ["in", ["Abandoned", "Notified"]],
			"expires_at": ["<", now]
		},
		fields=["name"]
	)
	
	for cart in expired_carts:
		try:
			cart_doc = frappe.get_doc("Abandoned Cart", cart.name)
			cart_doc.mark_as_expired()
		except Exception as e:
			frappe.log_error(
				f"Error expiring cart {cart.name}: {str(e)}",
				"Cart Expiry Error"
			)
	
	if expired_carts:
		frappe.logger().info(f"Expired {len(expired_carts)} abandoned carts")


def sync_cart_status():
	"""
	Hourly job to sync abandoned cart status with quotations.
	
	Marks carts as converted if quotation was submitted.
	"""
	# Find abandoned carts with submitted quotations
	converted_carts = frappe.db.sql("""
		SELECT ac.name
		FROM `tabAbandoned Cart` ac
		INNER JOIN `tabQuotation` q ON ac.quotation = q.name
		WHERE ac.status IN ('Abandoned', 'Notified')
		AND q.docstatus = 1
	""", as_dict=True)
	
	for cart in converted_carts:
		try:
			cart_doc = frappe.get_doc("Abandoned Cart", cart.name)
			cart_doc.status = "Converted"
			cart_doc.recovered_at = nowdatetime()
			cart_doc.recovery_source = "Direct"
			cart_doc.save(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(
				f"Error syncing cart {cart.name}: {str(e)}",
				"Cart Sync Error"
			)
