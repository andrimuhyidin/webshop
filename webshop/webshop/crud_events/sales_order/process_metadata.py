import frappe
import json

def process_order_metadata(doc, method):
	"""
	Hook: before_save on Sales Order.
	Process 'order_metadata' generic field if it exists.
	This allows the Headless API to pass ANY JSON data (Travel, Retail, etc)
	and have it stored/processed without hardcoding columns.
	"""
	# Check if metadata is passed via transient field (not in DB yet) or custom field
	metadata = doc.get("order_metadata")
	
	if not metadata:
		return

	if isinstance(metadata, str):
		try:
			metadata = json.loads(metadata)
		except ValueError:
			return

	# Example Logic:
	# If metadata contains "tags", add them to the doc
	if metadata.get("tags"):
		for tag in metadata.get("tags"):
			doc.add_tag(tag)
			
	# Example Logic:
	# If "internal_note" is present, add comment
	if metadata.get("internal_note"):
		doc.add_comment("Info", f"Webshop Note: {metadata.get('internal_note')}")

	# In a real scenario, this hook passes data to Integration Apps
	# e.g. bizops_tour_travel might listen to 'on_update' and read this metadata
