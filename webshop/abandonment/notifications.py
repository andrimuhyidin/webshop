# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Notification functions for cart abandonment.
"""

import frappe
from frappe import _
from frappe.utils import get_url, fmt_money


def send_abandonment_email(abandoned_cart: str):
	"""
	Send cart abandonment email to customer.
	
	Args:
		abandoned_cart: Name of the Abandoned Cart document
	"""
	try:
		cart = frappe.get_doc("Abandoned Cart", abandoned_cart)
		
		if not cart.customer_email:
			frappe.log_error(
				f"No email for abandoned cart {abandoned_cart}",
				"Cart Notification Error"
			)
			return
		
		if not cart.can_send_notification():
			return
		
		settings = frappe.get_cached_doc("Webshop Settings")
		
		# Get email template
		template_name = getattr(settings, "abandonment_email_template", None)
		
		if template_name and frappe.db.exists("Email Template", template_name):
			template = frappe.get_doc("Email Template", template_name)
			subject = template.subject
			message = frappe.render_template(template.response, get_email_context(cart))
		else:
			# Use default template
			subject, message = get_default_email_content(cart)
		
		# Send email
		frappe.sendmail(
			recipients=[cart.customer_email],
			subject=subject,
			message=message,
			reference_doctype="Abandoned Cart",
			reference_name=cart.name,
			unsubscribe_message=_("Unsubscribe from cart reminders"),
			delayed=False
		)
		
		# Update notification count
		cart.increment_notification_count()
		
		frappe.logger().info(
			f"Sent abandonment email to {cart.customer_email} for cart {cart.name}"
		)
		
	except Exception as e:
		frappe.log_error(
			f"Error sending abandonment email for {abandoned_cart}: {str(e)}",
			"Cart Notification Error"
		)


def get_email_context(cart) -> dict:
	"""
	Get context for email template rendering.
	
	Args:
		cart: Abandoned Cart document
		
	Returns:
		Dictionary with template context
	"""
	quotation = frappe.get_doc("Quotation", cart.quotation)
	
	# Get cart items
	items = []
	for item in quotation.items[:5]:
		items.append({
			"item_name": item.item_name,
			"item_code": item.item_code,
			"qty": item.qty,
			"rate": fmt_money(item.rate, currency=cart.currency),
			"amount": fmt_money(item.amount, currency=cart.currency),
			"image": item.image or ""
		})
	
	return {
		"customer_name": cart.customer_name or "Pelanggan",
		"customer_email": cart.customer_email,
		"cart_value": fmt_money(cart.cart_value, currency=cart.currency),
		"items_count": cart.items_count,
		"items": items,
		"items_summary": cart.cart_items_summary,
		"recovery_url": cart.recovery_url,
		"currency": cart.currency,
		"company": frappe.defaults.get_global_default("company"),
		"company_name": frappe.defaults.get_global_default("company"),
		"site_url": get_url()
	}


def get_default_email_content(cart) -> tuple:
	"""
	Get default email subject and content.
	
	Args:
		cart: Abandoned Cart document
		
	Returns:
		Tuple of (subject, message)
	"""
	context = get_email_context(cart)
	
	subject = _("Keranjang Belanja Anda Menunggu!")
	
	message = f"""
	<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
		<h2 style="color: #333;">Hai {context['customer_name']},</h2>
		
		<p>Kami melihat Anda memiliki beberapa item di keranjang belanja yang belum diselesaikan.</p>
		
		<div style="background: #f9f9f9; padding: 20px; border-radius: 8px; margin: 20px 0;">
			<h3 style="margin-top: 0; color: #555;">Ringkasan Keranjang Anda:</h3>
			<p><strong>Jumlah Item:</strong> {context['items_count']}</p>
			<p><strong>Total:</strong> {context['cart_value']}</p>
			<pre style="white-space: pre-wrap; font-family: inherit;">{context['items_summary']}</pre>
		</div>
		
		<p>Jangan sampai ketinggalan! Selesaikan pembelian Anda sekarang:</p>
		
		<div style="text-align: center; margin: 30px 0;">
			<a href="{context['recovery_url']}" 
			   style="background: #5e64ff; color: white; padding: 12px 30px; 
			          text-decoration: none; border-radius: 5px; font-weight: bold;">
				Lanjutkan Belanja
			</a>
		</div>
		
		<p style="color: #888; font-size: 12px;">
			Jika Anda memiliki pertanyaan, jangan ragu untuk menghubungi kami.
		</p>
		
		<hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
		
		<p style="color: #888; font-size: 12px;">
			{context['company_name']}
		</p>
	</div>
	"""
	
	return subject, message


def send_whatsapp_notification(abandoned_cart: str):
	"""
	Send cart abandonment notification via WhatsApp.
	
	Requires frappe_whatsapp app to be installed.
	
	Args:
		abandoned_cart: Name of the Abandoned Cart document
	"""
	if "frappe_whatsapp" not in frappe.get_installed_apps():
		return
	
	try:
		cart = frappe.get_doc("Abandoned Cart", abandoned_cart)
		
		if not cart.customer_phone:
			return
		
		# Clean phone number
		phone = cart.customer_phone.replace(" ", "").replace("-", "")
		if not phone.startswith("+"):
			phone = "+62" + phone.lstrip("0")  # Assume Indonesian number
		
		# Create WhatsApp message
		message = f"""Hai {cart.customer_name or 'Pelanggan'},

Keranjang belanja Anda masih menunggu! 🛒

📦 {cart.items_count} item
💰 Total: {fmt_money(cart.cart_value, currency=cart.currency)}

Klik link berikut untuk melanjutkan:
{cart.recovery_url}

Terima kasih! 🙏"""
		
		frappe.get_doc({
			"doctype": "WhatsApp Message",
			"to": phone,
			"type": "Outgoing",
			"message": message,
			"content_type": "text"
		}).insert(ignore_permissions=True)
		
	except Exception as e:
		frappe.log_error(
			f"Error sending WhatsApp notification for {abandoned_cart}: {str(e)}",
			"Cart WhatsApp Notification Error"
		)
