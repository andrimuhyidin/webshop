# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

"""
WhatsApp notification integration for Webshop.

Sends order notifications via WhatsApp when frappe_whatsapp app is installed.
"""

import frappe
from frappe.utils import fmt_money
from typing import Optional


def is_whatsapp_enabled() -> bool:
	"""Check if WhatsApp integration is available and enabled."""
	if "frappe_whatsapp" not in frappe.get_installed_apps():
		return False
	
	# Check if webshop WhatsApp notifications are enabled
	settings = frappe.get_cached_doc("Webshop Settings")
	return getattr(settings, "enable_whatsapp_notifications", False)


def get_customer_phone(doc) -> Optional[str]:
	"""Get customer phone number from document."""
	# Try contact mobile first
	if hasattr(doc, "contact_mobile") and doc.contact_mobile:
		return normalize_phone(doc.contact_mobile)
	
	# Try to get from customer
	if hasattr(doc, "customer") and doc.customer:
		phone = frappe.db.get_value(
			"Customer",
			doc.customer,
			["mobile_no", "phone"],
			as_dict=True
		)
		if phone:
			return normalize_phone(phone.mobile_no or phone.phone)
	
	# Try from contact
	if hasattr(doc, "contact_person") and doc.contact_person:
		contact_phone = frappe.db.get_value("Contact", doc.contact_person, "mobile_no")
		if contact_phone:
			return normalize_phone(contact_phone)
	
	return None


def normalize_phone(phone: str) -> Optional[str]:
	"""Normalize phone number to WhatsApp format."""
	if not phone:
		return None
	
	# Remove spaces, dashes, etc.
	phone = "".join(c for c in phone if c.isdigit() or c == "+")
	
	# Add Indonesia country code if not present
	if phone.startswith("0"):
		phone = "+62" + phone[1:]
	elif not phone.startswith("+"):
		phone = "+62" + phone
	
	return phone


def send_whatsapp_message(phone: str, message: str, template_name: str = None) -> bool:
	"""
	Send WhatsApp message.
	
	Args:
		phone: Recipient phone number
		message: Message content
		template_name: Optional template name for template messages
		
	Returns:
		True if sent successfully, False otherwise
	"""
	try:
		if not phone:
			return False
		
		# Create WhatsApp Message
		msg = frappe.get_doc({
			"doctype": "WhatsApp Message",
			"to": phone,
			"type": "Outgoing",
			"message": message,
			"content_type": "text",
			"message_type": "Template" if template_name else "Text"
		})
		msg.insert(ignore_permissions=True)
		
		return True
		
	except Exception as e:
		frappe.log_error(
			f"Error sending WhatsApp message to {phone}: {str(e)}",
			"Webshop WhatsApp Notification"
		)
		return False


def send_order_confirmation(doc, method=None):
	"""
	Send order confirmation via WhatsApp.
	
	Called via doc_events hook on Sales Order.on_submit.
	
	Args:
		doc: Sales Order document
		method: Hook method name
	"""
	if not is_whatsapp_enabled():
		return
	
	# Only for shopping cart orders
	if not is_webshop_order(doc):
		return
	
	phone = get_customer_phone(doc)
	if not phone:
		return
	
	# Get items summary
	items_list = []
	for item in doc.items[:5]:
		items_list.append(f"• {item.item_name} x {int(item.qty)}")
	
	if len(doc.items) > 5:
		items_list.append(f"... dan {len(doc.items) - 5} item lainnya")
	
	items_summary = "\n".join(items_list)
	
	message = f"""✅ *Pesanan Dikonfirmasi*

Halo {doc.customer_name or 'Pelanggan'},

Pesanan Anda telah dikonfirmasi!

📦 *No. Pesanan:* {doc.name}
📅 *Tanggal:* {frappe.utils.format_date(doc.transaction_date)}

*Rincian Pesanan:*
{items_summary}

💰 *Total:* {fmt_money(doc.grand_total, currency=doc.currency)}

Kami akan segera memproses pesanan Anda.

Terima kasih telah berbelanja! 🙏"""
	
	frappe.enqueue(
		send_whatsapp_message,
		phone=phone,
		message=message,
		queue="short"
	)


