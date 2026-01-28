# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, add_days, get_url
import secrets


class AbandonedCart(Document):
	"""
	Abandoned Cart DocType for tracking abandoned shopping carts.
	
	Manages abandoned cart records, notification tracking,
	and recovery workflows.
	"""
	
	def validate(self):
		"""Validate abandoned cart before saving."""
		self.set_customer_details()
		self.set_cart_details()
		self.generate_recovery_token()
		self.set_expiry()
	
	def set_customer_details(self):
		"""Set customer details from quotation."""
		if not self.quotation:
			return
		
		quotation = frappe.get_doc("Quotation", self.quotation)
		
		# Get customer/lead details
		if quotation.quotation_to == "Customer" and quotation.party_name:
			self.customer = quotation.party_name
			customer = frappe.get_doc("Customer", quotation.party_name)
			self.customer_name = customer.customer_name
		elif quotation.quotation_to == "Lead" and quotation.party_name:
			lead = frappe.get_doc("Lead", quotation.party_name)
			self.customer_name = lead.lead_name
		
		# Get contact email
		if quotation.contact_email:
			self.customer_email = quotation.contact_email
		elif quotation.contact_person:
			contact = frappe.get_doc("Contact", quotation.contact_person)
			self.customer_email = contact.email_id
		
		# Get phone if available
		if quotation.contact_mobile:
			self.customer_phone = quotation.contact_mobile
	
	def set_cart_details(self):
		"""Set cart value and items summary from quotation."""
		if not self.quotation:
			return
		
		quotation = frappe.get_doc("Quotation", self.quotation)
		
		self.cart_value = quotation.grand_total
		self.currency = quotation.currency
		self.items_count = len(quotation.items)
		
		# Create items summary
		items_summary = []
		for item in quotation.items[:5]:  # Limit to first 5 items
			items_summary.append(f"• {item.item_name} x {item.qty}")
		
		if len(quotation.items) > 5:
			items_summary.append(f"... dan {len(quotation.items) - 5} item lainnya")
		
		self.cart_items_summary = "\n".join(items_summary)
		
		# Set last activity
		self.last_activity_at = quotation.modified
	
	def generate_recovery_token(self):
		"""Generate unique recovery token for cart recovery links."""
		if not self.recovery_token:
			self.recovery_token = secrets.token_urlsafe(32)
		
		# Generate recovery URL
		base_url = get_url()
		self.recovery_url = f"{base_url}/api/method/webshop.abandonment.api.recover_cart?token={self.recovery_token}"
	
	def set_expiry(self):
		"""Set cart expiry date."""
		if not self.expires_at:
			# Default expiry: 30 days from abandonment
			settings = frappe.get_cached_doc("Webshop Settings")
			expiry_days = getattr(settings, "cart_expiry_days", 30) or 30
			self.expires_at = add_days(self.abandoned_at or now_datetime(), expiry_days)
	
	def mark_as_recovered(self, sales_order=None, source="Direct"):
		"""Mark cart as recovered."""
		self.status = "Recovered"
		self.recovered_at = now_datetime()
		self.recovery_source = source
		
		if sales_order:
			self.recovery_order = sales_order
		
		self.save(ignore_permissions=True)
	
	def mark_as_expired(self):
		"""Mark cart as expired."""
		self.status = "Expired"
		self.save(ignore_permissions=True)
	
	def increment_notification_count(self):
		"""Increment notification count after sending notification."""
		self.notification_count = (self.notification_count or 0) + 1
		self.last_notification_at = now_datetime()
		
		if self.status == "Abandoned":
			self.status = "Notified"
		
		self.save(ignore_permissions=True)
	
	def can_send_notification(self) -> bool:
		"""Check if notification can be sent."""
		settings = frappe.get_cached_doc("Webshop Settings")
		
		max_notifications = getattr(settings, "max_abandonment_notifications", 3) or 3
		notification_interval = getattr(settings, "notification_interval_hours", 24) or 24
		
		# Check max notifications
		if (self.notification_count or 0) >= max_notifications:
			return False
		
		# Check interval
		if self.last_notification_at:
			from frappe.utils import time_diff_in_hours
			hours_since_last = time_diff_in_hours(now_datetime(), self.last_notification_at)
			if hours_since_last < notification_interval:
				return False
		
		# Check if already recovered or expired
		if self.status in ["Recovered", "Expired", "Converted"]:
			return False
		
		return True
