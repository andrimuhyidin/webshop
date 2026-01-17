import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)
def get_products(industry_type=None, filters=None):
	"""
	Get list of products with support for deep filtering and industry-specific metadata.
	"""
	filters = frappe.parse_json(filters or "{}")
	
	query = frappe.qb.from_("Website Item").select("*")
	
	if industry_type:
		# Example: filter by custom field if it exists, or just return all for now
		pass
		
	# Basic implementation for now, will be expanded
	items = query.run(as_dict=True)
	
	# Enrich with metadata
	for item in items:
		item['item_metadata'] = {} # Placeholder for JSON logic
		
	return items

@frappe.whitelist(allow_guest=True)
def get_product_detail(item_code):
	"""
	Get detailed product info including rich metadata.
	"""
	if not frappe.db.exists("Website Item", item_code):
		frappe.throw(_("Item not found"), frappe.DoesNotExistError)

	item = frappe.get_doc("Website Item", item_code)
	item_dict = item.as_dict()
	
	# Generic Metadata Handling
	# We look for 'advanced_booking_config' (which would be added via Customize Form)
	# and expose it as a standardized 'item_metadata' JSON object
	config_str = item_dict.get("advanced_booking_config") or "{}"
	try:
		item_dict["item_metadata"] = frappe.parse_json(config_str)
	except Exception:
		item_dict["item_metadata"] = {}
		
	return item_dict