def send_order_shipped(doc, method=None):
	"""
	Send shipping notification via WhatsApp.
	
	Called via doc_events hook on Delivery Note.on_submit.
	
	Args:
		doc: Delivery Note document
		method: Hook method name
	"""
	if not is_whatsapp_enabled():
		return
	
	# Get Sales Order
	sales_orders = set()
	for item in doc.items:
		if item.against_sales_order:
			sales_orders.add(item.against_sales_order)
	
	if not sales_orders:
		return
	
	# Check if any is webshop order
	for so_name in sales_orders:
		so = frappe.get_doc("Sales Order", so_name)
		if not is_webshop_order(so):
			continue
		
		phone = get_customer_phone(so)
		if not phone:
			continue
		
		# Get tracking info if available
		tracking_info = ""
		if hasattr(doc, "tracking_number") and doc.tracking_number:
			tracking_info = f"\n📍 *No. Resi:* {doc.tracking_number}"
		if hasattr(doc, "transporter_name") and doc.transporter_name:
			tracking_info += f"\n🚚 *Kurir:* {doc.transporter_name}"
		
		message = f"""🚚 *Pesanan Dikirim*

Halo {so.customer_name or 'Pelanggan'},

Kabar baik! Pesanan Anda sedang dalam perjalanan!

📦 *No. Pesanan:* {so.name}
📋 *No. Pengiriman:* {doc.name}{tracking_info}

Pesanan akan segera tiba di alamat Anda.

Terima kasih! 🙏"""
		
		frappe.enqueue(
			send_whatsapp_message,
			phone=phone,
			message=message,
			queue="short"
		)


def send_payment_received(doc, method=None):
	"""
	Send payment confirmation via WhatsApp.
	
	Called via doc_events hook on Payment Entry.on_submit.
	
	Args:
		doc: Payment Entry document
		method: Hook method name
	"""
	if not is_whatsapp_enabled():
		return
	
	if doc.payment_type != "Receive":
		return
	
	# Get linked Sales Order/Invoice
	customer_name = doc.party_name if doc.party_type == "Customer" else None
	reference_doc = None
	
	for ref in doc.references:
		if ref.reference_doctype == "Sales Order":
			reference_doc = frappe.get_doc("Sales Order", ref.reference_name)
			break
		elif ref.reference_doctype == "Sales Invoice":
			reference_doc = frappe.get_doc("Sales Invoice", ref.reference_name)
			break
	
	if not reference_doc:
		return
	
	if not is_webshop_order(reference_doc):
		return
	
	phone = get_customer_phone(reference_doc)
	if not phone:
		return
	
	message = f"""💳 *Pembayaran Diterima*

Halo {customer_name or 'Pelanggan'},

Pembayaran Anda telah kami terima!

💰 *Jumlah:* {fmt_money(doc.paid_amount, currency=doc.paid_to_account_currency)}
📦 *Referensi:* {reference_doc.name}
📅 *Tanggal:* {frappe.utils.format_date(doc.posting_date)}

Pesanan Anda akan segera diproses.

Terima kasih! 🙏"""
	
	frappe.enqueue(
		send_whatsapp_message,
		phone=phone,
		message=message,
		queue="short"
	)


def send_order_status_update(doc, status: str, custom_message: str = None):
	"""
	Send custom order status update via WhatsApp.
	
	Args:
		doc: Sales Order document
		status: Status text
		custom_message: Optional custom message
	"""
	if not is_whatsapp_enabled():
		return
	
	phone = get_customer_phone(doc)
	if not phone:
		return
	
	if custom_message:
		message = custom_message
	else:
		message = f"""📢 *Update Pesanan*

Halo {doc.customer_name or 'Pelanggan'},

Status pesanan Anda telah diperbarui:

📦 *No. Pesanan:* {doc.name}
📌 *Status:* {status}

Terima kasih! 🙏"""
	
	frappe.enqueue(
		send_whatsapp_message,
		phone=phone,
		message=message,
		queue="short"
	)


def is_webshop_order(doc) -> bool:
	"""Check if order is from webshop."""
	# Check for Shopping Cart source
	if hasattr(doc, "source") and doc.source == "Shopping Cart":
		return True
	
	# Check order type in linked quotation
	if hasattr(doc, "items"):
		for item in doc.items:
			if hasattr(item, "prevdoc_doctype") and item.prevdoc_doctype == "Quotation":
				order_type = frappe.db.get_value("Quotation", item.prevdoc_docname, "order_type")
				if order_type == "Shopping Cart":
					return True
	
	return False
